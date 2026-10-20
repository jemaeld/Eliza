"""
settings_terminal.py
-----------------------
/settings: elegir la carpeta de DATOS de Eliza (config_json/, bitacora/,
_acd_store/, eliza_config.json).

- [P] Propia: la carpeta donde está Eliza (modo autocontenido, por defecto).
- [E] Externa: otra carpeta, por ejemplo una ruta de red compartida para
  que varios equipos vean la misma base de datos y bitácoras.

El cambio aplica de inmediato (eliza2.py recarga los comandos) y se recuerda
en los siguientes arranques.

Nota: antes /settings elegía una "carpeta destino ACD" que ya no se usaba
(los ACD se guardan en _acd_store/ dentro de la carpeta de datos). Esa
opción se retiró.
"""

import os
from tkinter import filedialog

import consola
import eliza_home


def abrir_settings_terminal(carpeta_actual, root):
    """Devuelve la NUEVA carpeta de datos si cambió, o None si no hubo cambios."""
    propia = eliza_home.ruta_ejecutable()
    externa = eliza_home.leer_carpeta_externa()

    consola.titulo("SETTINGS: carpeta de datos (ESC para salir)")
    consola.info(f"En uso ahora     : {carpeta_actual}")
    consola.info(f"Carpeta propia   : {propia}")
    consola.info(f"Externa guardada : {externa or '(ninguna)'}")
    print(f"{consola.COLOR_ENCABEZADO}[P] Usar carpeta propia   [E] Elegir carpeta externa{consola.COLOR_RESET}")

    try:
        opcion = consola.Cuestionario().preguntar("settings").lower()
    except (consola.Cancelado, KeyboardInterrupt, EOFError):
        opcion = ''

    if opcion == 'p':
        nueva = None
    elif opcion == 'e':
        nueva = filedialog.askdirectory(title="Carpeta de datos de Eliza (local o de red)", parent=root)
        if not nueva:
            consola.aviso("No se eligió ninguna carpeta. Sin cambios.")
            return None
        nueva = os.path.normpath(nueva)
    else:
        consola.info("Sin cambios.")
        return None

    try:
        carpeta = eliza_home.establecer_carpeta(nueva)
    except OSError as e:
        consola.aviso(f"No se pudo usar esa carpeta: {e}")
        return None

    consola.ok(f"Carpeta de datos: {carpeta}")
    return carpeta
