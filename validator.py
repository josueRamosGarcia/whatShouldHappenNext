"""Módulo de Validación y Corrección de Recomendaciones (src/validator.py).

Este módulo actúa como la capa de control de calidad final del sistema.
Revisa las recomendaciones recibidas (procedentes de la IA o de la decisión base)
frente al contrato de datos y las reglas de negocio activas. Si detecta alguna
violación o inconsistencia grave, reemplaza la recomendación por la decisión
base segura y retorna la lista de problemas encontrados.
"""

from src.ingest import parse_fecha
from src.rules import CONTACTO
from src.baseline import recomendacion_base

# Catálogos de valores válidos según el contrato de datos
ACCIONES = {
    'contact', 'request_information', 'resolve_objection',
    'escalate', 'wait', 'no_action'
}
TIMINGS = {
    'immediate', 'within_24h', 'at_date', 'on_new_information',
    'not_applicable'
}
NIVELES = {'low', 'medium', 'high'}
CAMPOS_REC = [
    'case_id', 'action', 'timing', 'scheduled_for', 'reason',
    'evidence_event_ids', 'confidence', 'confidence_reason',
    'risk_level', 'requires_human_review', 'missing_information'
]
FRASES_R5 = [
    'listo para comprar', 'intencion de compra confirmada',
    'quiere comprar', 'va a comprar'
]


def validar_y_corregir(rec: dict, case_id: str, estado: dict, reglas: dict, now) -> tuple[dict, list[str]]:
    """Valida una recomendación contra las reglas de negocio y el contrato de datos.

    Si se encuentran inconsistencias o violaciones de reglas, la recomendación se reemplaza
    por la decisión base determinista generada por `recomendacion_base`. Si no hay violaciones
    graves, ajusta banderas obligatorias (ej. `requires_human_review` para 'escalate') y
    retorna la recomendación aprobada junto con una lista vacía de problemas.

    Args:
        rec (dict): Diccionario con la recomendación a validar.
        case_id (str): Identificador esperado del caso.
        estado (dict): Estado del caso producido por `construir_estado`.
        reglas (dict): Resultado de la evaluación de reglas producido por `evaluar_reglas`.
        now (datetime): Fecha y hora de evaluación actual (UTC).

    Returns:
        tuple[dict, list[str]]:
            - dict: Recomendación válida (la original corregida/ajustada o la decisión base).
            - list[str]: Lista de cadenas describiendo los problemas encontrados (vacía si es válida).
    """
    p = []

    # 1. Verificar la presencia de todos los campos requeridos en el contrato
    faltan = [c for c in CAMPOS_REC if c not in rec]
    if faltan:
        p.append('faltan campos: ' + ', '.join(faltan))
    else:
        a, t, s = rec['action'], rec['timing'], rec['scheduled_for']

        # Validación del identificador del caso
        if rec['case_id'] != case_id:
            p.append('case_id no coincide')

        # Validación del catálogo y reglas de acciones
        if a not in ACCIONES:
            p.append('accion fuera del catalogo')
        elif a not in reglas['permitidas']:
            p.append(a + ' prohibida por ' + ', '.join(reglas['bloqueos']))

        # Validación del catálogo y coherencia de timing
        if t not in TIMINGS:
            p.append('timing invalido')
        elif a == 'no_action' and t != 'not_applicable':
            p.append('no_action requiere not_applicable')
        elif a == 'wait' and t not in ('at_date', 'on_new_information'):
            p.append('wait requiere at_date u on_new_information')
        elif a in CONTACTO | {'escalate'} and t not in ('immediate', 'within_24h', 'at_date'):
            p.append('timing no valido para ' + a)

        # Validación del campo scheduled_for
        if t == 'at_date':
            try:
                f = parse_fecha(s)
                if f < now:
                    p.append('scheduled_for esta en el pasado')
                if a in CONTACTO and reglas['desbloqueo'] and f < reglas['desbloqueo']:
                    p.append('contacto programado antes del desbloqueo')
            except Exception:
                p.append('scheduled_for invalida')
        elif s is not None:
            p.append('scheduled_for debe ser null')

        # Validación de eventos de evidencia
        ev = rec['evidence_event_ids']
        if not isinstance(ev, list) or not ev or any(i not in estado['ids'] for i in ev):
            p.append('evidencia vacia o con event_id inexistente')

        # Validación de niveles de confianza y riesgo
        if rec['confidence'] not in NIVELES or rec['risk_level'] not in NIVELES:
            p.append('niveles invalidos')

        # Validación de tipos de datos para banderas booleanas y listas
        if not isinstance(rec['requires_human_review'], bool) or not isinstance(rec['missing_information'], list):
            p.append('tipos invalidos')

        # Regla R5: