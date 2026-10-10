"""Aplicacion Principal Streamlit (app.py).

Interfaz de usuario para el sistema de toma de decisiones y recomendaciones comerciales.
Construida segun la especificacion del Plan Persona B (Pasos 1 y 6).
Provee carga de eventos, evaluacion asistida por IA (Gemini) o por reglas base,
inspeccion detallada por caso, deteccion de que cambio entre versiones y exportacion oficial en JSON.
"""

import os
import json
import streamlit as st

from src.ingest import Store, cargar_eventos, parse_fecha
from src.history import registrar, cambios, exportar_json

# Importacion dinamica de pipeline con fallback seguro
try:
    from src.pipeline import cargar_manifest, evaluar_todo
except (ImportError, AttributeError):
    try:
        from pipeline import cargar_manifest, evaluar_todo
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
    page_title='Qué debe pasar después',
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


# Barra lateral de navegacion y controles
with st.sidebar:
    st.markdown("<h2 style='margin-bottom:0;'>🧭 Qué debe pasar después</h2>", unsafe_allow_html=True)
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

        filas.append({
            'Caso': cid,
            'Acción': r.get('action'),
            'Cuándo (Timing)': r.get('timing'),
            'Programado Para': r.get('scheduled_for') or '-',
            'Confianza': r.get('confidence'),
            'Riesgo': r.get('risk_level'),
            'Revisión Humana': 'Sí' if r.get('requires_human_review') else 'No',
            'Contacto Bloqueado': bloqueos_str,
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
                for ev in eventos_ordenados:
                    fecha_str = ev['_dt'].strftime('%Y-%m-%d %H:%M:%S UTC')
                    data_str = json.dumps(ev.get('data', {}), ensure_ascii=False)
                    st.markdown(f"- **`{ev['event_id']}`** `{fecha_str}` | `{ev['event_type']}`  \n  `{data_str}`")
            else:
                st.write("No hay eventos registrados para este caso.")

        with col_der:
            st.subheader('🎯 Recomendación vigente')
            st.json(r)

            interp = meta.get('interpretacion')
            if interp:
                st.markdown("#### 🧠 Interpretación de la IA")
                with st.expander("Ver hechos, inferencias y faltantes", expanded=True):
                    st.write("**Hechos observados:**")
                    for h in interp.get('hechos_observados', []):
                        st.markdown(f"- {h.get('texto')} (`{h.get('event_id')}`)")

                    st.write("**Inferencias:**")
                    for i in interp.get('inferencias', []):
                        st.markdown(f"- {i.get('texto')} *(Certeza: `{i.get('certeza')}`)*")

                    st.write("**Información faltante:**")
                    faltantes = interp.get('informacion_faltante', [])
                    if faltantes:
                        for f in faltantes:
                            st.markdown(f"- {f}")
                    else:
                        st.markdown("- *Ninguna reportada*")

            # Seccion Qué Cambió (muestra de valor clave para P06 tras updates.jsonl)
            ch = cambios(hist, cid)
            if ch:
                st.markdown("#### ⚡ ¿Qué cambió con el nuevo evento?")
                st.info(f"🆕 **Eventos nuevos recibidos:** {', '.join(ch['eventos_nuevos']) or 'Ninguno'}")
                for campo, antes, ahora in ch['campos']:
                    st.markdown(f"- **`{campo}`:** `{antes}` ➡️ **`{ahora}`**")
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
