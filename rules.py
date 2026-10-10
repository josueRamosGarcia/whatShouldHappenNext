"""Módulo de Evaluación de Reglas de Negocio R1 a R4 (src/rules.py).

Este módulo es el motor central de seguridad y restricciones del proyecto. Evalúa el
estado consolidado de un caso frente a la fecha actual (`now`) y determina el conjunto
de acciones permitidas, registrando los bloqueos activos, la fecha de desbloqueo y
las evidencias asociadas.
"""

from datetime import timedelta

# Conjunto de acciones de contacto externo directo hacia el cliente
CONTACTO = {'contact', 'request_information', 'resolve_objection'}

# Catalogo completo de acciones posibles en el sistema
TODAS = CONTACTO | {'escalate', 'wait', 'no_action'}


def evaluar_reglas(estado: dict, now) -> dict:
    """Evalúa las reglas R1 a R4 sobre el estado de un caso y determina las acciones permitidas.

    Reglas aplicadas:
    - R1: Si el caso está cerrado, solo se permite 'no_action'.
    - R2: Si `contact_allowed` es False, se bloquean las acciones de contacto.
    - R3: Si la fecha actual (`now`) es menor a `contact_not_before`, se bloquean las acciones de contacto.
    - R4: Se bloquean las acciones de contacto si transcurrieron menos de 24 horas desde el último
          contacto sin que haya existido un mensaje del cliente estrictamente posterior a este.

    Las acciones 'escalate', 'wait' y 'no_action' permanecen siempre permitidas (salvo en R1).

    Args:
        estado (dict): Diccionario con el estado actual del caso (generado por `construir_estado`).
        now (datetime): Fecha y hora de evaluación consciente de zona horaria (UTC).

    Returns:
        dict: Resultado del análisis de reglas con la siguiente estructura:
            {
                'permitidas': set,        # Conjunto de acciones permitidas
                'bloqueos': dict,         # Diccionario {'Rx': 'motivo'} con las reglas violadas
                'desbloqueo': datetime | None, # Fecha máxima de liberación del contacto
                'evidencia': list         # Lista de event_id que explican los bloqueos
            }
    """
    # R1: Caso cerrado
    if estado['cerrado']:
        return {
            'permitidas': {'no_action'},
            'bloqueos': {'R1': 'caso cerrado'},
            'desbloqueo': None,
            'evidencia': [estado['id_cierre']]
        }

    bloqueos, fechas, evidencia, indefinido = {}, [], [], False

    # R2: Permiso explícito de contacto desactivado
    if estado['contact_allowed'] is False:
        bloqueos['R2'] = 'contact_allowed=false'
        indefinido = True
        evidencia += estado['ev_restriccion']

    # R3: Restricción temporal (contact_not_before)
    nb = estado['contact_not_before']
    if nb and now < nb:
        bloqueos['R3'] = 'antes de contact_not_before'
        fechas.append(nb)
        evidencia += estado['ev_restriccion']

    # R4: Ventana de reposo de 24 horas tras último contacto
    uc = estado['ultimo_contacto']
    if uc and now < uc + timedelta(hours=24):
        um = estado['ultimo_mensaje']
        # Se libera R4 únicamente si hay un mensaje posterior al último contacto
        if not (um and um > uc):
            bloqueos['R4'] = 'menos de 24h desde el ultimo contacto'
            fechas.append(uc + timedelta(hours=24))
            evidencia.append(estado['id_ultimo_contacto'])

    permitidas = set(TODAS)

    # Si existe algún bloqueo activo (R2, R3 o R4), se remueven las acciones de contacto
    if bloqueos:
        permitidas -= CONTACTO

    # El desbloqueo es None si hay una restricción indefinida (R2) o no hay fechas registradas;
    # de lo contrario, se toma la fecha más lejana (max).
    desbloqueo = None if (indefinido or not fechas) else max(fechas)

    return {
        'permitidas': permitidas,
        'bloqueos': bloqueos,
        'desbloqueo': desbloqueo,
        'evidencia': list(dict.fromkeys(evidencia))
    }