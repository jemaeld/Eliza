# Eliza V2.3: instalador y /update

## Nuevo

- **Instalador desde cero:** se distribuyen solo `Eliza.bat` + `Eliza.py`.
  El .bat busca Python, descarga la última versión de GitHub a `app\`, crea
  `.venv`, instala dependencias y arranca Eliza.
- **`/update`:** compara el commit instalado (`app\VERSION.json`) con el
  último de `main`, descarga, reemplaza `app\` y reinicia Eliza (código de
  salida 10, que Eliza.bat interpreta como "volver a arrancar").
- **Primer arranque:** si el equipo no tiene `eliza_local.json`, Eliza
  pregunta la carpeta de datos: `[R]` remota (escribiéndola o con ventana)
  o `[L]` local (`<instalación>\datos`).
- El banner muestra la versión instalada.

## Cambios

- Estructura: el programa vive en `app\`; los datos locales, en `datos\`.
  `eliza2.bat` y `compilar.bat` se retiraron: los reemplaza `Eliza.bat`.
  Con la distribución por .bat ya no hace falta compilar, y se evita el
  falso positivo de Defender.
- **Contraseña VNC fuera del código** (no debe estar en un repositorio): se
  pide la primera vez que se abre un VNC y se guarda en `eliza_config.json`
  de la carpeta de datos. Si los datos son remotos, se pide una sola vez
  para todos los equipos.
- Ninguna base de datos (`config_json`, bitácoras, `_acd_store`) se sube al
  repositorio (`.gitignore`).

## Detalles del instalador

- Un `.venv` copiado de otra carpeta o equipo se detecta como roto y se
  recrea.
- Las dependencias se reinstalan solo si `app\requirements.txt` cambió.
- `app\` se reemplaza por renombrado (app → app.old → borrar): un fallo a
  medias no deja la instalación rota.
- Si una versión trae un `Eliza.bat` distinto, se deja como
  `Eliza.bat.nuevo` y el .bat en ejecución se reemplaza a sí mismo en su
  siguiente vuelta (sobrescribir un .bat mientras corre lo corrompe).
- Repo privado: token de solo lectura, pedido una vez
  (`eliza_github_token.txt` o variable `ELIZA_GITHUB_TOKEN`).

## v2.3.1: contraseña de acceso

- Al arrancar, Eliza pide una contraseña (sin decir para qué es) y no
  arranca sin ella (3 intentos). Es el `vnc_password` de la carpeta de
  datos: la primera instalación del sistema la define y las demás deben
  conocerla. Cada instalación guarda solo una huella sha256 en
  `eliza_local.json` y no la vuelve a pedir mientras no cambie.
- Se retiró la pregunta de contraseña al abrir el primer VNC.
- Limitación: filtra el uso casual. Quien modifique el código o lea
  `eliza_config.json` puede saltarla.

## v2.3.2: ordenar en /edit

- Botón **Ordenar A-Z** en el editor (`/edit vnc`, `/edit apps`, `/edit acd`):
  ordena por nombre.
- Clic en cualquier encabezado ordena por esa columna; otro clic invierte
  el orden (▲/▼).
- Orden natural: los números se comparan como números (L31E5 antes que
  L31E25, 10.140.126.9 antes que 10.140.126.10).
- El orden se guarda en el JSON con Ctrl+S, y así queda también en el
  autocompletado.
