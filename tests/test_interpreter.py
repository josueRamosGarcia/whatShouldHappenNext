"""Pruebas unitarias para el modulo src/interpreter.py."""

from unittest.mock import patch
from datetime import datetime, timezone
from src.interpreter import formatear_eventos, interpretar


def test_formatear_eventos():
    eventos = [
        {
            'event_id': 'e1',
            'case_id': 'P01',
            'event_type': 'message.received',
            'occurred_at': '2026-10-09T10:00:00Z',
            'data': {'message': 'Hola mundo'},
            '_dt': datetime(2026, 10, 9, 10, 0, tzinfo=timezone.utc),
            '_orden': 1
        },
        {
            'event_id': 'e2',
            'case_id': 'P01',
            'event_type': 'proposal.viewed',
            'occurred_at': '2026-10-09T11:00:00Z',
            'data': {'section': 'pricing'},
            '_dt': datetime(2026, 10, 9, 11, 0, tzinfo=timezone.utc),
            '_orden': 2
        }
    ]
    txt = formatear_eventos(eventos)
    assert '[e1]' in txt
    assert '<mensaje_cliente>Hola mundo</mensaje_cliente>' in txt
    assert '[e2]' in txt


def test_interpretar_filtra_ids_inventados_y_valida_permitidas():
    eventos = []
    estado = {'ids': {'e1', 'e2'}}
    reglas = {'permitidas': {'resolve_objection', 'wait'}, 'bloqueos': {}}
    now = datetime(2026, 10, 9, 16, 0, tzinfo=timezone.utc)

    mock_llm_resp = {
        'hechos_observados': [
            {'texto': 'hecho 1', 'event_id': 'e1'},
            {'texto': 'hecho inventado', 'event_id': 'e999'}
        ],
        'inferencias': [
            {'texto': 'inf 1', 'basada_en': ['e1'], 'certeza': 'high'},
            {'texto': 'inf inventada', 'basada_en': ['e888'], 'certeza': 'low'}
        ],
        'informacion_faltante': ['dato X'],
        'intencion_cliente': 'tiene_duda',
        'accion_sugerida': 'resolve_objection',
        'fecha_reevaluacion': None,
        'razon': 'Duda en e1'
    }

    with patch('src.interpreter.pedir_json', return_value=mock_llm_resp):
        res = interpretar('P01', eventos, estado, reglas, now)
        assert res is not None
        # Solo se conserva e1
        assert len(res['hechos_observados']) == 1
        assert res['hechos_observados'][0]['event_id'] == 'e1'
        assert len(res['inferencias']) == 1
        assert res['inferencias'][0]['basada_en'] == ['e1']


def test_interpretar_rechaza_accion_no_permitida():
    eventos = []
    estado = {'ids': {'e1'}}
    reglas = {'permitidas': {'wait'}, 'bloqueos': {'R2': 'contact_allowed=false'}}
    now = datetime(2026, 10, 9, 16, 0, tzinfo=timezone.utc)

    mock_llm_resp = {
        'hechos_observados': [{'texto': 'hecho 1', 'event_id': 'e1'}],
        'inferencias': [],
        'informacion_faltante': [],
        'intencion_cliente': 'interesado',
        'accion_sugerida': 'contact',  # NO permitida
        'fecha_reevaluacion': None,
        'razon': 'Contactar'
    }

    with patch('src.interpreter.pedir_json', return_value=mock_llm_resp):
        res = interpretar('P01', eventos, estado, reglas, now)
        assert res is None  # Debe retornar None para que Persona A use decision base
