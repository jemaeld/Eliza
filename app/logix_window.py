"""
logix_window.py
------------------
/logix: MONITOR DE VARIABLES Allen-Bradley (Logix) vía pylogix, con
escritura controlada de 1 a N veces.

Cada FILA es una conexión independiente: su propia IP, su propio polling y
su propio hilo de sondeo. Columnas:

    CONEX | IP | POLL | TAG | VALOR | ESCRITURA | COMENTARIO

- CONEX: ● ON / ○ OFF / … conectando / × ERR. Clic para conectar o
  desconectar. El detalle del error aparece en la barra de estado de abajo
  al seleccionar la fila.
- TAG: "+ Agregar" (Ctrl+N) y doble clic en TAG abren el asistente de tags
  (logix_tag_dialog): scope, programa y tag leídos del PLC.
- IP, POLL y COMENTARIO se editan con doble clic en la celda. Cambiar la IP
  de una fila conectada la reconecta.
- ESCRITURA: "Escribir…" (Ctrl+E) o doble clic en VALOR/ESCRITURA abre la
  ventana de escritura (logix_escritura): un valor 1..N veces (o continuo)
  al ritmo del polling de la fila, con indicador IDLE / WORKING / DONE.
- "Guardar/Cargar registro": IP, polling, tag y comentario en JSON. Las
  escrituras no se guardan: una fila cargada nunca escribe sola.

Hilos: pylogix no debe compartir una instancia de PLC entre hilos, así que
cada fila crea su conexión dentro de su hilo. El hilo lee el tag y, si la
fila tiene una escritura en curso, escribe antes de leer (así la lectura
muestra el efecto). La GUI solo da órdenes y muestra resultados.

Esc cierra el monitor (detiene escrituras y desconecta todo).
"""

import json
import os
import queue
import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox, filedialog

import estilo_consola as estilo
import logix_escritura
import logix_explorador
import logix_tag_dialog
import logix_tools

try:
    from pylogix import PLC
    PYLOGIX_DISPONIBLE = True
except ImportError:
    PLC = None
    PYLOGIX_DISPONIBLE = False

POLLING_MIN_MS = logix_tools.POLLING_MIN_MS
POLLING_DEFAULT_MS = logix_tools.POLLING_DEFAULT_MS

COLOR_EXITO = "#00ff00"
COLOR_ERROR = "#ff5555"
COLOR_PENDIENTE = "#ffcc00"

CONEX_OFF = "○ OFF"
CONEX_CONECTANDO = "…"
CONEX_ON = "● ON"
CONEX_ERROR = "× ERR"

COLUMNAS = ('conexion', 'ip', 'polling', 'tag', 'valor', 'escritura', 'comentario')
ENCABEZADOS = {'conexion': 'CONEX', 'ip': 'IP', 'polling': 'POLL', 'tag': 'TAG', 'valor': 'VALOR',
               'escritura': 'ESCRITURA', 'comentario': 'COMENTARIO'}
ANCHOS = {'conexion': 70, 'ip': 120, 'polling': 55, 'tag': 340, 'valor': 160, 'escritura': 160,
          'comentario': 300}
EDICION_EN_CELDA = ('ip', 'polling', 'comentario')
ABREN_ESCRITURA = ('valor', 'escritura')

TIPOS_ARCHIVO = [("Registro de tags (JSON)", "*.json"), ("Todos los archivos", "*.*")]


