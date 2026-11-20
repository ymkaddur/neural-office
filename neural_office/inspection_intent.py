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
    'syntax': {'json'}, 'pages': {'pdf'}, 'dimensions': {'png', 'jpeg'},
    'visual': {'png', 'jpeg'}, 'zip': {'zip'}, 'html': {'html'},
}


def reader_modes(checks, kinds):
    """Plan at most one native read per source, retaining the strongest required operation."""
    modes = {kind: 'inspect' for check in checks for kind in READER_FORMATS.get(check, ())}
    if 'pages' in checks:
        modes['pdf'] = 'page_count'
    if 'hours' in checks and kinds.count('pdf') == 1 and kinds.count('json') == 1:
        modes.update(pdf='inspect', json='inspect')
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
    return requested or ['clarify']


def requested_checks(objective, kinds):
    normalized = unicodedata.normalize('NFKD', objective.casefold())
    text = ''.join(char for char in normalized if not unicodedata.combining(char))
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
            ('zip','zip' in kinds), ('dimensions',bool(kinds & {'jpeg','png'})), ('pages','pdf' in kinds)] if applies] or ['clarify']


def reader_findings(check, inputs, views):
    titles = {'syntax':'Validar la sintaxis JSON', 'pages':'Contar páginas del PDF',
              'dimensions':'Comprobar las dimensiones', 'visual':'Revisar la legibilidad',
              'zip':'Inventariar el paquete', 'html':'Comprobar HTML'}
    if check == 'contract':
        return [dict(rule='contract', status='insufficient', title='Hace falta revisar el criterio contractual',
                     detail='Puedo comparar el valor de las dos fuentes. La lectura local no determina si la condición del contrato es válida.', sources=[])]
    if check == 'clarify':
        return [dict(rule='scope', status='insufficient', title='Hace falta concretar la comprobación',
                     detail='Puedo comparar el plazo PDF/JSON, validar JSON, contar páginas, inventariar un ZIP, medir una imagen o comprobar HTML. Elige la tarea que corresponde a tu pregunta.', sources=[])]
    files = [item for item in inputs if item['kind'] in READER_FORMATS[check]]
    if not files:
        return [dict(rule=check, status='insufficient', title=titles[check], detail='Falta una fuente compatible con esta comprobación.', sources=[])]
    results = []
    for item in files:
        view = views[item['id']]
        base = dict(attachment_id=item['id'], name=item['name'], sha256=item['sha256'], kind=item['kind'])
        detail = view['detail']
        title = titles[check]
        outcome = 'observed' if view['status']=='ok' else 'insufficient'
        if check=='syntax':
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
