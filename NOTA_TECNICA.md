# Nota Técnica: What Should Happen Next?
**Prototipo de Decisiones Comerciales Asistidas por IA y Reglas Deterministas**  
*Hackathon RoadToTech 2026 · ByeCode*

---

### 1. Flujo de Datos y Arquitectura
El sistema implementa una arquitectura desacoplada por capas:
1. **Ingesta y Validación (`src/ingest.py`):** Carga incremental de archivos JSONL (`events.jsonl`, `updates.jsonl`). Parsea fechas a UTC, valida la estructura y contrato de cada evento, deduplica por `event_id` y captura errores de formato en auditoría sin detener el procesamiento de casos sanos.
2. **Reconstrucción del Estado (`src/state.py`):** Agrupa eventos por `case_id`, ordenándolos cronológicamente por `occurred_at` y desempatando por orden de llegada. Reconstruye el estado consolidado (aperturas, mensajes, montos, restricciones activas y cierre terminal).
3. **Motor de Reglas Deterministas (`src/rules.py`):** Evalúa el estado contra la fecha oficial del manifest (`now` en UTC) para definir el conjunto de acciones permitidas y bloqueos activos (R1–R4).
4. **Interpretación Semántica con IA (`src/interpreter.py` / `src/llm.py`):** Si está habilitada, Gemini analiza el contexto cronológico y propone una recomendación estructurada.
5. **Capa de Validación y Fallback (`src/validator.py` / `src/baseline.py`):** Valida la recomendación contra el contrato de 11 campos y las reglas activas. Si la IA viola una restricción o falla la conexión, conmuta automáticamente a la decisión base determinista.
6. **Historial y Versionado (`src/history.py`):** Detecta cambios al reevaluar con nuevos eventos, conserva versiones previas y exporta el JSON oficial de decisiones.
7. **Especialización Dev Shop y Bucle Cerrado (`src/devshop.py`):** Modela el ciclo comercial para consultoras de software ($150k MXN), extrayendo temperatura del lead, tipo de objeción técnica y permitiendo al ejecutivo registrar el resultado de su intervención para cerrar el bucle y detonar la siguiente decisión.

---

### 2. IA Utilizada y Seguridad (Prompt Injection)
- **Modelo:** Google Gemini API vía el SDK oficial `google-genai` (`gemini-2.5-flash` / `gemini-3.8-flash`) con `temperature=0.0` para garantizar reproducibilidad.
- **Rol:** La IA actúa estrictamente como **analista semántico**: extrae la intención del cliente, identifica hechos observados, deduce inferencias y detecta lagunas de información. **La IA nunca dicta ni altera reglas de negocio**.
- **Protección contra Inyección:** Los mensajes entrantes se aíslan entre etiquetas `<mensaje_cliente>` y el prompt del sistema instruye explícitamente al modelo a tratarlos como datos pasivos y no instrucciones ejecutables. Cualquier intento de evasión de reglas es interceptado y neutralizado por el validador determinista.

---

### 3. Contexto, Hechos, Inferencias e Información Faltante
En cada evaluación se inyecta el expediente cronológico completo del caso. La salida de la IA distingue de forma auditable:
- **Hechos observados (`hechos_observados`):** Afirmaciones objetivas asociadas obligatoriamente a un `event_id` existente (los IDs inventados o alucinados son purgados automáticamente).
- **Inferencias (`inferencias`):** Deducciones semánticas justificadas en eventos específicos y etiquetadas con su nivel de certeza (`low`, `medium`, `high`).
- **Información faltante (`informacion_faltante`):** Lagunas de contexto declaradas abiertamente (ej. falta de respuesta del cliente, dudas técnicas por confirmar internamente).

---

### 4. Reglas Deterministas e Inacción (R1 a R6)
- **R1 (Caso cerrado):** Acción única `no_action` con timing `not_applicable`. El cierre es definitivo.
- **R2 (`contact_allowed=false`):** Prohíbe contacto externo (`contact`, `request_information`, `resolve_objection`). Si el cliente escribió, recomienda `escalate` (revisión humana); si no, `wait`.
- **R3 (Antes de `contact_not_before`):** Prohíbe contacto hasta la fecha indicada; recomienda `wait` con `timing=at_date` y `scheduled_for` en UTC.
- **R4 (Ventana de 24h tras contacto):** Bloquea nuevos contactos durante 24h posteriores a `action.executed`, a menos que llegue un `message.received` posterior que libere el bloqueo.
- **R5 (Aperturas y no asunción de compra):** Las aperturas de propuesta (`proposal.viewed`) no justifican urgencia inmediata (`immediate`), descuentos ni presunción de intención de compra. Se recomienda `wait` con `on_new_information`.
- **R6 (Prevalencia de restricciones y datos reales):** Si falta información esencial, se reconoce explícitamente en `missing_information`. La restricción de contacto prevalece siempre sobre la conveniencia comercial.

---

### 5. Criterios de Confianza, Riesgo e Incertidumbre
- **Confianza:** `High` (caso cerrado o evidencia explícita sin faltantes), `Medium` (mensaje claro pero con datos internos faltantes), `Low` (solo aperturas o mensajes ambiguos).
- **Riesgo:** `High` (rechazo explícito del cliente o inconsistencias), `Medium` (escalamiento a responsable humano o mensaje con contacto bloqueado), `Low` (espera o seguimiento seguro permitido).
- **Incertidumbre y Limitaciones:** El modelo opera en lenguaje natural sin calibración estadística probabilística formal. No se ejecutan acciones automáticas reales (correo/WhatsApp). Ante interrupciones de conectividad o respuestas no conformes, el validador conmuta de forma transparente al motor de respaldo determinista, garantizando 0% de violaciones normativas.