class LogixWindow:
    def __init__(self, ip_inicial, root, carpeta_registros=None):
        self.ip_inicial = ip_inicial
        self.root = root

        self.lock = threading.Lock()
        self.entradas_por_iid = {}   # iid -> ver agregar_fila()
        self._hilos_por_iid = {}
        self._detener_por_iid = {}
        self._ventanas_escritura = {}  # iid -> VentanaEscritura
        self._contador_iid = 0
        self._cerrado = False
        self.cola = queue.Queue()
        self.editor_entry = None
        self._after_id = None
        self._ultima_carpeta = carpeta_registros or os.getcwd()
        self.explorador = logix_explorador.ExploradorPLC()
        self._ultima_ip = ip_inicial or ""

        self.window = tk.Toplevel(root)
        estilo.aplicar_estilo_base(self.window, "ELIZA :: logix", "1260x560")
        self.window.overrideredirect(True)
        self.window.bind('<Escape>', lambda e: self.cerrar())
        self.window.bind('<Control-n>', lambda e: self.asistente_agregar())
        self.window.bind('<Control-e>', lambda e: self.abrir_escritura())
        self.window.bind('<Delete>', lambda e: self.eliminar_fila())

        self._construir_ui()

        if not PYLOGIX_DISPONIBLE:
            messagebox.showerror("Falta pylogix",
                                 "No se encontró la librería 'pylogix'. Instálala con:\n\npip install pylogix",
                                 parent=self.window)
        elif self.ip_inicial:
            self.window.after(200, self.asistente_agregar)

        self._after_id = self.window.after(80, self._procesar_cola)

    # ---------------------------------------------------------
    def _construir_ui(self):
        barra = ttk.Frame(self.window, style="TLabel")
        barra.pack(fill='x', padx=10, pady=10)
        ttk.Label(barra, text="MONITOR DE VARIABLES", font=estilo.FONT_MONO_BOLD).pack(side='left', padx=(0, 16))
        ttk.Button(barra, text="+ Agregar", command=self.asistente_agregar).pack(side='left')
        ttk.Button(barra, text="- Eliminar", command=self.eliminar_fila).pack(side='left', padx=5)
        ttk.Button(barra, text="Escribir…", command=self.abrir_escritura).pack(side='left', padx=(0, 16))
        ttk.Button(barra, text="Guardar registro", command=self.guardar_registro).pack(side='left')
        ttk.Button(barra, text="Cargar registro", command=self.cargar_registro).pack(side='left', padx=5)
        ttk.Button(barra, text="Detener escrituras", command=self.detener_todas_escrituras).pack(side='right')

        self.tree = ttk.Treeview(self.window, columns=COLUMNAS, show='headings', selectmode='extended')
        for col in COLUMNAS:
            self.tree.heading(col, text=ENCABEZADOS[col])
            self.tree.column(col, width=ANCHOS[col], minwidth=40, anchor='center' if col == 'conexion' else 'w',
                             stretch=col in ('tag', 'comentario'))
        self.tree.pack(fill='both', expand=True, padx=10, pady=(0, 4))
        self.tree.tag_configure('conectado', foreground=COLOR_EXITO)
        self.tree.tag_configure('desconectado', foreground=COLOR_PENDIENTE)
        self.tree.tag_configure('error', foreground=COLOR_ERROR)
        self.tree.tag_configure('escribiendo', background='#4a3b00', foreground='#ffe066')

        self.tree.bind('<Double-1>', self._on_double_click)
        self.tree.bind('<Button-1>', self._on_single_click)
        self.tree.bind('<<TreeviewSelect>>', lambda e: self._actualizar_barra_estado())

        self.var_barra = tk.StringVar()
        tk.Label(self.window, textvariable=self.var_barra, bg=estilo.ENTRY_BG, fg=estilo.FG_DATA,
                 font=estilo.FONT_MONO, anchor='w', padx=8, pady=3).pack(fill='x', padx=10)
        ttk.Label(self.window,
                  text="Clic en CONEX: conectar/desconectar · Doble clic: TAG asistente · VALOR/ESCRITURA escribir · "
                       "IP/POLL/COMENTARIO editar · Ctrl+N agregar · Ctrl+E escribir · Supr eliminar · Esc cierra"
                  ).pack(fill='x', padx=10, pady=(4, 10))

    def _siguiente_iid(self):
        self._contador_iid += 1
        return str(self._contador_iid)

    # ---------------------------------------------------------
    # Filas
    def agregar_fila(self, ip="", polling_ms=POLLING_DEFAULT_MS, tag="", comentario=""):
        iid = self._siguiente_iid()
        with self.lock:
            self.entradas_por_iid[iid] = {
                'ip': ip, 'polling_ms': polling_ms, 'tag': tag, 'comentario': comentario,
                'trabajo': logix_tools.TrabajoEscritura(),
                # solo los toca el hilo de la GUI:
                'valor': '', 'conexion': CONEX_OFF, 'estado_texto': 'Desconectado',
            }
        self.tree.insert('', 'end', iid=iid, values=(CONEX_OFF, ip, str(polling_ms), tag, '', '', comentario),
                         tags=('desconectado',))
        self.tree.selection_set(iid)
        self.tree.see(iid)
        return iid

    def fila(self, iid):
        """Copia del estado de una fila para las ventanas auxiliares (o None si ya no existe)."""
        with self.lock:
            e = self.entradas_por_iid.get(iid)
            if e is None:
                return None
            t = e['trabajo']
            trabajo = {'estado': t.estado, 'valor_texto': t.valor_texto, 'total': t.total, 'hechas': t.hechas,
                       'errores': t.errores, 'ultimo_status': t.ultimo_status, 'mensaje': t.mensaje,
                       'progreso': t.progreso_texto(), 'corrida': t.corrida, 'historial': list(t.historial)}
            return {'ip': e['ip'], 'tag': e['tag'], 'polling_ms': e['polling_ms'], 'valor': e['valor'],
                    'conexion': e['conexion'], 'estado_texto': e['estado_texto'], 'trabajo': trabajo}

    def eliminar_fila(self):
        if self.editor_entry is not None:
            return  # Supr dentro de una celda en edición no debe borrar la fila
        for iid in self.tree.selection():
            self._quitar_fila(iid)

    def _quitar_fila(self, iid):
        self._desconectar_fila(iid, silencioso=True)
        with self.lock:
            self.entradas_por_iid.pop(iid, None)
        if self.tree.exists(iid):
            self.tree.delete(iid)
        ventana = self._ventanas_escritura.pop(iid, None)
        if ventana:
            ventana.cerrar()

    def _fila_conectada(self, iid):
        hilo = self._hilos_por_iid.get(iid)
        return hilo is not None and hilo.is_alive()

    def _seleccion(self):
        seleccion = self.tree.selection()
        return seleccion[0] if seleccion and seleccion[0] in self.entradas_por_iid else None

    # ---------------------------------------------------------
    # Asistente de tags
    def _ip_sugerida(self):
        iid = self._seleccion()
        if iid:
            return self.entradas_por_iid[iid].get('ip') or self._ultima_ip
        return self._ultima_ip

    def asistente_agregar(self):
        if self._cerrado:
            return
        datos = logix_tag_dialog.abrir_dialogo_tag(self.window, self.explorador, ip=self._ip_sugerida())
        if datos:
            self._ultima_ip = datos['ip']
            self.agregar_fila(ip=datos['ip'], tag=datos['tag'], comentario=datos['comentario'])

    def asistente_editar(self, iid):
        entrada = self.entradas_por_iid.get(iid)
        if not entrada:
            return
        datos = logix_tag_dialog.abrir_dialogo_tag(
            self.window, self.explorador, ip=entrada.get('ip', ''), tag=entrada.get('tag', ''),
            comentario=entrada.get('comentario', ''), editar=True)
        if not datos or iid not in self.entradas_por_iid:
            return
        self._ultima_ip = datos['ip']
        self._aplicar_edicion(iid, 'tag', datos['tag'])
        self._aplicar_edicion(iid, 'comentario', datos['comentario'])
        if datos['ip'] != entrada.get('ip', ''):
            self._aplicar_edicion(iid, 'ip', datos['ip'])

    # ---------------------------------------------------------
    # Escritura
    def abrir_escritura(self, iid=None):
        iid = iid or self._seleccion()
        if not iid:
            self.var_barra.set("Selecciona una fila para escribir en su tag.")
            return
        ventana = self._ventanas_escritura.get(iid)
        if ventana is not None:
            ventana.traer_al_frente()
            return
        self._ventanas_escritura[iid] = logix_escritura.VentanaEscritura(self, iid)

    def ventana_escritura_cerrada(self, iid):
        self._ventanas_escritura.pop(iid, None)

    def iniciar_escritura(self, iid, valor_texto, total):
        """Lanza ValueError con un mensaje para el usuario si no se puede iniciar."""
        entrada = self.entradas_por_iid.get(iid)
        if not entrada:
            raise ValueError("La fila ya no existe.")
        if not entrada['tag']:
            raise ValueError("La fila no tiene tag.")
        if not entrada['ip']:
            raise ValueError("La fila no tiene IP.")
        with self.lock:
            entrada['trabajo'].iniciar(valor_texto, total)
        if not self._fila_conectada(iid):
            self._conectar_fila(iid)  # la escritura empieza en cuanto conecte
        self._refrescar_fila(iid)

    def detener_escritura(self, iid):
        with self.lock:
            entrada = self.entradas_por_iid.get(iid)
            if entrada:
                entrada['trabajo'].detener()
        self._refrescar_fila(iid)

    def reiniciar_escritura(self, iid):
        with self.lock:
            entrada = self.entradas_por_iid.get(iid)
            if entrada:
                entrada['trabajo'].reiniciar()
        self._refrescar_fila(iid)

    def detener_todas_escrituras(self):
        with self.lock:
            for entrada in self.entradas_por_iid.values():
                entrada['trabajo'].detener()
        for iid in self.tree.get_children(''):
            self._refrescar_fila(iid)

    # ---------------------------------------------------------
    # Guardar / cargar registro de tags (JSON)
    def guardar_registro(self):
        with self.lock:
            filas = [
                {'ip': self.entradas_por_iid[iid]['ip'], 'polling_ms': self.entradas_por_iid[iid]['polling_ms'],
                 'tag': self.entradas_por_iid[iid]['tag'],
                 'comentario': self.entradas_por_iid[iid].get('comentario', '')}
                for iid in self.tree.get_children('') if iid in self.entradas_por_iid
            ]
        if not filas:
            messagebox.showinfo("Sin tags", "No hay filas para guardar.", parent=self.window)
            return
        ruta = filedialog.asksaveasfilename(
            parent=self.window, title="Guardar registro de tags", initialdir=self._ultima_carpeta,
            initialfile="registro_logix.json", defaultextension=".json", filetypes=TIPOS_ARCHIVO)
        if not ruta:
            return
        try:
            n = logix_tools.guardar_registro(ruta, filas)
        except OSError as e:
            messagebox.showerror("Error al guardar", f"No se pudo escribir el archivo:\n{e}", parent=self.window)
            return
        self._ultima_carpeta = os.path.dirname(ruta)
        messagebox.showinfo("Registro guardado",
                            f"Se guardaron {n} tag(s) en:\n{ruta}\n\n(Las escrituras no se guardan.)",
                            parent=self.window)

    def cargar_registro(self):
        ruta = filedialog.askopenfilename(parent=self.window, title="Cargar registro de tags",
                                          initialdir=self._ultima_carpeta, filetypes=TIPOS_ARCHIVO)
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
        if self.tree.get_children(''):
            respuesta = messagebox.askyesnocancel(
                "Cargar registro",
                f"El registro tiene {len(filas)} tag(s).\n\n"
                "Sí = REEMPLAZAR las filas actuales (se desconectan y se detienen sus escrituras)\n"
                "No = AGREGAR al final de las actuales\n"
                "Cancelar = no hacer nada",
                parent=self.window)
            if respuesta is None:
                return
            if respuesta:
                for iid in list(self.tree.get_children('')):
                    self._quitar_fila(iid)
        for fila in filas:
            self.agregar_fila(ip=fila['ip'], polling_ms=fila['polling_ms'], tag=fila['tag'],
                              comentario=fila['comentario'])

    # ---------------------------------------------------------
    # Clics
    def _columna_en(self, event):
        if self.tree.identify('region', event.x, event.y) != 'cell':
            return None, None
        row_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        if not row_id or not col_id:
            return None, None
        indice = int(col_id.replace('#', '')) - 1
        if indice < 0 or indice >= len(COLUMNAS):
            return None, None
        return row_id, COLUMNAS[indice]

    def _on_single_click(self, event):
        row_id, clave = self._columna_en(event)
        if clave == 'conexion':
            self._alternar_conexion(row_id)

    def _alternar_conexion(self, iid):
        if self._fila_conectada(iid):
            self._desconectar_fila(iid)
        else:
            self._conectar_fila(iid)

    def _on_double_click(self, event):
        if self.editor_entry is not None:
            return
        row_id, clave = self._columna_en(event)
        if not row_id:
            return
        if clave == 'tag':
            self.asistente_editar(row_id)
        elif clave in ABREN_ESCRITURA:
            self.abrir_escritura(row_id)
        elif clave in EDICION_EN_CELDA:
            self._editar_en_celda(row_id, clave)

    def _editar_en_celda(self, row_id, clave):
        bbox = self.tree.bbox(row_id, clave)
        if not bbox:
            return
        x, y, ancho, alto = bbox
        self.editor_entry = tk.Entry(self.tree, bg=estilo.ENTRY_BG, fg=estilo.FG_DATA, insertbackground=estilo.FG,
                                     font=estilo.FONT_MONO, borderwidth=1)
        self.editor_entry.insert(0, self.tree.set(row_id, clave))
        self.editor_entry.select_range(0, tk.END)
        self.editor_entry.focus()
        self.editor_entry.place(x=x, y=y, width=max(ancho, 120), height=alto)

        def confirmar(_event=None):
            if self.editor_entry is None:
                return
            nuevo_valor = self.editor_entry.get().strip()
            self._cerrar_editor_celda()
            self._aplicar_edicion(row_id, clave, nuevo_valor)

        def cancelar(_event=None):
            self._cerrar_editor_celda()
            return 'break'

        self.editor_entry.bind('<Return>', confirmar)
        self.editor_entry.bind('<FocusOut>', confirmar)
        self.editor_entry.bind('<Escape>', cancelar)

    def _cerrar_editor_celda(self):
        if self.editor_entry is not None:
            entry, self.editor_entry = self.editor_entry, None
            entry.destroy()

    def _aplicar_edicion(self, row_id, clave, nuevo_valor):
        if row_id not in self.entradas_por_iid:
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
                    parent=self.window)
                polling = POLLING_MIN_MS
            nuevo_valor = polling
        with self.lock:
            self.entradas_por_iid[row_id]['polling_ms' if clave == 'polling' else clave] = nuevo_valor
        self.tree.set(row_id, clave, str(nuevo_valor))
        if clave == 'ip' and self._fila_conectada(row_id):
            self._conectar_fila(row_id)  # reconecta con la IP nueva
        self._actualizar_barra_estado()

    # ---------------------------------------------------------
    # Conexión e hilo de sondeo
    def _conectar_fila(self, iid):
        if not PYLOGIX_DISPONIBLE:
            messagebox.showerror("Falta pylogix", "Instálala con: pip install pylogix", parent=self.window)
            return
        ip = self.entradas_por_iid.get(iid, {}).get('ip', '').strip()
        if not ip:
            messagebox.showerror("Falta IP", "Esta fila no tiene IP.", parent=self.window)
            return
        # Se espera a que termine una conexión previa de la fila antes de abrir otra.
        self._desconectar_fila(iid, silencioso=True, detener_escritura=False)
        detener = threading.Event()
        self._detener_por_iid[iid] = detener
        hilo = threading.Thread(target=self._loop_polling_fila, args=(iid, ip, detener), daemon=True)
        self._hilos_por_iid[iid] = hilo
        self._poner_conexion(iid, CONEX_CONECTANDO, "Conectando...")
        hilo.start()

    def _desconectar_fila(self, iid, silencioso=False, detener_escritura=True):
        detener = self._detener_por_iid.get(iid)
        hilo = self._hilos_por_iid.get(iid)
        if detener is not None:
            detener.set()
        if hilo is not None and hilo.is_alive():
            hilo.join(timeout=2)
        self._hilos_por_iid.pop(iid, None)
        self._detener_por_iid.pop(iid, None)
        if detener_escritura:
            with self.lock:
                entrada = self.entradas_por_iid.get(iid)
                if entrada:
                    entrada['trabajo'].detener("Detenido (desconectado)")
        if not silencioso and self.tree.exists(iid):
            self._poner_conexion(iid, CONEX_OFF, "Desconectado")
            self._poner_valor(iid, '')
            self._refrescar_fila(iid)

    def _loop_polling_fila(self, iid, ip, detener):
        """Hilo de la fila: escribe (si hay escritura en curso) y lee, cada 'polling' ms."""
        try:
            plc = PLC(ip)
        except Exception as e:
            self.cola.put((iid, 'conexion', (CONEX_ERROR, f'Error: {e}')))
            return

        try:
            prueba = plc.GetPLCTime()
            if getattr(prueba, 'Status', None) == 'Success':
                self.cola.put((iid, 'conexion', (CONEX_ON, 'Conectado')))
            else:
                self.cola.put((iid, 'conexion', (CONEX_ERROR, f'Sin respuesta: {prueba.Status}')))
        except Exception as e:
            # No se corta el hilo: si el equipo no soporta GetPLCTime pero sí
            # Read/Write, el ciclo de abajo lo confirma en cuanto haya un tag.
            self.cola.put((iid, 'conexion', (CONEX_ERROR, f'Sin respuesta: {e}')))

        while not detener.is_set():
            with self.lock:
                entrada = self.entradas_por_iid.get(iid)
                if entrada is None:
                    break
                tag = entrada['tag']
                polling_ms = entrada['polling_ms']
                trabajo = entrada['trabajo']
                escribir = trabajo.estado == logix_tools.WORKING
                corrida, valor = trabajo.corrida, trabajo.valor

            if tag:
                if escribir:
                    try:
                        status = plc.Write(tag, valor).Status
                    except Exception as e:
                        status = f'Error: {e}'
                    hora = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    with self.lock:
                        trabajo.registrar(corrida, status, hora)
                try:
                    r = plc.Read(tag)
                    if r.Status == 'Success':
                        self.cola.put((iid, 'valor', r.Value))
                        self.cola.put((iid, 'conexion', (CONEX_ON, 'Conectado')))
                    else:
                        self.cola.put((iid, 'valor', ''))
                        self.cola.put((iid, 'conexion', (CONEX_ERROR, f'Error de lectura: {r.Status}')))
                except Exception as e:
                    self.cola.put((iid, 'conexion', (CONEX_ERROR, f'Error de lectura: {e}')))

            detener.wait(max(polling_ms, POLLING_MIN_MS) / 1000)

        try:
            plc.Close()
        except Exception:
            pass

    # ---------------------------------------------------------
    # Pintar la tabla (siempre en el hilo de la GUI)
    def _poner_conexion(self, iid, simbolo, texto):
        entrada = self.entradas_por_iid.get(iid)
        if entrada is None or not self.tree.exists(iid):
            return
        entrada['conexion'], entrada['estado_texto'] = simbolo, texto
        self.tree.set(iid, 'conexion', simbolo)

    def _poner_valor(self, iid, valor):
        entrada = self.entradas_por_iid.get(iid)
        if entrada is None or not self.tree.exists(iid):
            return
        entrada['valor'] = '' if valor is None else str(valor)
        self.tree.set(iid, 'valor', entrada['valor'])

    def _refrescar_fila(self, iid):
        """Columna ESCRITURA y color de la fila según conexión y escritura."""
        entrada = self.entradas_por_iid.get(iid)
        if entrada is None or not self.tree.exists(iid):
            return
        with self.lock:
            trabajo = entrada['trabajo']
            texto = trabajo.texto_columna() if (trabajo.corrida or trabajo.estado != logix_tools.IDLE) else ''
            escribiendo = trabajo.estado == logix_tools.WORKING
        if self.tree.set(iid, 'escritura') != texto:
            self.tree.set(iid, 'escritura', texto)
        if escribiendo:
            etiqueta = 'escribiendo'
        elif entrada['conexion'] == CONEX_ON:
            etiqueta = 'conectado'
        elif entrada['conexion'] == CONEX_ERROR:
            etiqueta = 'error'
        else:
            etiqueta = 'desconectado'
        if self.tree.item(iid, 'tags') != (etiqueta,):
            self.tree.item(iid, tags=(etiqueta,))

    def _actualizar_barra_estado(self):
        iid = self._seleccion()
        if not iid:
            self.var_barra.set(f"{len(self.entradas_por_iid)} variable(s) · selecciona una fila para ver su detalle")
            return
        fila = self.fila(iid)
        texto = f"{fila['tag'] or '(sin tag)'}  @ {fila['ip'] or '(sin IP)'}  ·  {fila['estado_texto']}"
        t = fila['trabajo']
        if t['estado'] != logix_tools.IDLE or t['mensaje']:
            texto += f"  ·  escritura {t['estado']} {t['progreso']}"
            if t['ultimo_status'] and t['ultimo_status'] != 'Success':
                texto += f" (última: {t['ultimo_status']})"
        if self.var_barra.get() != texto:
            self.var_barra.set(texto)

    def _procesar_cola(self):
        if self._cerrado:
            return
        try:
            while True:
                iid, tipo, dato = self.cola.get_nowait()
                if not self.tree.exists(iid) or not self._fila_conectada(iid):
                    continue  # mensaje viejo de un hilo ya detenido
                if tipo == 'conexion':
                    self._poner_conexion(iid, *dato)
                elif tipo == 'valor':
                    self._poner_valor(iid, dato)
        except queue.Empty:
            pass
        for iid in self.tree.get_children(''):
            self._refrescar_fila(iid)
        self._actualizar_barra_estado()
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
        for ventana in list(self._ventanas_escritura.values()):
            ventana.cerrar()
        # Detener escrituras y desconectar todo ANTES de destruir la ventana:
        # evita hilos vivos tocando objetos de Tkinter mientras se limpian.
        for iid in list(self._hilos_por_iid.keys()):
            self._desconectar_fila(iid, silencioso=True)
        self.window.destroy()

    def ejecutar(self):
        self.root.wait_window(self.window)


def abrir_logix(ip_inicial, root, carpeta_registros=None):
    """Punto de entrada usado por eliza2.py."""
    ventana = LogixWindow(ip_inicial, root, carpeta_registros)
    ventana.ejecutar()
