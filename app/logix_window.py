"""
logix_window.py
------------------
Monitor y forzado de tags Allen-Bradley (Logix) vía pylogix. Ventana GUI
independiente (Tkinter) porque necesita refrescar continuamente en segundo
plano sin bloquear la consola.

Cada FILA es una conexión independiente y autocontenida: su propia IP, su
propio polling rate, su propio hilo de sondeo. Columnas:

    IP | POLLING (ms) | CONECTAR | TAG | VALOR ACTUAL | ESTADO | SOBRESCRIBIR | COMENTARIO

- Doble clic en IP, POLLING, TAG, SOBRESCRIBIR o COMENTARIO para editar esa
  celda. Editar IP/POLLING mientras la fila está conectada la reconecta sola
  con el valor nuevo.
- Clic (sencillo) en CONECTAR alterna conectar/desconectar esa fila.
- Un valor en SOBRESCRIBIR fuerza escritura continua en esa fila (pide
  confirmación, porque escribe sobre un PLC real). Vaciar la celda detiene
  el forzado.
- "Guardar registro" exporta las filas actuales (IP, polling, tag,
  comentario) a un JSON; "Cargar registro" las importa. Los forzados NO se
  guardan ni se cargan: las filas cargadas llegan desconectadas y sin
  forzar.

Nota de threading: pylogix recomienda NO compartir una instancia de PLC
entre hilos, así que cada fila crea y usa su propia conexión exclusivamente
dentro de su propio hilo; la ventana principal nunca la toca directamente.

ESC cierra la ventana (desconecta todas las filas primero).
"""

import json
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import estilo_consola as estilo
import logix_tools

try:
    from pylogix import PLC
    PYLOGIX_DISPONIBLE = True
except ImportError:
    PYLOGIX_DISPONIBLE = False

POLLING_MIN_MS = logix_tools.POLLING_MIN_MS
POLLING_DEFAULT_MS = logix_tools.POLLING_DEFAULT_MS

COLOR_EXITO = "#00ff00"      # verde: conexión confirmada
COLOR_ERROR = "#ff5555"      # rojo: no se pudo conectar
COLOR_PENDIENTE = "#ffcc00"  # ámbar: conectando / advertencia / desconectado

COLUMNAS = ('ip', 'polling', 'conectar', 'tag', 'valor', 'estado', 'sobrescribir', 'comentario')
COLUMNAS_EDITABLES = ('ip', 'polling', 'tag', 'sobrescribir', 'comentario')  # doble clic para editar

TIPOS_ARCHIVO = [("Registro de tags (JSON)", "*.json"), ("Todos los archivos", "*.*")]


