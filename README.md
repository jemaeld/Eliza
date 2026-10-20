# Eliza V2

Lanzador de herramientas industriales por teclado: VNC, APPS, proyectos ACD,
bitácora de turno, ping y monitor de tags Allen-Bradley.

## Instalar en un equipo nuevo

1. Requisito: **Python 3** instalado (python.org, con "Add python.exe to PATH"
   y tcl/tk).
2. Copia **`Eliza.bat`** y **`Eliza.py`** a la carpeta donde quieras
   instalarla (ej. `C:\Eliza`).
3. Ejecuta **`Eliza.bat`**. La primera vez:
   - descarga la última versión desde GitHub a `app\`
   - crea `.venv\` e instala las dependencias
   - arranca Eliza y te pregunta la **carpeta de datos**: `[R]` remota o
     compartida (la de red con las bases de datos) o `[L]` local.

Desde ahí, `Eliza.bat` es el lanzador de todos los días.

**Contraseña de acceso:** antes de arrancar, Eliza pide una contraseña. Sin
ella no arranca. La primera instalación de todo el sistema la define (se
escribe dos veces); las demás instalaciones deben escribir la misma. Cada
equipo la pide una sola vez, y otra vez solo si la contraseña cambia. Se
guarda en `eliza_config.json` de la carpeta de datos (`vnc_password`), y es
también la que Eliza escribe en los `.vnc`.

**Repositorio privado:** si GitHub responde que no encuentra el repositorio,
Eliza.py pide un **token de solo lectura** una vez y lo guarda en
`eliza_github_token.txt`. El token se crea en GitHub › Settings › Developer
settings › Fine-grained tokens, solo para `jemaeld/Eliza` y con el permiso
Contents: Read-only. Puedes copiar ese archivo junto con Eliza.bat y
Eliza.py para que no lo pida en cada equipo.

## Actualizar

Dentro de Eliza: **`/update`**. Compara la versión instalada con el último
commit de `main`, la descarga si hay una nueva y Eliza se reinicia sola
(Eliza.bat reinstala dependencias si cambiaron). Los datos no se tocan.

Fuera de Eliza: `python Eliza.py buscar` / `python Eliza.py actualizar`.

## Estructura de una instalación

```
C:\Eliza\
  Eliza.bat               instalador + lanzador
  Eliza.py                descarga / actualización (solo biblioteca estándar)
  app\                    el programa (se reemplaza completo en cada /update)
    VERSION.json          commit instalado
  .venv\                  entorno de Python
  datos\                  carpeta de datos LOCAL (si no se usa una remota)
  eliza_local.json        qué carpeta de datos usa este equipo
  eliza_github_token.txt  solo si el repo es privado
  eliza_error.log         errores inesperados
```

Carpeta de datos (local o remota): `config_json\` (vnc/apps/acd.json),
`bitacora\`, `_acd_store\` (oculta), `eliza_config.json`.

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
| `/settings` | Cambia la carpeta de datos (remota o local) |
| `/reload` | Relee la base de datos |
| `/update` | Descarga la última versión desde GitHub |
| `/clear`, `/help`, `exit` | |

Cualquier entrada de la base de datos se ejecuta escribiendo su nombre
(TAB autocompleta).

## Desarrollo

Clona el repo y ejecuta `Eliza.bat` desde la raíz del clon: detecta que
`app\` ya existe y no descarga nada. `/update` se niega a correr dentro de
un repositorio git (usa `git pull`). Los datos locales (`datos\`,
`eliza_local.json`, etc.) están en `.gitignore`.

**Publicar una versión:** haz push a `main`. Los equipos la reciben con
`/update`.

**Agregar un comando:** en `app\eliza2.py`, escribe
`def cmd_xxx(ctx, arg): ...` y agrégalo a `COMANDOS` con su descripción.

| Módulo (app\) | Rol |
|---|---|
| `eliza2.py` | Núcleo: banner, prompt, autocompletado, registro de comandos |
| `consola.py` | Colores, estilo y preguntas por consola con ESC = cancelar |
| `eliza_home.py` | Rutas de la instalación y de la carpeta de datos |
| `settings_terminal.py` | Primer arranque y `/settings` |
| `licencia.py` | Contraseña de acceso al arrancar |
| `actualizador.py` | `/update` (usa `Eliza.py` de la raíz) |
| `config_manager.py` | `eliza_config.json` |
| `json_db.py` | Lectura/escritura segura de JSON |
| `network_tools.py` | IP local y ping |
| `acd_tools.py` / `scanner_window.py` | ACD: escaneo, `_acd_store`, rutas |
| `edit_window.py` | Editor de tabla genérico |
| `add_tools.py` / `add_terminal.py` | Alta VNC/APPS |
| `bitacora_tools.py` / `bitacora_terminal.py` | Bitácora |
| `logix_tools.py` / `logix_window.py` | Monitor de tags |
| `estilo_consola.py` | Paleta de las ventanas Tkinter |

Historial de cambios en [`docs/`](docs/).
