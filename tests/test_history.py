"""Pruebas unitarias para el modulo src/history.py."""

import json
from src.history import registrar, cambios, exportar_json


def test_registrar_y_versionado():
    hist = {}
    rec1 = {
        'case_id': 'P06',
        'action': 'wait',
        'timing': 'at_date',
        'scheduled_for': '2026-10-10T14:00:00Z',
        'confidence': 'high',
        'risk_level': 'low',
        'requires_human_review': False,
    }
    meta1 = {'ids_evento': ['P06-e1', 'P06-e2']}

    assert registrar(hist, 'P06', rec1, meta1) is True
    assert len(hist['P06']) == 1

    # Mismo registro no agrega nueva version
    assert registrar(hist, 'P06', rec1, meta1) is False
    assert len(hist['P06']) == 1

    # Si cambia la accion, se agrega nueva version
    rec2 = dict(rec1)
    rec2['action'] = 'resolve_objection'
    rec2['timing'] = 'within_24h'
    rec2['scheduled_for'] = None
    meta2 = {'ids_evento': ['P06-e1', 'P06-e2', 'P06-e3']}

    assert registrar(hist, 'P06', rec2, meta2) is True
    assert len(hist['P06']) == 2


def test_cambios():
    hist = {}
    rec1 = {
        'action': 'wait',
        'timing': 'at_date',
        'scheduled_for': '2026-10-10T14:00:00Z',
        'confidence': 'high',
        'risk_level': 'low',
        'requires_human_review': False,
    }
    meta1 = {'ids_evento': ['P06-e1', 'P06-e2']}
    registrar(hist, 'P06', rec1, meta1)

    rec2 = {
        'action': 'resolve_objection',
        'timing': 'within_24h',
        'scheduled_for': None,
        'confidence': 'high',
        'risk_level': 'low',
        'requires_human_review': False,
    }
    meta2 = {'ids_evento': ['P06-e1', 'P06-e2', 'P06-e3']}
    registrar(hist, 'P06', rec2, meta2)

    diff = cambios(hist, 'P06')
    assert diff is not None
    assert diff['eventos_nuevos'] == ['P06-e3']
    nombres_campos = [c[0] for c in diff['campos']]
    assert 'action' in nombres_campos
    assert 'timing' in nombres_campos
    assert 'scheduled_for' in nombres_campos


def test_exportar_json():
    hist = {
        'P01': [{'rec': {'case_id': 'P01', 'action': 'resolve_objection'}}],
        'P02': [{'rec': {'case_id': 'P02', 'action': 'wait'}}]
    }
    salida = exportar_json(hist)
    cargado = json.loads(salida)
    assert len(cargado) == 2
    assert cargado[0]['case_id'] == 'P01'
    assert cargado[1]['case_id'] == 'P02'
