"""
consola.py
-----------
Piezas compartidas de la interfaz de TERMINAL de Eliza: colores ANSI,
estilo de prompt_toolkit y preguntas por consola con ESC = cancelar.

Antes cada módulo (eliza2, add_terminal, bitacora_terminal, settings,
eliza_home) tenía su propia copia de los colores y del truco del ESC; ahora
viven solo aquí.

Sobre el ESC: se usa event.app.exit(result=_ESC) y la excepción se lanza
ya fuera del loop de prompt_toolkit. app.exit(exception=...) deja la
PromptSession en mal estado si se reutiliza. Aun así, cada flujo con ESC
usa su PROPIA PromptSession desechable, nunca la del "ELIZA>" principal.
"""

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

COLOR_ENCABEZADO = "\033[95m"          # magenta
COLOR_DATOS = "\033[36m"               # cian
COLOR_RESET = "\033[0m"
COLOR_LOGO = "\033[92m\033[1m"         # verde brillante + negrita
COLOR_BORDE = "\033[90m"               # gris
COLOR_ETIQUETA = "\033[1m\033[95m"     # magenta negrita

ESTILO = Style.from_dict({
    'prompt': 'bg:#000000 #00ff00 bold',
    'vnc': '#00ffff', 'apps': '#ffff00', 'acd': '#ff00ff', 'cmd': '#5f87ff bold',
    'completion-menu': 'bg:#222222 #ffffff',
    'completion-menu.completion.current': 'bg:#00aa00 #000000 bold',
    'completion-menu.meta.completion': 'bg:#222222 #888888',
    'completion-menu.meta.completion.current': 'bg:#00aa00 #000000',
})


def titulo(texto):
    print(f"\n{COLOR_ENCABEZADO}--- {texto} ---{COLOR_RESET}")


def info(texto):
    print(f"{COLOR_DATOS} {texto}{COLOR_RESET}")


def ok(texto):
    print(f"{COLOR_DATOS} [*] {texto}{COLOR_RESET}")


def aviso(texto):
    print(f"{COLOR_DATOS} [!] {texto}{COLOR_RESET}")


# ---------------------------------------------------------
# Preguntas con ESC = cancelar

class Cancelado(Exception):
    """El usuario presionó ESC durante un flujo de preguntas."""


_ESC = object()


def _kb_escape():
    kb = KeyBindings()

    @kb.add('escape')
    def _(event):
        event.app.exit(result=_ESC)
    return kb


class Cuestionario:
    """
    Sesión desechable para un flujo de preguntas por consola.
    Cualquier pregunta lanza Cancelado si el usuario presiona ESC.
    """

    def __init__(self):
        self._sesion = PromptSession(style=ESTILO)
        self._kb = _kb_escape()

    def prompt(self, mensaje):
        """Prompt crudo (mensaje tal cual, puede ser HTML). Lanza Cancelado con ESC."""
        resultado = self._sesion.prompt(mensaje, key_bindings=self._kb)
        if resultado is _ESC:
            raise Cancelado()
        return resultado.strip()

    def preguntar(self, etiqueta, default=""):
        """Pregunta un valor; Enter vacío devuelve 'default' (se muestra entre corchetes)."""
        sufijo = f" [{default}]" if default else ""
        return self.prompt(f"{etiqueta}{sufijo}: ") or default

    def obligatorio(self, etiqueta):
        while True:
            valor = self.preguntar(etiqueta)
            if valor:
                return valor
            aviso("Este campo es obligatorio.")
