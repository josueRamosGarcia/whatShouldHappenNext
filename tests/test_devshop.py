"""Pruebas unitarias para el modulo src/devshop.py (Nicho Dev Shop y Feedback Loop)."""

from datetime import datetime, timezone, timedelta
from src.ingest import Store, cargar_eventos
from src.state import construir_estado
from src.rules import evaluar_reglas
from src.devshop import analizar_oportunidad, registrar_intervencion_comercial


def test_analizar_oportunidad_caso_p01():
    store = Store()
    cargar_eventos(open('data/events.jsonl', encoding='utf-8').read(), store)
    estado = construir_estado(store.casos['P01'])
    now = datetime(2026, 10, 9, 16, 0, tzinfo=timezone.utc)

    op = analizar_oportunidad(estado, None, now)
    assert "Instalación" in op['etapa'] or "Alcance Técnico" in op['etapa']
    assert "Técnica" in op['tipo_objecion']
    assert "150,000" in op['monto_formateado']


def test_bucle_retroalimentacion_no_contesto_activa_r4():
    store = Store()
    cargar_eventos(open('data/events.jsonl', encoding='utf-8').read(), store)
    now = datetime(2026, 10, 9, 16, 0, tzinfo=timezone.utc)

    # En P01 no habia bloqueos inicialmente
    estado_antes = construir_estado(store.casos['P01'])
    reglas_antes = evaluar_reglas(estado_antes, now)
    assert 'R4' not in reglas_antes['bloqueos']

    # Simulamos que el vendedor intento contactar pero el cliente no contesto
    nuevos = registrar_intervencion_comercial(
        store, 'P01', accion_ejecutada='contact', tipo_resultado='no_contesto', now=now
    )
    assert len(nuevos) == 1
    assert nuevos[0]['event_type'] == 'action.executed'

    # Ahora el estado debe tener ultimo_contacto y R4 debe activarse (24h de reposo)
    estado_despues = construir_estado(store.casos['P01'])
    reglas_despues = evaluar_reglas(estado_despues, now + timedelta(hours=1))
    assert 'R4' in reglas_despues['bloqueos']


def test_bucle_retroalimentacion_cliente_responde_libera_r4():
    store = Store()
    cargar_eventos(open('data/events.jsonl', encoding='utf-8').read(), store)
    now = datetime(2026, 10, 9, 16, 0, tzinfo=timezone.utc)

    # Vendedor contacta y cliente responde con pregunta de entrega
    nuevos = registrar_intervencion_comercial(
        store, 'P01', accion_ejecutada='resolve_objection',
        tipo_resultado='respuesta_duda',
        texto_cliente="Aclarada la duda. ¿Cuándo inician los sprints?",
        now=now
    )
    assert len(nuevos) == 2
    assert nuevos[0]['event_type'] == 'action.executed'
    assert nuevos[1]['event_type'] == 'message.received'

    # Como el cliente respondio despues de la llamada, R4 NO debe bloquear
    estado_despues = construir_estado(store.casos['P01'])
    reglas_despues = evaluar_reglas(estado_despues, now + timedelta(hours=1))
    assert 'R4' not in reglas_despues['bloqueos']


def test_bucle_con_detalles_conversacion():
    from src.interpreter import formatear_eventos
    store = Store()
    cargar_eventos(open('data/events.jsonl', encoding='utf-8').read(), store)
    now = datetime(2026, 10, 9, 16, 0, tzinfo=timezone.utc)

    nuevos = registrar_intervencion_comercial(
        store, 'P01',
        accion_ejecutada='resolve_objection',
        tipo_resultado='respuesta_duda',
        detalles_accion="Se le aclaró que la instalación incluye configuración en AWS y testing",
        texto_cliente="Entendido. ¿Cuándo inician?",
        now=now
    )
    ev_accion = nuevos[0]
    assert 'detalles_conversacion' in ev_accion['data']
    assert "AWS" in ev_accion['data']['detalles_conversacion']

    # Verificar que formatear_eventos incluya lo que dijo el vendedor
    texto_prompt = formatear_eventos(store.casos['P01'])
    assert "<lo_que_dijo_el_vendedor>" in texto_prompt
    assert "configuración en AWS" in texto_prompt
