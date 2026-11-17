"""Deterministic checks over captured HTML bytes; never executes HTML or scripts."""
from html.parser import HTMLParser
import json
from .ledger import canonical, digest

SCOPE = 'static-html-checks-v2'


class Scan(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.findings=[]
        self.html_seen=False
        self.title_seen=False
        self.in_title=False
        self.title=[]
        self.labels=set()
        self.label_depth=0
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
        if tag=='label':
            self.label_depth+=1
            if values.get('for'): self.labels.add(values['for'])
        excluded_input = tag=='input' and values.get('type','').lower() in ('hidden','submit','reset','button','image')
        if tag in ('input','select','textarea') and not excluded_input:
            named = bool(self.label_depth or (values.get('aria-label') or '').strip()
                         or (values.get('aria-labelledby') or '').strip() or (values.get('title') or '').strip())
            self.controls.append((values.get('id'),named,self.getpos()))

    def handle_endtag(self, tag):
        if tag=='title': self.in_title=False
        if tag=='label': self.label_depth=max(0,self.label_depth-1)

    def handle_data(self, data):
        if self.in_title: self.title.append(data)


def audit_html(source):
    text=source.decode('utf-8-sig',errors='strict')
    scan=Scan()
    scan.feed(text)
    scan.close()
    if not scan.html_seen: scan.issue('HTML_ELEMENT_MISSING',(1,0))
    if not ''.join(scan.title).strip(): scan.issue('DOCUMENT_TITLE_MISSING',(1,0))
    for identity,named,position in scan.controls:
        if not named and (not identity or identity not in scan.labels): scan.issue('CONTROL_LABEL_CANDIDATE',position)
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
    return {'verifier':'static-html-recompute-v2','source_sha256':digest(source),
            'artifact_sha256':digest(artifact),'checks':checks,'passed':bool(checks) and all(checks.values()),
            'coverage':'Four static heuristics; no browser rendering, WCAG certification or security certification.'}
