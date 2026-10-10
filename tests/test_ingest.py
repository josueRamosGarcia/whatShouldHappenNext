"""Pruebas unitarias para la ingesta de datos (src/ingest.py)."""

from src.ingest import Store, cargar_eventos


def test_ingesta_events_jsonl():
    store = Store()
    contenido = open('data/events.jsonl', encoding='utf-8').read()
    res = cargar_eventos(contenido, store)

    assert res['nuevos'] == 15  # Ajustado a los 15 eventos unicos de tu archivo
    assert res['duplicados'] == 1
    assert res['errores'] == 0
    assert len(store.casos) == 6


def test_linea_basura_no_detiene_ingesta():
    store = Store()
    contenido_basura = (
        'esto no es un json valido\n'
        + open('data/events.jsonl', encoding='utf-8').read()
    )
    res = cargar_eventos(contenido_basura, store)

    assert res['errores'] == 1
    assert len(store.casos) == 6