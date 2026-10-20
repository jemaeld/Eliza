"""
settings_terminal.py
-----------------------
Elegir la carpeta de DATOS de Eliza (config_json/, bitacora/, _acd_store/,
eliza_config.json):

- [R] Remota: una carpeta compartida (p. ej. una unidad o ruta de red) para
  que varios equipos vean la misma base de datos y bitácoras.
- [L] Local:  <instalación>/datos, solo para este equipo.

Se usa en el primer arranque (primer_arranque) y con /settings
(abrir_settings_terminal). La elección se guarda en eliza_local.json.
"""

import os
from tkinter import filedialog

import consola
import eliza_home


def _pedir_remota(preguntas, root):
    """Pide la carpeta remota: escribiéndola, o Enter para elegirla con ventana."""
    consola.info("Escribe la ruta (ej. S:\\Control\\...\\[ ELIZA ]  o  \\\\servidor\\carpeta),")
    consola.info("o deja vacío y presiona Enter para elegirla con una ventana.")
    ruta = preguntas.preguntar("Carpeta remota")
    if not ruta:
        ruta = filedialog.askdirectory(title="Carpeta de datos remota de Eliza", parent=root)
    ruta = (ruta or '').strip().strip('"')
    if not ruta:
        return None
    if not os.path.isdir(ruta):
        consola.aviso(f"No existe o no está disponible: {ruta}")
        return None
    return os.path.normpath(ruta)


def _aplicar(nueva):
    try:
        carpeta = eliza_home.establecer_carpeta(nueva)
    except OSError as e:
        consola.aviso(f"No se pudo usar esa carpeta: {e}")
        return None
    consola.ok(f"Carpeta de datos: {carpeta}")
    return carpeta


def primer_arranque(root):
    """Pregunta la carpeta de datos hasta obtener una válida. Devuelve la carpeta elegida."""
    consola.titulo("BIENVENIDO A ELIZA: carpeta de datos")
    consola.info("Eliza guarda su base de datos (VNC/APPS/ACD) y las bitácoras en una carpeta.")
    consola.info("Si tu equipo comparte una carpeta en red, elige [R] para usar la misma base.")
    print(f"{consola.COLOR_ENCABEZADO}[R] Carpeta remota/compartida   [L] Local en este equipo{consola.COLOR_RESET}")

    preguntas = consola.Cuestionario()
    while True:
        try:
            opcion = preguntas.preguntar("Opción", "R").lower()
            if opcion == 'l':
                carpeta = _aplicar(None)
            elif opcion == 'r':
                ruta = _pedir_remota(preguntas, root)
                carpeta = _aplicar(ruta) if ruta else None
            else:
                consola.aviso("Elige R o L.")
                continue
        except consola.Cancelado:
            consola.aviso("Es necesario elegir una carpeta para continuar (L = local).")
            continue
        if carpeta:
            return carpeta


def abrir_settings_terminal(carpeta_actual, root):
    """/settings. Devuelve la NUEVA carpeta de datos si cambió, o None."""
    consola.titulo("SETTINGS: carpeta de datos (ESC para salir)")
    consola.info(f"En uso ahora   : {carpeta_actual}")
    consola.info(f"Remota guardada: {eliza_home.leer_carpeta_externa() or '(ninguna, se usa la local)'}")
    consola.info(f"Local          : {eliza_home.carpeta_local()}")
    print(f"{consola.COLOR_ENCABEZADO}[R] Elegir carpeta remota   [L] Usar datos locales{consola.COLOR_RESET}")

    preguntas = consola.Cuestionario()
    try:
        opcion = preguntas.preguntar("settings").lower()
        if opcion == 'l':
            return _aplicar(None)
        if opcion == 'r':
            ruta = _pedir_remota(preguntas, root)
            return _aplicar(ruta) if ruta else None
    except (consola.Cancelado, KeyboardInterrupt, EOFError):
        pass
    consola.info("Sin cambios.")
    return None
