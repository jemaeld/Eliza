"""
logix_tools.py
-----------------
Lógica pura para el monitor/forzado de tags Allen-Bradley (Logix) vía
pylogix. Sin GUI ni threading -- eso vive en logix_window.py.

Incluye:
- convertir_valor(): texto del usuario -> tipo probable para el PLC.
- guardar_registro() / cargar_registro(): exportar/importar la lista de
  tags de la sesión a un archivo JSON.
"""

import json
from datetime import datetime

VERSION_REGISTRO = 1
POLLING_MIN_MS = 50
POLLING_DEFAULT_MS = 100


def convertir_valor(texto):
    """
    Intenta convertir el texto escrito por el usuario al tipo más probable
    que espera el PLC: bool, int, float, o texto tal cual si nada aplica.
    """
    texto = texto.strip()
    bajo = texto.lower()
    if bajo in ('true', 'false'):
        return bajo == 'true'
    try:
        return int(texto)
    except ValueError:
        pass
    try:
        return float(texto)
    except ValueError:
        pass
    return texto


# ---------------------------------------------------------
# Registro de tags (JSON)
#
# Formato:
# {
#   "version": 1,
#   "fecha": "2026-10-15T19:03:00",
#   "tags": [
#     {"ip": "192.168.1.10", "polling_ms": 100, "tag": "Motor1.Run", "comentario": "Arranque banda"},
#     ...
#   ]
# }
#
# Los valores de SOBRESCRIBIR (forzado) NO se guardan a propósito: cargar un
# registro nunca debe empezar a escribir sobre un PLC sin que el usuario lo
# confirme fila por fila.
# ---------------------------------------------------------

def _normalizar_fila(fila):
    """Limpia una fila leída/por escribir. Devuelve dict o None si no sirve."""
    if not isinstance(fila, dict):
        return None
    ip = str(fila.get('ip', '') or '').strip()
    tag = str(fila.get('tag', '') or '').strip()
    comentario = str(fila.get('comentario', '') or '').strip()
    try:
        polling = int(fila.get('polling_ms', POLLING_DEFAULT_MS))
    except (TypeError, ValueError):
        polling = POLLING_DEFAULT_MS
    polling = max(polling, POLLING_MIN_MS)
    if not ip and not tag and not comentario:
        return None  # fila vacía, no aporta nada
    return {'ip': ip, 'polling_ms': polling, 'tag': tag, 'comentario': comentario}


def guardar_registro(ruta, filas):
    """
    Escribe la lista de filas a 'ruta' en JSON. 'filas' es una lista de
    dicts con ip, polling_ms, tag, comentario. Devuelve cuántas se guardaron.
    """
    limpias = [f for f in (_normalizar_fila(f) for f in filas) if f is not None]
    datos = {
        'version': VERSION_REGISTRO,
        'fecha': datetime.now().isoformat(timespec='seconds'),
        'tags': limpias,
    }
    with open(ruta, 'w', encoding='utf-8') as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=2)
    return len(limpias)


def cargar_registro(ruta):
    """
    Lee un registro JSON y devuelve la lista de filas normalizadas.
    Acepta también una lista suelta de filas (sin el envoltorio con
    'version'/'tags'). Lanza ValueError si el archivo no tiene un formato
    reconocible.
    """
    with open(ruta, 'r', encoding='utf-8') as fh:
        datos = json.load(fh)

    if isinstance(datos, dict):
        crudas = datos.get('tags')
    elif isinstance(datos, list):
        crudas = datos
    else:
        crudas = None

    if not isinstance(crudas, list):
        raise ValueError("El archivo no contiene una lista de tags reconocible.")

    return [f for f in (_normalizar_fila(f) for f in crudas) if f is not None]