class LogixWindow:
    def __init__(self, ip_inicial, root, carpeta_registros=None):
        self.ip_inicial = ip_inicial
        self.root = root  # raíz de Tkinter compartida por toda la sesión de Eliza

        self.lock = threading.Lock()
        self.entradas_por_iid = {}   # iid -> {'ip','polling_ms','tag','comentario','forzar','valor_forzado'}
        self._hilos_por_iid = {}     # iid -> threading.Thread
        self._detener_por_iid = {}   # iid -> threading.Event
        self._contador_iid = 0
        self._cerrado = False
        self.cola = queue.Queue()
        self.editor_entry = None
        self._after_id = None
        # Carpeta inicial para Guardar/Cargar registro: la carpeta de datos de
        # Eliza (antes era el directorio de trabajo, que variaba según desde
        # dónde se lanzara). Recuerda la última usada durante la sesión.
        self._ultima_carpeta = carpeta_registros or os.getcwd()

        # Toplevel de la raíz compartida, NO un Tk() propio -- crear varias
        # Tk() en el mismo proceso causa errores de Tcl al cerrarlas.
        self.window = tk.Toplevel(root)
        estilo.aplicar_estilo_base(self.window, "ELIZA :: logix", "1260x560")
        self.window.overrideredirect(True)
        self.window.bind('<Escape>', lambda e: self.cerrar())

        self._construir_ui()

        if not PYLOGIX_DISPONIBLE:
            messagebox.showerror(
                "Falta pylogix",
                "No se encontró la librería 'pylogix'. Instálala con:\n\npip install pylogix",
                parent=self.window
            )
        elif self.ip_inicial:
            # /logix <ip>: se agrega una primera fila ya con esa IP, lista para conectar.
            self.agregar_fila(ip=self.ip_inicial)

        self._after_id = self.window.after(80, self._procesar_cola)

    # ---------------------------------------------------------
    def _construir_ui(self):
        botones = ttk.Frame(self.window, style="TLabel")
        botones.pack(fill='x', padx=10, pady=10)
        ttk.Button(botones, text="+ Agregar tag", command=lambda: self.agregar_fila()).pack(side='left')
        ttk.Button(botones, text="- Eliminar tag", command=self.eliminar_fila).pack(side='left', padx=5)
        ttk.Button(botones, text="Guardar registro", command=self.guardar_registro).pack(side='left')
        ttk.Button(botones, text="Cargar registro", command=self.cargar_registro).pack(side='left', padx=5)
        ttk.Button(botones, text="Detener todos los forzados", command=self.detener_todos_forzados).pack(side='left')

        self.tree = ttk.Treeview(self.window, columns=COLUMNAS, show='headings', selectmode='extended')
        encabezados = {
            'ip': 'IP', 'polling': 'POLLING (ms)', 'conectar': 'CONECTAR', 'tag': 'TAG',
            'valor': 'VALOR ACTUAL', 'estado': 'ESTADO', 'sobrescribir': 'SOBRESCRIBIR',
            'comentario': 'COMENTARIO',
        }
        anchos = {
            'ip': 130, 'polling': 100, 'conectar': 90, 'tag': 220,
            'valor': 140, 'estado': 170, 'sobrescribir': 150, 'comentario': 220,
        }
        for col in COLUMNAS:
            self.tree.heading(col, text=encabezados[col])
            self.tree.column(col, width=anchos[col], anchor='w')
        self.tree.pack(fill='both', expand=True, padx=10, pady=(0, 5))
        self.tree.tag_configure('forzando', background='#552200', foreground='#ffcc66')
        self.tree.tag_configure('conectado', foreground=COLOR_EXITO)
        self.tree.tag_configure('desconectado', foreground=COLOR_PENDIENTE)

        self.tree.bind('<Double-1>', self._on_double_click)
        self.tree.bind('<Button-1>', self._on_single_click)

        pie = ttk.Frame(self.window, style="TLabel")
        pie.pack(fill='x', padx=10, pady=(0, 10))
        ttk.Label(
            pie,
            text="Doble clic en IP/POLLING/TAG/SOBRESCRIBIR/COMENTARIO para editar · "
                 "clic en CONECTAR conecta/desconecta esa fila · Esc cierra"
        ).pack(side='left')

    def _siguiente_iid(self):
        self._contador_iid += 1
        return str(self._contador_iid)

    # ---------------------------------------------------------
    def agregar_fila(self, ip="", polling_ms=POLLING_DEFAULT_MS, tag="", comentario=""):
        iid = self._siguiente_iid()
        with self.lock:
            self.entradas_por_iid[iid] = {
                'ip': ip, 'polling_ms': polling_ms, 'tag': tag, 'comentario': comentario,
                'forzar': False, 'valor_forzado': '',
            }
        self.tree.insert('', 'end', iid=iid, values=(
            ip, str(polling_ms), 'Conectar', tag, '', 'Desconectado', '', comentario
        ), tags=('desconectado',))
        self.tree.selection_set(iid)
        self.tree.see(iid)
        return iid

    def eliminar_fila(self):
        seleccion = self.tree.selection()
        if not seleccion:
            return
        for iid in seleccion:
            self._quitar_fila(iid)

    def _quitar_fila(self, iid):
        self._desconectar_fila(iid, silencioso=True)
        with self.lock:
            self.entradas_por_iid.pop(iid, None)
        if self.tree.exists(iid):
            self.tree.delete(iid)

    def detener_todos_forzados(self):
        with self.lock:
            for entrada in self.entradas_por_iid.values():
                entrada['forzar'] = False
                entrada['valor_forzado'] = ''
        for iid in self.tree.get_children(''):
            self.tree.set(iid, 'sobrescribir', '')
            estado_tag = 'conectado' if self._fila_conectada(iid) else 'desconectado'
            self.tree.item(iid, tags=(estado_tag,))

    def _fila_conectada(self, iid):
        hilo = self._hilos_por_iid.get(iid)
        return hilo is not None and hilo.is_alive()

    # ---------------------------------------------------------
    # Guardar / cargar registro de tags (JSON)
    def guardar_registro(self):
        # Respeta el orden visual de la tabla, no el orden de creación.
        with self.lock:
            filas = [
                {
                    'ip': self.entradas_por_iid[iid]['ip'],
                    'polling_ms': self.entradas_por_iid[iid]['polling_ms'],
                    'tag': self.entradas_por_iid[iid]['tag'],
                    'comentario': self.entradas_por_iid[iid].get('comentario', ''),
                }
                for iid in self.tree.get_children('')
                if iid in self.entradas_por_iid
            ]
        if not filas:
            messagebox.showinfo("Sin tags", "No hay filas para guardar.", parent=self.window)
            return

        ruta = filedialog.asksaveasfilename(
            parent=self.window, title="Guardar registro de tags",
            initialdir=self._ultima_carpeta, initialfile="registro_logix.json",
            defaultextension=".json", filetypes=TIPOS_ARCHIVO
        )
        if not ruta:
            return
        try:
            n = logix_tools.guardar_registro(ruta, filas)
        except OSError as e:
            messagebox.showerror("Error al guardar", f"No se pudo escribir el archivo:\n{e}", parent=self.window)
            return
        self._ultima_carpeta = os.path.dirname(ruta)
        messagebox.showinfo(
            "Registro guardado",
            f"Se guardaron {n} tag(s) en:\n{ruta}\n\n(Los valores de SOBRESCRIBIR no se guardan.)",
            parent=self.window
        )

    def cargar_registro(self):
        ruta = filedialog.askopenfilename(
            parent=self.window, title="Cargar registro de tags",
            initialdir=self._ultima_carpeta, filetypes=TIPOS_ARCHIVO
        )
        if not ruta:
            return
        try:
            filas = logix_tools.cargar_registro(ruta)
        except (OSError, json.JSONDecodeError, ValueError) as e:
            messagebox.showerror("Error al cargar", f"No se pudo leer el registro:\n{e}", parent=self.window)
            return
        self._ultima_carpeta = os.path.dirname(ruta)

        if not filas:
            messagebox.showinfo("Registro vacío", "El archivo no contiene tags.", parent=self.window)
            return

        # Si ya hay filas, preguntar si se reemplazan o se agregan al final.
        if self.tree.get_children(''):
            respuesta = messagebox.askyesnocancel(
                "Cargar registro",
                f"El registro tiene {len(filas)} tag(s).\n\n"
                "Sí = REEMPLAZAR las filas actuales (se desconectan y se detienen sus forzados)\n"
                "No = AGREGAR al final de las actuales\n"
                "Cancelar = no hacer nada",
                parent=self.window
            )
            if respuesta is None:
                return
            if respuesta:
                for iid in list(self.tree.get_children('')):
                    self._quitar_fila(iid)

        for fila in filas:
            self.agregar_fila(
                ip=fila['ip'], polling_ms=fila['polling_ms'],
                tag=fila['tag'], comentario=fila['comentario']
            )

    # ---------------------------------------------------------
    # Clic sencillo en CONECTAR alterna esa fila; el resto de columnas no hace nada aquí
    def _on_single_click(self, event):
        region = self.tree.identify('region', event.x, event.y)
        if region != 'cell':
            return
        row_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        if not row_id or not col_id:
            return
        col_index = int(col_id.replace('#', '')) - 1
        if col_index < 0 or col_index >= len(COLUMNAS):
            return
        if COLUMNAS[col_index] == 'conectar':
            self._alternar_conexion(row_id)

    def _alternar_conexion(self, iid):
        if self._fila_conectada(iid):
            self._desconectar_fila(iid)
        else:
            self._conectar_fila(iid)

    # ---------------------------------------------------------
    # Edición inline (ip, polling, tag, sobrescribir, comentario) -- mismo patrón que edit_window.py
    def _on_double_click(self, event):
        if self.editor_entry is not None:
            return
        region = self.tree.identify('region', event.x, event.y)
        if region != 'cell':
            return
        row_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        if not row_id or not col_id:
            return

        col_index = int(col_id.replace('#', '')) - 1
        if col_index < 0 or col_index >= len(COLUMNAS):
            return
        clave = COLUMNAS[col_index]
        if clave not in COLUMNAS_EDITABLES:
            return  # 'valor', 'estado' y 'conectar' no se editan escribiendo

        bbox = self.tree.bbox(row_id, col_id)
        if not bbox:
            return
        x, y, ancho, alto = bbox
        valor_actual = self.tree.set(row_id, col_id)

        self.editor_entry = tk.Entry(
            self.tree, bg=estilo.ENTRY_BG, fg=estilo.FG_DATA,
            insertbackground=estilo.FG, font=estilo.FONT_MONO, borderwidth=1
        )
        self.editor_entry.insert(0, valor_actual)
        self.editor_entry.select_range(0, tk.END)
        self.editor_entry.focus()
        self.editor_entry.place(x=x, y=y, width=ancho, height=alto)

        def confirmar(_event=None):
            nuevo_valor = self.editor_entry.get().strip()
            self._cerrar_editor_celda()
            self._aplicar_edicion(row_id, clave, nuevo_valor)

        def cancelar(_event=None):
            self._cerrar_editor_celda()
            return 'break'  # evita que este ESC también dispare el cierre de la ventana

        self.editor_entry.bind('<Return>', confirmar)
        self.editor_entry.bind('<FocusOut>', confirmar)
        self.editor_entry.bind('<Escape>', cancelar)

    def _cerrar_editor_celda(self):
        if self.editor_entry is not None:
            self.editor_entry.destroy()
            self.editor_entry = None

    def _aplicar_edicion(self, row_id, clave, nuevo_valor):
        if row_id not in self.entradas_por_iid:
            return

        if clave == 'ip':
            with self.lock:
                self.entradas_por_iid[row_id]['ip'] = nuevo_valor
            self.tree.set(row_id, 'ip', nuevo_valor)
            if self._fila_conectada(row_id):
                self._conectar_fila(row_id)  # reconecta sola con la IP nueva
            return

        if clave == 'polling':
            try:
                polling = int(nuevo_valor)
            except ValueError:
                polling = POLLING_DEFAULT_MS
            if polling < POLLING_MIN_MS:
                messagebox.showwarning(
                    "Polling muy rápido",
                    f"El mínimo permitido es {POLLING_MIN_MS} ms (para no saturar el PLC/la red). Se ajustó.",
                    parent=self.window
                )
                polling = POLLING_MIN_MS
            with self.lock:
                self.entradas_por_iid[row_id]['polling_ms'] = polling
            self.tree.set(row_id, 'polling', str(polling))
            # No hace falta reconectar: el hilo relee polling_ms en cada ciclo.
            return

        if clave == 'tag':
            with self.lock:
                self.entradas_por_iid[row_id]['tag'] = nuevo_valor
            self.tree.set(row_id, 'tag', nuevo_valor)
            return

        if clave == 'comentario':
            # Solo informativo: no afecta conexión ni sondeo.
            with self.lock:
                self.entradas_por_iid[row_id]['comentario'] = nuevo_valor
            self.tree.set(row_id, 'comentario', nuevo_valor)
            return

        # clave == 'sobrescribir'
        if not nuevo_valor:
            with self.lock:
                self.entradas_por_iid[row_id]['forzar'] = False
                self.entradas_por_iid[row_id]['valor_forzado'] = ''
            self.tree.set(row_id, 'sobrescribir', '')
            estado_tag = 'conectado' if self._fila_conectada(row_id) else 'desconectado'
            self.tree.item(row_id, tags=(estado_tag,))
            return

        tag_actual = self.entradas_por_iid.get(row_id, {}).get('tag') or '(sin nombre)'
        polling_actual = self.entradas_por_iid.get(row_id, {}).get('polling_ms', POLLING_DEFAULT_MS)
        if not messagebox.askyesno(
            "Confirmar forzado",
            f"¿Forzar escritura continua de '{nuevo_valor}' en el tag '{tag_actual}'\n"
            f"cada {polling_actual} ms? Esto escribe sobre el PLC en tiempo real.",
            parent=self.window
        ):
            self.tree.set(row_id, 'sobrescribir', '')
            return

        with self.lock:
            self.entradas_por_iid[row_id]['forzar'] = True
            self.entradas_por_iid[row_id]['valor_forzado'] = nuevo_valor
        self.tree.set(row_id, 'sobrescribir', nuevo_valor)
        self.tree.item(row_id, tags=('forzando',))

    # ---------------------------------------------------------
    def _conectar_fila(self, iid):
        if not PYLOGIX_DISPONIBLE:
            messagebox.showerror("Falta pylogix", "Instálala con: pip install pylogix", parent=self.window)
            return

        with self.lock:
            ip = self.entradas_por_iid.get(iid, {}).get('ip', '').strip()
        if not ip:
            messagebox.showerror("Falta IP", "Escribe una IP en esta fila antes de conectar.", parent=self.window)
            return

        # Si ya había una conexión corriendo en esta fila (ej. reconectar tras
        # editar la IP), se espera a que termine por completo antes de abrir
        # una nueva -- evita dos hilos vivos sobre la misma fila a la vez.
        self._desconectar_fila(iid, silencioso=True)

        detener = threading.Event()
        self._detener_por_iid[iid] = detener
        hilo = threading.Thread(target=self._loop_polling_fila, args=(iid, ip, detener), daemon=True)
        self._hilos_por_iid[iid] = hilo

        self.tree.set(iid, 'conectar', 'Conectando...')
        self.tree.set(iid, 'estado', 'Conectando...')
        hilo.start()

    def _desconectar_fila(self, iid, silencioso=False):
        detener = self._detener_por_iid.get(iid)
        hilo = self._hilos_por_iid.get(iid)
        if detener is not None:
            detener.set()
        if hilo is not None and hilo.is_alive():
            hilo.join(timeout=2)
        self._hilos_por_iid.pop(iid, None)
        self._detener_por_iid.pop(iid, None)

        if not silencioso and self.tree.exists(iid):
            self.tree.set(iid, 'conectar', 'Conectar')
            self.tree.set(iid, 'estado', 'Desconectado')
            self.tree.set(iid, 'valor', '')
            self.tree.item(iid, tags=('desconectado',))

    def _loop_polling_fila(self, iid, ip, detener):
        """
        Corre en un hilo por fila. Crea SU PROPIA instancia de PLC -- pylogix
        recomienda no compartir una instancia entre hilos.
        """
        try:
            plc = PLC(ip)
        except Exception as e:
            self.cola.put((iid, 'estado', (f'Error: {e}', COLOR_ERROR)))
            return

        # Prueba de conexión real al conectar (PLC(ip) solo guarda la IP,
        # no conecta de verdad hasta el primer Read/Write). GetPLCTime() no
        # necesita saber ningún tag.
        try:
            prueba = plc.GetPLCTime()
            if getattr(prueba, 'Status', None) == 'Success':
                self.cola.put((iid, 'estado', ('Conectado', COLOR_EXITO)))
                self.cola.put((iid, 'conectar', 'Desconectar'))
            else:
                self.cola.put((iid, 'estado', (f'Advertencia: {prueba.Status}', COLOR_PENDIENTE)))
                self.cola.put((iid, 'conectar', 'Desconectar'))
        except Exception as e:
            self.cola.put((iid, 'estado', (f'Sin respuesta: {e}', COLOR_ERROR)))
            self.cola.put((iid, 'conectar', 'Desconectar'))
            # No se corta el hilo: si el equipo no soporta GetPLCTime pero sí
            # Read/Write, el ciclo de abajo lo confirma en cuanto haya un tag.

        while not detener.is_set():
            with self.lock:
                datos = dict(self.entradas_por_iid.get(iid, {}))
            tag = datos.get('tag')
            polling_ms = datos.get('polling_ms', POLLING_DEFAULT_MS)

            if tag:
                if datos.get('forzar') and datos.get('valor_forzado'):
                    try:
                        valor = logix_tools.convertir_valor(datos['valor_forzado'])
                        plc.Write(tag, valor)
                    except Exception:
                        pass  # el error se refleja en el próximo Read

                try:
                    r = plc.Read(tag)
                    if r.Status == 'Success':
                        self.cola.put((iid, 'valor', (r.Value, r.Status)))
                        self.cola.put((iid, 'estado', ('Conectado', COLOR_EXITO)))
                    else:
                        # Antes cualquier respuesta se mostraba como "Conectado"
                        # aunque el tag no existiera (Value=None).
                        self.cola.put((iid, 'valor', ('', r.Status)))
                        self.cola.put((iid, 'estado', (f'Error: {r.Status}', COLOR_ERROR)))
                except Exception as e:
                    self.cola.put((iid, 'estado', (f'Error de lectura: {e}', COLOR_ERROR)))

            time.sleep(max(polling_ms, POLLING_MIN_MS) / 1000)

        try:
            plc.Close()
        except Exception:
            pass

    # ---------------------------------------------------------
    def _procesar_cola(self):
        if self._cerrado:
            return
        try:
            while True:
                iid, tipo, dato = self.cola.get_nowait()
                if not self.tree.exists(iid):
                    continue
                if tipo == 'estado':
                    texto, color = dato
                    self.tree.set(iid, 'estado', texto)
                    if not self.entradas_por_iid.get(iid, {}).get('forzar'):
                        tag_visual = 'conectado' if color == COLOR_EXITO else 'desconectado'
                        self.tree.item(iid, tags=(tag_visual,))
                elif tipo == 'conectar':
                    self.tree.set(iid, 'conectar', dato)
                elif tipo == 'valor':
                    valor, status = dato
                    self.tree.set(iid, 'valor', str(valor))
        except queue.Empty:
            pass
        if not self._cerrado:
            self._after_id = self.window.after(80, self._procesar_cola)

    # ---------------------------------------------------------
    def cerrar(self):
        self._cerrado = True
        if self._after_id is not None:
            try:
                self.window.after_cancel(self._after_id)
            except Exception:
                pass
        # Desconectar todas las filas (espera a que cada hilo termine) ANTES
        # de destruir la ventana -- evita threads vivos tocando objetos de
        # Tkinter en el instante en que se empiezan a limpiar.
        for iid in list(self._hilos_por_iid.keys()):
            self._desconectar_fila(iid, silencioso=True)
        self.window.destroy()

    def ejecutar(self):
        self.root.wait_window(self.window)


def abrir_logix(ip_inicial, root, carpeta_registros=None):
    """Punto de entrada usado por eliza2.py."""
    ventana = LogixWindow(ip_inicial, root, carpeta_registros)
    ventana.ejecutar()
