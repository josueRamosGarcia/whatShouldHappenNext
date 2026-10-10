"""Modulo de Ingesta de Datos (src/ingest.py).

Este modulo procesa, valida y almacena los eventos provenientes de archivos JSONL
(como `events.jsonl` y `updates.jsonl`). Realiza la conversion de fechas a objetos UTC,
aplica deduplicacion por `event_id`, y registra errores de formato o contrato sin detener
el procesamiento global.
"""

import json
from datetime import datetime, timezone

# Constantes de validacion segun el contrato de datos
TIPOS = {
    'case.opened',
    'proposal.viewed',
    'message.received',
    'action.executed',
    'constraint.updated',
    'case.closed',
}
CAMPOS = ('event_id', 'case_id', 'event_type', 'occurred_at', 'data')
CIERRES = ('accepted', 'rejected', 'cancelled')


def parse_fecha(s: str) -> datetime:
    """Convierte una cadena de fecha ISO-8601 a un objeto datetime en UTC.

    Args:
        s (str): Cadena de texto con la fecha en formato ISO-8601 (ej. '2026-10-09T16:00:00Z').

    Returns:
        datetime: Objeto datetime consciente de la zona horaria (timezone-aware) en UTC.
    """
    dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def fmt_fecha(dt: datetime) -> str:
    """Formatea un objeto datetime a una cadena ISO-8601 terminada en 'Z' (UTC).

    Args:
        dt (datetime): Objeto datetime a formatear.

    Returns:
        str: Cadena de texto en formato '%Y-%m-%dT%H:%M:%SZ'.
    """
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class Store:
    """Almacen central de eventos, errores y contador de estado de la ingesta.

    Permite acumular eventos de multiples lecturas (ej. events y updates) manteniendo
    la integridad de los datos procesados, detectando duplicados y gestionando
    el orden de llegada.

    Attributes:
        vistos (set): Conjunto de `event_id` ya procesados para deduplicacion.
        casos (dict): Diccionario que mapea cada `case_id` a la lista de sus eventos validos.
        errores (list): Lista de diccionarios con detalles de las lineas rechazadas.
        duplicados (int): Contador total de eventos omitidos por identificador duplicado.
        contador (int): Contador incremental para registrar el orden global de llegada.
    """

    def __init__(self):
        """Inicializa las estructuras de datos del almacen Store."""
        self.vistos = set()
        self.casos = {}
        self.errores = []
        self.duplicados = 0
        self.contador = 0


def _validar(ev: dict) -> None:
    """Valida la estructura interna y los tipos de datos de un evento.

    Verifica que el evento sea un diccionario, contenga los campos requeridos,
    respete los tipos permitidos y cumpla las restricciones del contrato especifico
    segun su `event_type`. Ademas, parsed la fecha `occurred_at` e inserta la clave `_dt`.

    Args:
        ev (dict): Diccionario con el evento decodificado desde JSON.

    Raises:
        ValueError: Si alguna clave falta, o si algun tipo/valor de dato no cumple el contrato.
    """
    if not isinstance(ev, dict):
        raise ValueError('la linea no es un objeto JSON')

    for c in CAMPOS:
        if c not in ev:
            raise ValueError('falta el campo ' + c)

    if not isinstance(ev['event_id'], str) or not ev['event_id']:
        raise ValueError('event_id invalido')

    if not isinstance(ev['case_id'], str) or not ev['case_id']:
        raise ValueError('case_id invalido')

    if ev['event_type'] not in TIPOS:
        raise ValueError('event_type desconocido')

    if not isinstance(ev['data'], dict):
        raise ValueError('data debe ser un objeto')

    # Conversion de fecha ISO a datetime UTC guardado en la clave interna _dt
    ev['_dt'] = parse_fecha(ev['occurred_at'])

    t, d = ev['event_type'], ev['data']

    # Validaciones especificas por tipo de evento
    if t == 'message.received' and not isinstance(d.get('message'), str):
        raise ValueError('falta message')

    if t == 'action.executed' and d.get('action') not in ('contact', 'request_information'):
        raise ValueError('action invalida')

    if t == 'case.closed' and d.get('status') not in CIERRES:
        raise ValueError('status de cierre invalido')

    if t == 'constraint.updated':
        if 'contact_allowed' not in d and 'contact_not_before' not in d:
            raise ValueError('constraint.updated sin campos')
        if 'contact_allowed' in d and not isinstance(d['contact_allowed'], bool):
            raise ValueError('contact_allowed debe ser booleano')
        if d.get('contact_not_before'):
            parse_fecha(d['contact_not_before'])


def cargar_eventos(texto: str, store: Store) -> dict:
    """Lee y procesa un texto JSONL linea por linea actualizando una instancia de Store.

    Parsea cada linea, la valida contra el contrato, ignora duplicados por `event_id`,
    asigna un numero de orden de llegada (`_orden`), registra errores sin detener
    el procesamiento y agrupa los eventos por `case_id`.

    Args:
        texto (str): Contenido completo de un archivo JSONL en formato de cadena.
        store (Store): Instancia del almacen donde se acumularan los datos procesados.

    Returns:
        dict: Resumen del proceso de ingesta con la estructura:
            {
                'nuevos': int,             # Cantidad de eventos validos agregados
                'casos_afectados': list,   # Lista ordenada de case_id modificados
                'duplicados': int,        # Total acumulado de eventos duplicados
                'errores': int             # Total acumulado de lineas con error
            }
    """
    nuevos, afectados = 0, set()

    for n, linea in enumerate(texto.splitlines(), 1):
        if not linea.strip():
            continue

        try:
            ev = json.loads(linea)
            _validar(ev)
        except Exception as ex:
            store.errores.append({
                'linea': n,
                'error': str(ex),
                'texto': linea[:120]
            })
            continue

        # Filtrado de duplicados por event_id
        if ev['event_id'] in store.vistos:
            store.duplicados += 1
            continue

        store.vistos.add(ev['event_id'])
        store.contador += 1
        ev['_orden'] = store.contador  # Orden de llegada global

        store.casos.setdefault(ev['case_id'], []).append(ev)
        nuevos += 1
        afectados.add(ev['case_id'])

    return {
        'nuevos': nuevos,
        'casos_afectados': sorted(afectados),
        'duplicados': store.duplicados,
        'errores': len(store.errores)
    }