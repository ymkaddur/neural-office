"""The Director may comment on cited fragments of one frozen local inspection."""
import json
import re

from .ledger import Denied, canonical, digest

SCOPE = 'local-inspection-excerpts-v1'
COMMENTARY = 'UNVERIFIED_ASSISTANCE'


def capture_excerpts(report, project_id, thread_id):
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
    if not fragments:
        raise Denied('NO_CITED_EXCERPTS')
    if len(fragments) > 8:
        raise Denied('EXCERPT_BUDGET')
    body = {'scope': SCOPE, 'project_id': project_id, 'thread_id': thread_id,
            'inspection_id': report['id'], 'fragments': fragments}
    snapshot = canonical(body).encode('utf-8')
    if len(snapshot) > 4608:
        raise Denied('EXCERPT_BUDGET')
    return snapshot, fragments


def material(snapshot):
    captured = json.loads(snapshot)
    if captured['scope'] != SCOPE or not 1 <= len(captured['fragments']) <= 8:
        raise Denied('EXCERPT_SCOPE_INVALID')
    return captured


def make_report(snapshot, outputs):
    source = material(snapshot)
    return canonical({'schema': 1, 'scope': SCOPE, 'source_sha256': digest(snapshot),
                      'inspection_id': source['inspection_id'], 'thread_id': source['thread_id'],
                      'authorized_fragments': source['fragments'], 'findings': [],
                      'model_commentary_status': COMMENTARY, 'role_outputs': outputs}).encode('utf-8')


def verify_report(snapshot, artifact):
    checks = {}
    try:
        report = json.loads(artifact)
        expected = make_report(snapshot, report['role_outputs'])
        checks['matches_authorized_excerpts'] = expected == artifact
        checks['outputs_type'] = type(report['role_outputs']) is list
    except (KeyError, ValueError, UnicodeError, TypeError, Denied):
        checks['parse'] = False
    return {'verifier': SCOPE, 'source_sha256': digest(snapshot),
            'artifact_sha256': digest(artifact), 'checks': checks, 'passed': all(checks.values()),
            'coverage': 'Identidad de los extractos autorizados y del comentario del modelo.'}
