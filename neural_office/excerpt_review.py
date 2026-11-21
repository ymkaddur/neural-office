"""The Director may comment on cited fragments of one frozen local inspection."""
import json
import re

from .ledger import Denied, canonical, digest
from . import written_answer

SCOPE = 'local-inspection-excerpts-v1'
TEXT_SCOPE = 'local-director-text-v1'
SCOPES = (SCOPE, TEXT_SCOPE)
COMMENTARY = 'UNVERIFIED_ASSISTANCE'


def hour_answer_requested(objective, fragments):
    """One quoted hour measurement and an explicit request to return its number and unit."""
    if len(fragments) != 1 or not re.search(r'\b(?:horas?|hours?)\b', objective, re.I):
        return False
    if not re.search(r'\b(?:(?:cifra|número|numero|valor) y (?:su |la )?unidad|'
                     r'(?:number|value) and (?:its |the )?unit)[.!?\s]*$', objective, re.I):
        return False
    values = re.findall(r'(?<![\w.,])\d+(?:[.,]\d+)?\s*(?:horas?|hours?|h)\b',
                        fragments[0]['quote'], re.I)
    return len(values) == 1


def _disclosure(report, project_id, thread_id):
    """Build the server-owned disclosure once. A client cannot supply file text."""
    includes = {item['id']: item for item in report['attachments']}
    fragments = []
    for finding in report['findings']:
        for citation in finding.get('sources', []):
            item = includes.get(citation.get('attachment_id'))
            if item is None:
                raise Denied('INSPECTION_CITATION_INVALID')
            quote = citation.get('quote')
            # The inspector can show surrounding HTML locally. Model scope for
            # static HTML has always been limited to the rule and its position.
            if item['kind'] == 'html':
                code = citation.get('code', quote)
                if not isinstance(code, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{1,95}', code):
                    continue
                quote = code
            if type(quote) is not str or not quote.strip():
                continue
            fragment = {'attachment_id': item['id'], 'name': item['name'],
                        'sha256': item['sha256'], 'quote': quote}
            if item['kind'] == 'html':
                fragment['code'] = quote
            for locator in ('page', 'line', 'column', 'pointer', 'member', 'value', 'unit'):
                if locator in citation and citation[locator] is not None:
                    fragment[locator] = citation[locator]
            if fragment not in fragments:
                fragments.append(fragment)
    text_only = (not includes and bool(report['objective'].strip()) and
                 [f['rule'] for f in report['findings']] == ['text_brief'])
    body = {'scope': TEXT_SCOPE if text_only else SCOPE, 'project_id': project_id, 'thread_id': thread_id,
            'inspection_id': report['id'], 'fragments': fragments}
    if text_only:
        body['objective'] = report['objective']
        if written_answer.contract(report['objective']):
            body['answer_check_version'] = 1
    snapshot = canonical(body).encode('utf-8')
    reason = None
    if not fragments and not text_only:
        reason = 'NO_CITED_EXCERPTS'
    elif len(fragments) > 8 or len(snapshot) > 4608:
        reason = 'EXCERPT_BUDGET'
    return snapshot, fragments, body['scope'], reason


def scope_size(report, project_id, thread_id):
    snapshot, fragments, scope, reason = _disclosure(report, project_id, thread_id)
    return dict(project_id=project_id, thread_id=thread_id, report_id=report['id'], scope=scope,
                bytes=len(snapshot), fragments=len(fragments), allowed=reason is None, reason=reason)


def capture_excerpts(report, project_id, thread_id):
    snapshot, fragments, _, reason = _disclosure(report, project_id, thread_id)
    if reason:
        raise Denied(reason)
    return snapshot, fragments


def material(snapshot):
    captured = json.loads(snapshot)
    if captured['scope'] == TEXT_SCOPE:
        if captured['fragments'] != [] or not isinstance(captured.get('objective'), str) or not captured['objective'].strip():
            raise Denied('EXCERPT_SCOPE_INVALID')
        return captured
    if captured['scope'] != SCOPE or not 1 <= len(captured['fragments']) <= 8:
        raise Denied('EXCERPT_SCOPE_INVALID')
    return captured


def make_report(snapshot, outputs):
    source = material(snapshot)
    report = {'schema': 1, 'scope': source['scope'], 'source_sha256': digest(snapshot),
                      'inspection_id': source['inspection_id'], 'thread_id': source['thread_id'],
                      'authorized_fragments': source['fragments'], 'findings': [],
                      'model_commentary_status': COMMENTARY, 'role_outputs': outputs}
    if source['scope'] == TEXT_SCOPE and source.get('answer_check_version') == 1:
        result = written_answer.check(source['objective'], outputs)
        if result is not None:
            report['answer_check'] = result
    return canonical(report).encode('utf-8')


def verify_report(snapshot, artifact):
    checks = {}
    checked_scope = SCOPE
    try:
        checked_scope = material(snapshot)['scope']
        report = json.loads(artifact)
        expected = make_report(snapshot, report['role_outputs'])
        checks['matches_authorized_excerpts'] = expected == artifact
        checks['outputs_type'] = type(report['role_outputs']) is list
    except (KeyError, ValueError, UnicodeError, TypeError, Denied):
        checks['parse'] = False
    return {'verifier': checked_scope, 'source_sha256': digest(snapshot),
            'artifact_sha256': digest(artifact), 'checks': checks, 'passed': all(checks.values()),
            'coverage': ('Identidad del encargo escrito y de la respuesta del Director.' if checked_scope == TEXT_SCOPE
                         else 'Identidad de los extractos autorizados y del comentario del modelo.')}
