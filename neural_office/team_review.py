"""Three deterministic passes over a completed local inspection, using captured evidence only."""
from collections import Counter
import time
import math

from .ledger import Denied, canonical, digest


ROLES = ('researcher', 'planner', 'implementer', 'verifier', 'skeptic', 'integrator')
INSTRUCTIONS = (
    ('Identifica las capturas que sostienen el encargo.', 'Delimita las comprobaciones solicitadas.',
     'Asocia cada resultado con sus citas.', 'Comprueba a quién pertenece cada cita.',
     'Localiza las preguntas que quedaron abiertas.', 'Reúne lo observado y sus límites.'),
    ('Contrasta las referencias y sus coordenadas.', 'Ordena las discrepancias y las comprobaciones pendientes.',
     'Prepara un índice de evidencia por fuente.', 'Contrasta ese índice con las citas originales.',
     'Distingue las discrepancias de la falta de evidencia.', 'Prepara la entrega con el resultado del contraste.'),
    ('Identifica la versión exacta de las fuentes.', 'Delimita lo que debe decir la entrega.',
     'Compón el informe de las comprobaciones.', 'Compara el informe con los hechos registrados.',
     'Comprueba que las reservas llegan al informe.', 'Entrega el informe contrastado al Director.'),
)
ACTIONS = (
    ('Inventarió las fuentes', 'Delimitó el encargo', 'Vinculó las citas', 'Verificó las capturas', 'Revisó la cobertura', 'Reunió los resultados'),
    ('Localizó las referencias', 'Ordenó las comprobaciones', 'Indexó la evidencia', 'Contrastó el índice', 'Revisó las discrepancias', 'Preparó la síntesis'),
    ('Comprobó las versiones', 'Fijó el alcance', 'Compuso el informe', 'Verificó el informe', 'Contrastó las limitaciones', 'Entregó el resultado'),
)


def location(citation):
    parts = []
    for field, label in (('page', 'pág.'), ('line', 'línea'), ('column', 'col.')):
        if citation.get(field):
            parts.append(f'{label} {citation[field]}')
    if citation.get('pointer'):
        parts.append(str(citation['pointer']))
    if citation.get('member'):
        parts.append(str(citation['member']))
    return ' · '.join([citation['name'], *parts])


