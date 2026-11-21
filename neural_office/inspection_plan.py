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
    modifier: str = ''
    excluded: tuple = ()


SEPARATOR = re.compile(
    r'[;!?¿¡\n]+|\.(?=\s|$)|(?:,\s*|\s+y\s+)luego\s+|\s+(?:y|e|and)\s+(?=(?:¿|qué\b|cuál|cuánt|dónde|cómo|quién|'
    r'(?:valida|comprueba|revisa|compara|verifica|cuenta|busca|encuentra|localiza|muestra|inspecciona|'
    r'indica|identifica|redacta|escribe|genera|resume|haz|traduce|prop[oó]n|explica|extrae|crea|'
    r'adjunta|calcula|envía|clasifica|ordena|enumera|analiza|lee|dime|prepara|publica|guarda|diseña)\b))', re.I)
QUOTED = re.compile(r'«[^»]*»|“[^”]*”|"[^"]*"|‘[^’]*’|\'[^\']*\'|' + r'\x60[^\x60]*\x60')
SEARCH = re.compile(r'^(?:(?:puedes?|podr[ií]as?)\s+)?(?:busca(?:r)?|encuentra|encontrar|localiza(?:r)?)\s+(.+)$', re.I | re.S)
SUFFIX = re.compile(r'(?<![\w.-])[\w-]+(?:\.[\w-]+)*\.[^\W\d_][\w-]*', re.UNICODE)
FORMAT = re.compile(r'\b(pdf|json|xml|zip|html?|markdown|md|xlsx|docx|pptx|odt|ods|odp|txt|csv|tsv|png|jpe?g|gif|webp|bmp|tiff?|wav)\b', re.I)
ALIASES = {'markdown': 'md', 'jpg': 'jpeg', 'htm': 'html', 'tif': 'tiff'}
EXCLUDED = re.compile(r'(?<![\w.-])(?:excepto|salvo|excluye|excluyendo|omite|ignora)(?![\w.-])|'
                      r'\bsin\s+(?:consultar|leer|incluir|usar|abrir|revisar)\b|'
                      r'\bno\s+(?:consultes|leas|incluyas|uses|abras|revises)\b', re.I)
QUALIFIED_PAGES = re.compile(r'\bpaginas?\s+(?:que|donde|con|sin|anteriores|posteriores)\b|'
                             r'\b(?:paginas? .*?)?(?:contienen|mencionan)\b')
SAME_FILE = re.compile(r'\b(?:ese|este|el)\s+mismo\s+(?:archivo|documento|fichero)\b', re.I)
EXAMPLE = re.compile(r'\bp\.\s*ej\.(?:\s*,)?', re.I)
ORDINAL_WORD = r'(?:primer[oa]?|segund[oa]|tercer[oa]?|cuart[oa]|quint[oa]|sext[oa]|s[eé]ptim[oa]|octav[oa]|[uú]ltim[oa])'
ORDINAL_NOUN = r'(?:archivo|documento|adjunto|fichero)\b'
ORDINAL_JOIN = r'(?:\s*,\s*|\s+[ye]\s+)(?:(?:el|la)\s+)?'
ORDINAL = re.compile(
    rf'\b({ORDINAL_WORD})(?:\s+{ORDINAL_NOUN}|(?=(?:{ORDINAL_JOIN}{ORDINAL_WORD})+\s+{ORDINAL_NOUN}))', re.I)
POSITIONS = {'prim':0,'segu':1,'terc':2,'cuar':3,'quin':4,'sext':5,'sept':6,'octa':7,'ulti':-1}
ARGUMENT = r'(?:«([^»]{1,120})»|“([^”]{1,120})”|"([^"]{1,120})")'
FILTER_PAGES = re.compile(r'^(.*?\bp[aá]ginas?)\s+(?:que\s+(?:contienen|mencionan)|donde\s+(?:aparece|figura))\s+'+ARGUMENT+r'(.*)$',re.I)
CONTAINS_GUARD = re.compile(r'^(.+?)\s+(?:solo|solamente)\s+si\s+(?:contiene|menciona)\s+'+ARGUMENT+r'\s*$', re.I)


