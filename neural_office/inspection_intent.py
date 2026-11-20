"""Scope the local Director's answer to operations the readers actually performed."""
import re
import unicodedata


# Split independent questions and requests. Keep document names, field names
# and phrases such as "PDF y JSON" together.
CLAUSES = re.compile(
    r'[¿?¡!;]+|[.](?=\s|$)|\s+(?:y|e|and)\s+(?=(?:cuant\w*|que|cual\w*|'
    r'por que|donde|quien|como|muestra|valida|compara|comprueba|verifica|cuenta|revisa|what|how)\b)'
)
CONTEXT = re.compile(r'(?:revisa|inspecciona) (?:la entrega(?: del portal)?|los archivos(?: adjuntos)?)')
DECISION = re.compile(
    r'(?:(?:dime|recuerdame|muestrame) )?'
    r'(?:(?:(?:que(?: (?:valor|plazo|fuente|opcion))?|cual) )?(?:decidimos|acordamos|elegimos)|'
    r'(?:(?:cual (?:es|fue) )?la )?decision (?:guardada|anterior|del hilo)|'
    r'(?:(?:cual (?:es|fue) )?el )?plazo (?:elegido|confirmado)|con cual nos quedamos|'
    r'que (?:se decidio|quedo acordado))'
    r'(?: en este hilo| (?:sobre|para|respecto a) el plazo(?: de (?:la )?(?:primera )?respuesta)?)?'
)
HOURS = re.compile(
    r'\b(primera respuesta|(?:tiempo|plazo) de (?:la )?respuesta|response_sla_hours|first response|response time)\b|'
    r'\b(?:compar\w*|verific\w*|comprueb\w*|coinciden|concuerdan|revisa)\s+'
    r'(?:(?:el|los dos|los|ambos|dos)\s+)?plazos?(?=$|[,.:]|\s+[ye]\s+identifica\b)'
)
OTHER_DEADLINE = re.compile(
    r'\bplazos?\s+(?:de|del|para)\s+(?!(?:la\s+)?(?:primera respuesta|respuesta)\b)\S+'
)
READER_FORMATS = {
    'syntax': {'json'}, 'pages': {'pdf'}, 'dimensions': {'png', 'jpeg', 'gif', 'webp', 'tiff', 'bmp'},
    'visual': {'png', 'jpeg', 'gif', 'webp', 'tiff', 'bmp'}, 'zip': {'zip'}, 'html': {'html'},
}


def reader_modes(checks, kinds):
    """Plan at most one native read per source, retaining the strongest required operation."""
    modes = {kind: 'inspect' for check in checks for kind in READER_FORMATS.get(check, ())}
    if 'general' in checks or 'literal' in checks:
        modes.update(dict.fromkeys(kinds, 'inspect'))
    if 'pages' in checks:
        modes['pdf'] = 'page_count'
    if 'hours' in checks and kinds.count('pdf') == 1 and kinds.count('json') == 1:
        modes.update(pdf='inspect', json='inspect')
    if ('general' in checks or 'literal' in checks) and 'pdf' in kinds:
        modes['pdf'] = 'text'
    return modes


def _clause_checks(text, kinds):
    if re.search(r'\b(no|excepto|salvo|ignora|omite|without|except|ignore|not)\b', text):
        return ['clarify']
    if re.search(r'\b(legal(?:mente)?|juridic\w*|contractualmente|validez contractual|cumple (?:la ley|el contrato))\b', text):
        return ['contract']
    if OTHER_DEADLINE.search(text) or re.search(r'\b(tiempo de carga|validar el esquema|cumple el esquema)\b', text):
        return ['clarify']
    if DECISION.fullmatch(text.strip(',. ')):
        return ['decision']
    if re.search(r'\b(?:decidimos|acordamos|elegimos|decision|nos quedamos)\b', text):
        return ['clarify']
    rules = [
        ('visual', r'\b(legib\w*|le[ei]ble\w*|se lee|se ve|contraste|tipograf\w*|colores|readab\w*|legib\w*)\b'),
        ('syntax', r'\b(sintaxis|sintactic\w*|syntax|valida[rc]?\w* (?:el |este |the )?json|json (?:es )?valid\w*)\b'),
        ('hours', HOURS),
        ('zip', r'\b(inventar\w*|contiene el (?:zip|paquete)|(?:dentro|contenido) del (?:zip|paquete)|zip contents|list files)\b'),
        ('dimensions', r'\b(dimension\w*|resolucion|pixeles|pixels?|anchura|altura|ancho|alto|width|height)\b'),
        ('html', r'\b((comprueba|comprobar|revisa|valida|audita|check|validate) (?:el |este |the )?html|etiquetas? de (?:control|imagen)|controles sin etiqueta|alternativas? de imagen|alt text)\b'),
        ('pages', r'\b(cuantas paginas|numero de paginas|contar paginas|cuenta (?:las )?paginas|page count|how many pages)\b'),
    ]
    requested = [name for name, pattern in rules if re.search(pattern, text)]
    if 'html' in kinds and not requested and re.search(r'\b(titulo del documento|idioma del documento|evidencia de esta revision|comprobacion estatica)\b', text):
        return ['html']
    if not requested and re.search(r'\b(inspecciona|identifica|describe|muestra|lee|extrae|resume|revisa|comprueba)\s+(?:(?:el|la|los|las|este|estos|esta|estas|mi|mis)\s+)?(?:texto|contenido|archivos?|adjuntos?|documentos?|fichero|entrega|hoja de calculo|presentacion|audio|video|capturas?)\b', text):
        return ['general']
    return requested or ['clarify']


