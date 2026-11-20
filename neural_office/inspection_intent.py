"""Scope the local Director's answer to operations the readers actually performed."""
import re
import unicodedata


def requested_checks(objective, kinds):
    text = ''.join(char for char in unicodedata.normalize('NFKD', objective.casefold())
                   if not unicodedata.combining(char))
    # A negated or ambiguous instruction needs clarification. Source contents
    # never select a task. The user can choose a supported check from the desk.
    text = re.sub(r'\b(?:si no (?:coinciden|concuerdan)|o no)\b', ' ', text)
    if re.search(r'\b(no|excepto|salvo|ignora|omite|without|except|ignore|not)\b', text):
        return ['clarify']
    if re.search(r'\b(decidimos|acordamos|elegimos|decision (?:guardada|anterior|del hilo)|plazo (?:elegido|confirmado))\b', text):
        return ['decision']
    if re.search(r'\b(legal(?:mente)?|juridic\w*|contractualmente|validez contractual|cumple (?:la ley|el contrato))\b', text):
        return ['contract']
    if re.search(r'\b(plazo de (?:pago|garantia|entrega)|tiempo de carga|validar el esquema|cumple el esquema)\b', text):
        return ['clarify']
    rules = [
        ('visual', r'\b(legib\w*|le[ei]ble\w*|se lee|se ve|contraste|tipograf\w*|colores|readab\w*|legib\w*)\b'),
        ('syntax', r'\b(sintaxis|sintactic\w*|syntax|valida[rc]?\w* (?:el |este |the )?json|json (?:es )?valid\w*)\b'),
        ('hours', r'\b(plazos?|primera respuesta|tiempo de respuesta|response_sla_hours|first response|sla|response time)\b'),
        ('zip', r'\b(inventar\w*|contiene el (?:zip|paquete)|contenido del (?:zip|paquete)|zip contents|list files)\b'),
        ('dimensions', r'\b(dimension\w*|resolucion|pixeles|pixels?|anchura|altura|ancho|alto|width|height)\b'),
        ('html', r'\b((comprueba|comprobar|revisa|valida|audita|check|validate) (?:el |este |the )?html|etiquetas? de (?:control|imagen)|controles sin etiqueta|alternativas? de imagen|alt text)\b'),
        ('pages', r'\b(cuantas paginas|numero de paginas|contar paginas|cuenta (?:las )?paginas|page count|how many pages)\b'),
    ]
    requested = [name for name, pattern in rules if re.search(pattern, text)]
    if 'html' in kinds and not requested and re.search(r'\b(titulo del documento|idioma del documento|evidencia de esta revision|comprobacion estatica)\b', text):
        return ['html']
    if requested:
        return requested
    if text.strip():
        return ['clarify']
    if {'pdf', 'json'} <= kinds:
        return ['hours']
    return [action for action, applies in [('syntax','json' in kinds), ('html','html' in kinds),
            ('zip','zip' in kinds), ('dimensions',bool(kinds & {'jpeg','png'})), ('pages','pdf' in kinds)] if applies] or ['clarify']


def reader_findings(check, inputs, views):
    formats = {'syntax': {'json'}, 'pages': {'pdf'}, 'dimensions': {'png','jpeg'},
               'visual': {'png','jpeg'}, 'zip': {'zip'}, 'html': {'html'}}
    titles = {'syntax':'Validar la sintaxis JSON', 'pages':'Contar páginas del PDF',
              'dimensions':'Comprobar las dimensiones', 'visual':'Revisar la legibilidad',
              'zip':'Inventariar el paquete', 'html':'Comprobar HTML'}
    if check == 'contract':
        return [dict(rule='contract', status='insufficient', title='Hace falta revisar el criterio contractual',
                     detail='Puedo comparar el valor de las dos fuentes. La lectura local no determina si la condición del contrato es válida.', sources=[])]
    if check == 'clarify':
        return [dict(rule='scope', status='insufficient', title='Hace falta concretar la comprobación',
                     detail='Puedo comparar el plazo PDF/JSON, validar JSON, contar páginas, inventariar un ZIP, medir una imagen o comprobar HTML. Elige la tarea que corresponde a tu pregunta.', sources=[])]
    files = [item for item in inputs if item['kind'] in formats[check]]
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
            count=len(view['entries'])
            title=f"{count} entrada en el ZIP" if count==1 else f"{count} entradas en el ZIP"
            detail='Abre el inventario para elegir un miembro y ver su contenido.'
        refs = [dict(base, quote='', **{k:view[k] for k in ('line','column') if view.get(k)})]
        results.append(dict(rule=check, status=outcome, title=title, detail=detail, sources=refs))
    return results
