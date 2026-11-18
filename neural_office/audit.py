"""Deterministic checks over captured HTML bytes; never executes HTML or scripts."""
from html.parser import HTMLParser
import json
from .ledger import canonical, digest

SCOPE = 'static-html-checks-v3'

VOID = frozenset('area base br col embed hr img input link meta param source track wbr'.split())
LABELABLE = frozenset(('button', 'input', 'meter', 'output', 'progress', 'select', 'textarea'))


class NameSource:
    def __init__(self, tag, attrs, parent_label):
        self.tag = tag
        self.named = bool((attrs.get('aria-label') or '').strip())
        if tag == 'img':
            self.named |= bool((attrs.get('alt') or '').strip())
        self.title = bool((attrs.get('title') or '').strip())
        self.parent_label = parent_label
        self.target = attrs.get('for')
        self.claimed = False


class Scan(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.findings=[]
        self.html_seen=False
        self.title_seen=False
        self.in_title=False
        self.title=[]
        self.labels={}
        self.ids={}
        self.stack=[]
        self.open_tags={}
        self.label=None
        self.controls=[]

    def issue(self, code, position):
        self.findings.append({'code':code,'line':position[0],'column':position[1]+1})

    def handle_starttag(self, tag, attrs):
        values=dict(attrs)
        if tag=='html':
            self.html_seen=True
            if not (values.get('lang') or '').strip(): self.issue('HTML_LANGUAGE_MISSING',self.getpos())
        if tag=='title': self.in_title=True; self.title_seen=True
        if tag=='img' and 'alt' not in values: self.issue('IMAGE_ALT_MISSING',self.getpos())
        node = NameSource(tag, values, self.label)
        if values.get('id'):
            self.ids.setdefault(values['id'], node)
        implicit = None
        hidden = tag == 'input' and (values.get('type') or '').lower() == 'hidden'
        if tag in LABELABLE and not hidden and self.label and not self.label.claimed:
            self.label.claimed = True
            if self.label.target is None:
                implicit = self.label
        if tag == 'label':
            self.label = node
            if node.target:
                self.labels.setdefault(node.target, []).append(node)
        if tag not in VOID:
            self.stack.append(node)
            self.open_tags[tag] = self.open_tags.get(tag, 0) + 1
        elif tag == 'img' and self.stack and node.named:
            self.stack[-1].named = True
        excluded_input = tag=='input' and (values.get('type') or '').lower() in ('hidden','submit','reset','button','image')
        if tag in ('input','select','textarea') and not excluded_input:
            self.controls.append((values, node, implicit, self.getpos()))

    def close_node(self):
        child = self.stack.pop()
        self.open_tags[child.tag] -= 1
        if child.tag == 'label':
            self.label = child.parent_label
        if self.stack and child.tag not in LABELABLE and child.tag not in ('script', 'style', 'template'):
            self.stack[-1].named |= child.named

    def handle_endtag(self, tag):
        if tag=='title': self.in_title=False
        if self.open_tags.get(tag):
            while self.stack[-1].tag != tag:
                self.close_node()
            self.close_node()

    def handle_data(self, data):
        if self.in_title: self.title.append(data)
        if self.stack and data.strip():
            self.stack[-1].named = True

    def missing_names(self):
        while self.stack:
            self.close_node()
        labelled = {key for key, values in self.labels.items() if any(node.named for node in values)}
        for attrs, node, implicit, position in self.controls:
            key = attrs.get('id')
            refs = [self.ids[ref] for ref in (attrs.get('aria-labelledby') or '').split() if ref in self.ids]
            if refs and any(ref.named or ref.title for ref in refs):
                continue
            if (attrs.get('aria-label') or '').strip() or node.title or (implicit and implicit.named):
                continue
            if self.ids.get(key) is node and key in labelled:
                continue
            self.issue('CONTROL_LABEL_CANDIDATE', position)


def audit_html(source):
    text=source.decode('utf-8-sig',errors='strict')
    scan=Scan()
    scan.feed(text)
    scan.close()
    if not scan.html_seen: scan.issue('HTML_ELEMENT_MISSING',(1,0))
    if not ''.join(scan.title).strip(): scan.issue('DOCUMENT_TITLE_MISSING',(1,0))
    scan.missing_names()
    return sorted(scan.findings,key=lambda x:(x['line'],x['column'],x['code']))


def make_report(source, outputs):
    return canonical({'schema':1,'scope':SCOPE,'source_sha256':digest(source),
        'findings':audit_html(source),'model_commentary_status':'UNVERIFIED_ASSISTANCE',
        'role_outputs':outputs}).encode('utf-8')


def verify_report(source, artifact):
    checks={}
    try:
        report=json.loads(artifact)
        checks['schema']=type(report) is dict and set(report)=={
            'schema','scope','source_sha256','findings','model_commentary_status','role_outputs'}
        checks['scope']=type(report.get('schema')) is int and report['schema']==1 and report.get('scope')==SCOPE
        checks['source_identity']=report.get('source_sha256')==digest(source)
        checks['findings_match_recomputed']=canonical(report.get('findings'))==canonical(audit_html(source))
        checks['commentary_label']=report.get('model_commentary_status')=='UNVERIFIED_ASSISTANCE'
        checks['outputs_type']=type(report.get('role_outputs')) is list
    except (ValueError,TypeError,AttributeError,UnicodeError):
        checks['parse']=False
    return {'verifier':'static-html-recompute-v3','source_sha256':digest(source),
            'artifact_sha256':digest(artifact),'checks':checks,'passed':bool(checks) and all(checks.values()),
            'coverage':'Four static heuristics; no browser rendering, WCAG certification or security certification.'}