def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.casefold()) if not unicodedata.combining(c))


def clauses(objective, name_pattern):
    # Keep offsets in the original text while protecting literals and selected filenames.
    masked = QUOTED.sub(lambda m: '\ufffc' * len(m[0]), objective)
    if name_pattern is not None:
        masked = name_pattern.sub(lambda m: '\ufffc' * len(m[0]), masked)
    masked = EXAMPLE.sub(lambda m: ' ' * len(m[0]), masked)
    start = 0
    for delimiter in SEPARATOR.finditer(masked):
        value = objective[start:delimiter.start()].strip()
        if value:
            yield value
        start = delimiter.end()
    if objective[start:].strip():
        yield objective[start:].strip()


def search_terms(clause):
    front = re.match(r'^en\s+(.+?),\s*(.+)$', clause, re.I)
    leading = ''
    if front:
        leading, clause = front.groups()
    absence = re.match(r'^(?:comprueba|verifica|confirma)\s+(?:que\s+)?no\s+(?:aparece|figura|se encuentra)\s+', clause,re.I)
    if absence:
        clause = 'Busca '+clause[absence.end():]
    match = SEARCH.fullmatch(clause)
    if not match:
        domain = re.search(r'\b(?:menciona|contiene)\s+([\w-]+(?:\.[\w-]+)+)\s*$', clause, re.I)
        if domain:
            return domain[1], clause[:domain.start()], ''
        referred = re.fullmatch(r'(?:dime|comprueba|verifica)\s+si\s+([\w-]+(?:\.[\w-]+)+)\s+se\s+menciona(?:\s+(all[ií]))?',clause,re.I)
        if referred:
            return referred[1], 'ese mismo archivo' if referred[2] else '', ''
        return '', (leading+' '+clause).strip(), ''
    request = match[1].strip()
    all_hits = re.match(r'^todas\s+las\s+(?:apariciones|coincidencias)\s+de\s+', request, re.I)
    if all_hits:
        request = request[all_hits.end():]
    quoted = QUOTED.match(request)
    if quoted:
        phrase, target = quoted[0][1:-1], request[quoted.end():].strip()
        if target and not re.match(r'^en\s+', target, re.I):
            return '', clause, ''
    else:
        parts = re.split(r'\s+en\s+', request, maxsplit=1, flags=re.I)
        phrase, target = parts[0], parts[1] if len(parts) == 2 else ''
    if not phrase.strip() or len(phrase) > 120 or '\n' in phrase:
        return '', clause, ''
    return phrase, (leading+' '+target).strip(), 'absent' if absence else 'all' if all_hits else ''


def shared_searches(part):
    """A second quoted term with its own target inherits only the search verb."""
    if not SEARCH.fullmatch(part):
        yield part
        return
    masked = QUOTED.sub(lambda m: '\ufffc' * len(m[0]), part)
    start = 0
    for join in re.finditer(r'\s+(?:y|e|and)\s+(?=\ufffc+\s+en\b)', masked, re.I):
        yield ('' if start == 0 else 'Busca ') + part[start:join.start()]
        start = join.end()
    yield ('' if start == 0 else 'Busca ') + part[start:]


