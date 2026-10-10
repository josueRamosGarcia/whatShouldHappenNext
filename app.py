"""Aplicacion Principal Streamlit (app.py).

Interfaz de usuario para el sistema de toma de decisiones y recomendaciones comerciales.
Construida segun la especificacion del Plan Persona B (Pasos 1 y 6).
Provee carga de eventos, evaluacion asistida por IA (Gemini) o por reglas base,
inspeccion detallada por caso, deteccion de que cambio entre versiones y exportacion oficial en JSON.
"""

import os
import json
import html
from datetime import timedelta
import streamlit as st

from src.ingest import Store, cargar_eventos, parse_fecha
from src.history import registrar, cambios, exportar_json
from src.state import construir_estado
from src.devshop import analizar_oportunidad, registrar_intervencion_comercial

# Importacion dinamica de pipeline con fallback seguro
try:
    from src.pipeline import cargar_manifest, evaluar_todo, evaluar_caso
except (ImportError, AttributeError):
    try:
        from pipeline import cargar_manifest, evaluar_todo, evaluar_caso
    except (ImportError, AttributeError):
        # Fallback provisional si Persona A aun no ha comiteado src/pipeline.py
        from src.state import construir_estado
        from src.rules import evaluar_reglas
        from src.recommender import recomendar

        def cargar_manifest(ruta='data/manifest.json'):
            if os.path.exists(ruta):
                with open(ruta, encoding='utf-8') as f:
                    return parse_fecha(json.load(f)['evaluation_at'])
            return parse_fecha('2026-10-09T16:00:00Z')

        def _fallback_baseline(case_id, estado, reglas, now):
            msgs = estado['mensajes']
            if estado['cerrado']:
                return {
                    'case_id': case_id, 'action': 'no_action', 'timing': 'not_applicable',
                    'scheduled_for': None, 'reason': f"Caso cerrado ({estado['cierre_status']}). R1: solo no_action.",
                    'evidence_event_ids': [estado['id_cierre']], 'confidence': 'high',
                    'confidence_reason': 'El cierre es definitivo y explicito.', 'risk_level': 'low',
                    'requires_human_review': False, 'missing_information': []
                }
            if reglas['bloqueos']:
                motivos = ', '.join(reglas['bloqueos'].values())
                ev = ([msgs[-1]['id']] if msgs else []) + [i for i in reglas['evidencia'] if i]
                ev = list(dict.fromkeys(ev)) or [estado['ultimo_id']]
                if reglas['desbloqueo']:
                    f_str = reglas['desbloqueo'].strftime('%Y-%m-%dT%H:%M:%SZ')
                    return {
                        'case_id': case_id, 'action': 'wait', 'timing': 'at_date', 'scheduled_for': f_str,
                        'reason': f"Contacto bloqueado ({motivos}). Reevaluar el {f_str}.",
                        'evidence_event_ids': ev, 'confidence': 'high',
                        'confidence_reason': 'La restriccion es explicita y verificable.', 'risk_level': 'low',
                        'requires_human_review': False, 'missing_information': []
                    }
                if msgs:
                    return {
                        'case_id': case_id, 'action': 'escalate', 'timing': 'within_24h', 'scheduled_for': None,
                        'reason': f"Contacto prohibido ({motivos}) pero el cliente escribio. Revision interna.",
                        'evidence_event_ids': ev, 'confidence': 'medium',
                        'confidence_reason': 'Restriccion explicita con mensaje del cliente.', 'risk_level': 'medium',
                        'requires_human_review': True, 'missing_information': ['Motivo de la prohibicion']
                    }
                return {
                    'case_id': case_id, 'action': 'wait', 'timing': 'on_new_information', 'scheduled_for': None,
                    'reason': f"Contacto prohibido ({motivos}). Reevaluar cuando se actualice la restriccion.",
                    'evidence_event_ids': ev, 'confidence': 'medium',
                    'confidence_reason': 'Restriccion explicita sin fecha fin.', 'risk_level': 'low',
                    'requires_human_review': False, 'missing_information': []
                }
            if msgs:
                ult = msgs[-1]
                if '?' in ult['texto'] or '¿' in ult['texto']:
                    return {
                        'case_id': case_id, 'action': 'resolve_objection', 'timing': 'within_24h', 'scheduled_for': None,
                        'reason': f"El cliente hizo una pregunta ({ult['id']}) y no hay bloqueos.",
                        'evidence_event_ids': [ult['id']], 'confidence': 'medium',
                        'confidence_reason': 'Pregunta explicita; falta validar internamente.', 'risk_level': 'low',
                        'requires_human_review': False, 'missing_information': ['Dato para responder pregunta']
                    }
                return {
                    'case_id': case_id, 'action': 'contact', 'timing': 'within_24h', 'scheduled_for': None,
                    'reason': f"El cliente escribio ({ult['id']}) y el contacto esta permitido.",
                    'evidence_event_ids': [ult['id']], 'confidence': 'medium',
                    'confidence_reason': 'Hay mensaje pero intencion no confirmada.', 'risk_level': 'low',
                    'requires_human_review': False, 'missing_information': ['Intencion de compra']
                }
            ev = [estado['aperturas'][-1]['id']] if estado['aperturas'] else [estado['ultimo_id']]
            return {
                'case_id': case_id, 'action': 'wait', 'timing': 'on_new_information', 'scheduled_for': None,
                'reason': 'Solo hay aperturas o ninguna senal del cliente (R5). Reevaluar al recibir evento.',
                'evidence_event_ids': ev, 'confidence': 'low',
                'confidence_reason': 'Aperturas no demuestran intencion de compra.', 'risk_level': 'low',
                'requires_human_review': False, 'missing_information': ['Respuesta del cliente']
            }

        def evaluar_caso(case_id, store, now, usar_ia=True):
            eventos = store.casos[case_id]
            estado = construir_estado(eventos)
            reglas = evaluar_reglas(estado, now)
            rec, interp, origen = None, None, 'reglas'
            if usar_ia:
                try:
                    salida = recomendar(case_id, eventos, estado, reglas, now)
                    if salida:
                        rec, interp = salida
                        origen = 'ia'
                except Exception as ex:
                    store.errores.append({'linea': None, 'error': f'IA fallo en {case_id}: {ex}', 'texto': ''})
            if rec is None:
                rec = _fallback_baseline(case_id, estado, reglas, now)
            meta = {
                'origen': origen,
                'correcciones': [],
                'bloqueos': reglas['bloqueos'],
                'ids_evento': sorted(estado['ids']),
                'interpretacion': interp
            }
            return rec, meta

        def evaluar_todo(store, now, usar_ia=True, casos=None):
            ids = casos or sorted(store.casos)
            return {c: evaluar_caso(c, store, now, usar_ia) for c in ids}


