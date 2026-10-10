# Aportes de Persona B: Nota Técnica y Paquete de Presentación

Este documento contiene los bloques listos para entregar a la **Persona A** (para integrar en la nota técnica final) y a la **Persona C** (para armar las diapositivas y el guion de la presentación).

---

## 1. Bloques para la Nota Técnica (Entregar a Persona A)

### IA Utilizada
Se implementó **Google Gemini API** a través del SDK oficial `google-genai` (modelo `gemini-2.5-flash` con `temperature=0` para reproducibilidad). La IA actúa estrictamente como analista semántico: extrae la intención del cliente, identifica hechos e información faltante, y únicamente puede sugerir una acción dentro del catálogo ya validado y permitido por el motor de reglas determinista de Persona A. La IA no dicta reglas de negocio.

### Distinción Hechos / Inferencias / Faltantes
La IA genera una estructura JSON estricta donde cada hecho observado (`hechos_observados`) se asocia obligatoriamente a un `event_id` verificable; las deducciones del modelo (`inferencias`) incluyen su nivel de certeza y eventos de respaldo; y las lagunas de contexto se declaran abiertamente en `informacion_faltante`. En la interfaz de usuario, estos tres elementos se exponen en paneles diferenciados para máxima transparencia y auditoría.

### Contexto y Trazabilidad
En cada ciclo de evaluación se provee al modelo el expediente cronológico íntegro del caso ordenado por fecha de ocurrencia y orden de llegada. Cada evento expone su folio `event_id` y contenido desglosado. Esto garantiza que la IA cuente con visibilidad de todas las interacciones previas (aperturas, cotizaciones, mensajes anteriores y restricciones activas) al emitir su sugerencia.

### Seguridad Frente a Mensajes Maliciosos (Prompt Injection)
Para mitigar ataques de inyección de instrucciones (ej. clientes intentando forzar descuentos o ignorar restricciones), los mensajes entrantes se aíslan entre etiquetas `<mensaje_cliente>` y el prompt de sistema los declara expresamente como datos pasivos y no como comandos ejecutables. Además, el validador estricto de Persona A intercepta y descarta cualquier propuesta que intente violar las restricciones R1–R4.

### Criterios de Confianza y Riesgo
Los niveles de confianza y riesgo no quedan al azar del modelo, sino que se calculan mediante reglas objetivas documentadas:

| Dimensión | Nivel | Criterio de Activación |
| :--- | :--- | :--- |
| **Confianza** | **High** | Caso cerrado o evidencia explícita/verificable en datos sin información faltante relevante. |
| **Confianza** | **Medium** | Mensaje claro del cliente pero existen datos faltantes que requieren confirmación interna. |
| **Confianza** | **Low** | Solo existen aperturas de propuestas (`proposal.viewed`) o el mensaje del cliente es ambiguo. |
| **Riesgo** | **High** | El cliente expresa rechazo explícito (`rechaza`) o existen contradicciones directas en el caso. |
| **Riesgo** | **Medium** | Se requiere escalamiento humano (`escalate`) o el cliente solicita contacto mientras rige un bloqueo activo. |
| **Riesgo** | **Low** | La recomendación es segura o conservadora (espera inofensiva o seguimiento estándar permitido). |

### Incertidumbre y Limitaciones
El modelo de lenguaje opera sobre lenguaje natural y carece de calibración estadística formal. Los datos analizados corresponden a escenarios comerciales simulados. Ante fallas de conexión a la API o respuestas mal formateadas, el sistema conmuta de forma transparente a la decisión base determinista (`baseline.py`), garantizando que ninguna acción inválida o riesgosa sea ejecutada de forma autónoma.

---

## 2. Paquete de Presentación (Entregar a Persona C)

### Los 5 Números Memorables del Proyecto
1. **6 casos** evaluados y auditados de punta a punta.
2. **1 duplicado ignorado** automáticamente por identificador único (`P02-e2`), manteniendo la integridad de la base.
3. **1 decisión que cambió de forma inteligente**: `P06` pasa de `wait` a `resolve_objection` al recibir la pregunta `P06-e3`, registrando dos versiones y trazabilidad completa.
4. **4 casos con contacto bloqueado o cerrado** respetados rigurosamente (`P03`, `P04`, `P05` y `P06` en estado inicial).
5. **0 violaciones de reglas**: 100% de cumplimiento en restricciones R1 a R4.

### Frases Clave para el Pitch / Demo
- *"La IA interpreta, las reglas deciden."*
- *"Nunca contactamos a un cliente si las reglas lo prohíben, sin importar lo que pida el mensaje."*
- *"Cada decisión cita evidencia real con su ID de evento; no hay recomendaciones a ciegas."*
- *"Cuando llega un evento nuevo, mostramos exactamente qué cambió y por qué."*
- *"Saber esperar también es una decisión estratégica."*

### Flujo Recomendado para la Demostración en Vivo
1. **Paso 1:** Abrir Streamlit, cargar `events.jsonl` del kit y pulsar **Evaluar todos los casos**.
2. **Paso 2:** Mostrar la tabla general y abrir el detalle de **P03** o **P04**: resaltar la **alerta roja de contacto bloqueado** visible en la parte superior sin necesidad de scroll.
3. **Paso 3:** Mostrar el caso **P06**, destacando que inicialmente recomienda `wait` hasta las 14:00 por la regla de reposo de 24 horas (R4).
4. **Paso 4:** Cargar `updates.jsonl` y volver a pulsar **Evaluar**.
5. **Paso 5:** Volver a **P06** y mostrar la sección **"¿Qué cambió?"**, demostrando cómo la llegada del evento `P06-e3` reactivó el contacto y modificó la acción a `resolve_objection` en 24h.
6. **Paso 6:** Ir a la pestaña **Errores y exportar** para descargar el archivo oficial `recommendations.json`.
