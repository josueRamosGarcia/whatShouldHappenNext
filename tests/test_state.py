"""Pruebas unitarias para la construccion del estado del caso (src/state.py)."""

from datetime import datetime, timezone
from src.ingest import Store, cargar_eventos
from src.state import construir_estado


def test_construir_estado_casos():
    """Verifica las condiciones clave de estado tras procesar events.jsonl:
    
    1. P06: ultimo_contacto debe ser a las 14:00 (respetando el orden cronologico
       de los eventos a pesar del orden en el archivo).
    2. P05: cerrado == True (el caso esta cerrado).
    3. P04: contact_allowed == False (restriccion activa).
    4. P03: contact_not_before == 2026-10-12T15:00:00Z.
    """
    # 1. Cargar eventos desde events.jsonl
    store = Store()
    contenido = open('data/events.jsonl', encoding='utf-8').read()
    cargar_eventos(contenido, store)

    # 2. Construir estado para cada caso
    estados = {
        case_id: construir_estado(eventos)
        for case_id, eventos in store.casos.items()
    }

    # Validacion P06: ultimo_contacto debe ser a las 14:00 UTC
    estado_p06 = estados['P06']
    assert estado_p06['ultimo_contacto'] == datetime(2026, 10, 9, 14, 0, 0, tzinfo=timezone.utc)

    # Validacion P05: debe estar cerrado
    estado_p05 = estados['P05']
    assert estado_p05['cerrado'] is True

    # Validacion P04: contact_allowed debe ser False
    estado_p04 = estados['P04']
    assert estado_p04['contact_allowed'] is False

    # Validacion P03: contact_not_before debe ser el 12 de octubre a las 15:00 UTC
    estado_p03 = estados['P03']
    assert estado_p03['contact_not_before'] == datetime(2026, 10, 12, 15, 0, 0, tzinfo=timezone.utc)