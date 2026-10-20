"""
bitacora_terminal.py
----------------------
Bitácora en modo TERMINAL:
- capturar_registro(): alta de un registro nuevo (/bitacora sin argumento).
- abrir_terminal():    visor por fecha con menú Cargar/Exportar/Copiar
                       (/bitacora <fecha>).

Cada flujo usa su propia PromptSession desechable (ver consola.py).
"""

import os
import subprocess

from prompt_toolkit.formatted_text import HTML

import bitacora_tools
import consola
import json_db

# nombre_columna -> ancho en caracteres
COLUMNAS = [
    ("INI", 5), ("TURNO", 6), ("FECHA", 11), ("HORA", 9), ("LINEA", 6),
    ("EST", 5), ("TIEMPO", 7), ("FALLA", 23), ("AJUSTE", 23),
    ("AUDITOR", 11), ("PREFIJO", 9), ("COMENTARIOS", 17),
]

TIEMPO_POR_DEFECTO = "15"


# ---------------------------------------------------------
# Captura

def capturar_registro(base_dir):
    """
    Fecha y hora se llenan solas (hora redondeada a 5 min); Línea y Falla son
    obligatorios; Tiempo vacío usa 15; el resto puede quedar vacío.
    ESC en cualquier momento cancela sin guardar nada.
    """
    ahora = bitacora_tools.redondear_hora_5min()
    fecha_str = ahora.strftime("%Y-%m-%d")
    hora_str = ahora.strftime("%H:%M:%S")

    consola.titulo("BITÁCORA: Nuevo registro (ESC para cancelar)")
    consola.info(f"Fecha: {fecha_str}   Hora: {hora_str}")

    p = consola.Cuestionario()
    try:
        entry = {
            "fecha": fecha_str,
            "hora": hora_str,
            "linea": p.obligatorio("Línea"),
            "estacion": p.preguntar("Estación"),
            "prefijo": p.preguntar("Prefijo"),
            "auditor": p.preguntar("Auditor"),
            "tiempo": p.preguntar("min", TIEMPO_POR_DEFECTO),
            "falla": p.obligatorio("Falla"),
            "ajuste": p.preguntar("Ajuste"),
            "comentarios": p.preguntar("Comentarios"),
        }
    except consola.Cancelado:
        consola.aviso("Registro cancelado. No se guardó nada.")
        return

    try:
        ruta = bitacora_tools.guardar_registro(base_dir, entry)
    except (json_db.JsonCorrupto, OSError) as e:
        consola.aviso(f"NO se guardó el registro: {e}")
        return
    consola.ok(f"Guardado en {os.path.relpath(ruta, base_dir)}")


# ---------------------------------------------------------
# Visor

def _truncar(texto, ancho):
    texto = str(texto or '')
    return (texto[:ancho - 2] + '…') if len(texto) > ancho - 1 else texto


def mostrar_tabla(registros):
    encabezado = "".join(nombre.ljust(ancho) for nombre, ancho in COLUMNAS)
    print(f"{consola.COLOR_ENCABEZADO}{encabezado}{consola.COLOR_RESET}")
    print(f"{consola.COLOR_ENCABEZADO}{'-' * len(encabezado)}{consola.COLOR_RESET}")

    for r in registros:
        turno = bitacora_tools.calcular_turno(r.get('hora', '00:00:00'))
        valores = [
            'JDRG', turno, r.get('fecha', ''), r.get('hora', ''), r.get('linea', ''),
            r.get('estacion', ''), r.get('tiempo', ''), r.get('falla', ''), r.get('ajuste', ''),
            r.get('auditor', ''), r.get('prefijo', ''), r.get('comentarios', ''),
        ]
        fila = "".join(_truncar(v, ancho).ljust(ancho) for v, (_, ancho) in zip(valores, COLUMNAS))
        print(f"{consola.COLOR_DATOS}{fila}{consola.COLOR_RESET}")


def _copiar_portapapeles(texto):
    """
    Copia con 'clip' (nativo de Windows). Se envía en UTF-16 con BOM: con
    UTF-8, clip interpretaba los bytes en la página de códigos de la consola
    y los acentos/ñ llegaban rotos a Excel.
    """
    try:
        proceso = subprocess.Popen(['clip'], stdin=subprocess.PIPE,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        proceso.communicate(input=texto.encode('utf-16'))
        return proceso.returncode == 0
    except Exception as e:
        consola.aviso(f"No se pudo copiar al portapapeles: {e}")
        return False


def abrir_terminal(base_dir, fecha_inicial=None):
    """Bucle interactivo: carga un día, muestra la tabla, y deja cargar otro / exportar / copiar / salir."""
    p = consola.Cuestionario()
    fecha_actual = None
    registros_actuales = []

    def cargar(fecha):
        nonlocal fecha_actual, registros_actuales
        registros = bitacora_tools.cargar_dia(base_dir, fecha)
        if not registros:
            consola.aviso(f"No se encontraron registros para la fecha {fecha}.")
            return
        fecha_actual, registros_actuales = fecha, registros
        consola.titulo(f"BITÁCORA {fecha} ({len(registros)} registro(s))")
        mostrar_tabla(registros)

    if fecha_inicial:
        cargar(fecha_inicial)

    while True:
        print(f"\n{consola.COLOR_ENCABEZADO}[C] Cargar archivo   [E] Exportar   [Y] Copiar   [Q]/ESC Salir{consola.COLOR_RESET}")
        try:
            opcion = p.prompt(HTML('<prompt>bitacora> </prompt>')).lower()
        except (consola.Cancelado, KeyboardInterrupt, EOFError):
            break

        if not opcion:
            continue

        if opcion in ('q', 'salir', 'exit'):
            break

        try:
            if opcion in ('c', 'cargar'):
                fechas = bitacora_tools.listar_fechas_disponibles(base_dir)
                if fechas:
                    muestra = ', '.join(fechas[:15]) + ('...' if len(fechas) > 15 else '')
                    consola.info(f"Disponibles: {muestra}")
                else:
                    consola.info("(Aún no hay archivos en bitacora/)")
                arg = p.preguntar("Fecha (hoy / DD / MM/DD / YYYY-MM-DD)")
                if not arg:
                    continue
                fecha_resuelta, error = bitacora_tools.resolver_fecha_arg(arg)
                if error:
                    consola.aviso(error)
                    continue
                cargar(fecha_resuelta)

            elif opcion in ('e', 'exportar'):
                if not registros_actuales:
                    consola.aviso("No hay datos cargados para exportar. Usa [C] primero.")
                    continue
                ruta_default = os.path.join(base_dir, f"bitacora_{fecha_actual}.tsv")
                ruta = p.preguntar("Ruta de exportación", ruta_default)
                tsv = bitacora_tools.formatear_tsv(registros_actuales)
                try:
                    # utf-8-sig (con BOM): Excel lo abre con acentos correctos.
                    with open(ruta, 'w', encoding='utf-8-sig', newline='\r\n') as f:
                        f.write(tsv)
                    consola.ok(f"Exportado a {ruta}")
                except OSError as e:
                    consola.aviso(f"No se pudo exportar: {e}")

            elif opcion in ('y', 'copiar'):
                if not registros_actuales:
                    consola.aviso("No hay datos cargados para copiar. Usa [C] primero.")
                    continue
                if _copiar_portapapeles(bitacora_tools.formatear_tsv(registros_actuales)):
                    consola.ok(f"Copiado al portapapeles ({len(registros_actuales)} registro(s)).")

            else:
                consola.aviso("Opción no reconocida.")
        except consola.Cancelado:
            continue  # ESC dentro de una sub-pregunta vuelve al menú
