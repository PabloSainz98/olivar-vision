# Auditoria local de imagenes

Este documento describe la ejecucion de la fase 2. No autoriza descargas ni sustituye el inventario de licencias de `configs/datasets.json`.

## Entrada permitida

La configuracion actual solo acepta la version 3 de `roboflow_hahmedai_olive_s_leaf_diseases`, marcada `APTO_PARA_AUDITORIA`. La raiz local debe conservar las particiones y carpetas de clase de la exportacion:

```text
<raiz>/
  train/<clase>/<imagen>
  valid/<clase>/<imagen>
  test/<clase>/<imagen>
```

La ruta no se guarda en la configuracion ni en los informes. Se proporciona solo al proceso:

```bash
OLIVAR_ROBOFLOW_ROOT=/ruta/local/autorizada make data-audit
```

Sin esa variable, sin directorio o sin archivos, el comando termina con codigo 2 y no escribe un informe. `make check` nunca consulta la red ni usa este directorio.

## Salidas y codigos

- `0`: auditoria tecnica completa sin errores bloqueantes.
- `2`: configuracion, permiso local, ruta o entrada ausente; no se fabrica un resultado positivo.
- `3`: se genero informe, pero hay corrupcion, etiquetas/formato inesperados o fuga exacta/casi duplicada entre fuentes o particiones.

Una ejecucion real escribe `reports/dataset_audit.json` y `reports/dataset_audit.md`. Ambos estan excluidos de Git porque contienen rutas relativas y nombres de archivos. Si ya existe un informe diferente, la CLI se niega a sobrescribirlo; `--replace-report` exige una decision explicita despues de revisarlo.

## Comprobaciones

Cada archivo registra fuente/version, ruta relativa, particion, etiqueta original, bytes, formato, dimensiones, orientacion, SHA-256 y hash perceptual. El auditor decodifica PNG, BMP y Netpbm con Python estandar; en macOS usa `sips` en un directorio temporal para JPEG, TIFF, WebP y HEIC. Los originales son de solo lectura y el informe compara una huella de entrada anterior y posterior.

El informe propone de forma determinista hasta cinco archivos validos por clase para revision manual y calcula una huella del manifiesto de particiones. No congela el split mientras la revision figure como pendiente o exista cualquier incidencia bloqueante.

El hash perceptual es `dhash64-luma-nearest-v1`: 64 comparaciones horizontales sobre una muestra de luminancia 9x8. Se consideran candidatos a casi duplicado los hashes con distancia Hamming menor o igual que 4. Es un filtro para revision manual: compresion, recorte, giro, texto superpuesto o fondos parecidos pueden producir falsos positivos o falsos negativos.

Una coincidencia exacta o perceptual entre particiones hace fallar la auditoria. No se borra, mueve ni reclasifica ninguna imagen. La ausencia de identificadores de arbol, sesion y finca se conserva como limitacion: una particion por archivo no demuestra generalizacion en campo.

## Revision manual pendiente

La configuracion mantiene `manual_review_status: PENDING`. Antes de congelar particiones deben revisarse muestras por clase, documentar imagenes ambiguas, confirmar que `Knot Disease` representa el tipo de captura esperado y actualizar esa evidencia. Un resultado tecnico sin errores no constituye validacion clinica ni habilita entrenamiento por si solo.
