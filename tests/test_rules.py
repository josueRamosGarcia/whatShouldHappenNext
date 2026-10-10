"""Pruebas unitarias para la evaluacion de reglas R1 a R4 (src/rules.py)."""

from src.ingest import Store, cargar_eventos, parse_fecha
from src.state import construir_estado
from src.rules import evaluar_reglas, CONTACTO, TODAS


def test_evaluar_reglas_casos_iniciales():
    """Verifica el comportamiento de las reglas sobre events.jsonl a las 16:00 UTC:

    - P01 y P02: Sin bloqueos -> Muestran las 6 acciones permitidas.
    - P03: Bloqueado por R3 (contact_not_before).
    - P04: Bloqueado por R2 (contact_allowed=false).
    - P05: Bloqueado por R1 (caso cerrado).
    - P06 (antes de update): Bloqueado por R4 (menos de 24h desde ultimo contacto).
    """
    # 1. Cargar el manifest para obtener la fecha de evaluacion "now"
    now = parse_fecha('2026-10-09T16:00:00Z')

    # 2. Cargar eventos de events.jsonl
    store = Store()
    contenido = open('data/events.jsonl', encoding='utf-8').read()
    cargar_eventos(contenido, store)

    # 3. Evaluar reglas para cada caso
    resultados = {}
    for case_id, eventos in store.casos.items():
        estado = construir_estado(eventos)
        resultados[case_id] = evaluar_reglas(estado, now)

    # Validacion P01 y P02: deben tener las 6 acciones permitidas (sin bloqueos)
    assert resultados['P01']['permitidas'] == TODAS
    assert len(resultados['P01']['bloqueos']) == 0

    assert resultados['P02']['permitidas'] == TODAS
    assert len(resultados['P02']['bloqueos']) == 0

    # Validacion P03: Bloqueo activo por R3 (contact_not_before)
    assert 'R3' in resultados['P03']['bloqueos']
    assert not (resultados['P03']['permitidas'] & CONTACTO)

    # Validacion P04: Bloqueo activo por R2 (contact_allowed=false)
    assert 'R2' in resultados['P04']['bloqueos']
    assert not (resultados['P04']['permitidas'] & CONTACTO)

    # Validacion P05: Bloqueo activo por R1 (caso cerrado, solo no_action)
    assert 'R1' in resultados['P05']['bloqueos']
    assert resultados['P05']['permitidas'] == {'no_action'}

    # Validacion P06 (antes): Bloqueo activo por R4 (menos de 24h del ultimo contacto)
    assert 'R4' in resultados['P06']['bloqueos']
    assert not (resultados['P06']['permitidas'] & CONTACTO)