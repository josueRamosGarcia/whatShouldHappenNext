"""Pruebas unitarias para el validador de recomendaciones (src/validator.py)."""

from src.ingest import Store, cargar_eventos, parse_fecha
from src.state import construir_estado
from src.rules import evaluar_reglas
from src.validator import validar_y_corregir


def test_validador_rechaza_contacto_prohibido_en_p04():
    """Verifica que si se genera una recomendacion invalida con 'contact' para P04,
    el validador la detecta, devuelve la lista de problemas y la reemplaza por
    la decision base segura ('escalate').
    """
    now = parse_fecha('2026-10-09T16:00:00Z')

    # 1. Cargar el caso P04 desde events.jsonl
    store = Store()
    contenido = open('data/events.jsonl', encoding='utf-8').read()
    cargar_eventos(contenido, store)

    estado = construir_estado(store.casos['P04'])
    reglas = evaluar_reglas(estado, now)

    # 2. Fabricar una recomendacion invalida que viola R2 (propone 'contact' cuando contact_allowed=false)
    rec_invalida = {
        'case_id': 'P04',
        'action': 'contact',  # Accion prohibida por R2
        'timing': 'within_24h',
        'scheduled_for': None,
        'reason': 'El cliente esta interesado, enviarle un mensaje.',
        'evidence_event_ids': ['P04-e2'],
        'confidence': 'high',
        'confidence_reason': 'El cliente envio un mensaje mostrando interes.',
        'risk_level': 'low',
        'requires_human_review': False,
        'missing_information': []
    }

    # 3. Validar y corregir
    rec_corregida, problemas = validar_y_corregir(rec_invalida, 'P04', estado, reglas, now)

    # 4. Comprobaciones:
    # - Debe existir al menos un problema reportado sobre la prohibicion
    assert len(problemas) > 0
    assert any('prohibida' in p for p in problemas)

    # - La recomendacion debe ser reemplazada por la decision base segura de P04 ('escalate')
    assert rec_corregida['action'] == 'escalate'
    assert rec_corregida['timing'] == 'within_24h'
    assert rec_corregida['scheduled_for'] is None