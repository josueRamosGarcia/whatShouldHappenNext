"""Pruebas unitarias para el modulo src/recommender.py."""

from unittest.mock import patch
from datetime import datetime, timezone
from src.recommender import _timing, _confianza, _riesgo, recomendar


def test_timing_no_action():
    t, s = _timing('no_action', {}, {}, datetime(2026, 10, 9, 16, 0, tzinfo=timezone.utc))
    assert t == 'not_applicable'
    assert s is None


def test_timing_wait_con_desbloqueo():
    desb = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc)
    now = datetime(2026, 10, 9, 16, 0, tzinfo=timezone.utc)
    t, s = _timing('wait', {'desbloqueo': desb}, {}, now)
    assert t == 'at_date'
    assert s == '2026-10-12T15:00:00Z'


def test_confianza_y_riesgo():
    estado_cerrado = {'cerrado': True, 'mensajes': []}
    c, c_razon = _confianza(estado_cerrado, {})
    assert c == 'high'

    estado_sin_mensajes = {'cerrado': False, 'mensajes': []}
    c, _ = _confianza(estado_sin_mensajes, {})
    assert c == 'low'

    r = _riesgo('escalate', {}, {'intencion_cliente': 'interesado'})
    assert r == 'medium'

    r_rechaza = _riesgo('wait', {}, {'intencion_cliente': 'rechaza'})
    assert r_rechaza == 'high'


def test_recomendar_exito():
    now = datetime(2026, 10, 9, 16, 0, tzinfo=timezone.utc)
    mock_interp = {
        'hechos_observados': [{'texto': 'Pregunta instalacion', 'event_id': 'P01-e2'}],
        'inferencias': [{'texto': 'Duda puntual', 'basada_en': ['P01-e2'], 'certeza': 'high'}],
        'informacion_faltante': ['Alcance de instalacion'],
        'intencion_cliente': 'tiene_duda',
        'accion_sugerida': 'resolve_objection',
        'fecha_reevaluacion': None,
        'razon': 'El cliente tiene dudas de instalacion.'
    }

    estado = {
        'cerrado': False,
        'mensajes': [{'id': 'P01-e2', 'texto': '¿Incluye instalacion?'}],
        'ids': {'P01-e1', 'P01-e2'},
        'ultimo_id': 'P01-e2'
    }
    reglas = {'permitidas': {'resolve_objection', 'wait'}, 'bloqueos': {}, 'evidencia': []}

    with patch('src.recommender.interpretar', return_value=mock_interp):
        res = recomendar('P01', [], estado, reglas, now)
        assert res is not None
        rec, interp = res
        assert rec['case_id'] == 'P01'
        assert rec['action'] == 'resolve_objection'
        assert rec['timing'] == 'within_24h'
        assert rec['scheduled_for'] is None
        assert 'P01-e2' in rec['evidence_event_ids']
        assert rec['confidence'] == 'medium'
        assert rec['risk_level'] == 'low'
        assert rec['requires_human_review'] is False
        assert rec['missing_information'] == ['Alcance de instalacion']