def scoped_sources(text, captures):
    rest = unicodedata.normalize('NFC', text)
    ids = set()
    # Match whole names, longest first. Do not treat the suffix of a matched filename as a second selector.
    for name in sorted({unicodedata.normalize('NFC',f['name']) for f in captures}, key=lambda n: (-len(n), n)):
        pattern = re.compile(r'(?<![\w.-])' + re.escape(name) + r'(?![\w-]|\.\w)', re.I)
        rest, count = pattern.subn(' ', rest)
        if count:
            matches = [f['id'] for f in captures if unicodedata.normalize('NFC',f['name']).casefold() == name.casefold()]
            if len(matches) != 1:
                return (), f'Hay varias capturas llamadas {name}. Selecciona la que quieres usar.', True
            ids.update(matches)
    absent = SUFFIX.search(rest)
    if absent:
        return (), f'El archivo {absent[0]} no está en la selección.', True
    positioned = set()
    for ordinal in ORDINAL.finditer(rest):
        position=POSITIONS[fold(ordinal[1])[:4]]
        if not captures or position>=len(captures):
            return (), 'La selección no contiene el adjunto en esa posición.', True
        positioned.add(captures[position]['id'])
    if ids and not positioned <= ids:
        return (), 'El nombre y la posición se refieren a archivos distintos.', True
    ids.update(positioned)
    formats = {ALIASES.get(t.lower(), t.lower()) for t in FORMAT.findall(rest)}
    if re.search(r'\bhojas? de calculo\b',fold(rest)):
        sheet_ids={f['id'] for f in captures if f['kind'] in ('xlsx','ods')}
        if not sheet_ids:
            return (), 'La selección no contiene una hoja de cálculo.', True
        if ids and not ids <= sheet_ids:
            return (), 'El nombre y el tipo de hoja de cálculo apuntan a fuentes distintas.', True
        if not ids:
            ids.update(sheet_ids)
    named=set(ids)
    for target in sorted(formats):
        matches = [f['id'] for f in captures if target in
                   (f['kind'], ALIASES.get(PurePath(f['name']).suffix[1:].lower(), PurePath(f['name']).suffix[1:].lower()))]
        if not matches:
            return (), f'La selección no contiene un archivo {target.upper()}.', True
        if named and not named.intersection(matches) and not re.search(r'\b(?:y|e|con|contra|entre)\b',rest,re.I):
            return (), f'El nombre del archivo y el formato {target.upper()} apuntan a fuentes distintas.', True
        if not ids.intersection(matches) or re.search(r'\b(?:todos|todas|ambos|ambas)\b',rest,re.I):
            ids.update(matches)
    return tuple(f['id'] for f in captures if not ids or f['id'] in ids), '', bool(ids)


