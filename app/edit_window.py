"""
edit_window.py
----------------
Editor de tabla GENÉRICO para los archivos JSON de config_json/ (vnc.json,
apps.json, acd.json, y cualquier otro que se agregue a futuro).

No conoce categorías de antemano: recibe la ruta de un JSON, detecta las
columnas a partir de las claves que ya usan sus entradas (name, action, info,
ip, ...) y arma la tabla dinámicamente. Así, si el día de mañana agregas
otro archivo de base de datos con otras claves, este mismo módulo lo edita
sin cambios.

Edición inline: doble clic sobre una celda para editarla (Enter confirma,
Esc cancela). Botones para agregar/eliminar filas y guardar cambios en disco.

Estética "consola", igual que scanner_window.py.

ESC cierra la ventana; si hay cambios sin guardar, primero pregunta.
"""

import os
import re
import tkinter as tk
from tkinter import ttk, messagebox

import estilo_consola as estilo
import json_db
import acd_tools

# Orden preferido de columnas cuando existen (el resto se agrega después,
# en el orden en que aparezcan en los datos).
ORDEN_PREFERIDO = ['name', 'action', 'info', 'ip', 'comentario']


class EditTableWindow:
    def __init__(self, categoria, ruta_json, root):
        self.categoria = categoria
        self.ruta_json = ruta_json
        # config_json/<archivo>.json -> la carpeta de datos es dos niveles arriba
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(ruta_json)))
        self.root = root  # raíz de Tkinter compartida por toda la sesión de Eliza

        # Lectura estricta: si el archivo está dañado, NO se abre el editor
        # (guardar desde una tabla vacía borraría todo su contenido).
        self.filas = json_db.cargar_lista(ruta_json, estricto=True)
        self.claves = self._detectar_columnas(self.filas)

        self.entradas_por_iid = {}
        self._contador_iid = 0
        self.cambios_sin_guardar = False
        self.se_guardo_algo = False  # esto es lo que le importa a eliza2.py (recargar o no)
        self.editor_entry = None
        self._confirmar_pendiente = None

        # Toplevel de la raíz compartida, NO un Tk() propio -- crear varias
        # Tk() en el mismo proceso causa errores de Tcl al cerrarlas.
        self.window = tk.Toplevel(root)
        estilo.aplicar_estilo_base(self.window, f"ELIZA :: edit [{categoria}]", "1000x560")
        self.window.overrideredirect(True)  # sin barra de título

        self._construir_ui()
        self._poblar_tabla()

        self.window.protocol("WM_DELETE_WINDOW", self.al_cerrar)
        self.window.bind('<Control-s>', lambda e: self.guardar())
        self.window.bind('<Escape>', lambda e: self.al_cerrar())  # pregunta solo si hay cambios sin guardar

    def _detectar_columnas(self, datos):
        claves_encontradas = []
        for entrada in datos:
            for clave in entrada.keys():
                if clave not in claves_encontradas:
                    claves_encontradas.append(clave)

        claves_ordenadas = [c for c in ORDEN_PREFERIDO if c in claves_encontradas]
        claves_ordenadas += [c for c in claves_encontradas if c not in claves_ordenadas]

        return claves_ordenadas or list(ORDEN_PREFERIDO)  # archivo vacío -> esquema por defecto

    # ---------------------------------------------------------
    def _construir_ui(self):
        barra = ttk.Frame(self.window, style="TLabel")
        barra.pack(fill='x', padx=10, pady=10)

        ttk.Label(
            barra, text=f"Editando: config_json/{os.path.basename(self.ruta_json)}",
            font=estilo.FONT_MONO_BOLD
        ).pack(side='left')

        ttk.Button(barra, text="Guardar (Ctrl+S)", command=self.guardar).pack(side='right')
        ttk.Button(barra, text="- Eliminar fila", command=self.eliminar_fila).pack(side='right', padx=5)
        ttk.Button(barra, text="+ Agregar fila", command=self.agregar_fila).pack(side='right')
        ttk.Button(barra, text="Ordenar A-Z", command=self.ordenar_a_z).pack(side='right', padx=5)

        # "Reescanear" solo tiene sentido para ACD (archivos con fecha real
        # en disco); no aparece al editar vnc.json/apps.json.
        if self.categoria.upper() == 'ACD':
            ttk.Button(barra, text="Reescanear todos", command=self.reescanear_todos).pack(side='right', padx=5)

        self.tree = ttk.Treeview(self.window, columns=self.claves, show='headings', selectmode='extended')
        for clave in self.claves:
            ancho = 320 if clave == 'action' else 220 if clave == 'info' else 140
            self.tree.column(clave, width=ancho, anchor='w')
            self.tree.heading(clave, text=clave.upper(), command=lambda c=clave: self.ordenar_por_columna(c))
        self.tree.pack(fill='both', expand=True, padx=10, pady=(0, 5))

        pie = ttk.Frame(self.window, style="TLabel")
        pie.pack(fill='x', padx=10, pady=(0, 10))
        ttk.Label(pie, text="Doble clic: editar · Clic en encabezado: ordenar por esa columna · Ctrl+S guarda · Esc cierra").pack(side='left')

        self.tree.bind('<Double-1>', self.iniciar_edicion_celda)

    def _poblar_tabla(self):
        for entrada in self.filas:
            iid = self._siguiente_iid()
            self.entradas_por_iid[iid] = entrada
            valores = [entrada.get(clave, '') for clave in self.claves]
            self.tree.insert('', 'end', iid=iid, values=valores)

    def _siguiente_iid(self):
        self._contador_iid += 1
        return str(self._contador_iid)

    # ---------------------------------------------------------
    # Edición inline: se superpone un tk.Entry sobre la celda tocada.
    def iniciar_edicion_celda(self, event):
        if self.editor_entry is not None:
            return  # ya hay una edición en curso

        region = self.tree.identify('region', event.x, event.y)
        if region != 'cell':
            return

        row_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)  # '#1', '#2', ...
        if not row_id or not col_id:
            return

        col_index = int(col_id.replace('#', '')) - 1
        if col_index < 0 or col_index >= len(self.claves):
            return
        clave = self.claves[col_index]

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
            if self.editor_entry is None:
                return  # ya se confirmó (Enter dispara también FocusOut al destruir el Entry)
            nuevo_valor = self.editor_entry.get()
            self.tree.set(row_id, col_id, nuevo_valor)
            self.entradas_por_iid[row_id][clave] = nuevo_valor
            self.cambios_sin_guardar = True
            self._cerrar_editor_celda()

        def cancelar(_event=None):
            self._cerrar_editor_celda()
            return 'break'  # evita que este ESC también dispare el cierre de la ventana

        self.editor_entry.bind('<Return>', confirmar)
        self.editor_entry.bind('<FocusOut>', confirmar)
        self.editor_entry.bind('<Escape>', cancelar)
        self._confirmar_pendiente = confirmar

    def _cerrar_editor_celda(self):
        self._confirmar_pendiente = None
        if self.editor_entry is not None:
            entry, self.editor_entry = self.editor_entry, None
            entry.destroy()

    def _confirmar_edicion_en_curso(self):
        """Aplica el texto de una celda que se está editando (Ctrl+S sin presionar Enter)."""
        if self._confirmar_pendiente is not None:
            self._confirmar_pendiente()

    # ---------------------------------------------------------
    def agregar_fila(self):
        nueva_entrada = {clave: '' for clave in self.claves}
        iid = self._siguiente_iid()
        self.entradas_por_iid[iid] = nueva_entrada
        self.tree.insert('', 'end', iid=iid, values=['' for _ in self.claves])
        self.tree.selection_set(iid)
        self.tree.see(iid)
        self.cambios_sin_guardar = True

    def eliminar_fila(self):
        seleccion = self.tree.selection()
        if not seleccion:
            return
        if not messagebox.askyesno(
            "Confirmar", f"¿Eliminar {len(seleccion)} fila(s)?", parent=self.window
        ):
            return
        for iid in seleccion:
            self.tree.delete(iid)
            self.entradas_por_iid.pop(iid, None)
        self.cambios_sin_guardar = True

    # ---------------------------------------------------------
    def reescanear_todos(self):
        """
        Vuelve a leer la fecha de modificación actual de CADA archivo
        protegido registrado en la tabla (todas las filas, sin necesidad de
        seleccionarlas) y refresca 'info'. No copia nada -- solo relee lo
        que ya está en _acd_store/. Al terminar, reordena la tabla
        alfabéticamente por nombre.
        """
        filas = self.tree.get_children('')
        if not filas:
            messagebox.showinfo("Reescanear", "No hay entradas para reescanear.", parent=self.window)
            return

        actualizados = 0
        errores = []
        for iid in filas:
            entrada = self.entradas_por_iid.get(iid)
            if not entrada:
                continue
            nombre = entrada.get('name', '(sin nombre)')
            destino = acd_tools.resolver_ruta_action(entrada.get('action', ''), self.base_dir)

            if not destino:
                errores.append(f"{nombre}: no se pudo determinar la ruta desde 'action'.")
                continue

            info_nuevo, error = acd_tools.reescanear(destino, entrada.get('ip', ''))
            if error:
                errores.append(f"{nombre}: {error}")
                continue

            entrada['info'] = info_nuevo
            self.tree.set(iid, 'info', info_nuevo)
            self.cambios_sin_guardar = True
            actualizados += 1

        if 'name' in self.claves:
            self.ordenar_por('name')

        mensaje = f"Se actualizaron {actualizados} de {len(filas)} entrada(s)."
        if errores:
            mensaje += "\n\nNo se pudieron actualizar:\n" + "\n".join(errores)
        messagebox.showinfo("Reescanear", mensaje, parent=self.window)

    # ---------------------------------------------------------
    # Ordenar. El orden de la tabla es el que se guarda en el JSON (Ctrl+S).

    @staticmethod
    def _clave_natural(texto):
        """
        Orden "natural": los números se comparan como números, no como texto,
        así L31E5 queda antes que L31E25 y 10.140.126.9 antes que 10.140.126.10.
        """
        partes = re.split(r'(\d+)', str(texto or '').strip().lower())
        return [(0, int(p), '') if p.isdigit() else (1, 0, p) for p in partes]

    def ordenar_por(self, clave, descendente=False):
        """Reordena las filas por 'clave'. Devuelve True si el orden cambió."""
        filas = list(self.tree.get_children(''))
        ordenadas = sorted(filas, key=lambda iid: self._clave_natural(self.tree.set(iid, clave)),
                           reverse=descendente)
        for clave_col in self.claves:  # indicador ▲/▼ solo en la columna usada
            flecha = (' ▼' if descendente else ' ▲') if clave_col == clave else ''
            self.tree.heading(clave_col, text=clave_col.upper() + flecha)
        self._orden_actual = (clave, descendente)
        if ordenadas == filas:
            return False
        for indice, iid in enumerate(ordenadas):
            self.tree.move(iid, '', indice)
        self.cambios_sin_guardar = True
        return True

    def ordenar_a_z(self):
        """Botón 'Ordenar A-Z': por nombre (o por la primera columna si no hay 'name')."""
        self._confirmar_edicion_en_curso()
        self.ordenar_por('name' if 'name' in self.claves else self.claves[0])

    def ordenar_por_columna(self, clave):
        """Clic en encabezado: ascendente; otro clic en la misma columna lo invierte."""
        self._confirmar_edicion_en_curso()
        anterior = getattr(self, '_orden_actual', None)
        descendente = bool(anterior and anterior[0] == clave and not anterior[1])
        self.ordenar_por(clave, descendente)

    # ---------------------------------------------------------
    def _recolectar_datos_actuales(self):
        return [self.entradas_por_iid[iid] for iid in self.tree.get_children('')]

    def guardar(self):
        self._confirmar_edicion_en_curso()  # por si había una celda en edición sin confirmar
        datos = self._recolectar_datos_actuales()
        # descarta filas completamente vacías (ej. una fila "+ Agregar" sin llenar)
        datos_limpios = [d for d in datos if any(str(v).strip() for v in d.values())]

        try:
            json_db.guardar_lista(self.ruta_json, datos_limpios)
        except OSError as e:
            messagebox.showerror("Error", f"No se pudo guardar: {e}", parent=self.window)
            return False

        self.filas = datos_limpios
        self.cambios_sin_guardar = False
        self.se_guardo_algo = True
        messagebox.showinfo(
            "Guardado",
            f"Se guardaron {len(datos_limpios)} entradas en {os.path.basename(self.ruta_json)}.",
            parent=self.window
        )
        return True

    def al_cerrar(self):
        self._confirmar_edicion_en_curso()
        if self.cambios_sin_guardar:
            respuesta = messagebox.askyesnocancel(
                "Cambios sin guardar",
                "Hay cambios sin guardar. ¿Deseas guardarlos antes de salir?",
                parent=self.window
            )
            if respuesta is None:
                return  # cancelar el cierre
            if respuesta and not self.guardar():
                return  # no se pudo guardar: la ventana sigue abierta
        self.window.destroy()

    # ---------------------------------------------------------
    def ejecutar(self):
        """Bloquea hasta que la ventana se cierre. Devuelve True si se guardó algo en disco."""
        self.root.wait_window(self.window)
        return self.se_guardo_algo


def abrir_editor_tabla(categoria, ruta_json, root):
    """Punto de entrada usado por eliza2.py. Devuelve True si se guardó algo."""
    try:
        ventana = EditTableWindow(categoria, ruta_json, root)
    except json_db.JsonCorrupto as e:
        print(f"[!] {e}\n    Corrige o restaura el archivo antes de editarlo (no se abrió para no sobrescribirlo).")
        return False
    return ventana.ejecutar()
