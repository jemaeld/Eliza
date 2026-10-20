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
