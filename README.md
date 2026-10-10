# What Should Happen Next? 🧭

Prototipo de decisiones y recomendaciones comerciales basadas en eventos, asistidas por Inteligencia Artificial y gobernadas por reglas deterministas de negocio. Desarrollado para el hackathon **ByeCode: What Should Happen Next?**.

El sistema procesa el ciclo de vida de propuestas comerciales, analiza señales de interés, interpreta mensajes del cliente con modelos de lenguaje (LLM), aplica reglas de negocio inviolables (R1 a R6) y genera recomendaciones estructuradas explicando **qué hacer, cuándo y por qué**, con capacidad de recomendar esperar (`wait`) o no intervenir (`no_action`).

---

## 🚀 Características Principales

1. **Ingesta Robusta y Auditoría:**
   - Carga incremental de eventos en formato JSONL (`events.jsonl`, `updates.jsonl`).
   - Deduplicación automática por `event_id`.
   - Agrupación por `case_id` y ordenamiento cronológico (`occurred_at` UTC y desempate por orden de llegada).
   - Tolerancia a fallos: captura y muestra errores de formato sin detener el procesamiento de los demás casos.

2. **Arquitectura Híbrida (IA Semántica + Reglas Deterministas):**
   - **La IA interpreta, las reglas deciden:** La IA analiza el contexto y extrae hechos, inferencias e información faltante.
   - **Motor de Reglas Determinista:** Validador formal previo a la publicación que garantiza el 100% de cumplimiento de las restricciones R1 a R6.
   - **Respaldo Determinista Seguro (`baseline.py`):** Si la IA falla, no está configurada o propone una acción inválida, el sistema conmuta automáticamente a la decisión base determinista sin interrumpir la operación.

3. **Especialización Dev Shop y Bucle Cerrado (Closed-Loop Feedback):**
   - Diseñado para agencias y consultoras de desarrollo de software con cotizaciones de alto valor ($150,000 MXN en Fixed Price / T&M).
   - Diagnóstico comercial: etapa en el embudo, temperatura del lead y foco de objeción técnica.
   - **Bucle Cerrado Interactivo:** El ejecutivo registra el resultado de la acción ejecutada, inyectando eventos compatibles con el contrato (`action.executed`, `message.received`, `constraint.updated`, `case.closed`) y detonando la reevaluación inmediata.

4. **Trazabilidad y Reevaluación ("¿Qué cambió?"):**
   - Reevaluación reactiva al recibir nuevos eventos.
   - Historial de versiones que detecta y destaca los cambios entre la decisión anterior y la vigente (ej. caso `P06`).
   - Exportación de las decisiones vigentes en formato JSON estandarizado conforme al contrato de 11 campos.

5. **Interfaz Visual Intuitiva (Streamlit):**
   - **Pestaña 📊 Casos:** Tabla consolidada con estado, timing, confianza, riesgo y bloqueos activos.
   - **Pestaña 🔍 Detalle del Caso:** Historial cronológico de eventos, recomendación vigente, desglose de IA (hechos, inferencias, faltantes) y comparativa de cambios. Alertas visuales destacadas para contactos bloqueados.
   - **Pestaña 📁 Errores y exportar:** Métricas de ingesta, auditoría de duplicados y descarga del archivo `recommendations.json`.

---

## 🛠️ Instalación y Configuración

### 1. Prerrequisitos
- Python 3.10 o superior (probado en Python 3.13)
- Gestor de paquetes `pip`

### 2. Clonar el repositorio y crear entorno virtual
```bash
git clone <URL_DEL_REPOSITORIO>
cd whatShouldHappenNext

# Crear entorno virtual
python -m venv .venv

# Activar entorno virtual
# En Windows (PowerShell):
.venv\Scripts\Activate.ps1
# En Linux/macOS:
source .venv/bin/activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Variables de Entorno (Sin Secretos)
El proyecto incluye una plantilla `.env.example`. Para habilitar la integración con la API de Google Gemini:
1. Copia el archivo `.env.example` a `.env`:
   ```bash
   cp .env.example .env
   ```
2. Configura tu API Key de Google Gemini en el archivo `.env`:
   ```env
   GEMINI_API_KEY=tu_api_key_de_google_ai_studio
   LLM_MODEL=gemini-2.5-flash
   ```
> **Nota:** La API Key es **opcional**. Si no configuras la variable `GEMINI_API_KEY`, o si desmarcas la casilla de IA en la interfaz, el sistema funcionará perfectamente en modo determinista seguro utilizando el módulo `baseline.py`.

---

## 💻 Ejecución

### Opción 1: Aplicación Web Interactiva (Streamlit)
Inicia la interfaz de usuario:
```bash
streamlit run app.py
```
Abre tu navegador en `http://localhost:8501`. Desde allí puedes:
1. Cargar `events.jsonl` o subir archivos propios desde la barra lateral.
2. Hacer clic en **🚀 Evaluar todos los casos**.
3. Cargar `updates.jsonl` y volver a evaluar para observar la reevaluación del caso `P06`.
4. Descargar el archivo oficial `recommendations.json` en la pestaña **Errores y exportar**.

### Opción 2: Modo Consola / Script CLI
Para ejecutar una evaluación completa rápida desde la terminal:
```bash
python run_cli.py
```

### Opción 3: Ejecución de Pruebas Automatizadas
Para correr la suite completa de 26 pruebas unitarias (`pytest`):
```bash
pytest
```

---

## 🧠 Explicación del Uso de IA

