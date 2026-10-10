import os, json, re
from dotenv import load_dotenv
from google import genai

# Carga las variables del archivo .env al entorno (como si hicieras el 'export')
load_dotenv()

# Inicializa el cliente
client = genai.Client()

def llamar_modelo(system, user):
    # Unificamos el prompt del sistema y el del usuario para la API de Interacciones
    prompt_completo = f"Instrucciones del sistema:\n{system}\n\nDatos:\n{user}"
    
    interaction = client.interactions.create(
        model=os.environ.get('LLM_MODEL', 'gemini-3.8-flash'),
        input=prompt_completo
    )
    return interaction.output_text

def extraer_json(texto):
    # Limpia las etiquetas de markdown si el modelo las incluye
    texto = re.sub(r'```(?:json)?', '', texto).strip()
    i, j = texto.find('{'), texto.rfind('}')
    return json.loads(texto[i:j + 1])

def pedir_json(system, user, reintentos=1):
    for _ in range(reintentos + 1):
        try:
            return extraer_json(llamar_modelo(system, user))
        except Exception as ex:
            ultimo = ex
            print('Falló la IA:', ultimo)
    return None