def review(objective, attachments, findings, checks, cancelled, notify=None, *, progress=None):
    by_id = {item['id']: item for item in attachments}
    references = [c for f in findings for c in f['sources']]
    facts = [f['detail'] for f in findings]
    missing = [(f['title']+' · ' if f['rule']=='file_content' else '')+f['detail']
               for f in findings if f['status'] == 'insufficient']
    disputed = [f['detail'] for f in findings if f['status'] == 'mismatch']
    evidence = {}
    limits = list(dict.fromkeys(missing))
    if any(f['rule'] == 'static_html' for f in findings):
        limits.append('La lectura estática del HTML deja pendiente comprobar el portal en una ventana real.')
    entries = {}
    previous = None
    receipts = []

    def publish(role, cycle, phase, message):
        if progress is not None:
            progress(message, len(attachments), role, cycle, phase)
        if phase == 'completed' and notify is not None:
            notify(message, len(attachments))

    def step(cycle, role, work):
        nonlocal previous
        if cancelled():
            raise Denied('ATTACHMENT_READ_CANCELLED')
        index = ROLES.index(role)
        action = ACTIONS[cycle-1][index]
        instruction = INSTRUCTIONS[cycle-1][index]
        publish(role, cycle, 'running', f'Iteración {cycle} · {instruction}')
        tick = time.monotonic_ns()
        try:
            lines = work()
        except Exception:
            publish(role, cycle, 'failed', f'Iteración {cycle} · Operación fallida')
            raise
        row = dict(round=cycle, role=role, instruction=instruction,
                   action=action, details=lines, at=time.time(), duration_us=(time.monotonic_ns()-tick)//1000,
                   parent=previous)
        # Timing belongs to the receipt. Identity describes the exact causal content.
        row['sha256'] = digest(canonical([cycle, role, previous, objective, action, lines]))
        previous = row['sha256']
        receipts.append(row)
        publish(role, cycle, 'completed', f'Iteración {cycle} · {action}')
        return lines

    def check_sources():
        for c in references:
            item = by_id.get(c['attachment_id'])
            if not item or (c['name'], c['sha256']) != (item['name'], item['sha256']):
                raise Denied('ATTACHMENT_INTEGRITY_FAILED')
        return [f'{len(references)} citas contrastadas con las capturas de este hilo.']

    def build_index():
        counts = Counter(c['attachment_id'] for c in references)
        evidence.update({item['id']: counts[item['id']] for item in attachments})
        return [f"{item['name']} · {evidence[item['id']]} citas" for item in attachments]

    def check_index():
        if sum(evidence.values()) != len(references) or set(evidence) != set(by_id):
            raise Denied('ATTACHMENT_INTEGRITY_FAILED')
        return [f'{sum(evidence.values())} referencias en {len(evidence)} fuentes.']

    def assemble():
        entries.update(objective=objective, results=list(facts), limitations=list(limits),
                       sources=[dict(name=i['name'], sha256=i['sha256']) for i in attachments])
        return list(facts) or ['Los lectores no registraron conclusiones.']

    def verify_report():
        if entries['results'] != facts or entries['objective'] != objective:
            raise Denied('ATTACHMENT_INTEGRITY_FAILED')
        return [f'{len(facts)} respuestas contrastadas con la inspección.', digest(canonical(entries))]

    def verify_limits():
        if entries['limitations'] != limits:
            raise Denied('ATTACHMENT_INTEGRITY_FAILED')
        return limits or ['Las comprobaciones solicitadas no registraron reservas adicionales.']

    step(1, 'researcher', lambda: [i['name']+' · '+i['kind'] for i in attachments])
    step(1, 'planner', lambda: [f['title'] for f in findings] or list(checks))
    step(1, 'implementer', lambda: [f"{f['title']} · {len(f['sources'])} citas" for f in findings])
    step(1, 'verifier', check_sources)
    step(1, 'skeptic', lambda: list(limits) or ['Sin limitaciones identificadas en estas comprobaciones.'])
    step(1, 'integrator', lambda: [f'{len(facts)} resultados; {len(limits)} limitaciones registradas.'])
    step(2, 'researcher', lambda: list(dict.fromkeys(location(c) for c in references)) or ['Sin citas localizadas.'])
    step(2, 'planner', lambda: [f['title'] for f in sorted(findings, key=lambda f: f['status'] not in ('insufficient', 'mismatch'))])
    step(2, 'implementer', build_index)
    step(2, 'verifier', check_index)
    step(2, 'skeptic', lambda: disputed+missing or ['Sin discrepancias ni evidencia insuficiente en los resultados.'])
    step(2, 'integrator', lambda: [f'{len(disputed)} discrepancias · {len(missing)} respuestas con evidencia insuficiente.'])
    step(3, 'researcher', lambda: [i['name']+' · '+i['sha256'] for i in attachments])
    step(3, 'planner', lambda: [objective or 'Inspección local', f'{len(facts)} comprobaciones incluidas.'])
    step(3, 'implementer', assemble)
    step(3, 'verifier', verify_report)
    step(3, 'skeptic', verify_limits)
    step(3, 'integrator', lambda: [f"Informe de {len(entries['sources'])} fuentes.", *entries['limitations']])
    if cancelled():
        raise Denied('ATTACHMENT_READ_CANCELLED')
    return dict(version=1, engine='deterministic', rounds=3, receipts=receipts,
                delivery=entries, delivery_sha256=digest(canonical(entries)))


def verify_saved(report):
    """Recheck the recorded statements against saved evidence without rereading a user's files."""
    from .inspection_intent import requested_checks
    recorded = report.get('team')
    if not isinstance(recorded, dict):
        raise Denied('ATTACHMENT_INTEGRITY_FAILED')
    files = report['attachments']
    checks = requested_checks(report['objective'], {f['kind'] for f in files},
                              allow_dialogue=report['rule_version'] != 'local-inspection-5')
    expected = review(report['objective'], files, report['findings'], checks, lambda: False)
    if (not isinstance(recorded.get('receipts'), list)
            or len(recorded['receipts']) != len(expected['receipts'])
            or {k: v for k, v in recorded.items() if k != 'receipts'} !=
               {k: v for k, v in expected.items() if k != 'receipts'}):
        raise Denied('ATTACHMENT_INTEGRITY_FAILED')
    for saved, correct in zip(recorded['receipts'], expected['receipts']):
        if not isinstance(saved, dict):
            raise Denied('ATTACHMENT_INTEGRITY_FAILED')
        at, elapsed = saved.get('at'), saved.get('duration_us')
        if (type(at) not in (int, float) or not math.isfinite(at) or at <= 0
                or type(elapsed) is not int or elapsed < 0
                or saved != {**correct, 'at': at, 'duration_us': elapsed}):
            raise Denied('ATTACHMENT_INTEGRITY_FAILED')
