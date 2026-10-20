"""
logix_escritura.py
--------------------
Ventana "Escribir" de /logix: escribe un valor en el tag de una fila de 1 a
N veces (o continuo) al ritmo del polling de esa fila, y deja monitorear la
escritura mientras ocurre.

    ┌ ELIZA :: logix :: Escribir ───────────────────────────────┐
    │ TAG        Program:Estacion30.Timer.DN                    │
    │ IP / POLL  10.140.126.30 · 100 ms · ● ON                  │
    │ VALOR ACTUAL           1                                  │
    │ Escribir [ 0      ]   Veces [ 10 ]  [ ] Continuo          │
    │ [            IDLE · clic para iniciar            ]        │
    │ [■■■■■■■■■■                                      ] 3/10   │
    │ Bitácora: 12:00:01.120  #1  Success ...                   │
    └───────────────────────────────────────────────────────────┘

El botón grande es un indicador de 3 estados:
    IDLE     -> clic: inicia
    WORKING  -> clic: detiene (queda IDLE con el avance alcanzado)
    DONE     -> clic: vuelve a IDLE para otra corrida

La ventana NO es modal y se puede cerrar con Esc: la escritura sigue en
segundo plano (el progreso se ve en la columna ESCRITURA del monitor). Toda
la escritura la hace el hilo de la fila (logix_window); esta ventana solo
da órdenes y muestra el estado.
"""

import tkinter as tk
from tkinter import ttk

import estilo_consola as estilo
import logix_tools

REFRESCO_MS = 150

COLORES_ESTADO = {
    logix_tools.IDLE: ("#333333", estilo.FG),
    logix_tools.WORKING: ("#ffcc00", "#000000"),
    logix_tools.DONE: (estilo.ACCENT, "#000000"),
}
TEXTO_ESTADO = {
    logix_tools.IDLE: "IDLE  ·  clic para iniciar",
    logix_tools.WORKING: "WORKING {progreso}  ·  clic para detener",
    logix_tools.DONE: "DONE {progreso}  ·  clic para reiniciar",
}


