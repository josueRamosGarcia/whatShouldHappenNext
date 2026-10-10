"""Pruebas unitarias para verificar el set de variantes de prueba (Paso 8)."""

from datetime import datetime, timezone
from src.ingest import Store, cargar_eventos
from src.state import construir_estado
from src.rules import evaluar_reglas, CONTACTO


def test_carga_variantes_sin_errores():
    store = Store()
    contenido = open('data/variantes.jsonl', encoding='utf-8').read()
    res = cargar_eventos(contenido, store)

    assert res['errores'] == 0
    assert len(store.casos) == 7
    assert set(store.casos.keys()) == {'V01', 'V02', 'V03', 'V04', 'V05', 'V06', 'V07'}


def test_variante_v02_solo_aperturas():
    store = Store()
    contenido = open('data/variantes.jsonl', encoding='utf-8').read()
    cargar_eventos(contenido, store)

    estado_v02 = construir_estado(store.casos['V02'])
    assert len(estado_v02['aperturas']) == 3
    assert len(estado_v02['mensajes']) == 0


def test_variante_v05_contacto_pasadas_24h_libera_r4():
    store = Store()
    contenido = open('data/variantes.jsonl', encoding='utf-8').read()
    cargar_eventos(contenido, store)

    now = datetime(2026, 10, 9, 16, 0, tzinfo=timezone.utc)
    estado_v05 = construir_estado(store.casos['V05'])
    reglas_v05 = evaluar_reglas(estado_v05, now)

    # R4 no debe bloquear porque pasaron 30 horas
    assert 'R4' not in reglas_v05['bloqueos']
    assert bool(reglas_v05['permitidas'] & CONTACTO)


def test_variante_v07_caso_cerrado_terminal():
    store = Store()
    contenido = open('data/variantes.jsonl', encoding='utf-8').read()
    cargar_eventos(contenido, store)

    now = datetime(2026, 10, 9, 16, 0, tzinfo=timezone.utc)
    estado_v07 = construir_estado(store.casos['V07'])
    reglas_v07 = evaluar_reglas(estado_v07, now)

    assert estado_v07['cerrado'] is True
    assert reglas_v07['permitidas'] == {'no_action'}
