"""
licencia.py
-------------
Contraseña de acceso al arrancar Eliza ("licencia de usuario legítimo").

La contraseña es la misma que Eliza escribe en los .vnc al conectar
(eliza_config.json -> vnc_password, en la carpeta de datos). Al usuario solo
se le pide "Contraseña", sin decir para qué es.

- La guarda la carpeta de datos (si es remota, la comparten todos los equipos).
- Cada instalación guarda solo una HUELLA (sha256) en eliza_local.json. Así,
  después del primer arranque válido no se vuelve a pedir, y si la
  contraseña de la carpeta de datos cambia, se vuelve a pedir.
- Primer arranque de una instalación: se debe escribir la contraseña que
  ya tiene la carpeta de datos (3 intentos). Si la carpeta de datos todavía
  no tiene ninguna (instalación inicial de todo el sistema), la que se
  escriba (dos veces) queda como contraseña.
- Si no se escribe una contraseña válida, Eliza no arranca.

Limitación: el código es Python legible y la contraseña vive en
eliza_config.json, así que esto filtra el uso casual, no a alguien que
modifique el código o tenga acceso a la carpeta de datos.
"""

import hashlib
import json
import os

from prompt_toolkit import PromptSession

import config_manager
import consola
import eliza_home

CLAVE_CONFIG = 'vnc_password'
CLAVE_LOCAL = 'licencia'
INTENTOS = 3


def _huella(texto):
    return hashlib.sha256(("eliza:" + texto).encode('utf-8')).hexdigest()


def _ruta_local():
    return os.path.join(eliza_home.ruta_instalacion(), eliza_home.NOMBRE_PUNTERO)


def _leer_huella_local():
    try:
        with open(_ruta_local(), 'r', encoding='utf-8') as f:
            return json.load(f).get(CLAVE_LOCAL) or None
    except (OSError, json.JSONDecodeError, AttributeError):
        return None


def _guardar_huella_local(huella):
    """Agrega la huella a eliza_local.json sin tocar la carpeta de datos guardada ahí."""
    ruta = _ruta_local()
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        if not isinstance(datos, dict):
            datos = {}
    except (OSError, json.JSONDecodeError):
        datos = {}
    datos[CLAVE_LOCAL] = huella
    with open(ruta, 'w', encoding='utf-8') as f:
        json.dump(datos, f, indent=4, ensure_ascii=False)


def _pedir(sesion, mensaje):
    try:
        return sesion.prompt(mensaje, is_password=True).strip()
    except (KeyboardInterrupt, EOFError):
        return ''


def verificar(ctx):
    """
    Devuelve True si se puede arrancar. Pide la contraseña solo cuando hace
    falta. Si se define o se recupera, la deja en ctx.config.
    """
    guardada = (ctx.config.get(CLAVE_CONFIG) or '').strip()
    huella_local = _leer_huella_local()

    if guardada and huella_local == _huella(guardada):
        return True  # instalación ya validada con la contraseña vigente

    sesion = PromptSession(style=consola.ESTILO)
    consola.titulo("ELIZA: acceso")

    # Caso inicial de todo el sistema: nadie ha definido contraseña
    # todavía (ni en la carpeta de datos ni en esta instalación).
    if not guardada and not huella_local:
        consola.info("Define la contraseña de acceso.")
        primera = _pedir(sesion, "Contraseña: ")
        if primera and _pedir(sesion, "Confírmala: ") == primera:
            ctx.config = config_manager.actualizar_clave(ctx.base_dir, CLAVE_CONFIG, primera)
            _guardar_huella_local(_huella(primera))
            consola.ok("Contraseña registrada.")
            return True
        consola.aviso("No coinciden o quedó vacía. Eliza no puede arrancar.")
        return False

    for intento in range(1, INTENTOS + 1):
        valor = _pedir(sesion, "Contraseña: ")
        if not valor:
            break
        if guardada and valor == guardada:
            _guardar_huella_local(_huella(valor))
            return True
        if not guardada and huella_local == _huella(valor):
            # La carpeta de datos no tiene contraseña (p. ej. se está
            # usando la local porque la remota no está disponible), pero
            # esta instalación ya la conocía: se valida contra su huella
            # y se repone en la carpeta de datos.
            ctx.config = config_manager.actualizar_clave(ctx.base_dir, CLAVE_CONFIG, valor)
            return True
        if intento < INTENTOS:
            consola.aviso("Contraseña incorrecta.")

    consola.aviso("Acceso denegado. Eliza no puede arrancar.")
    return False
