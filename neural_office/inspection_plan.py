"""Bind each part of a local request to the captured sources it actually names."""
from dataclasses import dataclass
from pathlib import PurePath
import re
import unicodedata

from .inspection_intent import CONTEXT, READER_FORMATS, reader_modes, requested_checks


@dataclass(frozen=True)
class Task:
    action: str
    sources: tuple
    clause: str
    phrase: str = ''
    limit: str = ''
    explicit: bool = False


SEPARATOR = re.compile(
    r'[;!?¿¡\n]+|\.(?=\s|$)|\s+(?:y|e|and)\s+(?=(?:¿|qué\b|cuál|cuánt|dónde|cómo|quién|'
    r'(?:valida|comprueba|revisa|compara|verifica|cuenta|busca|encuentra|localiza|muestra|inspecciona|'
    r'indica|identifica|redacta|escribe|genera|resume|haz|traduce|prop[oó]n|explica|extrae|crea|'
    r'adjunta|calcula|envía|clasifica|ordena|enumera|analiza|lee|dime|prepara|publica|guarda|diseña)\b))', re.I)
QUOTED = re.compile(r'«[^»]*»|“[^”]*”|"[^"]*"|‘[^’]*’|\'[^\']*\'|' + r'\x60[^\x60]*\x60')
SEARCH = re.compile(r'^(?:(?:puedes?|podr[ií]as?)\s+)?(?:busca(?:r)?|encuentra|encontrar|localiza(?:r)?)\s+(.+)$', re.I | re.S)
SUFFIX = re.compile(r'(?<![\w.-])[\w-]+(?:\.[\w-]+)*\.[^\W\d_][\w-]*', re.UNICODE)
FORMAT = re.compile(r'\b(pdf|json|xml|zip|html|markdown|xlsx|docx|pptx|odt|ods|odp|txt|csv|png|jpe?g|wav)\b', re.I)
ALIASES = {'markdown': 'md', 'jpg': 'jpeg', 'htm': 'html'}


def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.casefold()) if not unicodedata.combining(c))


def clauses(objective):
    # Match boundary positions without splitting inside the requested literal or a quoted filename.
    masked = QUOTED.sub(lambda m: '\ufffc' * len(m[0]), objective)
    start = 0
    for delimiter in SEPARATOR.finditer(masked):
        value = objective[start:delimiter.start()].strip()
        if value:
            yield value
        start = delimiter.end()
    if objective[start:].strip():
        yield objective[start:].strip()


def search_terms(clause):
    match = SEARCH.fullmatch(clause)
    if not match:
        return '', clause
    request = match[1].strip()
    quoted = QUOTED.match(request)
    if quoted:
        phrase, target = quoted[0][1:-1], request[quoted.end():].strip()
        if target and not re.match(r'^en\s+', target, re.I):
            return '', clause
    else:
        parts = re.split(r'\s+en\s+', request, maxsplit=1, flags=re.I)
        phrase, target = parts[0], parts[1] if len(parts) == 2 else ''
    if not phrase.strip() or len(phrase) > 120 or '\n' in phrase:
        return '', clause
    return phrase, target


def scoped_sources(text, captures):
    rest = text
    ids = set()
    if re.search(r'\b(?:excepto|salvo|excluye|excluyendo|omite|ignora)\b',fold(rest)):
        return (), 'Para excluir archivos, ajusta la selección y repite la comprobación.', True
    # Match whole names, longest first. Do not treat the suffix of a matched filename as a second selector.
    for name in sorted({f['name'] for f in captures}, key=lambda n: (-len(n), n)):
        pattern = re.compile(r'(?<![\w.-])' + re.escape(name) + r'(?![\w-]|\.\w)', re.I)
        rest, count = pattern.subn(' ', rest)
        if count:
            matches = [f['id'] for f in captures if f['name'].casefold() == name.casefold()]
            if len(matches) != 1:
                return (), f'Hay varias capturas llamadas {name}. Selecciona la que quieres usar.', True
            ids.update(matches)
    absent = SUFFIX.search(rest)
    if absent:
        return (), f'El archivo {absent[0]} no está en la selección.', True
    formats = {ALIASES.get(t.lower(), t.lower()) for t in FORMAT.findall(rest)}
    named=set(ids)
    for target in sorted(formats):
        matches = [f['id'] for f in captures if target in
                   (f['kind'], ALIASES.get(PurePath(f['name']).suffix[1:].lower(), PurePath(f['name']).suffix[1:].lower()))]
        if not matches:
            return (), f'La selección no contiene un archivo {target.upper()}.', True
        if named and not named.intersection(matches) and not re.search(r'\b(?:y|e|con|contra|entre)\b',rest,re.I):
            return (), f'El nombre del archivo y el formato {target.upper()} apuntan a fuentes distintas.', True
        if not ids.intersection(matches):
            ids.update(matches)
    return tuple(f['id'] for f in captures if not ids or f['id'] in ids), '', bool(ids)


def plan(objective, captures):
    kinds = {f['kind'] for f in captures}
    all_ids = tuple(f['id'] for f in captures)
    if not objective.strip() or requested_checks(objective, kinds) == ['greeting']:
        return [Task(check, all_ids, objective) for check in requested_checks(objective, kinds)]
    tasks = []
    parts = list(clauses(objective))
    for part in parts:
        normalized = fold(part)
        if len(parts)>1 and (CONTEXT.fullmatch(normalized) or re.fullmatch(r'(?:hola(?:,?\s+director)?|buenos d[ií]as|buenas (?:tardes|noches)|gracias)',normalized)):
            continue
        if any(t.action == 'hours' for t in tasks) and normalized == 'indica que dato debe confirmar la persona responsable':
            continue
        phrase, target = search_terms(part)
        sources, limit, explicit = scoped_sources(target, captures)
        checks = ['literal'] if phrase else requested_checks(part, kinds)
        if checks == ['clarify'] and re.match(r'^valida(?:r)?\b', normalized) and re.search(r'\b(?:json|xml)\b', normalized):
            checks = ['syntax']
        for check in checks:
            tasks.append(Task(check, sources, part, phrase, limit, explicit))
    return tasks or [Task('clarify', all_ids, objective)]


def read_plan(tasks, captures):
    """All clauses share one bounded read per capture, including multiple requests about the same PDF."""
    planned = {}
    by_id = {f['id']: f for f in captures}
    for task in tasks:
        if task.limit:
            continue
        modes = reader_modes([task.action], [by_id[i]['kind'] for i in task.sources])
        for i in task.sources:
            f = by_id[i]
            mode = modes.get(f['kind'])
            if task.action == 'syntax' and f['kind'] == 'text' and f['name'].lower().endswith('.xml'):
                mode = 'xml_syntax'
            if mode and (i not in planned or mode in ('text', 'xml_syntax') or planned[i] == 'page_count'):
                planned[i] = mode
    return planned


def unsupported(task, files):
    names = ', '.join(f['name'] for f in files)
    detail = task.limit
    if not detail and task.action in READER_FORMATS and files:
        detail = f'La comprobación solicitada no está disponible para {names}.'
        if task.action=='pages' and all(f['kind']=='text' for f in files):
            detail = f'{names} contiene texto sin paginación fija. El lector cuenta las páginas de documentos PDF.'
    if not detail:
        detail = 'La inspección local no realiza esta parte del encargo.'
    return dict(rule='scope', status='insufficient', title='Pendiente · '+task.clause, detail=detail, sources=[])
