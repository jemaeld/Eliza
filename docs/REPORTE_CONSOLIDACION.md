# Eliza V2.2: reporte de consolidación

Fecha: 2026-10-20 · Base: ElizaV2.tar (19 módulos .py, 3 JSON, .bat, .spec)

## 1. Acción requerida antes de usarla

**Copia tus datos vivos de S: a la carpeta de Eliza.** Hasta ahora Eliza no
leía la carpeta del proyecto: `eliza_local.json` la mandaba a
una carpeta de red (unidad S:). El `config_json/` que venía
en el proyecto es una **copia vieja**: el `acd.json` no tiene `comentario` y
apunta a rutas personales, sin `_acd_store`.

Copia desde la carpeta de red a la carpeta de Eliza, reemplazando:

- `config_json\` (vnc.json, apps.json, acd.json)
- `bitacora\`
- `_acd_store\` (está oculta: activa "mostrar ocultos" o usa `xcopy /h /e`)
- `eliza_config.json` (si existe)

Las entradas ACD viejas con ruta absoluta a `<carpeta de red>\_acd_store\...` siguen
funcionando: si esa ruta no existe, Eliza busca el mismo archivo en el
`_acd_store` local.

## 2. Dependencias externas encontradas y eliminadas

| # | Dependencia | Corrección |
|---|---|---|
| D1 | `eliza_local.json` obligaba a usar la carpeta de red. Sin él, preguntaba la carpeta en el primer arranque | La carpeta de datos por defecto es la **carpeta propia de Eliza**. Una carpeta externa ahora es opcional (`/settings`). Si la externa no está disponible, Eliza avisa y sigue con la propia en vez de bloquearse |
| D2 | `eliza2.bat` hacía `call .venv\Scripts\activate.bat` sin `cd` a su carpeta. Fallaba al lanzarlo desde un acceso directo u otra consola. Además, `activate.bat` guarda la ruta donde se creó el venv (p. ej. `...\ELIZA_v2\.venv`): si renombras o copias la carpeta, el venv apunta al lugar viejo | El .bat hace `cd /d "%~dp0"` y usa `.venv\Scripts\python.exe` directo, sin `activate`. Si `.venv` falta o está roto, lo recrea e instala `requirements.txt` |
| D3 | `/scan_acd` guardaba en `acd.json` la **ruta absoluta** al `_acd_store` (atada a la ubicación de la carpeta de datos) | Las entradas nuevas guardan `open "_acd_store/XXXX.ACD"` (relativa). Las viejas se rescatan como se explica en la sección 1 |
| D4 | El selector de guardar/cargar de `/logix` empezaba en el directorio de trabajo (variaba según desde dónde se lanzara) | Empieza en la carpeta de datos |

## 3. Bugs corregidos

### Graves (pérdida de datos o cierre de Eliza)

| # | Bug | Corrección |
|---|---|---|
| B1 | Cualquier error en un comando **cerraba Eliza por completo**. Ejemplo: abrir un ACD cuyo archivo ya no existe, o `gethostbyname` fallando al mostrar el banner | El bucle atrapa el error, lo muestra y lo guarda en `eliza_error.log`; Eliza sigue corriendo. Abrir una entrada inexistente solo avisa |
| B2 | Si un JSON estaba dañado (p. ej. guardado a medias desde otro equipo por red), **agregar un registro borraba todo su contenido**: lo leía como `[]` y escribía solo el nuevo. Aplicaba a bitácora, acd.json y /add | `json_db.agregar_entrada` usa lectura estricta y se niega a escribir sobre un archivo dañado. `/edit` tampoco abre un archivo dañado |
| B3 | Escritura no atómica: un corte de red o apagón a medio guardar dejaba el JSON truncado | Escribe a un archivo `.tmp` y luego hace `os.replace` |
| B4 | Re-registrar un ACD con la misma Línea/Estación/IP fallaba con "Permission denied": Windows no deja sobrescribir un archivo **oculto** | Quita el atributo oculto, copia y lo vuelve a ocultar |
| B5 | `/edit`: ESC cerraba **sin preguntar** y se perdían los cambios sin guardar. Además, Ctrl+S con una celda en edición descartaba lo escrito en esa celda | ESC pregunta solo si hay cambios sin guardar; Ctrl+S confirma la celda en edición |

### Medios

| # | Bug | Corrección |
|---|---|---|
| B6 | Copiar la bitácora (`[Y]`) mandaba UTF-8 a `clip`: **acentos y ñ llegaban rotos a Excel**. El TSV exportado tampoco tenía BOM | `clip` recibe UTF-16; el TSV se escribe en `utf-8-sig` con fin de línea CRLF |
| B7 | `/logix` mostraba "Conectado" aunque el tag no existiera (Status ≠ Success, Value=None) | Muestra `Error: <status>` en rojo |
| B8 | Registrar el mismo ACD dos veces creaba **entradas duplicadas** | Pregunta y actualiza la entrada existente, conservando su comentario |
| B9 | Nombres repetidos en un JSON: solo la última entrada es accesible y las demás se ocultaban sin aviso | Se avisa al arrancar. **Tu acd.json tiene 3: `L69E30`, `L76E20`, `L83E49+52`** → corrígelos con `/edit acd` |
| B10 | Un JSON con sintaxis rota o entradas sin `name` se ignoraba en silencio | Se reporta qué archivo falló y por qué |
| B11 | `/ping` pasaba el texto directo a `os.system`: `/ping 1.1.1.1 & del ...` ejecutaba comandos | Solo acepta caracteres válidos de IP/host |
| B12 | `/add` con .lnk: rutas con `$` o con acentos se resolvían mal (comillas dobles en PowerShell, codificación de salida) | Comillas simples y salida UTF-8 |
| B13 | Los `.vnc` temporales se acumulaban en `%TEMP%` (uno por conexión, con la contraseña dentro) | Prefijo `eliza_vnc_` y limpieza automática de los anteriores |
| B14 | Al ejecutar una entrada se quitaba `"open "` en **cualquier** parte de la ruta, no solo al inicio | Solo se quita el prefijo |
| B15 | Ventanas sin barra de título no siempre recibían el foco, así que ESC/Ctrl+S no respondían hasta hacer clic | Se fuerza el foco al abrir |
| B16 | `/settings` configuraba una "carpeta destino ACD" que **ningún módulo usaba** desde que existe `_acd_store` | `/settings` ahora elige la carpeta de datos (propia o externa) |
| B17 | VNC sin campo `ip` (solo `action: vnc x.x.x.x`) no conectaba | Toma la IP del `action` |

## 4. Limpieza

- **Eliminados:** `vnc_manager.py` (TightVNC, sin uso; ya se había decidido retirarlo), `logix_tools.tar` (respaldo viejo), `ELIZA_v2.spec` (basura de PyInstaller, se regenera), `eliza_local.json` (puntero a S:), `LEEME_COMPILAR.md` (reemplazado por `LEEME.md`).
- **Nuevo `consola.py`:** los colores ANSI y el mecanismo de ESC = cancelar estaban copiados en 5 módulos; ahora están en uno solo.
- **`eliza2.py`:** el `if` gigante de comandos pasó a ser un **registro `COMANDOS`** (nombre → descripción + función). La captura de bitácora se movió a `bitacora_terminal.py`.
- Imports sin uso eliminados (`subprocess`, `platform`, etc.) y código muerto quitado (`get_acd_version`, `_cargar_json`, `_extraer_ruta_de_action` duplicado). `pyflakes`: 0 advertencias.
- La contraseña VNC salió del código y pasó a `eliza_config.json` (`vnc_password`, `vnc_puerto`).
- Docstrings que mencionaban módulos ya eliminados quedaron actualizados.

## 5. Nuevo

- `/reload`: relee la base de datos (útil si otro equipo la modificó).
- `/bitacora ayer`.
- Escribir el nombre de una entrada **sin** `[CAT]` la ejecuta si es único.
- El banner muestra qué carpeta de datos se usa (propia/externa) y cuántas entradas cargó.
- `compilar.bat`: compila a `dist\ELIZA_v2.exe` usando el mismo `.venv`.

## 6. Pendientes y recomendaciones para la expansión

1. **Concurrencia en red.** Con la carpeta compartida, si dos equipos guardan la bitácora del mismo día al mismo tiempo, uno puede perder su registro: no se corrompe, pero gana el último en escribir. Si se va a compartir de verdad, conviene un archivo por equipo y día (`2026-10-20_PCNAME.json`) que el visor junte al mostrar.
2. **`/logix`:** desconectar o eliminar una fila puede congelar la ventana hasta 2 s por fila si el PLC no responde (`join` con timeout en el hilo de la GUI). Para muchas filas conviene desconectar en segundo plano.
3. **Redondeo de hora en la bitácora:** a las 23:58 se redondea a 00:00 del **día siguiente**, y el registro cae en el archivo de mañana (turno C). Decide si eso es lo deseado.
4. **Defender y el .exe:** sigue igual. `eliza2.bat` evita el problema en el día a día.
5. **Siguiente paso natural:** con `COMANDOS` + `Contexto`, cada módulo nuevo es un archivo `xxx_tools.py` (lógica) + `xxx_terminal.py`/`xxx_window.py` (interfaz) + una línea en `COMANDOS`.

## 7. Cómo se probó

- 30 pruebas automáticas de la lógica: carpeta de datos (propia, externa y externa caída), JSON dañado, escritura atómica, registro/reemplazo/rescate de rutas ACD, configuración, carga de la base, todos los comandos, VNC/APPS/ACD inexistente, inyección en ping, captura de bitácora. Todas pasan.
- Arranque completo de `main()` con entrada simulada: banner, `/ip`, `/edit`, `/bitacora`, entrada por nombre, `exit`.
- **No probado en Windows real:** ventanas Tkinter, `os.startfile`, `attrib`, `clip`, PowerShell, pylogix contra PLC y el `.bat`. Esta revisión se hizo en un entorno Linux. Prueba rápida sugerida: `eliza2.bat` → `/help` → abrir un VNC → `/edit vnc` → `/bitacora hoy` → `[Y]` y pegar en Excel → `/logix`.