# Configuracion de pagina Streamlit
st.set_page_config(
    page_title='DevDeal Engine · Decisiones Comerciales',
    page_icon='🧭',
    layout='wide',
    initial_sidebar_state='expanded'
)

# Estilos CSS premium para experiencia visual superior
st.markdown("""
<style>
    /* Estilos globales limpios y modernos */
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(120deg, #1E88E5, #43A047);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .metric-badge {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-high { background-color: rgba(46, 125, 50, 0.15); color: #2E7D32; border: 1px solid #81C784; }
    .badge-medium { background-color: rgba(239, 108, 0, 0.15); color: #EF6C00; border: 1px solid #FFB74D; }
    .badge-low { background-color: rgba(66, 66, 66, 0.15); color: #616161; border: 1px solid #BDBDBD; }
    .badge-blocked { background-color: rgba(198, 40, 40, 0.15); color: #C62828; border: 1px solid #E57373; }
    .card {
        border-radius: 10px;
        padding: 1.2rem;
        background-color: var(--secondary-background-color);
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        margin-bottom: 1rem;
    }

    /* Mini tarjetas de la ficha comercial */
    .mini-metric {
        border-radius: 8px;
        padding: 0.45rem 0.7rem;
        background-color: var(--secondary-background-color);
        border-left: 3px solid #1E88E5;
    }
    .mini-metric .mm-label {
        font-size: 0.68rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        opacity: 0.65;
        margin: 0;
    }
    .mini-metric .mm-value {
        font-size: 0.95rem;
        font-weight: 600;
        line-height: 1.25;
        margin: 0;
        word-break: break-word;
    }

    /* Linea de tiempo de eventos */
    .ev-item {
        border-radius: 8px;
        padding: 0.5rem 0.75rem;
        margin-bottom: 0.5rem;
        background-color: var(--secondary-background-color);
        border-left: 3px solid #43A047;
        font-size: 0.85rem;
    }
    .ev-head { display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center; margin-bottom: 0.25rem; }
    .ev-id { font-weight: 700; }
    .ev-type {
        padding: 0.05rem 0.45rem; border-radius: 4px; font-size: 0.72rem; font-weight: 600;
        background-color: rgba(30, 136, 229, 0.15); color: #1E88E5;
    }
    .ev-date { font-size: 0.72rem; opacity: 0.6; }
    .ev-data { margin: 0; padding-left: 0; list-style: none; }
    .ev-data li { margin: 0.1rem 0; }
    .ev-data .k { opacity: 0.65; }

    /* Recomendacion vigente */
    .rec-card {
        border-radius: 10px;
        padding: 0.9rem 1rem;
        background-color: var(--secondary-background-color);
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        margin-bottom: 0.6rem;
    }
    .rec-action { font-size: 1.3rem; font-weight: 700; margin: 0 0 0.3rem 0; }
    .rec-pill {
        display: inline-block; padding: 0.15rem 0.55rem; border-radius: 999px;
        font-size: 0.75rem; font-weight: 600; margin: 0 0.3rem 0.3rem 0;
        background-color: rgba(30, 136, 229, 0.12); color: #1E88E5; border: 1px solid rgba(30, 136, 229, 0.35);
    }
    .rec-pill.high { background-color: rgba(46,125,50,0.15); color: #2E7D32; border-color: #81C784; }
    .rec-pill.medium { background-color: rgba(239,108,0,0.15); color: #EF6C00; border-color: #FFB74D; }
    .rec-pill.low { background-color: rgba(66,66,66,0.15); color: #757575; border-color: #BDBDBD; }
    .rec-pill.danger { background-color: rgba(198,40,40,0.15); color: #C62828; border-color: #E57373; }
    .rec-label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.04em; opacity: 0.6; margin: 0.5rem 0 0.1rem 0; }
    .rec-text { font-size: 0.88rem; margin: 0; }
</style>
""", unsafe_allow_html=True)

