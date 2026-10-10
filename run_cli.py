"""Script de Consola para Pruebas Rápidas sin Interfaz (run_cli.py).

Este archivo ejecuta el flujo completo del sistema desde la línea de comandos.
Carga el manifest, ingesta `events.jsonl`, evalúa todos los casos en modo sin IA (base),
luego ingesta `updates.jsonl` y muestra la reevaluación del caso P06 en formato JSON.
"""

import json
from src.ingest import Store, cargar_eventos
from src.pipeline import cargar_manifest, evaluar_todo

if __name__ == '__main__':
    store = Store()
    now = cargar_manifest()

    # Carga inicial de eventos desde events.jsonl
    print(cargar_eventos(open('data/events.jsonl', encoding='utf-8').read(), store))

    # Evaluación inicial de los 6 casos (sin usar IA)
    for c, (rec, meta) in evaluar_todo(store, now, usar_ia=False).items():
        print(c, rec['action'], rec['timing'], rec['scheduled_for'], meta['origen'])

    # Carga de la actualización desde updates.jsonl
    print(cargar_eventos(open('data/updates.jsonl', encoding='utf-8').read(), store))

    # Reevaluación del caso P06 con los nuevos eventos
    rec, meta = evaluar_todo(store, now, usar_ia=False, casos=['P06'])['P06']
    print(json.dumps(rec, ensure_ascii=False, indent=2))