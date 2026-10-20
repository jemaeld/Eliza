"""
eliza2.py
----------
Núcleo de consola de Eliza V2: banner, prompt "ELIZA>" con autocompletado,
y despacho de comandos.

PARA AGREGAR UN COMANDO NUEVO: escribe una función  cmd_xxx(ctx, arg)  y
regístrala en COMANDOS (al final de la sección de comandos) con su
descripción. Con eso aparece en el autocompletado con "/" y en /help.

  - ctx.base_dir      carpeta de datos (config_json/, bitacora/, _acd_store/)
  - ctx.tk_root       raíz oculta de Tkinter (para ventanas Toplevel/diálogos)
  - ctx.config        eliza_config.json ya cargado
  - ctx.recargar()    vuelve a leer config_json/ (tras modificar la base de datos)
  - arg               texto después del comando ('' si no hay)
"""

import os
import re
import sys
import json
import glob
import time
import getpass
import tempfile
import traceback
import tkinter as tk
from datetime import datetime

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import HTML

import acd_tools
import actualizador
import licencia
import add_terminal
import bitacora_terminal
import bitacora_tools
import config_manager
import consola
import edit_window
import eliza_home
import logix_window
import network_tools
import scanner_window
import settings_terminal
from consola import COLOR_BORDE, COLOR_DATOS, COLOR_ETIQUETA, COLOR_LOGO, COLOR_RESET

VERSION = "ELIZA v2.3 -- by JDRG"

# Categorías cuyas entradas tienen IP y se pueden usar con /ping y /logix por nombre
CATEGORIAS_CON_IP = ("VNC", "ACD")

PREFIJO_VNC_TEMPORAL = "eliza_vnc_"


# =========================================================
# Contexto de la sesión

class Contexto:
    def __init__(self, tk_root):
        self.tk_root = tk_root
        self.base_dir = None
        self.config = {}
        self.mapa_comandos = {}
        self.modo_datos = "local"   # local | remota | local (remota no disponible)
        self.session = None
        self.salir = False
        self.codigo_salida = 0

    def usar_carpeta(self, carpeta, externa_no_disponible=False):
        self.base_dir = carpeta
        if externa_no_disponible:
            self.modo_datos = "local (remota no disponible)"
        else:
            self.modo_datos = "remota" if eliza_home.leer_carpeta_externa() else "local"

    def recargar(self, silencioso=False):
        """Relee config y config_json/. silencioso=True: no imprime nada y devuelve los avisos."""
        self.config = config_manager.cargar_config(self.base_dir)
        self.mapa_comandos, avisos = cargar_datos_todos(self.base_dir)
        if self.session is not None:
            self.session.completer.mapa_comandos = self.mapa_comandos
        if silencioso:
            return avisos
        for a in avisos:
            consola.aviso(a)
        consola.ok(f"Base de datos recargada ({len(self.mapa_comandos)} entradas).")
        return avisos


def cargar_datos_todos(base_dir):
    """
    Lee todos los .json de config_json/ y arma el mapa '[CATEGORIA] nombre' -> entrada.
    Devuelve (mapa, avisos). Un archivo dañado o una entrada sin 'name' ya no se
    ignoran en silencio: se reportan para que se puedan corregir.
    """
    ruta_config = os.path.join(base_dir, 'config_json')
    os.makedirs(ruta_config, exist_ok=True)
    mapa, avisos = {}, []
    for archivo in sorted(os.listdir(ruta_config)):
        if not archivo.lower().endswith(".json"):
            continue
        categoria = archivo[:-5].upper()
        try:
            with open(os.path.join(ruta_config, archivo), 'r', encoding='utf-8-sig') as f:
                datos = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
            avisos.append(f"config_json/{archivo} no se pudo leer y se ignoró: {e}")
            continue
        if not isinstance(datos, list):
            avisos.append(f"config_json/{archivo} no contiene una lista; se ignoró.")
            continue
        sin_nombre, repetidos = 0, []
        for item in datos:
            nombre = str(item.get('name', '')).strip() if isinstance(item, dict) else ''
            if not nombre:
                sin_nombre += 1
                continue
            clave = f"[{categoria}] {nombre}"
            if clave in mapa:
                repetidos.append(nombre)
            mapa[clave] = {"categoria": categoria, "data": item}
        if sin_nombre:
            avisos.append(f"config_json/{archivo}: {sin_nombre} entrada(s) sin 'name' se omitieron.")
        if repetidos:
            avisos.append(f"config_json/{archivo}: nombres repetidos, solo se usa la última entrada de cada uno: "
                          f"{', '.join(sorted(set(repetidos)))} (corrígelo con /edit {categoria.lower()}).")
    return mapa, avisos