# Inicializacion de estado persistente en session_state
if 'store' not in st.session_state:
    st.session_state.store = Store()
    st.session_state.historial = {}
    st.session_state.now = cargar_manifest('data/manifest.json')
    st.session_state.resumen = None

store = st.session_state.store
hist = st.session_state.historial


def leer(ruta: str) -> str:
    """Lee el contenido de un archivo UTF-8."""
    with open(ruta, encoding='utf-8') as f:
        return f.read()


def _esc(valor) -> str:
    """Escapa texto para insertarlo de forma segura en HTML."""
    return html.escape(str(valor))


def _fmt_valor(valor) -> str:
    """Formatea un valor de evento de forma legible (visual)."""
    if isinstance(valor, (dict, list)):
        return json.dumps(valor, ensure_ascii=False)
    if valor is None or valor == '':
        return '-'
    return str(valor)


def mini_metric(col, etiqueta, valor):
    """Tarjeta compacta de metrica (reemplazo visual de st.metric)."""
    col.markdown(
        f"<div class='mini-metric'><p class='mm-label'>{_esc(etiqueta)}</p>"
        f"<p class='mm-value'>{_esc(valor)}</p></div>",
        unsafe_allow_html=True
    )


def render_evento(ev):
    """Muestra un evento como tarjeta de linea de tiempo."""
    fecha_str = ev['_dt'].strftime('%Y-%m-%d %H:%M UTC')
    data = ev.get('data', {}) or {}
    if isinstance(data, dict) and data:
        items = ''.join(
            f"<li><span class='k'>{_esc(k)}:</span> {_esc(_fmt_valor(v))}</li>"
            for k, v in data.items()
        )
    else:
        items = f"<li><span class='k'>{_esc(_fmt_valor(data))}</span></li>"
    st.markdown(
        f"<div class='ev-item'><div class='ev-head'>"
        f"<span class='ev-id'>{_esc(ev['event_id'])}</span>"
        f"<span class='ev-type'>{_esc(ev['event_type'])}</span>"
        f"<span class='ev-date'>{_esc(fecha_str)}</span></div>"
        f"<ul class='ev-data'>{items}</ul></div>",
        unsafe_allow_html=True
    )


