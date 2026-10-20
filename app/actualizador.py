"""
actualizador.py
-----------------
Puente entre Eliza y el instalador Eliza.py (que vive en la raíz de la
instalación, junto a Eliza.bat). Toda la lógica de descarga está en
Eliza.py para tener UNA sola implementación, usada tanto por Eliza.bat
(instalación inicial) como por /update.

Código de salida 10: Eliza termina con ese código después de actualizarse
y Eliza.bat lo interpreta como "volver a arrancar" (revisa dependencias
nuevas y relanza la versión recién instalada).
"""

import importlib.util
import json
import os

import consola
import eliza_home

CODIGO_REINICIAR = 10


def _cargar_instalador():
    ruta = os.path.join(eliza_home.ruta_instalacion(), "Eliza.py")
    if not os.path.isfile(ruta):
        raise FileNotFoundError(f"No se encontró el instalador: {ruta}")
    spec = importlib.util.spec_from_file_location("eliza_instalador", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def version_actual():
    """Texto corto de la versión instalada (commit), o 'dev' si no hay VERSION.json."""
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION.json")
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        return f"{datos.get('commit', '')[:7]} ({(datos.get('fecha') or '')[:10]})"
    except (OSError, json.JSONDecodeError):
        return "dev"


def ejecutar_update():
    """
    Flujo de /update. Devuelve True si se instaló una versión nueva (hay que
    reiniciar Eliza), False en cualquier otro caso.
    """
    consola.titulo("UPDATE")
    try:
        instalador = _cargar_instalador()
    except Exception as e:
        consola.aviso(f"No se pudo cargar Eliza.py: {e}")
        return False

    if os.path.isdir(os.path.join(eliza_home.ruta_instalacion(), ".git")):
        consola.aviso("Esta copia es el repositorio de desarrollo: actualiza con 'git pull'.")
        return False

    consola.info("Consultando GitHub...")
    try:
        instalada, disponible, hay_nueva = instalador.hay_actualizacion()
    except instalador.ErrorActualizacion as e:
        consola.aviso(str(e))
        return False

    consola.info(f"Instalada : {instalador.describir(instalada)}")
    consola.info(f"Disponible: {instalador.describir(disponible)}")
    if not hay_nueva:
        consola.ok("Ya tienes la última versión.")
        return False

    try:
        respuesta = consola.Cuestionario().preguntar("¿Instalar la nueva versión? (s/n)", "s").lower()
    except consola.Cancelado:
        respuesta = 'n'
    if respuesta not in ('s', 'si', 'sí', 'y'):
        consola.info("Actualización cancelada.")
        return False

    try:
        instalador.instalar(disponible)
    except instalador.ErrorActualizacion as e:
        consola.aviso(f"No se actualizó: {e}")
        return False
    except OSError as e:
        consola.aviso(f"No se actualizó (error de archivos): {e}")
        return False

    consola.ok("Actualización instalada. Eliza se va a reiniciar...")
    return True
