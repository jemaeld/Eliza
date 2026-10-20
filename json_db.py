"""
json_db.py
-----------
Lectura/escritura de los archivos JSON de Eliza (config_json/, bitacora/,
eliza_config.json).

Dos protecciones importantes, pensadas para una carpeta de datos que puede
ser de red y compartida entre varios equipos:

1. Escritura atómica: se escribe a un archivo temporal y luego se reemplaza
   el original (os.replace). Si el equipo se apaga o se cae la red a medio
   guardar, el archivo original queda intacto en vez de quedar truncado.

2. No se pisa un archivo dañado: agregar_entrada() usa lectura ESTRICTA. Si
   el JSON existente no se puede leer, lanza JsonCorrupto en vez de tratarlo
   como lista vacía (antes eso borraba todo el contenido al agregar un solo
   registro).
"""

import os
import json


class JsonCorrupto(Exception):
    """El archivo existe pero no es una lista JSON válida."""


def cargar_lista(ruta_json, estricto=False):
    """
    Devuelve la lista guardada en ruta_json ([] si no existe).
    estricto=False: si está dañado, devuelve [] (útil solo para mostrar).
    estricto=True:  si está dañado, lanza JsonCorrupto (usar antes de escribir).
    """
    if not os.path.exists(ruta_json):
        return []
    try:
        with open(ruta_json, 'r', encoding='utf-8-sig') as f:
            datos = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        if estricto:
            raise JsonCorrupto(f"No se pudo leer {ruta_json}: {e}") from e
        return []
    if isinstance(datos, list):
        return datos
    if estricto:
        raise JsonCorrupto(f"{ruta_json} no contiene una lista.")
    return []


def escribir_json(ruta, datos):
    """Escritura atómica de cualquier dato JSON."""
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    temporal = ruta + ".tmp"
    with open(temporal, 'w', encoding='utf-8') as f:
        json.dump(datos, f, indent=4, ensure_ascii=False)
    os.replace(temporal, ruta)


def guardar_lista(ruta_json, datos):
    escribir_json(ruta_json, datos)


def agregar_entrada(ruta_json, entry):
    """Agrega 'entry' al final de la lista y guarda. Devuelve la lista actualizada."""
    datos = cargar_lista(ruta_json, estricto=True)
    datos.append(entry)
    guardar_lista(ruta_json, datos)
    return datos