def render_recomendacion(rec):
    """Muestra la recomendacion vigente en formato legible en lugar de JSON crudo."""
    conf = str(rec.get('confidence') or '')
    riesgo = str(rec.get('risk_level') or '')
    revision = bool(rec.get('requires_human_review'))
    pills = f"<span class='rec-pill'>⏱ {_esc(rec.get('timing') or '-')}</span>"
    if rec.get('scheduled_for'):
        pills += f"<span class='rec-pill'>📅 {_esc(rec.get('scheduled_for'))}</span>"
    pills += f"<span class='rec-pill {_esc(conf)}'>Confianza: {_esc(conf or '-')}</span>"
    pills += f"<span class='rec-pill {_esc(riesgo)}'>Riesgo: {_esc(riesgo or '-')}</span>"
    pills += (
        "<span class='rec-pill danger'>👤 Requiere revisión humana</span>"
        if revision else "<span class='rec-pill'>👤 Sin revisión humana</span>"
    )

    evid = rec.get('evidence_event_ids') or []
    evid_html = ' '.join(f"<span class='rec-pill'>{_esc(e)}</span>" for e in evid) or '-'
    faltantes = rec.get('missing_information') or []
    falt_html = (
        '<ul style="margin:0;padding-left:1.1rem;font-size:0.88rem;">'
        + ''.join(f'<li>{_esc(f)}</li>' for f in faltantes) + '</ul>'
    ) if faltantes else "<p class='rec-text'>Ninguna</p>"

    st.markdown(
        f"<div class='rec-card'>"
        f"<p class='rec-action'>{_esc(rec.get('action') or '-')}</p>"
        f"{pills}"
        f"<p class='rec-label'>Motivo</p><p class='rec-text'>{_esc(rec.get('reason') or '-')}</p>"
        f"<p class='rec-label'>Razón de la confianza</p><p class='rec-text'>{_esc(rec.get('confidence_reason') or '-')}</p>"
        f"<p class='rec-label'>Evidencia</p><div>{evid_html}</div>"
        f"<p class='rec-label'>Información faltante</p>{falt_html}"
        f"</div>",
        unsafe_allow_html=True
    )
    with st.expander("Ver JSON original"):
        st.json(rec)


# Barra lateral de navegacion y controles
with st.sidebar:
    st.markdown("<h2 style='margin-bottom:0;'>🧭 DevDeal Engine</h2>", unsafe_allow_html=True)
    st.caption("Gobernanza comercial para Dev Shops y Consultoras B2B")
    st.caption(f"⏱️ **Hora de evaluación:** `{st.session_state.now.strftime('%Y-%m-%dT%H:%M:%SZ')}`")
    st.divider()

    st.subheader('1. Cargar eventos')
    archivo = st.file_uploader('Subir archivo .jsonl', type=['jsonl', 'json', 'txt'], key='uploader')

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button('📥 events.jsonl', use_container_width=True, help='Cargar casos base P01 a P06'):
            if os.path.exists('data/events.jsonl'):
                st.session_state.resumen = cargar_eventos(leer('data/events.jsonl'), store)
                st.rerun()
            else:
                st.error("No se encontró data/events.jsonl")

    with col_btn2:
        if st.button('🔄 updates.jsonl', use_container_width=True, help='Cargar actualización P06-e3'):
            if os.path.exists('data/updates.jsonl'):
                st.session_state.resumen = cargar_eventos(leer('data/updates.jsonl'), store)
                st.rerun()
            else:
                st.error("No se encontró data/updates.jsonl")

    if st.button('🧪 Cargar variantes.jsonl (7 pruebas)', use_container_width=True):
        if os.path.exists('data/variantes.jsonl'):
            st.session_state.resumen = cargar_eventos(leer('data/variantes.jsonl'), store)
            st.rerun()
        else:
            st.error("No se encontró data/variantes.jsonl")

    if st.button('Subir archivo procesado', use_container_width=True) and archivo is not None:
        contenido = archivo.read().decode('utf-8')
        st.session_state.resumen = cargar_eventos(contenido, store)
        st.rerun()

    if st.session_state.resumen:
        r = st.session_state.resumen
        st.success(f"✅ +{r['nuevos']} nuevos | ⚠️ {r['duplicados']} duplicados | 🛑 {r['errores']} errores")

    st.divider()
    st.subheader('2. Evaluar decisiones')
    usar_ia = st.checkbox('Usar IA (Gemini API)', value=True, help='Desmarcar para usar modo manual (reglas base sin IA)')

    if st.button('🚀 Evaluar todos los casos', type='primary', use_container_width=True):
        if not store.casos:
            st.warning('Primero carga eventos antes de evaluar.')
        else:
            with st.spinner('Evaluando casos con IA y verificando reglas...'):
                resultados = evaluar_todo(store, st.session_state.now, usar_ia=usar_ia)
                for cid, (rec, meta) in resultados.items():
                    registrar(hist, cid, rec, meta)
            st.success(f"Evaluados {len(resultados)} casos.")
            st.rerun()


