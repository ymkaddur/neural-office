"""Deterministic checks over captured HTML bytes; never executes HTML or scripts."""
from html import unescape
from html.parser import HTMLParser
import json
import re
from .ledger import canonical, digest

SCOPE = 'static-html-checks-v4'

VOID = frozenset('area base br col embed hr img input link meta param source track wbr'.split())
LABELABLE = frozenset(('button', 'input', 'meter', 'output', 'progress', 'select', 'textarea'))


def inline_hidden(style):
    declarations = {}
    for declaration in style.lower().split(';'):
        key, _, value = declaration.partition(':')
        key = key.strip()
        if key not in ('display', 'visibility'):
            continue
        value, mark, suffix = value.partition('!')
        important = bool(mark and suffix.strip() == 'important')
        if key not in declarations or important or not declarations[key][1]:
            declarations[key] = (value.strip(), important)
    return (declarations.get('display', ('',))[0] == 'none' or
            declarations.get('visibility', ('',))[0] in ('hidden', 'collapse'))


class NameSource:
    def __init__(self, tag, attrs, parent_label, parent):
        self.tag = tag
        self.inert = tag == 'template' or bool(parent and parent.inert)
        self.foreign = tag in ('svg', 'math') or bool(parent and parent.foreign and parent.tag != 'foreignobject')
        style = attrs.get('style')
        self.hidden = bool((parent and parent.hidden) or 'hidden' in attrs or
                           (attrs.get('aria-hidden') or '').strip().lower() == 'true' or (style and inline_hidden(style)))
        self.named = bool((attrs.get('aria-label') or '').strip())
        if tag == 'img':
            self.named |= bool((attrs.get('alt') or '').strip())
        self.title = bool((attrs.get('title') or '').strip())
        self.all_named = self.named
        self.parent_label = parent_label
        self.target = attrs.get('for')
        self.claimed = False