def literal_query(objective):
    match = re.fullmatch(r'\s*(?:busca|buscar|encuentra|localiza)\s+[«"]([^»"\r\n]{1,120})[»"]'
                         r'(?:\s+en\s+(?:los\s+|todos\s+los\s+)?(?:archivos|adjuntos|documentos)(?:\s+adjuntos)?)?[.!]?\s*',
                         objective, flags=re.I)
    return match.group(1) if match else None


def literal_findings(phrase, inputs, views):
    rows = []
    for item in inputs:
        view = views[item['id']]
        name = item['name']
        text = view.get('text')
        status = 'insufficient'
        detail = 'El lector no recuperó texto en el que buscar la expresión.'
        citation = dict(attachment_id=item['id'], name=name, sha256=item['sha256'], kind=item['kind'], quote='')
        coverage = {}
        if item['kind']=='pdf' and 'pages_examined' in view:
            coverage=dict(total_pages=view['pages'],examined_pages=view['pages_examined'],text_pages=view['pages_with_text'],
                          image_pages=view['image_pages'],complete=not view['text_truncated'])
        if isinstance(text, str):
            slices = view.get('page_texts', [dict(page=view.get('page'), text=text)])
            found = next(((part.get('page'), number, line, match)
                         for part in slices
                         for number, line in enumerate(part['text'].splitlines(), start=view.get('text_start_line', 1))
                         if (match := re.search(re.escape(phrase),line,re.I))), None)
            if found:
                page, number, line, match = found
                status='observed'
                detail=f'«{phrase}» aparece en el texto recuperado de {name}.'
                citation.update(quote=line[max(0,match.start()-50):match.end()+80], line=number)
                if page:
                    citation['page']=page
            else:
                partial = (view.get('text_truncated') or item['kind'] not in ('text','other','json','html','pdf'))
                status='insufficient' if partial else 'observed'
                detail=('La expresión no aparece en el extracto recuperado.' if partial else
                        'La expresión no aparece en el texto completo del archivo.')
                if coverage and partial:
                    checked, total = coverage['examined_pages'], coverage['total_pages']
                    detail=f'No apareció en el texto recuperado de {name}. Se examinaron {checked} de {total} páginas.'
                    if checked < total:
                        detail+=f' Pendientes de lectura: {checked+1}–{total}.' if total>checked+1 else f' Falta la página {total}.'
                    if not coverage['text_pages']:
                        detail+=' No se recuperó texto seleccionable.'
                    elif coverage['image_pages']:
                        detail+=' La búsqueda no lee el texto dentro de las imágenes.'
                    elif checked==total:
                        detail+=' El texto extraído tiene cobertura parcial.'
        rows.append(dict(rule='literal',status=status,title=name,detail=detail,sources=[citation],**({'coverage':coverage} if coverage else {})))
    return rows


def requested_checks(objective, kinds, *, allow_dialogue=True):
    if literal_query(objective):
        return ['literal']
    normalized = unicodedata.normalize('NFKD', objective.casefold())
    text = ''.join(char for char in normalized if not unicodedata.combining(char))
    if allow_dialogue and re.fullmatch(r'\s*[¡!¿?]*\s*(?:hola(?:,?\s+director)?|buen[oa]s(?: dias| tardes| noches)?|que puedes hacer|ayuda)\s*[!.¿?¡]*\s*', text):
        return ['greeting']
    if text.strip():
        text = re.sub(r'\b(?:si no (?:coinciden|concuerdan)|o no)\b', ' ', text)
        clauses = [part.strip() for part in CLAUSES.split(' '.join(text.split())) if part.strip()]
        checks = []
        for clause in clauses:
            if len(clauses) > 1 and CONTEXT.fullmatch(clause):
                continue
            if 'hours' in checks and re.fullmatch(
                r'indica que (?:dato|valor) debe confirmar la persona responsable', clause
            ):
                continue
            for check in _clause_checks(clause, kinds):
                if check not in checks:
                    checks.append(check)
        return checks or ['clarify']
    if {'pdf', 'json'} <= kinds:
        return ['hours']
    return [action for action, applies in [('syntax','json' in kinds), ('html','html' in kinds),
            ('zip','zip' in kinds), ('dimensions',bool(kinds & READER_FORMATS['dimensions'])), ('pages','pdf' in kinds),
            ('general',bool(kinds - {'json','html','zip','pdf'} - READER_FORMATS['dimensions']))] if applies] or ['general']


