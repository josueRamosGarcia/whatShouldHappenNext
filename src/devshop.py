"""Modulo de Contexto Dev Shop y Bucle de Retroalimentacion Comercial (src/devshop.py).

Este modulo especializa el motor para el nicho de Agencias / Consultoras de Desarrollo
de Software (Dev Shops). Extrae variables comerciales (etapa del trato, tipo de objecion,
temperatura del lead) y proporciona la logica para cerrar el bucle de recomendacion
mediante el registro de intervenciones y generacion de eventos conformes al contrato.
"""

from datetime import datetime, timezone, timedelta
from src.ingest import parse_fecha, fmt_fecha


def analizar_oportunidad(estado: dict, interp: dict | None, now: datetime) -> dict:
    """Extrae variables de negocio y diagnostico comercial para una agencia de software.

    Args:
        estado: Diccionario con el estado consolidado del caso (src/state.py).
        interp: Interpretacion semantica del modelo o None.
        now: Timestamp oficial de evaluacion en UTC.

    Returns:
        dict con variables comerciales:
            - etapa: Etapa en el embudo comercial del Dev Shop
            - temperatura: Nivel de calor del lead (Caliente, Tibio, Frio)
            - tipo_objecion: Categoria de duda detectada (Tecnica, Cronograma, Presupuesto)
            - modelo_sugerido: Modelo de cobro recomendado (Fixed Price, T&M, Dedicated)
            - dias_inactivo: Dias transcurridos desde el ultimo contacto o mensaje
    """
    monto = estado.get('monto') or 150000
    mensajes = estado.get('mensajes', [])
    aperturas = estado.get('aperturas', [])
    cerrado = estado.get('cerrado', False)
    cierre_status = estado.get('cierre_status')

    # 1. Etapa en el ciclo comercial de la consultora
    if cerrado:
        etapa = f"Contrato Cerrado ({cierre_status})" if cierre_status == 'accepted' else "Oportunidad Descartada"
    elif estado.get('contact_not_before') and estado['contact_not_before'] > now:
        etapa = "En Espera de Comité / Directorio"
    elif not estado.get('contact_allowed', True):
        etapa = "Restricción Contractual Activa"
    elif mensajes:
        ult_texto = mensajes[-1]['texto'].lower()
        if 'entrega' in ult_texto or 'fecha' in ult_texto or 'cuándo' in ult_texto or 'sprint' in ult_texto:
            etapa = "Negociación de Cronograma y Sprints"
        elif 'instalación' in ult_texto or 'soporte' in ult_texto or 'stack' in ult_texto or 'arquitectura' in ult_texto:
            etapa = "Aclaración de Alcance Técnico"
        else:
            etapa = "Seguimiento de Propuesta Técnica"
    elif aperturas:
        etapa = "Propuesta Técnica en Revisión"
    else:
        etapa = "Cotización Inicial Enviada"

    # 2. Tipo de Objeción o Consulta Técnica
    tipo_objecion = "Ninguna identificada"
    if mensajes:
        ult_msg = mensajes[-1]['texto'].lower()
        if any(w in ult_msg for w in ['instalación', 'despliegue', 'arquitectura', 'stack', 'servidor', 'cloud']):
            tipo_objecion = "Técnica (Alcance de despliegue e infraestructura)"
        elif any(w in ult_msg for w in ['fecha', 'entrega', 'tiempo', 'cuándo', 'plazo', 'sprint']):
            tipo_objecion = "Cronograma (Fechas de entrega e hitos)"
        elif any(w in ult_msg for w in ['precio', 'costo', 'descuento', 'presupuesto', 'tarifa', 'usd', 'mxn']):
            tipo_objecion = "Económica (Tarifa o términos de pago)"
        elif '?' in ult_msg or '¿' in ult_msg:
            tipo_objecion = "Consulta General sobre la propuesta"

    # 3. Temperatura del Trato (Lead Score cualitativo)
    if cerrado:
        temperatura = "🎯 Ganado" if cierre_status == 'accepted' else "⏹️ Concluido"
    elif mensajes and any(w in mensajes[-1]['texto'].lower() for w in ['interesa', 'entrega', 'cuándo', 'empezar']):
        temperatura = "🔥 Caliente (Alta intención de compra)"
    elif len(mensajes) > 0 or len(aperturas) >= 2:
        temperatura = "⚡ Activo / Tibio (Evaluación activa)"
    else:
        temperatura = "❄️ Frío (Esperando señales del cliente)"

    # 4. Modelo de Negocio del Dev Shop
    if monto >= 100000:
        modelo = "Proyecto Cerrado (Fixed Price llave en mano)"
    else:
        modelo = "Bolsa de Horas (Time & Materials ágil)"

    # 5. Cálculo de días de inactividad
    ultimo_evento_dt = None
    if estado.get('ultimo_mensaje'):
        ultimo_evento_dt = estado['ultimo_mensaje']
    elif estado.get('ultimo_contacto'):
        ultimo_evento_dt = estado['ultimo_contacto']
    elif aperturas:
        ultimo_evento_dt = aperturas[-1]['fecha']

    dias_inactivo = 0
    if ultimo_evento_dt:
        delta = now - ultimo_evento_dt
        dias_inactivo = max(0, delta.days)

    return {
        'etapa': etapa,
        'temperatura': temperatura,
        'tipo_objecion': tipo_objecion,
        'modelo_sugerido': modelo,
        'monto_formateado': f"${monto:,.2f} MXN",
        'dias_inactivo': dias_inactivo
    }


