"""
eliza_home.py
---------------
Rutas de la instalación y de la carpeta de DATOS.

Instalación (carpeta donde están Eliza.bat y Eliza.py):
    Eliza.bat, Eliza.py
    app/                el programa (este archivo vive aquí)
    .venv/
    datos/              carpeta de datos LOCAL
    eliza_local.json    qué carpeta de datos usar en este equipo
    eliza_error.log

Carpeta de datos (local o remota): config_json/, bitacora/, _acd_store/,
eliza_config.json.

PRIMER ARRANQUE: si no existe eliza_local.json, Eliza pregunta qué carpeta
de datos usar (remota/compartida o local) y lo guarda. Después ya no
pregunta; se cambia con /settings.

Si la carpeta remota configurada no está disponible al arrancar (red caída,
unidad no mapeada), Eliza avisa y trabaja con la carpeta local en esa
sesión, sin borrar la configuración guardada.
"""

import os
import sys
import json

NOMBRE_PUNTERO = "eliza_local.json"
NOMBRE_DATOS_LOCALES = "datos"
ARCHIVOS_BASE = ('vnc.json', 'apps.json', 'acd.json')


def ruta_instalacion():
    """Carpeta raíz de la instalación (la que contiene Eliza.bat y app/)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    carpeta_app = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(carpeta_app)


def carpeta_local():
    return os.path.join(ruta_instalacion(), NOMBRE_DATOS_LOCALES)


def _ruta_puntero():
    return os.path.join(ruta_instalacion(), NOMBRE_PUNTERO)


def _mismo_directorio(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def es_primer_arranque():
    return not os.path.exists(_ruta_puntero())


def leer_carpeta_externa():
    """Carpeta remota/externa guardada, o None si se usa la local."""
    try:
        with open(_ruta_puntero(), 'r', encoding='utf-8') as f:
            carpeta = (json.load(f).get('carpeta_eliza') or '').strip()
    except (OSError, json.JSONDecodeError, AttributeError):
        return None
    if not carpeta or _mismo_directorio(carpeta, carpeta_local()):
        return None
    return carpeta


def preparar_estructura(carpeta_eliza):
    """Crea config_json/ (con jsons vacíos si no existen) y bitacora/ dentro de carpeta_eliza."""
    ruta_config_json = os.path.join(carpeta_eliza, 'config_json')
    os.makedirs(ruta_config_json, exist_ok=True)
    os.makedirs(os.path.join(carpeta_eliza, 'bitacora'), exist_ok=True)
    for nombre in ARCHIVOS_BASE:
        ruta = os.path.join(ruta_config_json, nombre)
        if not os.path.exists(ruta):
            with open(ruta, 'w', encoding='utf-8') as f:
                json.dump([], f)


def establecer_carpeta(carpeta_externa):
    """
    Guarda la carpeta de datos a usar en este equipo.
    None (o la carpeta local) -> datos locales en <instalación>/datos.
    Lanza OSError si la carpeta no se puede preparar.
    """
    if not carpeta_externa or _mismo_directorio(carpeta_externa, carpeta_local()):
        carpeta, guardar = carpeta_local(), ""
    else:
        carpeta, guardar = carpeta_externa, carpeta_externa
    preparar_estructura(carpeta)
    # Se conservan las otras claves del archivo (p. ej. la huella de licencia).
    try:
        with open(_ruta_puntero(), 'r', encoding='utf-8') as f:
            datos = json.load(f)
        if not isinstance(datos, dict):
            datos = {}
    except (OSError, json.JSONDecodeError):
        datos = {}
    datos['carpeta_eliza'] = guardar
    with open(_ruta_puntero(), 'w', encoding='utf-8') as f:
        json.dump(datos, f, indent=4, ensure_ascii=False)
    return carpeta


def resolver_carpeta_eliza():
    """
    Devuelve (carpeta, aviso). 'aviso' es None o un texto para mostrar
    (p. ej. si la carpeta remota no estaba disponible).
    """
    externa = leer_carpeta_externa()
    aviso = None
    if externa:
        if os.path.isdir(externa):
            try:
                preparar_estructura(externa)
                return externa, None
            except OSError as e:
                aviso = f"No se pudo usar la carpeta de datos remota ({e})."
        else:
            aviso = f"La carpeta de datos remota no está disponible: {externa}"
        aviso += " Se usan los datos LOCALES en esta sesión (revisa /settings)."

    local = carpeta_local()
    preparar_estructura(local)
    return local, aviso
