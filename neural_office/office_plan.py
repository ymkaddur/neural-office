"""Inspectable execution topology for the next office protocol. Planning is read-only."""
from .desktop_contract import valid
from .ledger import Denied, MAX_CALLS
from .runner import role_order


ROUND_PURPOSES = ('Establecer hechos y fuentes', 'Contrastar objeciones y corregir',
                  'Verificar la entrega contra el encargo')


def office_plan(objective):
    if not valid('objective', objective):
        raise Denied('DESKTOP_PARAMETER_INVALID')
    director, *specialists = role_order(7)
    steps = []
    previous = []
    for number, purpose in enumerate(ROUND_PURPOSES, start=1):
        assignment = f'r{number}.{director}'
        steps.append(dict(id=assignment, round=number, role=director, kind='assign',
                          purpose=purpose, depends_on=previous))
        previous = []
        for role in specialists:
            step_id = f'r{number}.{role}'
            steps.append(dict(id=step_id, round=number, role=role, kind='contribute',
                              depends_on=[assignment]))
            previous.append(step_id)
    steps.append(dict(id='delivery', round=len(ROUND_PURPOSES), role=director,
                      kind='delivery', depends_on=previous))
    return dict(schema=1, mode='plan_only', objective=objective, steps=steps,
                rounds=len(ROUND_PURPOSES), specialists_per_round=len(specialists),
                planned_model_calls=len(steps), current_call_limit=MAX_CALLS,
                model_calls=0, reservations=0)
