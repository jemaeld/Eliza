"""
config_manager.py
------------------
Configuración general de Eliza (fuera de config_json/, que está reservado a
las listas de comandos vnc.json, apps.json, acd.json).

eliza_config.json vive DENTRO de la carpeta de datos (ver eliza_home.py),
así que si esa carpeta es compartida, la configuración también.

Claves actuales:
- vnc_password: contraseña (ya cifrada, formato de archivo .vnc) que se
  escribe en el .vnc temporal al conectar. Antes estaba fija en el código.
- vnc_puerto:   puerto VNC por defecto.

Claves desconocidas o viejas (p. ej. 'carpeta_destino_acd') se conservan
tal cual y no afectan nada.
"""

import os
import json

import json_db

NOMBRE_ARCHIVO = "eliza_config.json"

VALORES_POR_DEFECTO = {
    "vnc_password": "002c648ab940042d",
    "vnc_puerto": 5900,
}


def _ruta_config(carpeta_eliza):
    return os.path.join(carpeta_eliza, NOMBRE_ARCHIVO)


def cargar_config(carpeta_eliza):
    """Lee eliza_config.json; completa las claves faltantes con los valores por defecto."""
    ruta = _ruta_config(carpeta_eliza)
    config = dict(VALORES_POR_DEFECTO)
    datos = {}
    if os.path.exists(ruta):
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                datos = json.load(f)
        except (json.JSONDecodeError, OSError):
            return config  # no se sobrescribe un archivo ilegible
        if isinstance(datos, dict):
            config.update(datos)

    if any(clave not in datos for clave in VALORES_POR_DEFECTO):
        try:
            guardar_config(carpeta_eliza, config)
        except OSError:
            pass
    return config


def guardar_config(carpeta_eliza, config):
    json_db.escribir_json(_ruta_config(carpeta_eliza), config)