# Pestañas principales de la aplicacion
tab1, tab2, tab3 = st.tabs(['📊 Casos', '🔍 Detalle del Caso', '📁 Errores y exportar'])

# TAB 1: Resumen de casos en tabla
with tab1:
    st.markdown("### Tabla Consolidada de Decisiones")
    filas = []
    for cid in sorted(hist):
        v = hist[cid][-1]
        r = v['rec']
        meta = v['meta']
        bloqueos_str = ', '.join(meta.get('bloqueos', {}).values()) if meta.get('bloqueos') else 'No'
        estado_cid = construir_estado(store.casos[cid]) if cid in store.casos else {}
        diag = analizar_oportunidad(estado_cid, meta.get('interpretacion'), st.session_state.now)

        filas.append({
            'Caso': cid,
            'Cotización': diag['monto_formateado'],
            'Etapa Comercial': diag['etapa'],
            'Temperatura': diag['temperatura'],
            'Acción Recomendada': r.get('action'),
            'Cuándo (Timing)': r.get('timing'),
            'Programado Para': r.get('scheduled_for') or '-',
            'Confianza': r.get('confidence'),
            'Riesgo': r.get('risk_level'),
            'Revisión Humana': 'Sí' if r.get('requires_human_review') else 'No',
            'Bloqueado': bloqueos_str,
            'Origen': meta.get('origen'),
            'Versiones': len(hist[cid])
        })

    if filas:
        st.dataframe(filas, use_container_width=True)
    else:
        st.info('👆 Carga los eventos desde la barra lateral izquierda y presiona **Evaluar todos los casos** para ver los resultados.')