# =========================================================
# Banner / ayuda

LOGO_ELIZA = {
    'E': ["██████", "██    ", "████  ", "██    ", "██████"],
    'L': ["██    ", "██    ", "██    ", "██    ", "██████"],
    'I': ["██████", "  ██  ", "  ██  ", "  ██  ", "██████"],
    'Z': ["██████", "    ██", "  ██  ", "██    ", "██████"],
    'A': [" ████ ", "██  ██", "██████", "██  ██", "██  ██"],
}
ANCHO_ETIQUETA_BANNER = 11


def limpiar_pantalla():
    # Además de limpiar, 'cls' activa en Windows el soporte de colores ANSI de la consola.
    os.system('cls' if os.name == 'nt' else 'clear')


def _fila_caja(etiqueta, valor, ancho_interior):
    plano = f" {etiqueta:<{ANCHO_ETIQUETA_BANNER}}{valor}"
    relleno = " " * max(ancho_interior - len(plano), 1)
    return (f"{COLOR_BORDE}│{COLOR_RESET} {COLOR_ETIQUETA}{etiqueta:<{ANCHO_ETIQUETA_BANNER}}{COLOR_RESET}"
            f"{COLOR_DATOS}{valor}{COLOR_RESET}{relleno}{COLOR_BORDE}│{COLOR_RESET}")


def mostrar_banner(ctx):
    ahora = datetime.now()
    print()
    for fila in range(5):
        linea = "  ".join(LOGO_ELIZA[letra][fila] for letra in "ELIZA")
        print(f"{COLOR_LOGO}   {linea}{COLOR_RESET}")

    filas = [
        ("Usuario:", getpass.getuser()),
        ("Equipo/IP:", network_tools.ip_principal()),
        ("Fecha:", ahora.strftime("%Y-%m-%d")),
        ("Hora:", ahora.strftime("%H:%M:%S")),
        ("Datos:", f"{ctx.modo_datos} · {len(ctx.mapa_comandos)} entradas"),
        ("Versión:", actualizador.version_actual()),
    ]
    plano_max = max(len(f" {e:<{ANCHO_ETIQUETA_BANNER}}{v}") for e, v in filas)
    ancho = max(plano_max + 2, 40)

    print(f"{COLOR_BORDE}┌{'─' * ancho}┐{COLOR_RESET}")
    print(f"{COLOR_BORDE}│{COLOR_RESET}{COLOR_ETIQUETA}{VERSION.center(ancho)}{COLOR_RESET}{COLOR_BORDE}│{COLOR_RESET}")
    print(f"{COLOR_BORDE}├{'─' * ancho}┤{COLOR_RESET}")
    for etiqueta, valor in filas:
        print(_fila_caja(etiqueta, valor, ancho))
    print(f"{COLOR_BORDE}└{'─' * ancho}┘{COLOR_RESET}")
    print()


# =========================================================
# Búsquedas en la base de datos

def _quitar_prefijo_categoria(texto):
    """'[VNC] L31 Monitor' -> 'L31 Monitor' (lo que inserta el autocompletado con TAB)."""
    return re.sub(r'^\[[A-Za-z0-9_]+\]\s*', '', texto.strip())


def buscar_por_nombre(mapa, nombre, categorias=None):
    """Lista de (categoria, data) cuyo 'name' coincide exacto (sin distinguir mayúsculas)."""
    buscado = _quitar_prefijo_categoria(nombre).lower()
    return [(it['categoria'], it['data']) for it in mapa.values()
            if (categorias is None or it['categoria'] in categorias)
            and str(it['data'].get('name', '')).strip().lower() == buscado]


def resolver_ip(mapa, argumento):
    """
    Para /ping y /logix: si el argumento es el nombre de una entrada VNC/ACD,
    devuelve su IP; si no coincide con nada, se asume IP/host directo.
    Devuelve (ip, mensaje_info, error).
    """
    coincidencias = buscar_por_nombre(mapa, argumento, CATEGORIAS_CON_IP)
    if len(coincidencias) > 1:
        cats = ", ".join(c for c, _ in coincidencias)
        return None, None, f"Hay {len(coincidencias)} entradas llamadas '{argumento}' ({cats}). Usa la IP directamente."
    if len(coincidencias) == 1:
        cat, data = coincidencias[0]
        ip = (data.get('ip') or '').strip()
        if not ip:
            return None, None, f"La entrada '{data['name']}' [{cat}] no tiene IP registrada."
        return ip, f"Usando IP de '{data['name']}' [{cat}] -> {ip}", None
    return _quitar_prefijo_categoria(argumento), None, None


