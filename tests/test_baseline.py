"""Pruebas unitarias para la decision base sin IA (src/baseline.py)."""

from src.ingest import Store, cargar_eventos, parse_fecha
from src.state import construir_estado
from src.rules import evaluar_reglas
from src.baseline import recomendacion_base


def test_recomendacion_base_tabla_seccion_3():
    """Verifica que la recomendacion base genere exactamente las acciones,
    timings y scheduled_for especificados en la tabla de resultados esperados.
    """
    now = parse_fecha('2026-10-09T16:00:00Z')

    store = Store()
    contenido = open('data/events.jsonl', encoding='utf-8').read()
    cargar_eventos(contenido, store)

    recs = {}
    for case_id, eventos in store.casos.items():
        estado = construir_estado(eventos)
        reglas = evaluar_reglas(estado, now)
        recs[case_id] = recomendacion_base(case_id, estado, reglas, now)

    # P01: resolve_objection | within_24h | null
    assert recs['P01']['action'] == 'resolve_objection'
    assert recs['P01']['timing'] == 'within_24h'
    assert recs['P01']['scheduled_for'] is None

    # P02: wait | on_new_information | null
    assert recs['P02']['action'] == 'wait'
    assert recs['P02']['timing'] == 'on_new_information'
    assert recs['P02']['scheduled_for'] is None

    # P03: wait | at_date | 2026-10-12T15:00:00Z
    assert recs['P03']['action'] == 'wait'
    assert recs['P03']['timing'] == 'at_date'
    assert recs['P03']['scheduled_for'] == '2026-10-12T15:00:00Z'

    # P04: escalate | within_24h | null
    assert recs['P04']['action'] == 'escalate'
    assert recs['P04']['timing'] == 'within_24h'
    assert recs['P04']['scheduled_for'] is None

    # P05: no_action | not_applicable | null
    assert recs['P05']['action'] == 'no_action'
    assert recs['P05']['timing'] == 'not_applicable'
    assert recs['P05']['scheduled_for'] is None

    # P06 (antes de update): wait | at_date | 2026-10-10T14:00:00Z
    assert recs['P06']['action'] == 'wait'
    assert recs['P06']['timing'] == 'at_date'
    assert recs['P06']['scheduled_for'] == '2026-10-10T14:00:00Z'


def test_recomendacion_base_p06_despues_de_update():
    """Verifica el cambio de P06 tras aplicar el evento de updates.jsonl:
    P06 despues -> resolve_objection | within_24h | null
    """
    now = parse_fecha('2026-10-09T16:00:00Z')

    store = Store()
    cargar_eventos(open('data/events.jsonl', encoding='utf-8').read(), store)
    cargar_eventos(open('data/updates.jsonl', encoding='utf-8').read(), store)

    estado = construir_estado(store.casos['P06'])
    reglas = evaluar_reglas(estado, now)
    rec = recomendacion_base('P06', estado, reglas, now)

    assert rec['action'] == 'resolve_objection'
    assert rec['timing'] == 'within_24h'
    assert rec['scheduled_for'] is None
    assert 'P06-e3' in rec['evidence_event_ids']