# TAB 2: Detalle por caso, historial, recomendacion e impacto de cambios
with tab2:
    if hist:
        cid = st.selectbox('Selecciona un caso a inspeccionar:', sorted(hist))
        v = hist[cid][-1]
        r, meta = v['rec'], v['meta']

        # Ficha Comercial y Diagnóstico del Trato
        estado_cid = construir_estado(store.casos[cid]) if cid in store.casos else {}
        diag = analizar_oportunidad(estado_cid, meta.get('interpretacion'), st.session_state.now)

        st.markdown(f"#### 💼 Ficha Comercial: `{cid}` ({diag['monto_formateado']})")
        cm1, cm2, cm3, cm4 = st.columns(4)
        mini_metric(cm1, "Modelo Contratación", diag['modelo_sugerido'].split('(')[0].strip())
        mini_metric(cm2, "Etapa en Embudo", diag['etapa'])
        mini_metric(cm3, "Temperatura Lead", diag['temperatura'])
        mini_metric(cm4, "Foco de Consulta", diag['tipo_objecion'])
        st.divider()

        # Deteccion de bloqueos en la parte superior sin hacer scroll (vital para P03 y P04)
        if meta.get('bloqueos'):
            st.error(f"⛔ **Contacto bloqueado por reglas activas:** {', '.join(meta['bloqueos'].values())}")

        if meta.get('correcciones'):
            st.warning(f"⚠️ **El validador corrigió la propuesta de la IA:** {'; '.join(meta['correcciones'])}")

        col_izq, col_der = st.columns([1, 1])

        with col_izq:
            st.subheader('📜 Historial cronológico de eventos')
            if cid in store.casos:
                eventos_ordenados = sorted(store.casos[cid], key=lambda e: (e['_dt'], e['_orden']))
                with st.container(height=520, border=False):
                    for ev in eventos_ordenados:
                        render_evento(ev)
            else:
                st.write("No hay eventos registrados para este caso.")

        with col_der:
            st.subheader('🎯 Recomendación vigente')
            render_recomendacion(r)

            # Seccion Qué Cambió (muestra de valor clave para P06 tras updates.jsonl)
            ch = cambios(hist, cid)
            if ch:
                st.markdown("#### ⚡ ¿Qué cambió con el nuevo evento?")
                st.info(f"🆕 **Eventos nuevos recibidos:** {', '.join(ch['eventos_nuevos']) or 'Ninguno'}")
                for campo, antes, ahora in ch['campos']:
                    st.markdown(f"- **`{campo}`:** `{antes}` ➡️ **`{ahora}`**")

        # Interpretacion de la IA a todo el ancho, en 3 columnas para reducir scroll vertical
        interp = meta.get('interpretacion')
        if interp:
            st.markdown("#### 🧠 Interpretación de la IA")
            with st.expander("Ver hechos, inferencias y faltantes", expanded=True):
                ia1, ia2, ia3 = st.columns(3)
                with ia1:
                    st.write("**Hechos observados:**")
                    for h in interp.get('hechos_observados', []):
                        st.markdown(f"- {h.get('texto')} (`{h.get('event_id')}`)")

                with ia2:
                    st.write("**Inferencias:**")
                    for i in interp.get('inferencias', []):
                        st.markdown(f"- {i.get('texto')} *(Certeza: `{i.get('certeza')}`)*")

                with ia3:
                    st.write("**Información faltante:**")
                    faltantes = interp.get('informacion_faltante', [])
                    if faltantes:
                        for f in faltantes:
                            st.markdown(f"- {f}")
                    else:
                        st.markdown("- *Ninguna reportada*")

        # Seccion Interactiva: Bucle Cerrado de Seguimiento Comercial
        st.markdown("---")
        st.markdown("### 🔄 Bucle Cerrado: Registrar Intervención del Ejecutivo")
        st.caption("¿Se ejecutó la recomendación con el prospecto? Registra el resultado comercial para actualizar el expediente y disparar la siguiente recomendación en tiempo real.")

        with st.expander("⚡ Formulario de Seguimiento Comercial (Closed-Loop)", expanded=True):
            col_f1, col_f2 = st.columns([1, 1])
            with col_f1:
                acciones_cat = ['contact', 'resolve_objection', 'request_information', 'escalate']
                acc_idx = acciones_cat.index(r.get('action')) if r.get('action') in acciones_cat else 0
                accion_sel = st.selectbox(
                    "Acción ejecutada por el ejecutivo:",
                    acciones_cat,
                    index=acc_idx,
                    key=f"fb_acc_{cid}"
                )
                detalles_accion = st.text_area(
                    "💬 Contexto de la llamada/correo (lo que le comunicamos al cliente):",
                    placeholder="Ej: Se le aclaró que el alcance cubre despliegue en AWS, configuración de servidores y 1 mes de garantía post-lanzamiento...",
                    help="Este contexto se inyecta al expediente para que la IA sepa exactamente qué se aclaró y no repita la misma sugerencia.",
                    key=f"fb_det_{cid}",
                    height=85
                )
                res_sel = st.selectbox(
                    "Resultado o respuesta del prospecto:",
                    [
                        "📞 El cliente atendió y tiene una duda de cronograma/sprints",
                        "⏳ El cliente pidió pausar contacto hasta que sesione su comité",
                        "❌ No contestó / Llamada a buzón (activa reposo R4)",
                        "🎯 El cliente aceptó la propuesta y firmó contrato",
                        "✍️ Mensaje personalizado del cliente"
                    ],
                    key=f"fb_res_{cid}"
                )
            with col_f2:
                texto_cliente = ""
                fecha_bloqueo = None
                if "pausar contacto" in res_sel:
                    fecha_d = st.date_input(
                        "Fecha permitida para volver a contactar:",
                        value=st.session_state.now.date() + timedelta(days=5),
                        key=f"fb_date_{cid}"
                    )
                    fecha_bloqueo = fecha_d.strftime("%Y-%m-%dT15:00:00Z")
                    st.info(f"Se registrará restricción R3 hasta `{fecha_bloqueo}`.")
                elif "duda de cronograma" in res_sel:
                    texto_cliente = st.text_input(
                        "Pregunta del cliente:",
                        value="Recibido. ¿Cuál sería la fecha estimada de entrega del primer sprint?",
                        key=f"fb_txt_{cid}"
                    )
                elif "firmó contrato" in res_sel:
                    st.success("Se registrará el cierre formal del proyecto como ganado (case.closed: accepted).")
                elif "No contestó" in res_sel:
                    st.warning("Se registrará el intento de contacto (activando reposo de 24 horas por regla R4).")
                else:
                    texto_cliente = st.text_area(
                        "Mensaje o notas del cliente:",
                        placeholder="Escribe lo que respondió el cliente...",
                        key=f"fb_custom_{cid}"
                    )

            if st.button("⚡ Registrar Intervención y Reevaluar Caso", type="primary", use_container_width=True, key=f"btn_feed_{cid}"):
                if "duda de cronograma" in res_sel:
                    tipo_res = 'respuesta_duda'
                elif "pausar contacto" in res_sel:
                    tipo_res = 'pausa_comite'
                elif "firmó contrato" in res_sel:
                    tipo_res = 'cierre_exito'
                elif "No contestó" in res_sel:
                    tipo_res = 'no_contesto'
                else:
                    tipo_res = 'personalizado'

                nuevos_evs = registrar_intervencion_comercial(
                    store=store,
                    case_id=cid,
                    accion_ejecutada=accion_sel,
                    tipo_resultado=tipo_res,
                    detalles_accion=detalles_accion,
                    texto_cliente=texto_cliente,
                    fecha_desbloqueo_iso=fecha_bloqueo,
                    now=st.session_state.now
                )
                rec_nueva, meta_nueva = evaluar_caso(cid, store, st.session_state.now, usar_ia=usar_ia)
                registrar(hist, cid, rec_nueva, meta_nueva)
                st.toast(f"✅ Se registraron {len(nuevos_evs)} eventos y se reevaluó {cid}.", icon="🔄")
                st.rerun()
    else:
        st.info('Aún no hay casos evaluados. Carga eventos y pulsa Evaluar.')


# TAB 3: Errores de ingesta y exportacion JSON
with tab3:
    st.subheader('Auditoría de Ingesta')
    st.metric(label="Duplicados ignorados", value=store.duplicados)

    if store.errores:
        st.error(f"Se encontraron {len(store.errores)} línea(s) con error de formato:")
        st.dataframe(store.errores)
    else:
        st.success('✅ Cero errores de formato en los archivos procesados.')

    st.divider()
    st.subheader('Exportación de Recomendaciones Oficiales')

    if hist:
        salida_json = exportar_json(hist)
        col_exp1, col_exp2 = st.columns(2)

        with col_exp1:
            st.download_button(
                label='⬇️ Descargar recommendations.json',
                data=salida_json,
                file_name='recommendations.json',
                mime='application/json',
                use_container_width=True
            )

        with col_exp2:
            if st.button('💾 Guardar copia en outputs/recommendations.json', use_container_width=True):
                os.makedirs('outputs', exist_ok=True)
                with open('outputs/recommendations.json', 'w', encoding='utf-8') as f:
                    f.write(salida_json)
                st.success('Copia guardada con éxito en outputs/recommendations.json')
    else:
        st.info('Evalúa los casos para habilitar la descarga del archivo de respuestas.')
