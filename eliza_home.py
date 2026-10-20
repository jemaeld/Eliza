"""
eliza_home.py
---------------
Resuelve dónde vive la "Carpeta Eliza": la carpeta raíz de datos que contiene
config_json/ (vnc.json, apps.json, acd.json), bitacora/, _acd_store/ y
eliza_config.json.

POR DEFECTO ES LA PROPIA CARPETA DE ELIZA (donde está eliza2.py o el .exe).
Así Eliza es autocontenida: copias la carpeta completa a otro lado (USB,
otro equipo, otra ruta) y funciona sin depender de ningún otro folder.

Opcionalmente, con /settings, se puede apuntar a una carpeta de datos
EXTERNA (por ejemplo una ruta de red compartida entre varios equipos). Esa
elección se guarda en 'eliza_local.json' junto al script/.exe. Si ese
archivo no existe, se usa la carpeta propia.

Si la carpeta externa configurada no está disponible al arrancar (red caída,
unidad no mapeada), Eliza NO se detiene ni pregunta: avisa y trabaja con su
carpeta propia durante esa sesión, sin borrar la configuración guardada.
"""

import os
import sys
import json

NOMBRE_PUNTERO = "eliza_local.json"
ARCHIVOS_BASE = ('vnc.json', 'apps.json', 'acd.json')


def ruta_ejecutable():
    """Carpeta donde vive el .exe compilado, o el .py si corre sin compilar."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _ruta_puntero():
    return os.path.join(ruta_ejecutable(), NOMBRE_PUNTERO)


def _mismo_directorio(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def leer_carpeta_externa():
    """Devuelve la carpeta externa guardada en el puntero, o None si no hay (o si apunta a la propia)."""
    ruta = _ruta_puntero()
    if not os.path.exists(ruta):
        return None
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            carpeta = (json.load(f).get('carpeta_eliza') or '').strip()
    except (json.JSONDecodeError, OSError, AttributeError):
        return None
    if not carpeta or _mismo_directorio(carpeta, ruta_ejecutable()):
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
    Guarda la carpeta de datos a usar en los próximos arranques.
    None (o la propia carpeta de Eliza) -> borra el puntero y vuelve al modo autocontenido.
    Lanza OSError si la carpeta no se puede preparar.
    """
    ruta_puntero = _ruta_puntero()
    if not carpeta_externa or _mismo_directorio(carpeta_externa, ruta_ejecutable()):
        if os.path.exists(ruta_puntero):
            os.remove(ruta_puntero)
        preparar_estructura(ruta_ejecutable())
        return ruta_ejecutable()

    preparar_estructura(carpeta_externa)
    with open(ruta_puntero, 'w', encoding='utf-8') as f:
        json.dump({'carpeta_eliza': carpeta_externa}, f, indent=4, ensure_ascii=False)
    return carpeta_externa


def resolver_carpeta_eliza():
    """
    Punto de entrada: devuelve (carpeta, aviso). 'aviso' es None o un texto
    para mostrar al usuario (p. ej. si la carpeta externa no estaba disponible).
    """
    externa = leer_carpeta_externa()
    if externa:
        if os.path.isdir(externa):
            try:
                preparar_estructura(externa)
                return externa, None
            except OSError as e:
                aviso = f"No se pudo usar la carpeta de datos externa ({e})."
        else:
            aviso = f"La carpeta de datos externa no está disponible: {externa}"
        aviso += " Se usa la carpeta propia de Eliza en esta sesión (revisa /settings)."
    else:
        aviso = None

    propia = ruta_ejecutable()
    preparar_estructura(propia)
    return propia, aviso
