"""
scanner_window.py
------------------
Ventana gráfica (Tkinter) para escanear una carpeta en busca de proyectos
ACD/L5K y registrarlos en la base de datos de Eliza (config_json/acd.json).

Módulo independiente: no depende del núcleo de consola (eliza2.py), solo de
acd_tools.py. Se invoca desde eliza2.py con /scan_acd.

Estética "consola": fondo negro, texto verde/cian, fuente monoespaciada.
"""

import os
import datetime as dt
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

import acd_tools
import estilo_consola as estilo


class ScannerWindow:
    def __init__(self, ruta_acd_json, base_dir, root):
        self.ruta_acd_json = ruta_acd_json
        self.base_dir = base_dir
        self.root = root  # raíz de Tkinter compartida por toda la sesión de Eliza
        self.hubo_cambios = False  # para que eliza2.py sepa si debe recargar mapa_comandos

        # Toplevel de la raíz compartida, NO un Tk() propio -- crear varias
        # Tk() en el mismo proceso causa errores de Tcl al cerrarlas.
        self.window = tk.Toplevel(root)
        estilo.aplicar_estilo_base(self.window, "ELIZA :: scan_acd", "950x560")
        self.window.overrideredirect(True)  # sin barra de título
        self.window.bind('<Escape>', lambda e: self.window.destroy())  # ESC cierra/aborta

        self.sort_column = "Última fecha"
        self.sort_reverse = True
        self.src_var = tk.StringVar()

        self._construir_ui()

    # ---------------------------------------------------------
    def _construir_ui(self):
        top_frame = ttk.Frame(self.window, style="TLabel")
        top_frame.pack(fill='x', padx=10, pady=10)

        ttk.Label(top_frame, text='Carpeta Origen>', width=16).pack(side='left')
        entry = tk.Entry(top_frame, textvariable=self.src_var, bg=estilo.ENTRY_BG, fg=estilo.FG_DATA,
                          insertbackground=estilo.FG, font=estilo.FONT_MONO, borderwidth=0)
        entry.pack(side='left', fill='x', expand=True, padx=5)
        ttk.Button(top_frame, text='Elegir...', command=self.elegir_carpeta).pack(side='left')

        cols = ('Archivo', 'Última fecha', 'Ubicación', 'Ruta completa', 'IP')
        self.tree = ttk.Treeview(self.window, columns=cols, show='headings', selectmode='browse')
        self.tree.column('Archivo', width=260, anchor='w')
        self.tree.column('Última fecha', width=150, anchor='w')
        self.tree.column('Ubicación', width=420, anchor='w')
        self.tree.column('Ruta completa', width=0, stretch=tk.NO)
        self.tree.column('IP', width=0, stretch=tk.NO)
        self.tree.heading('Archivo', text='Archivo')
        self.tree.heading('Última fecha', text='Última fecha', command=lambda: self.ordenar_por('Última fecha'))
        self.tree.heading('Ubicación', text='Ubicación')
        self.tree.pack(fill='both', expand=True, padx=10, pady=(0, 5))

        status_frame = ttk.Frame(self.window, style="TLabel")
        status_frame.pack(fill='x', padx=10, pady=(0, 10))
        ttk.Label(status_frame, text="[clic derecho] abrir archivo / abrir ubicación / agregar a base de datos").pack(side='left')

        self.context_menu = estilo.crear_menu_contextual(self.window)
        self.context_menu.add_command(label="Abrir archivo", command=self.abrir_archivo)
        self.context_menu.add_command(label="Abrir ubicación", command=self.abrir_carpeta)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Agregar a Base de Datos...", command=self.agregar_a_bd)
        self.tree.bind("<Button-3>", self.mostrar_menu_contextual)

    # ---------------------------------------------------------
    def elegir_carpeta(self):
        directorio = filedialog.askdirectory(title="Seleccionar carpeta de origen", parent=self.window)
        if directorio:
            self.src_var.set(directorio)
            self.escanear()

    def escanear(self):
        carpeta = self.src_var.get()
        if not carpeta or not os.path.isdir(carpeta):
            messagebox.showerror("Error", "Selecciona una carpeta válida.", parent=self.window)
            return

        self.tree.delete(*self.tree.get_children())
        self.window.config(cursor="watch")
        self.window.update()

        resultados = acd_tools.buscar_archivos_acd(carpeta)

        self.window.config(cursor="")

        if not resultados:
            messagebox.showinfo(
                "Sin resultados",
                f"No se encontraron archivos con las extensiones: {', '.join(acd_tools.VALID_EXTS)}",
                parent=self.window
            )
            return

        for info in resultados:
            ubicacion = self._truncar_ruta(os.path.dirname(info['fullpath']))
            self.tree.insert('', 'end', values=(
                info['file'], info['latest_ts_str'], ubicacion, info['fullpath'], info['ip_detectada']
            ))

        self.ordenar_por(self.sort_column, inicial=True)

    def _truncar_ruta(self, ruta):
        try:
            partes = os.path.normpath(ruta).split(os.sep)
            return os.path.join("...", *partes[-3:]) if len(partes) > 3 else ruta
        except Exception:
            return ruta

    def ordenar_por(self, columna, inicial=False):
        if self.sort_column == columna and not inicial:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = columna
            self.sort_reverse = True  # por defecto, la más nueva primero

        datos = [(self.tree.set(item, columna), item) for item in self.tree.get_children('')]

        if columna == 'Última fecha':
            def clave(x):
                try:
                    return dt.datetime.strptime(x[0], '%Y-%m-%d %H:%M:%S')
                except (ValueError, IndexError):
                    return dt.datetime.min
            datos.sort(key=clave, reverse=self.sort_reverse)
        else:
            datos.sort(key=lambda x: x[0].lower(), reverse=self.sort_reverse)

        for index, (_, item) in enumerate(datos):
            self.tree.move(item, '', index)

        self.tree.heading(columna, command=lambda: self.ordenar_por(columna))

    # ---------------------------------------------------------
    def mostrar_menu_contextual(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self.context_menu.post(event.x_root, event.y_root)

    def _seleccion_actual(self):
        seleccion = self.tree.selection()
        if not seleccion:
            return None
        return self.tree.item(seleccion[0], 'values')

    def _abrir(self, ruta):
        try:
            os.startfile(ruta)
        except OSError as e:
            messagebox.showerror("Error", f"No se pudo abrir:\n{ruta}\n\n{e}", parent=self.window)

    def abrir_archivo(self):
        valores = self._seleccion_actual()
        if valores:
            self._abrir(valores[3])

    def abrir_carpeta(self):
        valores = self._seleccion_actual()
        if valores:
            self._abrir(os.path.dirname(valores[3]))

    def agregar_a_bd(self):
        valores = self._seleccion_actual()
        if not valores:
            return
        original_filepath, ip_detectada = valores[3], valores[4]

        linea = simpledialog.askstring("Paso 1/3: Línea", "Número de LÍNEA:", parent=self.window)
        if not linea:
            return
        estacion = simpledialog.askstring("Paso 2/3: Estación", "Número de ESTACIÓN:", parent=self.window)
        if not estacion:
            return
        ip = simpledialog.askstring(
            "Paso 3/3: IP", "IP principal del equipo:",
            parent=self.window, initialvalue=ip_detectada or ""
        )
        if not ip:
            return

        linea, estacion, ip = linea.strip(), estacion.strip(), ip.strip()
        nombre = acd_tools.nombre_entrada(linea, estacion)
        if acd_tools.buscar_por_nombre(self.ruta_acd_json, nombre) is not None:
            if not messagebox.askyesno(
                "Ya existe",
                f"Ya hay una entrada '{nombre}' en la base de datos ACD.\n\n"
                "¿Reemplazarla con este archivo? (se conserva su comentario)",
                parent=self.window
            ):
                return

        entry, reemplazada, error = acd_tools.registrar_acd(
            original_filepath, self.base_dir, linea, estacion, ip, self.ruta_acd_json
        )

        if error:
            messagebox.showerror("Error", error, parent=self.window)
            return

        self.hubo_cambios = True
        accion = "actualizó" if reemplazada else "agregó"
        messagebox.showinfo(
            "Éxito",
            f"Se {accion} la entrada '{entry['name']}' en la base de datos ACD.",
            parent=self.window
        )

    # ---------------------------------------------------------
    def ejecutar(self):
        """Bloquea hasta que la ventana se cierre. Devuelve True si hubo cambios en acd.json."""
        self.root.wait_window(self.window)
        return self.hubo_cambios


def abrir_scanner_acd(ruta_acd_json, base_dir, root):
    """Punto de entrada usado por eliza2.py."""
    ventana = ScannerWindow(ruta_acd_json, base_dir, root)
    return ventana.ejecutar()
