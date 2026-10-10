"""Pruebas unitarias para el modulo src/llm.py."""

from unittest.mock import patch, MagicMock
from src.llm import extraer_json, pedir_json


def test_extraer_json_plano():
    texto = '{"ok": true, "mensaje": "exito"}'
    res = extraer_json(texto)
    assert res == {"ok": True, "mensaje": "exito"}


def test_extraer_json_markdown():
    texto = "```json\n{\"accion\": \"wait\", \"certeza\": \"high\"}\n```"
    res = extraer_json(texto)
    assert res == {"accion": "wait", "certeza": "high"}


def test_extraer_json_con_texto_alrededor():
    texto = "Hola aqui esta el json:\n{\"data\": 42}\nespero te sirva"
    res = extraer_json(texto)
    assert res == {"data": 42}


def test_pedir_json_fallo_devuelve_none():
    with patch('src.llm.llamar_modelo', side_effect=Exception("API offline")):
        res = pedir_json("system", "user", reintentos=1)
        assert res is None


def test_pedir_json_exito():
    with patch('src.llm.llamar_modelo', return_value='{"valido": 100}'):
        res = pedir_json("system", "user", reintentos=0)
        assert res == {"valido": 100}