# =========================================================
# Ejecutar entradas de la base de datos

def _limpiar_vnc_temporales():
    """Borra los .vnc temporales de lanzamientos anteriores (antes se acumulaban en %TEMP%)."""
    limite = time.time() - 60
    for ruta in glob.glob(os.path.join(tempfile.gettempdir(), PREFIJO_VNC_TEMPORAL + "*.vnc")):
        try:
            if os.path.getmtime(ruta) < limite:
                os.remove(ruta)
        except OSError:
            pass


def lanzar_vnc(ip, config):
    _limpiar_vnc_temporales()
    contenido = (f"[connection]\nhost={ip}\nport={config.get('vnc_puerto', 5900)}\n"
                 f"password={config.get('vnc_password', '')}\n")
    with tempfile.NamedTemporaryFile(mode='w', prefix=PREFIJO_VNC_TEMPORAL, suffix='.vnc',
                                     delete=False, encoding='utf-8') as f:
        f.write(contenido)
    os.startfile(f.name)


def ejecutar_entrada(ctx, item):
    data = item['data']
    if item['categoria'] == "VNC":
        ip = (data.get('ip') or '').strip()
        if not ip:
            accion = (data.get('action') or '').strip()
            ip = accion[4:].strip() if accion.lower().startswith('vnc ') else ''
        if not ip:
            consola.aviso(f"'{data['name']}' no tiene IP registrada.")
            return
        lanzar_vnc(ip, ctx.config)
    else:
        ruta = acd_tools.resolver_ruta_action(data.get('action', ''), ctx.base_dir)
        if not ruta:
            consola.aviso(f"'{data['name']}' no tiene acción registrada.")
            return
        try:
            os.startfile(ruta)
        except OSError as e:
            consola.aviso(f"No se pudo abrir '{data['name']}': {ruta}\n     {e}")
            return
    consola.ok(f"Ejecutando: {data['name']}")


# =========================================================
# Comandos

def cmd_clear(ctx, arg):
    limpiar_pantalla()
    mostrar_banner(ctx)


def cmd_ip(ctx, arg):
    consola.titulo("DETALLE DE RED")
    for detalle in network_tools.interfaces_ipv4():
        consola.info(f"> {detalle}")


def cmd_ping(ctx, arg):
    if not arg:
        consola.aviso("Uso: /ping <ip_o_host>  |  /ping <nombre_guardado>")
        return
    destino, mensaje, error = resolver_ip(ctx.mapa_comandos, arg)
    if error:
        consola.aviso(error)
        return
    if mensaje:
        consola.ok(mensaje)
    exito, texto = network_tools.lanzar_ping(destino)
    (consola.ok if exito else consola.aviso)(texto)


def cmd_settings(ctx, arg):
    nueva = settings_terminal.abrir_settings_terminal(ctx.base_dir, ctx.tk_root)
    if nueva:
        ctx.usar_carpeta(nueva)
        ctx.recargar()


def cmd_scan_acd(ctx, arg):
    ruta_acd_json = os.path.join(ctx.base_dir, 'config_json', 'acd.json')
    if scanner_window.abrir_scanner_acd(ruta_acd_json, ctx.base_dir, ctx.tk_root):
        ctx.recargar()


def cmd_edit(ctx, arg):
    ruta_config = os.path.join(ctx.base_dir, 'config_json')
    disponibles = sorted(f[:-5].upper() for f in os.listdir(ruta_config) if f.lower().endswith('.json'))
    if not arg:
        consola.aviso(f"Uso: /edit <categoria>. Disponibles: {', '.join(disponibles)}")
        return
    nombre_archivo = arg.lower() + '.json'
    ruta_json = os.path.join(ruta_config, nombre_archivo)
    if not os.path.exists(ruta_json):
        consola.aviso(f"No existe config_json/{nombre_archivo}. Disponibles: {', '.join(disponibles)}")
        return
    if edit_window.abrir_editor_tabla(arg.upper(), ruta_json, ctx.tk_root):
        ctx.recargar()