class VentanaEscritura:
    def __init__(self, monitor, iid):
        self.monitor = monitor
        self.iid = iid
        self._historial_mostrado = (None, 0)

        self.win, marco = estilo.ventana_emergente(monitor.window, "ELIZA :: logix :: Escribir")
        estilo.configurar_desplegables(self.win)

        self.var_tag = tk.StringVar()
        self.var_conexion = tk.StringVar()
        self.var_valor = tk.StringVar()
        self.var_escribir = tk.StringVar()
        self.var_veces = tk.StringVar(value="1")
        self.var_continuo = tk.BooleanVar(value=False)
        self.var_progreso = tk.StringVar()
        self.var_mensaje = tk.StringVar()

        self._construir(marco)
        fila = monitor.fila(iid)
        if fila and fila['trabajo']['valor_texto']:
            self.var_escribir.set(fila['trabajo']['valor_texto'])
            total = fila['trabajo']['total']
            self.var_continuo.set(total == 0)
            self.var_veces.set(str(total or 1))
        self._continuo_cambiado()

        self.win.bind('<Escape>', lambda e: self.cerrar())
        self.entry_valor.bind('<Return>', lambda e: self._clic_indicador())

        self.win.update_idletasks()
        estilo.centrar_ventana(self.win, max(self.win.winfo_reqwidth(), 620), self.win.winfo_reqheight())
        self.win.lift()
        self.win.focus_force()
        self.entry_valor.focus_set()
        self._refrescar()

    # ---------------------------------------------------------
    def _construir(self, marco):
        def etiqueta(padre, texto, fila):
            tk.Label(padre, text=texto, bg=estilo.BG, fg=estilo.FG, font=estilo.FONT_MONO,
                     anchor='w').grid(row=fila, column=0, sticky='w', pady=3, padx=(0, 12))

        datos = tk.Frame(marco, bg=estilo.BG)
        datos.pack(fill='x')
        datos.columnconfigure(1, weight=1)
        etiqueta(datos, "TAG", 0)
        tk.Label(datos, textvariable=self.var_tag, bg=estilo.BG, fg=estilo.FG_DATA, font=estilo.FONT_MONO_BOLD,
                 anchor='w', wraplength=470, justify='left').grid(row=0, column=1, sticky='w')
        etiqueta(datos, "IP / POLL", 1)
        tk.Label(datos, textvariable=self.var_conexion, bg=estilo.BG, fg=estilo.FG_DATA, font=estilo.FONT_MONO,
                 anchor='w').grid(row=1, column=1, sticky='w')
        etiqueta(datos, "VALOR ACTUAL", 2)
        tk.Label(datos, textvariable=self.var_valor, bg=estilo.ENTRY_BG, fg=estilo.FG_DATA,
                 font=("Consolas", 20, "bold"), anchor='w', padx=10).grid(row=2, column=1, sticky='ew', pady=6)

        # --- parámetros
        params = tk.Frame(marco, bg=estilo.BG)
        params.pack(fill='x', pady=(8, 4))
        tk.Label(params, text="Escribir", bg=estilo.BG, fg=estilo.FG, font=estilo.FONT_MONO).pack(side='left')
        self.entry_valor = tk.Entry(params, textvariable=self.var_escribir, width=14, bg=estilo.ENTRY_BG,
                                    fg=estilo.FG_DATA, insertbackground=estilo.FG, font=estilo.FONT_MONO_BOLD,
                                    relief='flat', disabledbackground=estilo.BG)
        self.entry_valor.pack(side='left', padx=(8, 20), ipady=3)
        tk.Label(params, text="Veces", bg=estilo.BG, fg=estilo.FG, font=estilo.FONT_MONO).pack(side='left')
        self.spin_veces = tk.Spinbox(params, from_=1, to=1000000, textvariable=self.var_veces, width=7,
                                     bg=estilo.ENTRY_BG, fg=estilo.FG_DATA, insertbackground=estilo.FG,
                                     buttonbackground=estilo.ACCENT, font=estilo.FONT_MONO_BOLD, relief='flat',
                                     disabledbackground=estilo.BG)
        self.spin_veces.pack(side='left', padx=(8, 16), ipady=3)
        self.chk_continuo = tk.Checkbutton(params, text="Continuo", variable=self.var_continuo,
                                           command=self._continuo_cambiado, bg=estilo.BG, fg=estilo.FG,
                                           selectcolor=estilo.ENTRY_BG, activebackground=estilo.BG,
                                           activeforeground=estilo.FG_DATA, font=estilo.FONT_MONO,
                                           highlightthickness=0)
        self.chk_continuo.pack(side='left')

        # --- indicador / botón de 3 estados
        self.indicador = tk.Label(marco, text="", font=("Consolas", 13, "bold"), pady=10, cursor="hand2")
        self.indicador.pack(fill='x', pady=(10, 6))
        self.indicador.bind('<Button-1>', lambda e: self._clic_indicador())

        estilo_barra = ttk.Style(self.win)
        estilo_barra.configure("Eliza.Horizontal.TProgressbar", troughcolor=estilo.ENTRY_BG,
                               background=estilo.FG, bordercolor=estilo.BG, lightcolor=estilo.FG,
                               darkcolor=estilo.ACCENT)
        self.barra = ttk.Progressbar(marco, style="Eliza.Horizontal.TProgressbar", maximum=100)
        self.barra.pack(fill='x')
        tk.Label(marco, textvariable=self.var_progreso, bg=estilo.BG, fg=estilo.FG_DATA, font=estilo.FONT_MONO,
                 anchor='w').pack(fill='x', pady=(4, 0))
        self.lbl_mensaje = tk.Label(marco, textvariable=self.var_mensaje, bg=estilo.BG, fg="#888888",
                                    font=("Consolas", 9), anchor='w', height=1)
        self.lbl_mensaje.pack(fill='x')

        # --- bitácora de escrituras
        tk.Label(marco, text="Bitácora de escrituras", bg=estilo.BG, fg=estilo.FG, font=estilo.FONT_MONO,
                 anchor='w').pack(fill='x', pady=(8, 2))
        self.lista = tk.Listbox(marco, height=7, bg=estilo.ENTRY_BG, fg=estilo.FG_DATA, font=estilo.FONT_MONO,
                                relief='flat', highlightthickness=0, selectbackground=estilo.ACCENT,
                                activestyle='none')
        self.lista.pack(fill='both', expand=True)

        pie = tk.Frame(marco, bg=estilo.BG)
        pie.pack(fill='x', pady=(8, 0))
        tk.Label(pie, text="Enter: iniciar · Esc: cerrar (la escritura sigue en segundo plano)",
                 bg=estilo.BG, fg="#888888", font=("Consolas", 9)).pack(side='left')
        ttk.Button(pie, text="Cerrar", command=self.cerrar).pack(side='right')

    # ---------------------------------------------------------
    def _continuo_cambiado(self):
        self.spin_veces.configure(state='disabled' if self.var_continuo.get() else 'normal')

    def _clic_indicador(self):
        fila = self.monitor.fila(self.iid)
        if not fila:
            return
        estado = fila['trabajo']['estado']
        if estado == logix_tools.WORKING:
            self.monitor.detener_escritura(self.iid)
        elif estado == logix_tools.DONE:
            self.monitor.reiniciar_escritura(self.iid)
        else:
            try:
                total = 0 if self.var_continuo.get() else int(self.var_veces.get())
                if not self.var_continuo.get() and total < 1:
                    raise ValueError("Las veces deben ser 1 o más.")
                self.monitor.iniciar_escritura(self.iid, self.var_escribir.get(), total)
            except ValueError as e:
                mensaje = str(e)
                if 'invalid literal' in mensaje:
                    mensaje = "Las veces deben ser un número entero."
                self.var_mensaje.set(mensaje)
                self.lbl_mensaje.configure(fg=estilo.PELIGRO)
                return
        self._refrescar(una_vez=True)

    def _refrescar(self, una_vez=False):
        if not self.win.winfo_exists():
            return
        fila = self.monitor.fila(self.iid)
        if fila is None:  # la fila se eliminó del monitor
            self.cerrar()
            return

        self.var_tag.set(fila['tag'] or "(sin tag)")
        self.var_conexion.set(f"{fila['ip']} · {fila['polling_ms']} ms · {fila['conexion']}")
        self.var_valor.set(fila['valor'] if fila['valor'] != '' else "—")

        t = fila['trabajo']
        estado = t['estado']
        fondo, texto = COLORES_ESTADO[estado]
        self.indicador.configure(text=TEXTO_ESTADO[estado].format(progreso=t['progreso']), bg=fondo, fg=texto)

        trabajando = estado == logix_tools.WORKING
        self.entry_valor.configure(state='disabled' if trabajando else 'normal')
        self.chk_continuo.configure(state='disabled' if trabajando else 'normal')
        self.spin_veces.configure(state='disabled' if trabajando or self.var_continuo.get() else 'normal')

        if t['total']:
            self.barra.configure(mode='determinate', value=100 * t['hechas'] / t['total'])
        else:
            self.barra.configure(mode='determinate', value=100 if t['hechas'] else 0)
        detalle = f"{t['progreso']}  ·  errores: {t['errores']}"
        if t['ultimo_status']:
            detalle += f"  ·  última: {t['ultimo_status']}"
        self.var_progreso.set(detalle)
        if t['mensaje'] or estado != logix_tools.IDLE:
            self.var_mensaje.set(t['mensaje'])
            self.lbl_mensaje.configure(fg=estilo.PELIGRO if t['errores'] else "#888888")

        clave = (t['corrida'], len(t['historial']))
        if clave != self._historial_mostrado:
            self.lista.delete(0, 'end')
            for hora, numero, status in t['historial'][-200:]:
                self.lista.insert('end', f"{hora}  #{numero:<5} {status}")
                if status != 'Success':
                    self.lista.itemconfigure('end', fg=estilo.PELIGRO)
            self.lista.see('end')
            self._historial_mostrado = clave

        if not una_vez:
            self.win.after(REFRESCO_MS, self._refrescar)

    def cerrar(self):
        self.monitor.ventana_escritura_cerrada(self.iid)
        try:
            self.win.destroy()
        except tk.TclError:
            pass

    def traer_al_frente(self):
        self.win.lift()
        self.win.focus_force()
