"""
add_terminal.py
------------------
/add: alta de entradas VNC/APPS. Abre el selector de archivos NATIVO (única
parte con ventana: navegar carpetas de Windows solo con texto no es
práctico) y el resto se captura por consola. ESC cancela el resto del alta.
"""

import os
from tkinter import filedialog

import add_tools
import consola
import json_db


def _elegir_archivos(root):
    rutas = filedialog.askopenfilenames(
        title="Elegir archivo(s) para agregar (.vnc / .lnk / .exe)",
        filetypes=[("Soportados", "*.vnc *.lnk *.exe"), ("Todos", "*.*")],
        parent=root
    )
    return list(rutas)


def abrir_add_terminal(base_dir, root):
    """
    Por cada archivo elegido detecta categoría/IP/acción y solo pide lo que
    falta (Nombre, Info, y la IP si es VNC). Devuelve True si se guardó algo.
    """
    rutas = _elegir_archivos(root)
    if not rutas:
        consola.aviso("No se eligió ningún archivo.")
        return False

    preguntas = consola.Cuestionario()
    hubo_cambios = False

    for ruta in rutas:
        datos, error = add_tools.analizar_archivo(ruta)
        if error:
            consola.aviso(error)
            continue

        consola.titulo(f"Agregar: {os.path.basename(ruta)} (ESC para cancelar)")
        consola.info(f"Categoría detectada: {datos['categoria']}")

        try:
            nombre = preguntas.preguntar("Nombre", datos['nombre_sugerido'])
            info = preguntas.preguntar("Info")
            if datos['categoria'] == 'VNC':
                ip = preguntas.preguntar("IP", datos['ip'])
                action = f"vnc {ip}" if ip else ""
            else:
                ip = ""
                action = datos['action']
        except consola.Cancelado:
            consola.aviso("Alta cancelada. No se guardaron más archivos.")
            break

        if not nombre:
            consola.aviso("Nombre vacío, se omite este archivo.")
            continue
        if datos['categoria'] == 'VNC' and not ip:
            consola.aviso("Una entrada VNC necesita IP, se omite este archivo.")
            continue

        entry = {"name": nombre, "action": action, "info": info, "ip": ip}
        try:
            ruta_json = add_tools.guardar_entrada(datos['categoria'], entry, base_dir)
        except (json_db.JsonCorrupto, OSError) as e:
            consola.aviso(f"No se guardó '{nombre}': {e}")
            continue
        hubo_cambios = True
        consola.ok(f"Agregado '{nombre}' a {os.path.basename(ruta_json)}")

    return hubo_cambios