def cmd_add(ctx, arg):
    if add_terminal.abrir_add_terminal(ctx.base_dir, ctx.tk_root):
        ctx.recargar()


def cmd_bitacora(ctx, arg):
    if not arg:
        bitacora_terminal.capturar_registro(ctx.base_dir)
        return
    fecha, error = bitacora_tools.resolver_fecha_arg(arg)
    if error:
        consola.aviso(error)
        return
    bitacora_terminal.abrir_terminal(ctx.base_dir, fecha)


def cmd_logix(ctx, arg):
    ip = ""
    if arg:
        ip, mensaje, error = resolver_ip(ctx.mapa_comandos, arg)
        if error:
            consola.aviso(error)
            return
        if mensaje:
            consola.ok(mensaje)
    logix_window.abrir_logix(ip, ctx.tk_root, ctx.base_dir)


def cmd_reload(ctx, arg):
    ctx.recargar()


def cmd_update(ctx, arg):
    if actualizador.ejecutar_update():
        ctx.codigo_salida = actualizador.CODIGO_REINICIAR
        ctx.salir = True


def cmd_help(ctx, arg):
    consola.titulo("COMANDOS DISPONIBLES")
    for cmd, (descripcion, _) in COMANDOS.items():
        consola.info(f"{cmd:<12}{COLOR_RESET} {descripcion}")
    consola.info(f"{'exit / quit':<12}{COLOR_RESET} Cierra Eliza")

    if ctx.mapa_comandos:
        categorias = {}
        for item in ctx.mapa_comandos.values():
            categorias[item['categoria']] = categorias.get(item['categoria'], 0) + 1
        consola.titulo("BASE DE DATOS CARGADA")
        consola.info(f"Carpeta de datos: {ctx.base_dir}")
        for cat, cantidad in sorted(categorias.items()):
            consola.info(f"[{cat}] {cantidad} entradas")
        consola.info("Escribe el nombre (o usa TAB para autocompletar) para ejecutar una entrada.")
    print()


# Registro de comandos: nombre -> (descripción, función). El orden es el de /help.
COMANDOS = {
    '/clear':    ('Limpia la pantalla y vuelve a mostrar el banner', cmd_clear),
    '/ip':       ('Muestra el detalle de las interfaces de red locales', cmd_ip),
    '/ping':     ('Ping a una IP/host, o a una entrada VNC/ACD por nombre', cmd_ping),
    '/scan_acd': ('Escanea una carpeta y registra proyectos ACD/L5K encontrados', cmd_scan_acd),
    '/edit':     ('Editor de tabla para vnc/apps/acd (ej: /edit vnc)', cmd_edit),
    '/add':      ('Agrega VNC/APPS: elige archivo(s) .vnc/.lnk/.exe y completa por consola', cmd_add),
    '/bitacora': ('Sin fecha: nuevo registro. Con fecha (hoy, ayer, DD, MM/DD, YYYY-MM-DD): visor', cmd_bitacora),
    '/logix':    ('Monitor/forzado de tags Allen-Bradley (pylogix). IP/nombre opcional', cmd_logix),
    '/settings': ('Cambia la carpeta de datos: remota/compartida o local', cmd_settings),
    '/reload':   ('Vuelve a leer la base de datos (si otro equipo la modificó)', cmd_reload),
    '/update':   ('Busca y descarga la última versión de Eliza desde GitHub', cmd_update),
    '/help':     ('Muestra esta lista de comandos', cmd_help),
}
SALIDA = ('exit', 'quit', '/exit', '/quit')


# =========================================================
# Autocompletado

class ElizaCompleter(Completer):
    def __init__(self, mapa_comandos):
        self.mapa_comandos = mapa_comandos

    def get_completions(self, document, complete_event):
        # WORD=True para que "/" cuente como parte de la palabra.
        word = document.get_word_before_cursor(WORD=True).lower()

        if word.startswith('/'):
            for cmd, (descripcion, _) in COMANDOS.items():
                if word in cmd:
                    yield Completion(cmd, start_position=-len(word),
                                     display=HTML(f'<cmd>[CMD]</cmd> {cmd}'), display_meta=descripcion)
            return

        for texto, item in self.mapa_comandos.items():
            if word in texto.lower():
                cat = item['categoria'].lower()
                data = item['data']
                # Si hay comentario es más útil que ip|fecha; si no, se usa 'info'.
                comentario = str(data.get('comentario') or '').strip()
                meta = comentario or str(data.get('info') or '')
                yield Completion(texto, start_position=-len(word),
                                 display=HTML(f'<{cat}>[{item["categoria"]}]</{cat}> {data["name"]}'),
                                 display_meta=meta)