class Scan(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.findings=[]
        self.html_seen=False
        self.title_seen=False
        self.document_title=None
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
        if len(values) != len(attrs):
            values = dict(reversed(attrs))  # HTML keeps the first duplicate attribute.
        node = NameSource(tag, values, self.label, self.stack[-1] if self.stack else None)
        document_html = not node.inert and not node.foreign
        if tag=='html' and document_html:
            self.html_seen=True
            if not (values.get('lang') or '').strip(): self.issue('HTML_LANGUAGE_MISSING',self.getpos())
        if tag=='title' and document_html and not self.title_seen:
            self.document_title=node
            self.title_seen=True
        if document_html and tag in ('title', 'textarea'):
            self.set_cdata_mode(tag)
        if tag=='img' and document_html and 'alt' not in values: self.issue('IMAGE_ALT_MISSING',self.getpos())
        if not node.inert and values.get('id'):
            self.ids.setdefault(values['id'], node)
        implicit = None
        hidden = tag == 'input' and (values.get('type') or '').lower() == 'hidden'
        if document_html and tag in LABELABLE and not hidden and self.label and not self.label.claimed:
            self.label.claimed = True
            if self.label.target is None:
                implicit = self.label
        if tag == 'label' and document_html:
            self.label = node
            if node.target:
                self.labels.setdefault(node.target, []).append(node)
        if tag not in VOID:
            self.stack.append(node)
            self.open_tags[tag] = self.open_tags.get(tag, 0) + 1
        elif document_html and tag == 'img' and self.stack:
            self.stack[-1].all_named |= node.all_named
            self.stack[-1].named |= node.named and not node.hidden
        excluded_input = tag=='input' and (values.get('type') or '').lower() in ('hidden','submit','reset','button','image')
        if document_html and tag in ('input','select','textarea') and not excluded_input and not node.hidden:
            self.controls.append((values, node, implicit, self.getpos()))

    def close_node(self):
        child = self.stack.pop()
        self.open_tags[child.tag] -= 1
        if child is self.document_title:
            self.document_title = None
        if child is self.label:
            self.label = child.parent_label
        if self.stack and child.tag not in LABELABLE and child.tag not in ('script', 'style', 'template'):
            self.stack[-1].all_named |= child.all_named
            self.stack[-1].named |= child.named and not child.hidden

    def handle_endtag(self, tag):
        if self.open_tags.get(tag):
            while self.stack[-1].tag != tag:
                self.close_node()
            self.close_node()

    def handle_data(self, data):
        if self.cdata_elem in ('title', 'textarea'):
            data = unescape(data)
        if self.document_title is not None: self.title.append(data)
        if self.stack and data.strip():
            self.stack[-1].named = True
            self.stack[-1].all_named = True

    def close(self):
        super().close()
        if self.cdata_elem in ('title', 'textarea') and self.rawdata:
            self.handle_data(self.rawdata)
            self.rawdata = ''

    def missing_names(self):
        while self.stack:
            self.close_node()
        labelled = {key for key, values in self.labels.items() if any(node.named and not node.hidden for node in values)}
        for attrs, node, implicit, position in self.controls:
            key = attrs.get('id')
            refs = [self.ids[ref] for ref in (attrs.get('aria-labelledby') or '').split() if ref in self.ids]
            if refs and any((ref.all_named if ref.hidden else ref.named) or ref.title for ref in refs):
                continue
            if (attrs.get('aria-label') or '').strip() or node.title or (implicit and implicit.named):
                continue
            if self.ids.get(key) is node and key in labelled:
                continue
            self.issue('CONTROL_LABEL_CANDIDATE', position)


def audit_html(source):
    text=source.decode('utf-8-sig',errors='strict')
    scan=Scan()
    scan.feed(text.replace('\r\n', '\n').replace('\r', '\n'))
    scan.close()
    if not scan.html_seen: scan.issue('HTML_ELEMENT_MISSING',(1,0))
    if not ''.join(scan.title).strip(): scan.issue('DOCUMENT_TITLE_MISSING',(1,0))
    scan.missing_names()
    return sorted(scan.findings,key=lambda x:(x['line'],x['column'],x['code']))


RULE_FAMILIES = {
    'IMAGE_ALT_MISSING':r'\b(?:imagen sin (?:descripción|texto alternativo)|missing (?:image )?alt(?: text)?)\b',
    'CONTROL_LABEL_CANDIDATE':r'\b(?:control sin etiqueta|unlabelled control|unlabeled control)\b',
    'HTML_LANGUAGE_MISSING':r'\b(?:idioma del documento|missing document language)\b',
    'DOCUMENT_TITLE_MISSING':r'\b(?:título del documento|missing document title)\b',
    'HTML_ELEMENT_MISSING':r'\b(?:elemento html ausente|missing html element)\b',
}


def requested_rule(objective):
    """Recognize a request for the code and position of one supported static finding."""
    text = objective.casefold()
    if not re.search(r'\b(?:código|codigo|code)\b',text) or not re.search(r'\b(?:líneas?|lineas?|lines?)\b',text):
        return None
    found = [code for code, label in RULE_FAMILIES.items()
             if re.search(r'\b'+code.casefold()+r'\b',text) or re.search(label,text)]
    return found[0] if len(found) == 1 else None


def citation_only(objective, code):
    """Narrow output only for a positive match to a simple location request."""
    target = rf'\b{re.escape(code.casefold())}\b|{RULE_FAMILIES[code]}'
    remainder, count = re.subn(target, ' ', objective.casefold())
    words = re.findall(r'\w+', remainder)
    allowed = ('el la los las de del en este esta un una y su sus para por favor solo sólo '
               'código codigo exacto línea lineas líneas linea columna archivo documento '
               'the a this of in and its for only please exact code line lines file column document')
    if count != 1 or not words or words[0] not in ('indica','dime','devuelve','give','return','state'):
        return False
    return set(words[1:]) <= set(allowed.split())


def make_report(source, outputs, rule=None):
    report = {'schema':1,'scope':SCOPE,'source_sha256':digest(source),
        'findings':audit_html(source),'model_commentary_status':'UNVERIFIED_ASSISTANCE',
        'role_outputs':outputs}
    if rule is not None:
        report['requested_rule'] = rule
    return canonical(report).encode('utf-8')


def verify_report(source, artifact, rule=None):
    checks={}
    try:
        report=json.loads(artifact)
        keys={'schema','scope','source_sha256','findings','model_commentary_status','role_outputs'}
        if rule is not None:
            keys.add('requested_rule')
            checks['requested_rule']=report.get('requested_rule')==rule
        checks['schema']=type(report) is dict and set(report)==keys
        checks['scope']=type(report.get('schema')) is int and report['schema']==1 and report.get('scope')==SCOPE
        checks['source_identity']=report.get('source_sha256')==digest(source)
        checks['findings_match_recomputed']=canonical(report.get('findings'))==canonical(audit_html(source))
        checks['commentary_label']=report.get('model_commentary_status')=='UNVERIFIED_ASSISTANCE'
        checks['outputs_type']=type(report.get('role_outputs')) is list
    except (ValueError,TypeError,AttributeError,UnicodeError):
        checks['parse']=False
    return {'verifier':'static-html-recompute-v4','source_sha256':digest(source),
            'artifact_sha256':digest(artifact),'checks':checks,'passed':bool(checks) and all(checks.values()),
            'coverage':'Four static heuristics; no browser rendering, WCAG certification or security certification.'}