def reader_findings(check, inputs, views):
    titles = {'syntax':'Validar la sintaxis JSON', 'pages':'Contar páginas del PDF',
              'dimensions':'Comprobar las dimensiones', 'visual':'Revisar la legibilidad',
              'zip':'Inventariar el paquete', 'html':'Comprobar HTML'}
    if check == 'general':
        results = []
        for item in inputs:
            view = views[item['id']]
            text = (view.get('text') or '').strip()
            preview = text[:220]
            detail = view['detail']
            if preview:
                detail = preview + ('…' if len(text)>len(preview) or view.get('text_truncated') else '')
            elif view.get('width') and view.get('height'):
                detail = f"{view['width']} × {view['height']} px. {detail}"
            elif view.get('entries') is not None:
                detail = f"{len(view['entries'])} entradas en el paquete. {detail}"
            elif view.get('pages'):
                detail = f"{view['pages']} páginas. {detail}"
            title = item['name']
            status = 'observed' if view['status']=='ok' else 'insufficient'
            citation = dict(attachment_id=item['id'], name=title, sha256=item['sha256'],
                            kind=item['kind'], quote=preview)
            if view.get('page'):
                citation['page'] = view['page']
            results.append(dict(rule='file_content', status=status, title=title, detail=detail, sources=[citation]))
        return results
    if check == 'contract':
        return [dict(rule='contract', status='insufficient', title='Hace falta revisar el criterio contractual',
                     detail='Puedo comparar el valor de las dos fuentes. La lectura local no determina si la condición del contrato es válida.', sources=[])]
    if check == 'greeting':
        count = len(inputs)
        selected = 'un archivo seleccionado' if count == 1 else f'{count} archivos seleccionados'
        return [dict(rule='greeting', status='observed', title='Hola. ¿Qué quieres revisar?',
                     detail=f'Hay {selected}. Puedo leer su contenido o buscar una frase concreta. Tú eliges el encargo.',
                     sources=[])]
    if check == 'clarify':
        return [dict(rule='scope', status='insufficient', title='Hace falta concretar la comprobación',
                     detail='Puedo identificar los adjuntos, recuperar texto y contrastar datos que tengan una fuente. Indica qué archivo y qué dato quieres comprobar.', sources=[])]
    files = [item for item in inputs if item['kind'] in READER_FORMATS[check]
             or (check == 'syntax' and item['kind'] == 'text' and item['name'].lower().endswith('.xml'))]
    if not files:
        return [dict(rule=check, status='insufficient', title=titles[check], detail='Falta una fuente compatible con esta comprobación.', sources=[])]
    results = []
    for item in files:
        view = views[item['id']]
        base = dict(attachment_id=item['id'], name=item['name'], sha256=item['sha256'], kind=item['kind'])
        detail = view['detail']
        title = titles[check]
        outcome = 'observed' if view['status']=='ok' else 'insufficient'
        if check == 'syntax' and item['kind'] == 'text':
            label = {True:'XML bien formado',False:'Error de sintaxis XML'}.get(view.get('xml_valid'),'Sintaxis XML pendiente')
            title = label+' · '+item['name']
            detail = view.get('xml_detail', 'No se pudo comprobar la sintaxis XML de esta captura.')
            outcome = 'observed' if 'xml_valid' in view else 'insufficient'
        elif check=='syntax':
            if view['status']=='ok':
                title='La sintaxis JSON es válida'
                detail=f"El lector pudo analizar {item['name']}."
            elif view['status']=='invalid':
                title='El JSON contiene un error de sintaxis'
                outcome='observed'
        elif check=='visual' and view['status']=='ok':
            title='La legibilidad requiere revisión visual'
            detail='La imagen se ha abierto. Revisa el título en el visor a tamaño original. El lector local comprueba el archivo y sus dimensiones.'
            outcome='insufficient'
        elif check=='dimensions' and view['status']=='ok':
            title=f"{view['width']} × {view['height']} px"
            detail=f"Dimensiones de {item['name']} con la orientación de lectura aplicada."
        elif check=='pages' and view.get('pages') is not None:
            count=view['pages']
            title=f"{count} página" if count==1 else f"{count} páginas"
        elif check=='zip' and view['status']=='ok':
            entries = view['entries']
            count = len(entries)
            title=f"{count} entrada en el ZIP" if count==1 else f"{count} entradas en el ZIP"
            names = [entry['path'] for entry in entries if entry['readable'] and entry['path'].isprintable()]
            if not entries:
                detail = 'El paquete está vacío.'
            elif not names:
                detail = 'Abre el inventario para revisar los nombres y los límites de lectura.'
            else:
                detail = 'El inventario incluye ' + ', '.join(f'«{name}»' for name in names[:6]) + '.'
                if count > min(len(names), 6):
                    detail += ' El inventario completo muestra las demás entradas.'
        refs = [dict(base, quote='', **{k:view[k] for k in ('line','column') if view.get(k)})]
        results.append(dict(rule=check, status=outcome, title=title, detail=detail, sources=refs))
    return results
