# Eliza V2

Lanzador de herramientas industriales por teclado: VNC, APPS, proyectos ACD,
bitácora de turno, ping y monitor de tags Allen-Bradley.

## Ejecutar (sin compilar)

Doble clic en **`eliza2.bat`**. Siempre trabaja desde su propia carpeta, sin
importar desde dónde se lance.

- La primera vez crea `.venv\` e instala las dependencias de `requirements.txt`.
- Si `.venv\` se copió de otra carpeta o de otro equipo y ya no funciona, lo
  recrea solo.
- Si Eliza termina con error, la ventana se queda abierta para leer el mensaje.

Requisito: Python 3 instalado en el equipo (`py` o `python` en PATH).

## Carpeta de datos

Por defecto, **la carpeta de datos es la misma carpeta de Eliza**:

```
ElizaV2\
  eliza2.bat, eliza2.py, *.py
  config_json\      vnc.json, apps.json, acd.json
  bitacora\         un JSON por día (YYYY-MM-DD.json)
  _acd_store\       copias protegidas de los ACD (oculta)
  eliza_config.json contraseña y puerto VNC
```

Copias la carpeta completa a otro lado y funciona igual: no depende de
ningún otro folder.

**Opcional:** con `/settings` puedes apuntar a una carpeta de datos externa
(por ejemplo, una ruta de red para que varios equipos compartan la misma
base de datos y bitácoras). Esa elección se guarda en `eliza_local.json`
junto a Eliza. Si esa carpeta no está disponible al arrancar, Eliza avisa y
usa su carpeta propia en esa sesión. `/settings` → `[P]` vuelve al modo
autocontenido.

## Comandos

| Comando | Qué hace |
|---|---|
| `/ip` | Interfaces de red locales |
| `/ping <ip o nombre>` | Ping continuo en ventana aparte |
| `/scan_acd` | Escanea una carpeta y registra ACD/L5K |
| `/edit <vnc/apps/acd>` | Editor de tabla |
| `/add` | Alta de VNC/APPS desde .vnc/.lnk/.exe |
| `/bitacora` | Nuevo registro de bitácora |
| `/bitacora <hoy, ayer, DD, MM/DD, YYYY-MM-DD>` | Visor, exportar TSV, copiar a Excel |
| `/logix [ip o nombre]` | Monitor/forzado de tags (pylogix) |
| `/settings` | Carpeta de datos propia o externa |
| `/reload` | Relee la base de datos |
| `/clear`, `/help`, `exit` | |

Cualquier entrada de la base de datos se ejecuta escribiendo su nombre
(TAB autocompleta).

## Compilar a .exe (opcional)

`compilar.bat` → genera `dist\ELIZA_v2.exe`. El .exe usa como carpeta de
datos la carpeta donde lo pongas. Los ejecutables de PyInstaller suelen dar
falsos positivos en Defender; para el uso diario basta `eliza2.bat`.

## Agregar un comando nuevo

En `eliza2.py`, escribe `def cmd_xxx(ctx, arg): ...` y agrégalo al
diccionario `COMANDOS` con su descripción. Aparece solo en el autocompletado
y en `/help`.

## Estructura del código

| Módulo | Rol |
|---|---|
| `eliza2.py` | Núcleo: banner, prompt, autocompletado, registro de comandos |
| `consola.py` | Colores, estilo y preguntas por consola con ESC = cancelar |
| `eliza_home.py` | Resuelve la carpeta de datos |
| `config_manager.py` | `eliza_config.json` |
| `json_db.py` | Lectura/escritura segura de JSON |
| `network_tools.py` | IP local y ping |
| `acd_tools.py` / `scanner_window.py` | ACD: escaneo, `_acd_store`, rutas |
| `edit_window.py` | Editor de tabla genérico |
| `add_tools.py` / `add_terminal.py` | Alta VNC/APPS |
| `bitacora_tools.py` / `bitacora_terminal.py` | Bitácora |
| `logix_tools.py` / `logix_window.py` | Monitor de tags |
| `settings_terminal.py` | `/settings` |
| `estilo_consola.py` | Paleta de las ventanas Tkinter |

Errores inesperados se registran en `eliza_error.log` junto a Eliza.
