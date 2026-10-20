"""
config_manager.py
------------------
Configuración general de Eliza (fuera de config_json/, que está reservado a
las listas de comandos vnc.json, apps.json, acd.json).

eliza_config.json vive DENTRO de la carpeta de datos (ver eliza_home.py),
así que si esa carpeta es compartida, la configuración también.

Claves:
- vnc_password: contraseña VNC en el formato cifrado de los archivos .vnc
                (el valor de 'password=' de cualquier .vnc). No está en el
                código para no publicarla en el repositorio: si falta, Eliza
                la pregunta la primera vez que se abre un VNC.
- vnc_puerto:   puerto VNC por defecto.

Claves desconocidas o viejas (p. ej. 'carpeta_destino_acd') se conservan
tal cual y no afectan nada.
"""

import os
import json

import json_db

NOMBRE_ARCHIVO = "eliza_config.json"

VALORES_POR_DEFECTO = {
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


def actualizar_clave(carpeta_eliza, clave, valor):
    """Relee, cambia una sola clave y guarda (para no pisar cambios de otro equipo)."""
    config = cargar_config(carpeta_eliza)
    config[clave] = valor
    guardar_config(carpeta_eliza, config)
    return config