El uso de Inteligencia Artificial se rige por los siguientes principios de diseño:
- **Modelo:** Google Gemini API mediante el SDK oficial `google-genai` (`gemini-3.8-flash`), con `temperature=0.0` para garantizar respuestas estables y reproducibles.
- **Rol del Modelo:** Actúa exclusivamente como **analista semántico**. El prompt le prohíbe emitir acciones que contradigan las reglas del sistema y exige citar `event_id` reales para cada hecho observado e inferencia.
- **Protección contra Prompt Injection:** Los mensajes recibidos de clientes se encierran entre etiquetas delimitadoras `<mensaje_cliente>` y el prompt del sistema establece que los textos del cliente son únicamente datos pasivos y nunca instrucciones operativas.
- **Filtro Determinista de Seguridad:** La salida de la IA pasa por `src/validator.py`. Si el modelo alucina un `event_id`, propone una acción no permitida por R1–R4, o utiliza un timing incompatible, el validador descarta la propuesta de la IA y aplica la decisión base determinista (`src/baseline.py`).

---

## 📋 Contrato de Recomendación (11 Campos)

Cada recomendación emitida cumple estrictamente con el contrato:
| Campo | Tipo | Descripción |
| :--- | :--- | :--- |
| `case_id` | String | Identificador único del caso. |
| `action` | String | `contact`, `request_information`, `resolve_objection`, `escalate`, `wait`, `no_action`. |
| `timing` | String | `immediate`, `within_24h`, `at_date`, `on_new_information`, `not_applicable`. |
| `scheduled_for` | String \| null | ISO 8601 UTC si `timing=at_date`; `null` en otro caso. |
| `reason` | String | Explicación breve de la recomendación. |
| `evidence_event_ids` | List[String] | Lista de identificadores de evento reales que sustentan la decisión. |
| `confidence` | String | Nivel cualitativo (`low`, `medium`, `high`). |
| `confidence_reason` | String | Justificación de la evidencia que respalda la certeza o incertidumbre. |
| `risk_level` | String | Nivel de riesgo (`low`, `medium`, `high`). |
| `requires_human_review` | Boolean | `true` si requiere revisión de una persona; `false` en caso contrario. |
| `missing_information` | List[String] | Lista explícita de datos faltantes necesarios para avanzar. |

---

## 🛡️ Reglas de Negocio Implementadas

- **R1 (Caso cerrado):** Únicamente permite `no_action` con timing `not_applicable`. El cierre es definitivo.
- **R2 (`contact_allowed=false`):** Prohíbe contacto (`contact`, `request_information`, `resolve_objection`). Si el cliente escribió, deriva a `escalate`; si no, a `wait`.
- **R3 (`contact_not_before`):** Prohíbe contacto antes de la fecha estipulada. Obliga a `wait` con `timing=at_date`.
- **R4 (Ventana de 24 horas):** Tras un contacto (`action.executed`), deben transcurrir 24 horas antes de otro contacto, salvo que llegue un nuevo `message.received` posterior.
- **R5 (Aperturas sin intención confirmada):** La lectura de propuestas (`proposal.viewed`) no justifica descuentos, cierre ni urgencia inmediata (`immediate`).
- **R6 (Prevalencia de restricciones y faltantes):** Si falta información esencial, se reconoce en `missing_information`. Las restricciones de contacto prevalecen sobre cualquier conveniencia comercial.

---

## 📁 Estructura del Repositorio

```text
whatShouldHappenNext/
├── app.py                      # Interfaz gráfica web en Streamlit
├── run_cli.py                  # Script de ejecución por consola
├── requirements.txt            # Dependencias del proyecto
├── .env.example                # Plantilla de variables de entorno sin secretos
├── NOTA_TECNICA.md             # Nota técnica de 1 página para evaluación
├── NOTA_TECNICA_PERSONA_B.md   # Documento técnico detallado y guion de demo
├── data/
│   ├── manifest.json           # Timestamp oficial de evaluación (UTC)
│   ├── events.jsonl            # Casos base P01 a P06 (con prueba de duplicados)
│   ├── updates.jsonl           # Actualización incremental (evento P06-e3)
│   └── variantes.jsonl         # 7 casos de prueba adicionales con variantes
├── outputs/
│   └── recommendations.json    # Recomendaciones finales generadas de casos públicos
├── src/
│   ├── ingest.py               # Ingesta, validación de contrato y deduplicación
│   ├── state.py                # Reconstrucción de estado por caso
│   ├── rules.py                # Motor determinista de reglas R1 a R4
│   ├── validator.py            # Validador de contrato y corrector de anomalías
│   ├── baseline.py             # Motor determinista de decisión base (modo seguro)
│   ├── llm.py                  # Cliente Gemini API con temperatura 0
│   ├── interpreter.py          # Interpretador semántico con protección de inyección
│   ├── recommender.py          # Ensamblador de recomendación estructurada
│   ├── history.py              # Versionado de decisiones y comparador de cambios
│   └── pipeline.py             # Orquestador del flujo integral de evaluación
└── tests/
    ├── test_baseline.py        # Validación de decisiones esperadas en P01-P06
    ├── test_rules.py           # Pruebas de restricciones R1 a R4
    ├── test_validator.py       # Pruebas de rechazo y corrección de anomalías
    ├── test_variantes.py       # Pruebas sobre las 7 variantes de caso
    ├── test_history.py         # Pruebas de versionado y cálculo de "¿Qué cambió?"
    ├── test_ingest.py          # Pruebas de deduplicación y tolerancia a errores
    ├── test_interpreter.py     # Pruebas de extracción de hechos y filtrado
    ├── test_llm.py             # Pruebas de cliente LLM y extracción JSON
    ├── test_recommender.py     # Pruebas de ensamblado de recomendaciones
    └── test_state.py           # Pruebas de construcción cronológica de estado
```
