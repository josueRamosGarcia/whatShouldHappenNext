"""Modulo de conexion con el modelo de lenguaje (src/llm.py).

Adaptado para usar Gemini API mediante el SDK oficial google-genai.
Permite realizar consultas al LLM y extraer estructuras JSON limpias,
con soporte para reintentos y captura de errores sin romper el flujo principal.
"""

import os
import json
import re
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()


def _obtener_cliente() -> genai.Client:
    """Obtiene el cliente de Gemini utilizando la API key configurada."""
    api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('LLM_API_KEY')
    if not api_key:
        raise ValueError("No se encontro GEMINI_API_KEY ni LLM_API_KEY en las variables de entorno.")
    return genai.Client(api_key=api_key)


def llamar_modelo(system: str, user: str) -> str:
    """Llama al modelo Gemini con prompt de sistema y prompt de usuario.

    Args:
        system: Instrucciones de rol y comportamiento para el sistema.
        user: Contenido de entrada del usuario con los datos a evaluar.

    Returns:
        str: Texto generado por el modelo.
    """
    cliente = _obtener_cliente()
    modelo = os.environ.get('LLM_MODEL', 'gemini-3.8-flash')

    # Configuracion con temperatura 0 para respuestas estables y reproducibles
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=0.0,
    )

    respuesta = cliente.models.generate_content(
        model=modelo,
        contents=user,
        config=config,
    )
    return respuesta.text or ""


def extraer_json(texto: str) -> dict:
    """Limpia etiquetas de markdown y extrae el objeto JSON de la respuesta.

    Args:
        texto: Cadena devuelta por el modelo que puede contener bloques markdown.

    Returns:
        dict: Objeto JSON parseado.
    """
    texto_limpio = re.sub(r'```(?:json)?', '', texto).strip()
    i = texto_limpio.find('{')
    j = texto_limpio.rfind('}')
    if i == -1 or j == -1:
        raise ValueError("No se encontro delimitador JSON valido en la respuesta del modelo")
    return json.loads(texto_limpio[i:j + 1])


def pedir_json(system: str, user: str, reintentos: int = 1) -> dict | None:
    """Pide al modelo una respuesta en formato JSON con mecanismo de reintento.

    Args:
        system: Instruccion de sistema.
        user: Datos y peticion del usuario.
        reintentos: Numero de reintentos adicionales en caso de fallo (default 1).

    Returns:
        dict | None: Diccionario con la respuesta o None si la IA fallo.
    """
    ultimo = None
    for _ in range(reintentos + 1):
        try:
            return extraer_json(llamar_modelo(system, user))
        except Exception as ex:
            ultimo = ex
            print('Fallo la IA:', ultimo)
    return None