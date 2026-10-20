"""
logix_tag_dialog.py
---------------------
Asistente para agregar/editar un tag en /logix sin escribir la ruta a mano.

    IP          10.140.126.30
    Scope       (•) Principal (Controlador)   ( ) Subprograma
    Programa    [Estacion30      ▼]   (solo si es subprograma)
    Tag         [Motor1.Run      ▼]
    Comentario  [...]
    Ruta final: Program:Estacion30.Motor1.Run

- Programas y tags se leen del PLC en segundo plano (logix_explorador) y
  se ofrecen en listas filtrables mientras escribes (flecha abajo para
  ver la lista). Sin conexión, todo funciona como texto libre.
- Se pueden escribir miembros e índices: Motor[3].Run, UDT.Campo.
- Si se pega una ruta completa (Program:X.Y) en Tag, se separa sola.
- Enter acepta, Esc cancela.

abrir_dialogo_tag(...) devuelve {'ip', 'tag', 'comentario'} o None.
"""

import tkinter as tk
from tkinter import ttk

import estilo_consola as estilo
import logix_tools

INTERVALO_MS = 100


class DialogoTag:
    def __init__(self, padre, explorador, ip="", tag="", comentario="", titulo="Agregar tag",
                 texto_boton="Agregar"):
        self.explorador = explorador
        self.resultado = None
        self._ip_consultada = None
        self._tags_controlador = []
        self._programas = []
        self._tags_programa = []

        self.win, self._marco_exterior = estilo.ventana_emergente(padre, f"ELIZA :: logix :: {titulo}")
        estilo.configurar_desplegables(self.win)

        programa, nombre_tag = logix_tools.separar_ruta(tag)
        self.var_ip = tk.StringVar(value=ip)
        self.var_scope = tk.StringVar(value='programa' if programa else 'controlador')
        self.var_programa = tk.StringVar(value=programa or '')
        self.var_tag = tk.StringVar(value=nombre_tag)
        self.var_comentario = tk.StringVar(value=comentario)
        self.var_ruta = tk.StringVar()
        self.var_estado = tk.StringVar()

        self._construir(texto_boton)
        for var in (self.var_scope, self.var_programa, self.var_tag):
            var.trace_add('write', lambda *_: self._actualizar_ruta())
        self._actualizar_scope()
        self._actualizar_ruta()

        self.win.bind('<Return>', lambda e: self._aceptar())
        self.win.bind('<Escape>', lambda e: self._cancelar())

        self.win.update_idletasks()
        estilo.centrar_ventana(self.win, max(self.win.winfo_reqwidth(), 560), self.win.winfo_reqheight())
        self.win.after(INTERVALO_MS, self._revisar_resultados)
        self._consultar_plc()

        self.win.lift()
        self.win.focus_force()
        (self.entry_tag if ip else self.entry_ip).focus_set()
        self.win.grab_set()

    # ---------------------------------------------------------
    def _construir(self, texto_boton):
        marco = tk.Frame(self._marco_exterior, bg=estilo.BG)
        marco.pack(fill='both', expand=True)
        marco.columnconfigure(1, weight=1)

        def etiqueta(texto, fila):
            tk.Label(marco, text=texto, bg=estilo.BG, fg=estilo.FG, font=estilo.FONT_MONO,
                     anchor='w').grid(row=fila, column=0, sticky='w', pady=4, padx=(0, 10))

        def entrada(var, fila):
            e = tk.Entry(marco, textvariable=var, bg=estilo.ENTRY_BG, fg=estilo.FG_DATA,
                         insertbackground=estilo.FG, font=estilo.FONT_MONO, relief='flat')
            e.grid(row=fila, column=1, sticky='ew', pady=4, ipady=3)
            return e

        etiqueta("IP", 0)
        self.entry_ip = entrada(self.var_ip, 0)
        self.entry_ip.bind('<FocusOut>', lambda e: self._consultar_plc())

        etiqueta("Scope", 1)
        radios = tk.Frame(marco, bg=estilo.BG)
        radios.grid(row=1, column=1, sticky='w', pady=4)
        for texto, valor in (("Principal (Controlador)", 'controlador'), ("Subprograma", 'programa')):
            tk.Radiobutton(radios, text=texto, value=valor, variable=self.var_scope,
                           command=self._actualizar_scope, bg=estilo.BG, fg=estilo.FG,
                           selectcolor=estilo.ENTRY_BG, activebackground=estilo.BG,
                           activeforeground=estilo.FG_DATA, font=estilo.FONT_MONO,
                           highlightthickness=0).pack(side='left', padx=(0, 14))

        etiqueta("Programa", 2)
        self.combo_programa = ttk.Combobox(marco, textvariable=self.var_programa, font=estilo.FONT_MONO,
                                           style="Eliza.TCombobox")
        self.combo_programa.grid(row=2, column=1, sticky='ew', pady=4)
        self.combo_programa.bind('<KeyRelease>', self._filtrar_programas)
        self.combo_programa.bind('<<ComboboxSelected>>', lambda e: self._programa_elegido())
        self.combo_programa.bind('<FocusOut>', lambda e: self._programa_elegido())

        etiqueta("Tag", 3)
        self.entry_tag = ttk.Combobox(marco, textvariable=self.var_tag, font=estilo.FONT_MONO,
                                      style="Eliza.TCombobox")
        self.entry_tag.grid(row=3, column=1, sticky='ew', pady=4)
        self.entry_tag.bind('<KeyRelease>', self._tag_tecleado)

        etiqueta("Comentario", 4)
        entrada(self.var_comentario, 4)

        tk.Label(marco, text="Ruta final", bg=estilo.BG, fg=estilo.FG, font=estilo.FONT_MONO
                 ).grid(row=5, column=0, sticky='w', pady=(12, 2))
        tk.Label(marco, textvariable=self.var_ruta, bg=estilo.BG, fg=estilo.FG_DATA,
                 font=estilo.FONT_MONO_BOLD, anchor='w', wraplength=400, justify='left'
                 ).grid(row=5, column=1, sticky='w', pady=(12, 2))

        self.lbl_estado = tk.Label(marco, textvariable=self.var_estado, bg=estilo.BG, fg="#888888",
                                   font=("Consolas", 9), anchor='nw', wraplength=520, justify='left',
                                   height=2)  # 2 líneas fijas: un mensaje largo no corta los botones
        self.lbl_estado.grid(row=6, column=0, columnspan=2, sticky='w', pady=(6, 0))

        botones = tk.Frame(marco, bg=estilo.BG)
        botones.grid(row=7, column=0, columnspan=2, sticky='e', pady=(12, 0))
        ttk.Button(botones, text="Leer del PLC", command=lambda: self._consultar_plc(forzar=True)
                   ).pack(side='left', padx=(0, 20))
        ttk.Button(botones, text="Cancelar", command=self._cancelar).pack(side='left', padx=(0, 6))
        ttk.Button(botones, text=texto_boton, command=self._aceptar).pack(side='left')

    # ---------------------------------------------------------
    # Scope / ruta
    def _es_programa(self):
        return self.var_scope.get() == 'programa'

    def _actualizar_scope(self):
        if self._es_programa():
            self.combo_programa.configure(state='normal')
            self._programa_elegido()
        else:
            self.combo_programa.configure(state='disabled')
            self._poner_lista_tags(self._tags_controlador)

    def _actualizar_ruta(self):
        programa = self.var_programa.get() if self._es_programa() else None
        ruta = logix_tools.armar_ruta(programa, self.var_tag.get())
        if self._es_programa() and not self.var_programa.get().strip():
            ruta = "(falta el programa)"
        self.var_ruta.set(ruta or "(falta el tag)")

    def _tag_tecleado(self, event=None):
        texto = self.var_tag.get()
        programa, nombre = logix_tools.separar_ruta(texto)
        if programa:  # se pegó una ruta completa: se reparte en los campos
            self.var_scope.set('programa')
            self.var_programa.set(programa)
            self.var_tag.set(nombre)
            self._actualizar_scope()
            self.entry_tag.icursor('end')
            return
        if event is not None and event.keysym in ('Up', 'Down', 'Return', 'Escape', 'Tab'):
            return
        base = self._tags_programa if self._es_programa() else self._tags_controlador
        # Se filtra por la raíz del tag (antes del primer '.' o '['): así
        # 'Motor1.Ru' sigue mostrando 'Motor1' como sugerencia.
        raiz = texto.split('.')[0].split('[')[0]
        coincidencias = logix_tools.filtrar_nombres(base, raiz)
        self.entry_tag['values'] = coincidencias
        if base:
            self._estado(f"{len(coincidencias)} tag(s) coinciden · flecha abajo para ver la lista")

    def _filtrar_programas(self, event=None):
        if event is not None and event.keysym in ('Up', 'Down', 'Return', 'Escape', 'Tab'):
            return
        self.combo_programa['values'] = logix_tools.filtrar_nombres(self._programas, self.var_programa.get())

    def _programa_elegido(self):
        programa = logix_tools._sin_prefijo_programa(self.var_programa.get())
        if programa != self.var_programa.get():
            self.var_programa.set(programa)
        ip = self.var_ip.get().strip()
        self._tags_programa = []
        self._poner_lista_tags([])
        if programa and ip and self.explorador.disponible:
            en_cache = self.explorador.programa_en_cache(ip, programa)
            if en_cache is not None:
                self._tags_programa = en_cache
                self._poner_lista_tags(en_cache)
                self._estado(f"Programa '{programa}': {len(en_cache)} tag(s).")
            elif self.explorador.pedir_programa(ip, programa):
                self._estado(f"Leyendo tags del programa '{programa}'...")

    def _poner_lista_tags(self, nombres):
        self.entry_tag['values'] = logix_tools.filtrar_nombres(nombres, '')

    # ---------------------------------------------------------
    # Consulta al PLC
    def _consultar_plc(self, forzar=False):
        ip = self.var_ip.get().strip()
        if not ip:
            self._estado("Escribe la IP para leer programas y tags del PLC (opcional).")
            return
        if not self.explorador.disponible:
            self._estado("pylogix no está disponible: escribe el tag a mano.")
            return
        if ip == self._ip_consultada and not forzar:
            return
        self._ip_consultada = ip
        en_cache = self.explorador.controlador_en_cache(ip)
        if en_cache is not None and not forzar:
            self._cargar_controlador(en_cache)
            return
        if forzar:
            self.explorador.olvidar(ip)
        self.explorador.pedir_controlador(ip)
        self._estado(f"Leyendo programas y tags de {ip}... (puedes seguir escribiendo)")

    def _cargar_controlador(self, datos):
        self._tags_controlador = datos['tags']
        self._programas = datos['programas']
        self.combo_programa['values'] = self._programas
        self._estado(f"{len(self._tags_controlador)} tag(s) del controlador · "
                     f"{len(self._programas)} programa(s). Escribe para filtrar, flecha abajo para ver.")
        if self._es_programa():
            self._programa_elegido()
        else:
            self._poner_lista_tags(self._tags_controlador)

    def _revisar_resultados(self):
        if not self.win.winfo_exists():
            return
        ip = self.var_ip.get().strip()
        for evento in self.explorador.resultados():
            tipo, ip_evento = evento[0], evento[1]
            if ip_evento != ip:
                continue  # respuesta de una IP que ya no está en el campo
            if tipo == 'controlador':
                self._cargar_controlador(evento[2])
            elif tipo == 'programa':
                programa, nombres = evento[2], evento[3]
                if self._es_programa() and programa == self.var_programa.get().strip():
                    self._tags_programa = nombres
                    self._poner_lista_tags(nombres)
                    self._estado(f"Programa '{programa}': {len(nombres)} tag(s).")
            elif tipo == 'error':
                self._estado(f"No se pudo leer del PLC ({evento[2]}). Puedes escribir el tag a mano.",
                             error=True)
        self.win.after(INTERVALO_MS, self._revisar_resultados)

    def _estado(self, texto, error=False):
        self.var_estado.set(texto)
        self.lbl_estado.configure(fg=estilo.PELIGRO if error else "#888888")

    # ---------------------------------------------------------
    def _aceptar(self):
        ip = self.var_ip.get().strip()
        tag = self.var_tag.get().strip()
        programa = self.var_programa.get().strip() if self._es_programa() else None
        if not ip:
            self._estado("Falta la IP.", error=True)
            self.entry_ip.focus_set()
            return
        if self._es_programa() and not programa:
            self._estado("Elegiste Subprograma: falta el nombre del programa.", error=True)
            self.combo_programa.focus_set()
            return
        if not tag:
            self._estado("Falta el nombre del tag.", error=True)
            self.entry_tag.focus_set()
            return
        self.resultado = {
            'ip': ip,
            'tag': logix_tools.armar_ruta(programa, tag),
            'comentario': self.var_comentario.get().strip(),
        }
        self.win.destroy()

    def _cancelar(self):
        self.resultado = None
        self.win.destroy()


def abrir_dialogo_tag(padre, explorador, ip="", tag="", comentario="", editar=False):
    """Abre el asistente (modal). Devuelve {'ip', 'tag', 'comentario'} o None."""
    dialogo = DialogoTag(padre, explorador, ip=ip, tag=tag, comentario=comentario,
                         titulo="Editar tag" if editar else "Agregar tag",
                         texto_boton="Guardar" if editar else "Agregar")
    padre.wait_window(dialogo.win)
    return dialogo.resultado