# =========================================================
# Bucle principal

def _registrar_error(ctx, entrada):
    """Guarda el traceback en eliza_error.log (junto a Eliza) para poder depurar después."""
    ruta = os.path.join(eliza_home.ruta_instalacion(), "eliza_error.log")
    try:
        with open(ruta, 'a', encoding='utf-8') as f:
            f.write(f"\n=== {datetime.now():%Y-%m-%d %H:%M:%S} | entrada: {entrada!r}\n")
            f.write(traceback.format_exc())
    except OSError:
        pass
    return ruta


def procesar_entrada(ctx, entrada):
    if entrada.lower() in SALIDA:
        ctx.salir = True
        return

    comando, _, arg = entrada.partition(' ')
    comando = comando.lower()
    if comando in COMANDOS:
        COMANDOS[comando][1](ctx, arg.strip())
        return

    if entrada in ctx.mapa_comandos:
        ejecutar_entrada(ctx, ctx.mapa_comandos[entrada])
        return

    # Sin el prefijo [CAT]: si el nombre es único en toda la base, se ejecuta igual.
    coincidencias = [it for it in ctx.mapa_comandos.values()
                     if str(it['data'].get('name', '')).strip().lower() == entrada.lower()]
    if len(coincidencias) == 1:
        ejecutar_entrada(ctx, coincidencias[0])
    elif len(coincidencias) > 1:
        cats = ", ".join(it['categoria'] for it in coincidencias)
        consola.aviso(f"'{entrada}' existe en varias categorías ({cats}). Usa TAB para elegir.")
    else:
        consola.aviso("Comando no reconocido. Escribe /help para ver los comandos.")


def main():
    limpiar_pantalla()

    # Una sola raíz de Tkinter, oculta, para toda la sesión. Cada pantalla
    # (scan_acd, edit, logix, diálogos) es Toplevel de esta raíz: crear
    # varias Tk() en el mismo proceso provoca errores de Tcl al cerrarlas.
    tk_root = tk.Tk()
    tk_root.withdraw()

    ctx = Contexto(tk_root)
    if eliza_home.es_primer_arranque():
        settings_terminal.primer_arranque(tk_root)
        limpiar_pantalla()
    carpeta, remota_caida = eliza_home.resolver_carpeta_eliza()
    respaldo = False
    if remota_caida:
        carpeta, respaldo = settings_terminal.remota_no_disponible(remota_caida, tk_root)
    if carpeta is None:
        try:
            tk_root.destroy()
        except tk.TclError:
            pass
        return 0
    ctx.usar_carpeta(carpeta, externa_no_disponible=respaldo)
    avisos = ctx.recargar(silencioso=True)
    if not licencia.verificar(ctx, respaldo_local=respaldo):
        try:
            tk_root.destroy()
        except tk.TclError:
            pass
        return 1
    limpiar_pantalla()
    mostrar_banner(ctx)
    if respaldo:
        avisos.insert(0, "Trabajando con datos LOCALES en esta sesión (la remota no estaba disponible).")
    for a in avisos:
        consola.aviso(a)

    ctx.session = PromptSession(completer=ElizaCompleter(ctx.mapa_comandos), style=consola.ESTILO)

    while not ctx.salir:
        try:
            entrada = ctx.session.prompt(HTML('<prompt>ELIZA> </prompt>')).strip()
        except (KeyboardInterrupt, EOFError):
            break
        if not entrada:
            continue
        try:
            procesar_entrada(ctx, entrada)
        except KeyboardInterrupt:
            consola.aviso("Interrumpido.")
        except Exception as e:
            # Antes cualquier error (p. ej. abrir un ACD que ya no existe)
            # cerraba Eliza por completo. Ahora se informa y se sigue.
            ruta_log = _registrar_error(ctx, entrada)
            consola.aviso(f"Error inesperado: {e}")
            consola.info(f"    Detalle guardado en {ruta_log}")

    try:
        tk_root.destroy()
    except tk.TclError:
        pass
    return ctx.codigo_salida


if __name__ == "__main__":
    sys.exit(main())
