"""Módulo de Estado del Caso (src/state.py).

Este módulo procesa la secuencia histórica de eventos de un caso individual y construye
su estado actual (la "foto actual" del cliente). Aplica ordenamiento cronológico por fecha 
y orden de llegada, actualiza de forma parcial las restricciones de contacto, y respeta
el carácter terminal del cierre de casos.
"""

from src.ingest import parse_fecha


def construir_estado(eventos: list) -> dict:
    """Construye el estado consolidado de un caso a partir de su lista de eventos.

    La función procesa los eventos ordenándolos primero por fecha (`_dt`) y desempatando 
    por orden de llegada (`_orden`). Recorre cada evento actualizando las claves del
    diccionario de estado. La actualización de restricciones (`constraint.updated`) es parcial,
    sobrescribiendo solo los campos presentes en el evento. El cierre del caso (`case.closed`)
    es terminal: ningún evento posterior a él altera el estado.

    Args:
        eventos (list): Lista de diccionarios de eventos pertenecientes a un mismo caso,
            previamente validados e ingresados.

    Returns:
        dict: Diccionario que representa el estado del caso con la siguiente estructura:
            {
                'cerrado': bool,                   # Indica si el caso está cerrado
                'cierre_status': str | None,       # Estado del cierre ('accepted', 'rejected', etc.)
                'id_cierre': str | None,           # event_id del evento de cierre
                'monto': float | int | None,       # Monto de la propuesta en MXN
                'contact_allowed': bool,           # Permiso de contacto (default True)
                'contact_not_before': datetime | None, # Fecha mínima para reanudar contacto
                'ev_restriccion': list,            # Lista de event_id que modificaron restricciones
                'ultimo_contacto': datetime | None,# Fecha del último contacto realizado
                'id_ultimo_contacto': str | None,  # event_id del último contacto
                'ultimo_mensaje': datetime | None, # Fecha del último mensaje recibido del cliente
                'mensajes': list,                  # Lista de mensajes [{'id', 'fecha', 'texto'}]
                'aperturas': list,                 # Lista de lecturas [{'id', 'fecha', 'section'}]
                'ids': set,                        # Conjunto con todos los event_id del caso
                'ultimo_id': str | None            # Identificador del último evento procesado
            }
    """
    # Ordenar cronológicamente por fecha (_dt) y desempate por orden de llegada (_orden)
    eventos = sorted(eventos, key=lambda e: (e['_dt'], e['_orden']))

    # Estado inicial por defecto según el contrato compartido
    e = {
        'cerrado': False,
        'cierre_status': None,
        'id_cierre': None,
        'monto': None,
        'contact_allowed': True,
        'contact_not_before': None,
        'ev_restriccion': [],
        'ultimo_contacto': None,
        'id_ultimo_contacto': None,
        'ultimo_mensaje': None,
        'mensajes': [],
        'aperturas': [],
        'ids': set(),
        'ultimo_id': None
    }

    for ev in eventos:
        e['ids'].add(ev['event_id'])
        e['ultimo_id'] = ev['event_id']

        # Si el caso ya se cerró previamente, ningún evento posterior lo altera
        if e['cerrado']:
            continue

        t, d = ev['event_type'], ev['data']

        if t == 'case.opened':
            e['monto'] = d.get('proposal_amount_mxn')

        elif t == 'proposal.viewed':
            e['aperturas'].append({
                'id': ev['event_id'],
                'fecha': ev['_dt'],
                'section': d.get('section')
            })

        elif t == 'message.received':
            e['mensajes'].append({
                'id': ev['event_id'],
                'fecha': ev['_dt'],
                'texto': d['message']
            })
            e['ultimo_mensaje'] = ev['_dt']

        elif t == 'action.executed':
            e['ultimo_contacto'] = ev['_dt']
            e['id_ultimo_contacto'] = ev['event_id']

        elif t == 'constraint.updated':
            # Actualización parcial: solo sobrescribe los campos presentes en el evento
            if 'contact_allowed' in d:
                e['contact_allowed'] = d['contact_allowed']
            if 'contact_not_before' in d:
                v = d['contact_not_before']
                e['contact_not_before'] = parse_fecha(v) if v else None
            e['ev_restriccion'].append(ev['event_id'])

        elif t == 'case.closed':
            # El cierre es definitivo y terminal
            e['cerrado'] = True
            e['cierre_status'] = d.get('status')
            e['id_cierre'] = ev['event_id']

    return e