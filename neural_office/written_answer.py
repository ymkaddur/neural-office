"""Small, deliberately closed language for independently checkable written answers."""
import re


_NUMBER = r'([0-9]{1,9})'
_WORD = r'([^\W\d_][\w-]{0,39})'
_FLAGS = re.IGNORECASE


def contract(objective):
    text = ' '.join(objective.split())
    amount = re.fullmatch(
        rf'(?:El total es|Hay|Tengo) {_NUMBER}(?: [\wáéíóúñ-]+)? y '
        rf'(?:salen|regalo|retiro|gasto|vendo) {_NUMBER}(?: [\wáéíóúñ-]+)?\. ?'
        r'¿Cuánt[oa]s?(?: [\wáéíóúñ-]+)? (?:quedan|conservo|quedan disponibles)\?'
        r'(?: (?:Contesta|Responde) (?:solo |sólo )?con la cantidad\.?)?', text, _FLAGS)
    if amount:
        start, removed = map(int, amount.groups())
        return {'kind':'arithmetic', 'answer':str(start - removed), 'basis':f'{start} − {removed}'}
    expression = re.fullmatch(
        rf'(?:¿?Cuánto (?:es|son) |Calcula |Resuelve |¿?){_NUMBER}\s*([+−-])\s*{_NUMBER}[?.]?', text, _FLAGS)
    if expression:
        left, op, right = expression.groups()
        value = int(left) + int(right) if op == '+' else int(left) - int(right)
        return {'kind':'arithmetic','answer':str(value),'basis':f'{left} {op} {right}'}
    explicit = re.fullmatch(
        rf'(?:Responde|Di|Escribe|Contesta) (?:únicamente|solamente|solo|sólo) '
        rf'(?:(?:con )?la palabra )?{_WORD}\.?',
        text, _FLAGS)
    if explicit and explicit[1].casefold() not in {'cuál','qué','cuándo','cómo','dónde','cuánto'}:
        return {'kind':'literal','answer':explicit[1],'basis':'Palabra solicitada en el encargo'}
    color = re.fullmatch(
        rf'(?:En el acta |En el documento )?(?:el color elegido|el color acordado) es {_WORD}\. '
        r'(?:Di|Escribe|Responde) (?:solo|sólo|solamente|únicamente) (?:el color|el color elegido)\.?',
        text, _FLAGS)
    if color:
        return {'kind':'literal','answer':color[1],'basis':'Color declarado en el propio encargo'}
    return None


def check(objective, outputs):
    target = contract(objective)
    if target is None:
        return None
    director = next((r['content'] for r in outputs if r['role'] == 'director'), '')
    return {**target, 'matches':director.strip() == target['answer']}
