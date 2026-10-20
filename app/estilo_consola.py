"""
estilo_consola.py
------------------
Paleta y utilidades de estilo compartidas por las ventanas GUI de Eliza
(scanner_window, edit_window, logix_window, y las que se agreguen a
futuro), para que todas se vean consistentes sin duplicar código.
"""

import tkinter as tk
from tkinter import ttk

BG = "#000000"
FG = "#00ff00"          # verde terminal
FG_DATA = "#00ffff"     # cian, para datos/valores
ACCENT = "#00aa00"
ACCENT_ACTIVO = "#00cc00"
ENTRY_BG = "#111111"
PELIGRO = "#ff5555"
FONT_MONO = ("Consolas", 10)
FONT_MONO_BOLD = ("Consolas", 10, "bold")


def centrar_ventana(window, ancho, alto):
    """
    Centra la ventana en la pantalla, usando la resolución real detectada
    (en la práctica 1080p en los equipos donde corre Eliza, pero funciona
    igual de bien con cualquier otra resolución).
    """
    window.update_idletasks()
    pantalla_ancho = window.winfo_screenwidth()
    pantalla_alto = window.winfo_screenheight()
    x = max((pantalla_ancho // 2) - (ancho // 2), 0)
    y = max((pantalla_alto // 2) - (alto // 2), 0)
    window.geometry(f"{ancho}x{alto}+{x}+{y}")


def aplicar_estilo_base(window, titulo, geometry=None, resizable=True):
    """Configura título, tamaño (centrado en pantalla) y estilos ttk comunes."""
    window.title(titulo)
    window.configure(bg=BG)
    if not resizable:
        window.resizable(False, False)

    if geometry:
        ancho, alto = (int(v) for v in geometry.split('x'))
        centrar_ventana(window, ancho, alto)

    style = ttk.Style(window)
    style.theme_use('clam')
    style.configure("TLabel", background=BG, foreground=FG, font=FONT_MONO)
    style.configure("TButton", background=ACCENT, foreground=BG, borderwidth=0, padding=5, font=FONT_MONO_BOLD)
    style.map("TButton", background=[('active', ACCENT_ACTIVO)])
    style.configure("TEntry", fieldbackground=ENTRY_BG, foreground=FG_DATA, borderwidth=0)
    style.configure("Treeview", background=ENTRY_BG, fieldbackground=ENTRY_BG, foreground=FG_DATA,
                    rowheight=24, relief='flat', font=FONT_MONO)
    style.configure("Treeview.Heading", background=BG, foreground=FG, relief="flat", font=FONT_MONO_BOLD)
    style.map("Treeview.Heading", background=[('active', ENTRY_BG)])
    style.map("Treeview", background=[('selected', ACCENT)], foreground=[('selected', BG)])

    # Las ventanas sin barra de título (overrideredirect) no siempre reciben
    # el foco del teclado en Windows; sin esto, ESC/Ctrl+S no respondían
    # hasta hacer clic dentro de la ventana.
    window.after(100, lambda: _forzar_foco(window))
    return style


def configurar_desplegables(window):
    """Estilo oscuro para ttk.Combobox (campo y lista desplegable)."""
    style = ttk.Style(window)
    style.theme_use('clam')
    style.configure("TButton", background=ACCENT, foreground=BG, borderwidth=0, padding=5, font=FONT_MONO_BOLD)
    style.map("TButton", background=[('active', ACCENT_ACTIVO)])
    style.configure("Eliza.TCombobox", fieldbackground=ENTRY_BG, background=ACCENT, foreground=FG_DATA,
                    arrowcolor=BG, bordercolor=ENTRY_BG, lightcolor=ENTRY_BG, darkcolor=ENTRY_BG,
                    insertcolor=FG, padding=3)
    style.map("Eliza.TCombobox",
              fieldbackground=[('readonly', ENTRY_BG), ('disabled', BG)],
              foreground=[('disabled', '#555555')],
              background=[('disabled', '#333333'), ('active', ACCENT_ACTIVO)])
    # La lista que se despliega es un Listbox clásico: se configura con option_add.
    window.option_add('*TCombobox*Listbox.background', ENTRY_BG)
    window.option_add('*TCombobox*Listbox.foreground', FG_DATA)
    window.option_add('*TCombobox*Listbox.selectBackground', ACCENT)
    window.option_add('*TCombobox*Listbox.selectForeground', BG)
    window.option_add('*TCombobox*Listbox.font', FONT_MONO)


def _forzar_foco(window):
    try:
        window.lift()
        window.focus_force()
    except tk.TclError:
        pass  # la ventana ya se cerró


def crear_menu_contextual(window):
    """Crea un tk.Menu con la misma paleta, listo para agregarle add_command()."""
    return tk.Menu(window, tearoff=0, bg=ENTRY_BG, fg=FG,
                    activebackground=ACCENT, activeforeground=BG, relief='flat')