def registrar_intervencion_comercial(
    store,
    case_id: str,
    accion_ejecutada: str,
    tipo_resultado: str,
    detalles_accion: str = "",
    texto_cliente: str = "",
    fecha_desbloqueo_iso: str | None = None,
    now: datetime | None = None
) -> list[dict]:
    """Genera e inyecta eventos conformes al contrato en respuesta a una accion del vendedor.

    Permite cerrar el bucle: el vendedor ejecuta la recomendacion, registra que paso,
    y el sistema genera los eventos (action.executed, message.received, constraint.updated, etc.)
    que actualizan el estado del cliente y disparan la siguiente decision.

    Args:
        store: Instancia de Store de la aplicacion.
        case_id: Identificador del caso.
        accion_ejecutada: Accion realizada ('contact', 'resolve_objection', 'request_information').
        tipo_resultado: Codigo de resultado ('respuesta_duda', 'no_contesto', 'pausa_comite', 'cierre_exito', 'personalizado').
        detalles_accion: Lo que el ejecutivo converso o explico al cliente (enriquece el contexto).
        texto_cliente: Texto recibido del cliente o nota de respuesta.
        fecha_desbloqueo_iso: Cadena ISO-8601 si el cliente pidio no ser contactado hasta tal fecha.
        now: Timestamp actual (por defecto datetime actual en UTC).

    Returns:
        list[dict]: Lista de los nuevos eventos agregados al expediente.
    """
    ts = now or datetime.now(timezone.utc)
    ts_str = fmt_fecha(ts)
    nuevos_eventos = []

    # Contador para generar event_id unicos
    conteo_previo = len(store.casos.get(case_id, [])) + 1

    # 1. Registrar siempre el contacto ejecutado por el vendedor (action.executed)
    action_contrato = 'request_information' if accion_ejecutada == 'request_information' else 'contact'
    data_accion = {'action': action_contrato}
    if detalles_accion and detalles_accion.strip():
        data_accion['detalles_conversacion'] = detalles_accion.strip()
        data_accion['notas_vendedor'] = f"Intervención {accion_ejecutada}: {detalles_accion.strip()}"
    else:
        data_accion['notas_vendedor'] = f"Intervención: {accion_ejecutada}"

    ev_accion = {
        'event_id': f"{case_id}-act{conteo_previo}",
        'case_id': case_id,
        'event_type': 'action.executed',
        'occurred_at': ts_str,
        'data': data_accion,
        '_dt': ts,
        '_orden': store.contador + 1
    }
    store.vistos.add(ev_accion['event_id'])
    store.contador += 1
    store.casos.setdefault(case_id, []).append(ev_accion)
    nuevos_eventos.append(ev_accion)

    # 2. Manejar la respuesta del cliente según el tipo de resultado
    if tipo_resultado == 'respuesta_duda':
        # El cliente responde con nueva información o pregunta posterior
        ts_msg = ts + timedelta(minutes=5)
        ev_msg = {
            'event_id': f"{case_id}-msg{conteo_previo + 1}",
            'case_id': case_id,
            'event_type': 'message.received',
            'occurred_at': fmt_fecha(ts_msg),
            'data': {'message': texto_cliente or "Recibido. ¿Cuál sería la fecha estimada de entrega del primer sprint?"},
            '_dt': ts_msg,
            '_orden': store.contador + 1
        }
        store.vistos.add(ev_msg['event_id'])
        store.contador += 1
        store.casos[case_id].append(ev_msg)
        nuevos_eventos.append(ev_msg)

    elif tipo_resultado == 'pausa_comite':
        # El cliente pide pausar el contacto hasta sesión de comité
        ts_constraint = ts + timedelta(minutes=2)
        target_date = fecha_desbloqueo_iso or fmt_fecha(ts + timedelta(days=5))
        ev_constraint = {
            'event_id': f"{case_id}-req{conteo_previo + 1}",
            'case_id': case_id,
            'event_type': 'constraint.updated',
            'occurred_at': fmt_fecha(ts_constraint),
            'data': {'contact_not_before': target_date},
            '_dt': ts_constraint,
            '_orden': store.contador + 1
        }
        store.vistos.add(ev_constraint['event_id'])
        store.contador += 1
        store.casos[case_id].append(ev_constraint)
        nuevos_eventos.append(ev_constraint)

    elif tipo_resultado == 'cierre_exito':
        # El cliente acepta la propuesta y se cierra el contrato
        ts_close = ts + timedelta(minutes=10)
        ev_close = {
            'event_id': f"{case_id}-cls{conteo_previo + 1}",
            'case_id': case_id,
            'event_type': 'case.closed',
            'occurred_at': fmt_fecha(ts_close),
            'data': {'status': 'accepted'},
            '_dt': ts_close,
            '_orden': store.contador + 1
        }
        store.vistos.add(ev_close['event_id'])
        store.contador += 1
        store.casos[case_id].append(ev_close)
        nuevos_eventos.append(ev_close)

    elif tipo_resultado == 'personalizado' and texto_cliente.strip():
        # Mensaje personalizado del cliente
        ts_msg = ts + timedelta(minutes=5)
        ev_msg = {
            'event_id': f"{case_id}-msg{conteo_previo + 1}",
            'case_id': case_id,
            'event_type': 'message.received',
            'occurred_at': fmt_fecha(ts_msg),
            'data': {'message': texto_cliente.strip()},
            '_dt': ts_msg,
            '_orden': store.contador + 1
        }
        store.vistos.add(ev_msg['event_id'])
        store.contador += 1
        store.casos[case_id].append(ev_msg)
        nuevos_eventos.append(ev_msg)

    # Si fue 'no_contesto', solo se generó 'action.executed' (activando la regla R4 de reposo)

    return nuevos_eventos