def plan(objective, captures):
    objective = unicodedata.normalize('NFC',objective)
    kinds = {f['kind'] for f in captures}
    all_ids = tuple(f['id'] for f in captures)
    names = sorted({unicodedata.normalize('NFC',f['name']) for f in captures}, key=lambda name: (-len(name), name))
    name_pattern = re.compile(r'(?<![\w.-])(?:' + '|'.join(map(re.escape, names)) + r')(?![\w-]|\.\w)', re.I) if names else None
    def format_word(match):
        extension = PurePath(match[0]).suffix[1:]
        return extension if FORMAT.fullmatch(extension) else 'archivo'

    def instruction_words(text):
        # A selected filename identifies the input. Its basename cannot supply an instruction.
        if name_pattern is not None:
            text = name_pattern.sub(format_word, text)
        return ORDINAL.sub('archivo', text)
    if not objective.strip() or requested_checks(objective, kinds) == ['greeting']:
        return [Task(check, all_ids, objective) for check in requested_checks(objective, kinds)]
    tasks = []
    parts = [item for clause in clauses(objective, name_pattern) for item in shared_searches(clause)]
    allowed_parts = []
    excluded_ids = set()
    for part in parts:
        mask = QUOTED.sub(lambda m:' ' * len(m[0]), part)
        if name_pattern:
            mask = name_pattern.sub(lambda m:' ' * len(m[0]), mask)
        exclusion = EXCLUDED.search(mask)
        if exclusion:
            target = part[exclusion.end():]
            ids, issue, explicit = scoped_sources(target, captures)
            remainder = name_pattern.sub(' ',target) if name_pattern else target
            remainder = FORMAT.sub(' ',ORDINAL.sub(' ',fold(remainder)))
            remainder = re.sub(r'\b(?:hojas? de calculo|tod[oa]s?|archivos?|adjuntos?|documentos?|ficheros?|el|la|los|las|al|y|e|ni)\b',' ',remainder)
            # A restriction has to resolve to specific captures before any content is read.
            if issue or not explicit or not ids or re.search(r'[\w.-]',remainder):
                return [Task('clarify', (), objective, limit='Indica qué archivos deben quedar fuera de la lectura.', excluded=all_ids)]
            excluded_ids.update(ids)
            part = part[:exclusion.start()].strip(' ,')
        if part:
            allowed_parts.append(part)
    excluded = tuple(i for i in all_ids if i in excluded_ids)
    if excluded and (not allowed_parts or len(excluded) == len(all_ids)):
        return [Task('clarify', (), objective, limit='Indica una operación con alguna fuente autorizada.', excluded=excluded or all_ids)]
    parts = allowed_parts
    for part in parts:
        part = EXAMPLE.sub(' ',part).strip(' ,')
        normalized = fold(part)
        if len(parts)>1 and (CONTEXT.fullmatch(normalized) or re.fullmatch(r'(?:hola(?:,?\s+director)?|buenos d[ií]as|buenas (?:tardes|noches)|gracias)',normalized)):
            continue
        if any(t.action == 'hours' for t in tasks) and normalized == 'indica que dato debe confirmar la persona responsable':
            continue
        instruction = part
        modifier = ''
        filter_phrase = ''
        guarded = CONTAINS_GUARD.fullmatch(part)
        filtered = FILTER_PAGES.fullmatch(part)
        if guarded:
            instruction = guarded[1]
            filter_phrase = next(v for v in guarded.groups()[1:] if v)
            modifier = 'if_contains'
        elif filtered:
            instruction = filtered[1]+' '+filtered[5]
            filter_phrase = next(v for v in filtered.groups()[1:4] if v)
            modifier = 'pages_containing'
        phrase, target, literal_modifier = search_terms(instruction)
        sources, limit, explicit = scoped_sources(target, captures)
        sources = tuple(i for i in sources if i not in excluded_ids)
        if not sources and not limit:
            limit = 'La operación no tiene una fuente autorizada.'
        if not limit and SAME_FILE.search(QUOTED.sub(' ', instruction_words(target))):
            antecedent = tasks[-1].sources if tasks else all_ids
            if (len(antecedent) == 1 and (not tasks or (not tasks[-1].limit and tasks[-1].action != 'clarify'))
                    and (not explicit or sources == antecedent)):
                sources = antecedent
            else:
                sources = ()
                limit = 'Indica a qué archivo te refieres para continuar.'
            explicit = True
        words = instruction_words(instruction)
        checks = ['literal'] if phrase else requested_checks(words, kinds)
        request = fold(QUOTED.sub(' ', words))
        if modifier=='if_contains' and (len(sources)!=1 or checks not in (['pages'],['general'],['syntax'])):
            limit = 'Indica un solo archivo y una comprobación que pueda realizarse después de buscar la expresión.'
        elif re.search(r'\b(?:solo si|solamente si|siempre que|a condicion de que)\b', request) or request.startswith('si '):
            limit = 'La lectura local requiere una comprobación explícita de esa condición previa.'
        elif not phrase and re.search(r'(?<![\w.-])(?:esquema|schema)(?![\w-]|\.\w)', request):
            limit = 'El lector comprueba la sintaxis. Validar el esquema requiere otra comprobación.'
        elif 'pages' in checks and QUALIFIED_PAGES.search(request):
            limit = 'El lector cuenta el total del PDF. El recuento con ese filtro queda pendiente.'
        if checks == ['clarify'] and re.match(r'^valida(?:r)?\b', normalized) and re.search(r'\b(?:json|xml)\b', normalized):
            checks = ['syntax']
        elif checks == ['clarify'] and explicit and re.fullmatch(
            r'lee\s+(?:el\s+)?[\w-]+(?:\s*,\s*(?:su|el)\s+(?:texto|contenido))?',request.strip()
        ):
            checks = ['general']
        for check in checks:
            tasks.append(Task(check, sources, part, filter_phrase or phrase, limit, explicit, modifier or literal_modifier, excluded))
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
            if task.modifier in ('if_contains', 'pages_containing'):
                if f['kind']=='pdf':
                    mode = 'text'
                elif task.modifier=='if_contains':
                    mode = 'inspect'
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
