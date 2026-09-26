# Olivar Vision

Fecha: 26 de septiembre de 2026.

**Web publicada:** [Abrir Olivar Vision](https://pablosainz98.github.io/olivar-vision/)
desde el movil, sin instalar una app nativa.
**Codigo:** [PabloSainz98/olivar-vision](https://github.com/PabloSainz98/olivar-vision).

## Problema y objetivo

Quiero monitorizar mi olivar tomando fotos con mi iPhone. Todavia no dispongo de imagenes aereas, inventario de arboles, distancias entre ellos ni fotos etiquetadas del campo. Primero quiero desarrollar y evaluar modelos visuales; las fichas y el mapa llegaran despues. La app debe funcionar sin cobertura para las inferencias basicas y conservar la foto original y el resultado para revisarlos.

Una imagen RGB permite reconocer algunos sintomas visibles, pero no mide directamente edad, humedad del suelo, estado hidrico, disponibilidad de luz ni presencia de todas las enfermedades. La interfaz debe distinguir observacion, sospecha y diagnostico confirmado; nunca recomendar una cantidad de riego ni afirmar "arbol sano" por una foto aparentemente normal.

La prioridad vigente desde el 26-09-2026 es un cliente web movil compatible con
iPhone, Android y escritorio, sin instalacion nativa. La PWA conserva fotografias
RGB, contexto, repeticiones y medidas manuales; ofrece una estimacion acotada de
biomasa seca aerea, carbono almacenado y CO2 equivalente almacenado. La API web
de camara no expone `ARKit sceneDepth`, confianza, intrinsecos ni pose, y Safari
en iPhone no ofrece WebXR inmersivo. Por ello la web nunca presenta una foto RGB
como escaneo LiDAR: la captura L1 3D queda bloqueada para el camino web puro. El
clasificador fotografico sigue en pausa en fase 2, sin borrar ni modificar su
motor, datos o pruebas.

## Investigacion inicial de datasets

Comprobar versiones y licencias antes de descargar o redistribuir.

| Fuente | Que ofrece | Utilidad y cautela |
| --- | --- | --- |
| [Repositorio original CNN_olive_dataset](https://github.com/sinanuguz/CNN_olive_dataset) | 3.400 imagenes de hojas de Denizli, Turquia; clases sana, repilo (*olive peacock spot*) y sintomas etiquetados *Aculus olearius*. Archivos RAR de entrenamiento y prueba. | Dataset inicial para la linea base. El repositorio consultado no mostraba una licencia explicita: verificar derechos antes de incorporarlo o redistribuirlo. Registrar procedencia y division original. |
| [Copia en Kaggle de 3.400 hojas](https://www.kaggle.com/datasets/habibulbasher01644/olive-leaf-image-dataset) | Las mismas tres clases y aparente mismo origen; la pagina declara CC0. | Tratar como posible espejo, **no** como 3.400 ejemplos independientes adicionales. Comprobar procedencia, permisos y hashes perceptuales. La licencia declarada por un tercero no resuelve por si sola los derechos del original. |
| [Olive Leaf Dataset de Grati et al. (2026)](https://github.com/optim762-prog/olive_leaf_diseases) y [articulo](https://link.springer.com/article/10.1007/s44163-026-01441-7) | Segun el articulo, fotografias de campo de Tunez y Libano, con anotacion experta de hojas sanas, repilo y *Aculus*. Codigo y checkpoints publicados. | Candidato prioritario para prueba externa. Comprobar disponibilidad real de imagenes, etiquetas, procedencia, licencia y posible solapamiento antes de descargarlo. El articulo informa una caida de metricas cercana a 70 % F1 en datos heterogeneos frente a mas de 98 % en el otro conjunto: no asumir rendimiento de laboratorio en mi campo. |
| [Roboflow: olive's leaf diseases](https://universe.roboflow.com/hahmedai-whou6/olive-s-leaf-diseases) | 2.849 imagenes; etiquetas sana, *Aculus*, repilo y "knot disease"; CC BY 4.0 declarada. | Fuente exploratoria secundaria. No consta descripcion de como se obtuvieron ni confirmacion clinica; revisar imagenes, duplicados y derechos de origen. "Knot" podria requerir fotos de ramas, no de hojas. |
| [Kaggle: Olive Leaf Disease](https://www.kaggle.com/datasets/serhathoca/zeytin) | Conjunto citado en investigaciones de deteccion de repilo. | Inspeccionar tamano, clases, licencia y duplicados; no asumir independencia respecto al dataset de 3.400. |
| [Zenodo: verticilosis con imagenes RGB de dron](https://zenodo.org/records/8144164) | Imagenes aereas de tres olivares griegos; archivo de 4,5 GB. | Referencia de investigacion, **no** entrenar con el el modelo para fotos terrestres del movil: cambia por completo el punto de vista. |

Los conjuntos publicos permiten un prototipo de sintomas foliares concretos. No he identificado aqui un conjunto adecuado para inferir con foto de movil la edad exacta, la dosis de agua o la luz necesaria. No inventar etiquetas para esas tareas.

## Alcance fotografico conservado (en pausa)

1. Entrada: una fotografia cercana de hojas de olivo, tomada o importada en iPhone; orientacion y recorte correctos, control de desenfoque y aviso si no hay hoja util.
2. Salida: `posible_repilo`, `posibles_sintomas_aculus`, `sin_sintomas_visibles_del_catalogo`, `otra_anomalia_o_no_concluyente`. Estas etiquetas son de sintomas visibles, no prueba de agente causal. Si el entrenamiento inicial solo cubre tres clases, implementar rechazo/abstencion y dejar claro que "otra anomalia" no esta clasificada etiologicamente.
3. Mostrar foto, resultado, version del modelo y puntuacion calibrada cuando haya calibracion valida; texto "posible" y aviso de revision para cualquier sospecha. No presentar un softmax bruto como probabilidad clinica.
4. Guardar localmente imagenes y resultados, con consentimiento explicito para cualquier exportacion. Interfaz en espanol y usable sin red. Sin necesidad de mapa, cuentas ni servidor.
5. Incluir un flujo sencillo para marcar "correcto", "incorrecto" o "pendiente de confirmar", sin convertir una opinion del usuario en diagnostico verificado.

## Plan tecnico del clasificador (en pausa)

### 0. Auditoria de datos

Crear un script reproducible que registre URL, version, licencia, cantidad por clase, resolucion, integridad, distribucion y huellas de archivos. Detectar duplicados exactos y casi duplicados entre fuentes y entre `train`/`val`/`test`. Inspeccionar manualmente una muestra de cada clase y documentar discrepancias. Descargar solo fuentes con condiciones de uso verificadas; nunca versionar imagenes grandes o de derechos inciertos en Git.

### 1. Linea base entrenable

Entrenar en el Mac (M1 Max, 32 GB) un clasificador pequeno con transferencia de aprendizaje, por ejemplo MobileNetV3 Small o EfficientNet Lite si el soporte de exportacion lo permite. Registrar semilla, versiones, preprocesado, clases, divisiones, metricas y pesos. Comparar con una linea base sencilla. El modelo solo aprendera las etiquetas que esten justificadas por los datos disponibles; abstencion por baja confianza o imagen fuera de distribucion requiere evaluacion aparte.

Separar conjuntos por arbol, sesion, fuente y finca si esa informacion existe. Si no existe, documentarlo y no afirmar generalizacion. Reservar una evaluacion externa integra, sin usarla en ajuste de umbrales. Reportar matriz de confusion, precision y recall por clase, especialmente falsos negativos de anomalias, calibracion y tasa de abstencion; jamas limitarse a accuracy global.

### 2. Validacion en mi olivar

Preparar un protocolo de fotos para mi iPhone: primer plano enfocado de varias hojas por haz y enves, luz difusa cuando sea posible, incluir hojas normales y sintomaticas, guardar original sin filtros, fecha, observacion y, si se sabe, variedad y arbol. Fotografiar tambien sintomas que no correspondan a las clases publicas. Para la prueba, reunir imagenes de varios dias y arboles; separar todo un dia/arbol del entrenamiento cuando haya volumen suficiente. Pedir confirmacion experta de un subconjunto de casos dudosos. No fijar metricas objetivo arbitrarias sin conocer la frecuencia real de las clases; acordar umbrales segun falsos negativos y coste de revisiones en campo.

### 3. iPhone

Prototipo nativo en SwiftUI: camara/importacion, inferencia con Vision + Core ML, historial local, resultado interpretable y exportacion de resultados para auditoria. Entrenar fuera del telefono y exportar un modelo `.mlpackage` o formato Core ML compatible; verificar equivalencia de predicciones antes y despues de convertirlo, consumo de memoria, tiempo de respuesta y funcionamiento sin red en el iPhone real. La primera app puede usar un modelo simulado hasta que termine la auditoria del dataset; etiquetar claramente ese estado.

### 4. Extensiones, solo tras validar la primera tarea

- Fotos de copa: cambios visibles y, cuando existan imagenes repetidas comparables, tendencia por arbol; requerira futura identificacion del mismo arbol y estandarizacion de fotos.
- Agua: combinar lluvia, temperatura, riegos y medidas de suelo/arbol; foto RGB como indicio adicional, sin calcular dosis a partir de foto sola.
- Luz: observaciones de sombra, ubicacion y poda; no inferir requerimiento fisiologico a partir de una imagen aislada.
- Edad: preferir ano de plantacion o rango documentado; no prometer estimacion exacta por imagen.
- Otras enfermedades y plagas: ampliar una a una con imagenes representativas y etiquetas verificadas, no clasificador universal improvisado.
- Escaneo 3D y carbono: estudiar captura LiDAR con iPhone para geometria del olivo y, solo tras validacion local, estimacion parcial de biomasa y cambio de stock de carbono. El volumen envolvente de copa no es volumen de madera ni biomasa; una captura no mide absorcion anual de CO2. La extension independiente L0-L4, sus APIs, literatura, protocolo y puertas estan en `docs/lidar-carbon.md`.

## Protocolo operativo obligatorio para Codex

Este documento es el README maestro del repositorio. Copiarlo a `README.md` en la raiz cuando se cree el proyecto y mantenerlo alli. No crear un segundo plan que compita con el. Los detalles extensos de ejecucion pueden vivir en `docs/`, pero el estado, decisiones y proximo paso siempre se reflejan aqui. La seccion "Estado vivo" se actualiza en cada fase; el resto se corrige cuando cambien hechos o alcance. Nunca sobrescribir registros historicos sin explicacion.

### Al comenzar cada sesion o fase

1. Leer el `README.md` completo, especialmente "Estado vivo", "Registro de fases", "Decisiones y bloqueos" y "Siguiente accion".
2. Inspeccionar el repositorio realmente existente: `git status --short`, `git log -5 --oneline` si existe Git, arbol de archivos y configuracion de ejecucion. Revisar cambios sin confirmar y no descartarlos.
3. Comparar el estado documentado con los artefactos reales; si divergen, anotar la discrepancia y corregir el README antes de desarrollar. No marcar una fase como completada por mera existencia de archivos.
4. Ejecutar los comandos de comprobacion documentados para el ultimo hito completado, salvo que haya una razon concreta para acotarlos; registrar resultado o impedimento.
5. Elegir la siguiente fase no completada cuyo prerrequisito se cumpla. Implementar solo esa fase, salvo que el usuario pida expresamente otro alcance. Si una fuente o dependencia bloquea la fase, documentar el bloqueo y avanzar en trabajo independiente permitido.

### Al terminar cada sesion o fase

1. Ejecutar las pruebas y comprobaciones pertinentes. Registrar comando exacto, resultado, fecha y entorno; indicar claramente "no ejecutado" si corresponde. Distinguir pruebas de codigo de validacion agronomica.
2. Actualizar "Estado vivo", "Registro de fases", "Decisiones y bloqueos" y "Siguiente accion" en este mismo README. Resumir que archivos y funciones cambiaron y que quedo pendiente; mantener referencias a commits cuando existan.
3. Actualizar instrucciones de instalacion, comandos y criterios de aceptacion si el codigo cambio. No dejar comandos ficticios como si estuvieran funcionando.
4. Dejar el proyecto en un estado reproducible. Si la fase quedo a medias, marcarla `EN CURSO` o `BLOQUEADA` y definir el paso mas pequeno para retomarla.
5. Explicar al usuario que funciona ahora y que se comprobo, con enlaces al README y entregables. No describir planes como funciones ya implementadas.

## Instalacion y comandos

Requisitos actuales en macOS:

- `git`
- `make`
- `python3` 3.9 o superior
- `sips` incluido en macOS para decodificar JPEG/TIFF/WebP/HEIC durante una auditoria real
- Node.js 20 o posterior para las pruebas de la PWA; no hay dependencias npm.
- Sin red, sin datasets, sin Xcode obligatorio y sin dependencias Python externas para `make check`.
- Swift 5.9/Xcode solo para conservar y comprobar el prototipo nativo historico;
  no son necesarios para ejecutar la web.

Comandos disponibles:

```bash
make help
make setup
make check
make check-web
make web-serve
make status
make data-audit
make lidar-process SESSION=/ruta/privada/sesion
make lidar-compare LEFT=/ruta/sesion-1 RIGHT=/ruta/sesion-2 OUTPUT=/ruta/comparacion.json
make lidar-geometry SESSION=/ruta/sesion OUTPUT=/ruta/geometria.json TREE_ISOLATED=1 VERTICAL_COVERAGE=0.9 GROUND_Y_M=0
make lidar-geometry-compare LEFT=/ruta/geometria-1.json RIGHT=/ruta/geometria-2.json OUTPUT=/ruta/comparacion-geometria.json
make biomass-estimate INPUT=configs/biomass-carbon.example.json OUTPUT=/ruta/nueva/estimacion.json
make check-apple-toolchain
make check-lidar-swift
make check-ios
```

`make web-serve` abre el cliente en `http://127.0.0.1:8788/`. En un movil debe
usarse la [web HTTPS publicada](https://pablosainz98.github.io/olivar-vision/)
para que el navegador permita la camara.
La guia de uso, persistencia y limites esta en `web/README.md`.
`.github/workflows/pages.yml` comprueba la web con Node.js 24 y publica sus
recursos estaticos cuando cambia `web/` en `main`. No publica datos de campo.

`make data-audit` no descarga datos. Requiere una exportacion local autorizada y falla con codigo 2 sin ella:

```bash
OLIVAR_ROBOFLOW_ROOT=/ruta/local/autorizada make data-audit
```

La configuracion y los codigos de salida de imagenes se documentan en
`docs/data-audit.md`. `lidar-process` valida el paquete L1, conserva originales
y escribe solo bajo `derived/` y `validation/`; `lidar-compare` exige dos IDs de
sesion distintos del mismo grupo y no sobrescribe el informe. El formato y sus
limites estan en `docs/lidar-carbon.md`. `lidar-geometry` conserva los limites
observados, pero solo publica medidas de arbol si se declara aislado, existe
referencia de suelo y se cumplen coberturas operativas. `biomass-estimate` usa
una entrada versionada y no sobrescribe resultados; el ejemplo incluido es
sintetico y no es una medida del olivar. `lidar-geometry-compare` exige informes
de sesiones distintas del mismo grupo de repeticion, conserva ambos y registra
diferencias pareadas; esas diferencias no validan por si solas la precision ni
la repetibilidad de campo.

Los comandos de fases futuras del clasificador fallan de forma explicita hasta
que se implementen:

```bash
make train
make evaluate
make export-coreml
```

## Contrato de ejecucion y autoevaluacion

Los comandos siguientes son la interfaz objetivo, no afirmaciones sobre codigo existente. Implementar cada comando en la fase correspondiente, mediante `Makefile` o scripts documentados; `make help` listara los disponibles. En macOS, `make check` ejecutara solo comprobaciones locales sin datos privados, red, descargas ni Xcode obligatorio. Separar dependencias opcionales: `make check-ios` requiere Xcode y un simulador compatible; `make check-data` requiere datasets descargados y derechos verificados. Los tests deben comprobar comportamiento real, no solo que una funcion devuelve el valor que ella misma fija. Registrar tambien tamanos y hashes de datasets/modelos en un manifiesto, sin subir fotos ni pesos al Git por defecto.

- `make setup`: crear entorno reproducible y documentar versiones.
- `make check`: lint/formato cuando se configure, pruebas unitarias e integracion local sin red, validacion offline del manifiesto de datasets cuando exista, y comprobacion de estructura del proyecto.
- `make check-web`: comprobar sintaxis del cliente y service worker, paridad de
  biomasa, sesiones, capacidades y exportacion TAR sin red.
- `make web-serve`: servir la PWA en localhost para desarrollo; la camara movil
  fuera de localhost requiere HTTPS.
- `make data-audit`: generar `reports/dataset_audit.json` y resumen legible con recuentos, fuentes, licencias y duplicados; fallar si hay fuga entre particiones.
- `make train`: entrenar con configuracion versionada y guardar metricas, semilla, manifiesto y modelo fuera de Git.
- `make evaluate`: evaluar sobre particiones selladas, producir matriz de confusion, metricas por clase y abstencion.
- `make export-coreml`: convertir el modelo y comparar predicciones con la implementacion original sobre un conjunto fijo.
- `make check-lidar-swift`: compilar y probar el contrato/almacenamiento Swift
  en el host; no verifica ARKit ni un iPhone.
- `make check-apple-toolchain`: exigir Xcode completo y mostrar la seleccion,
  SDK, Swift y pasos de correccion; falla si solo hay Command Line Tools.
- `make check-ios`: compilar el host iOS y su paquete L1 para iOS Simulator con
  Xcode; el simulador debe informar LiDAR no compatible y no valida captura real.
- `make status`: imprimir estado de fases leido del README o de un fichero maquina enlazado sin sustituir la actualizacion humana del README; mostrar ultimo resultado comprobado y siguiente accion.

Si alguna herramienta no es viable en el entorno disponible, sustituirla por un comando equivalente documentado y verificable, y registrar el motivo. Ningun comando debe declarar exito si omite silenciosamente su comprobacion principal.

## Plan por fases con puertas de avance

| Fase | Entregable verificable | Comprobacion minima | Puerta de avance |
| --- | --- | --- | --- |
| 0. Arranque | Repositorio Git con `README.md` maestro, estructura `src/`, `tests/`, `scripts/`, `configs/`, `docs/`, `reports/`, `.gitignore`, entorno y comandos base | `make setup && make check && make status`; comprobar que fotos/modelos no se anaden por error a Git | README refleja estado real y siguiente fase; proyecto arranca desde checkout limpio |
| 1. Inventario de datasets | Fichas de procedencia, licencia, acceso, clases y manifiesto de fuentes; informe `reports/datasets.md` | Comprobaciones de manifiesto y licencias; `make check` | Se identifican fuentes aptas y fuentes inciertas; **no** descargar o distribuir datos sin permiso verificable |
| 2. Auditoria de imagenes | Script de recuentos, integridad, muestras, hashes exactos/perceptuales y fugas entre splits | `make data-audit`; tests con fixtures sinteticos de duplicados, corruptos y particiones contaminadas | Informe reproducible y splits congelados; los espejos no cuentan como fuentes independientes |
| 3. Modelo base | Entrenamiento CPU/MPS viable en M1 Max; configuracion y artefactos reproducibles | `make train && make evaluate`; smoke test pequeno y prueba de inferencia sobre una foto valida/invalida | Metricas por clase y matriz de confusion guardadas; limitaciones y falsos negativos explicitos |
| 4. Rechazo y validacion externa | Regla de abstencion, umbrales establecidos con validacion, evaluacion externa sin ajuste sobre test | `make evaluate`; tests de umbrales y entradas fuera de dominio; reporte separado por fuente | Resultados honestos en fotos externas; si no hay fuente independiente, marcar `PENDIENTE` y limitar claims |
| 5. Modelo en iPhone | Exportacion Core ML y app SwiftUI minima con captura/importacion, inferencia local y resultado comprensible | `make export-coreml && make check-ios`; test de equivalencia y prueba manual documentada en iPhone real | Inferencia sin red y rendimiento medido; sin falsos mensajes de diagnostico definitivo |
| 6. Prueba en mi olivar | Protocolo de recoleccion y conjunto privado con fotos de varios dias, sanas, anomalas y no concluyentes; evaluacion por arbol/sesion | `make evaluate-field` con reporte separado; revision manual de errores y falsos negativos | Decidir con datos de campo si publicar como apoyo visual, recolectar mas, recalibrar o suspender una clase |
| 7. Evolucion por evidencia | Incorporar historial visual, identificacion de arbol y luego nuevas clases/multimodalidad de manera incremental | Regresion con conjunto de campo congelado y pruebas de app; comparar modelo anterior/nuevo | Aceptar nueva version solo si mejora el uso real sin degradacion inaceptable; documentar rollback |

Dependencias: 0 -> 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7. La app de la fase 5 puede prepararse con modelo de demostracion durante las fases 3-4, pero no anunciar capacidad real hasta la evaluacion. La fase 6 depende de obtener fotos del olivar y puede quedar `PENDIENTE DE DATOS` sin bloquear mantenimiento del software. Cada nueva version del modelo debe guardar dataset, codigo, hiperparametros, metricas, fecha y compatibilidad con la app; preservar una version anterior funcional para volver atras.

### Extension independiente LiDAR-carbono

Esta linea no renumera ni desbloquea las fases principales. Dependencias:
L0 -> L1 -> L2 -> L3 -> L4. El detalle y las referencias estan en
`docs/lidar-carbon.md`.

| Nivel | Estado | Entregable y puerta resumida |
| --- | --- | --- |
| L0. Factibilidad | EN CURSO - CAMINO WEB LIDAR BLOQUEADO | La PWA detecta APIs reales; Safari/iPhone no expone WebXR AR ni ARKit depth. Falta decidir una fuente 3D externa si se mantiene L1 |
| L1. Captura trazable | EN CURSO - CAMPO PENDIENTE | El prototipo nativo/formato v1 quedan como referencia; la web implementa RGB/manual en un formato separado y no afirma equivalencia LiDAR |
| L2. Geometria validada | PREPARADA EN SINTETICO - PUERTA PENDIENTE | Medidas de altura, copa y diametro con calidad/cobertura sobre nube aislada; falta piloto repetido frente a referencias, sesgo, MAE/RMSE e incertidumbre |
| L3. Biomasa local | PREPARADA EN SINTETICO - PUERTA PENDIENTE | Ecuacion v1 acotada a Leccino/vaso/secano y diametro manual; faltan calibracion local y validacion independiente |
| L4. Cambio de carbono | PLANIFICADA | Inventarios repetidos y balance de poda/perdidas; solo entonces valorar un resultado anual limitado |

## Estado vivo

- Estado documentado: CLIENTE WEB PUBLICADO EN GITHUB PAGES - VALIDACION MOVIL Y CAMPO PENDIENTES (26-09-2026). Ninguna puerta L0-L3 se valida con la PWA ni con datos sinteticos.
- Fase activa: migracion web de la linea LiDAR-carbono; el clasificador queda en fase 2, EN PAUSA - PENDIENTE DE DATOS, con su motor y pruebas sin cambios.
- Extension LiDAR-carbono: la PWA es el cliente principal para RGB, contexto, medidas manuales, repeticiones y calculo experimental. L0-L1 siguen abiertos porque Safari/iPhone no expone la captura LiDAR necesaria; L2-L3 permanecen PREPARADAS EN SINTETICO - PUERTAS PENDIENTES y L4 PLANIFICADA. El host iOS historico compila en simulador, pero ya no es el camino de producto solicitado.
- Ultimo hito completado: fase 1 - inventario formal de datasets y licencias, commits `50e6dc9` y `09adb83`. La fase 2 solo ha completado su motor, CLI, controles de integridad y pruebas sinteticas.
- Ultimas modificaciones: 26-09-2026 en `main`: se creo `web/` como PWA sin dependencias, con deteccion de capacidades, camara RGB, sesiones IndexedDB, grupos de repeticion, referencias y geometria manual, comparacion, TAR con SHA-256, uso offline y estimador de biomasa/carbono. El estimador web comparte los 31 casos de paridad Python/Swift. El arbol `ios/` se conserva sin convertirlo en requisito. No se modificaron el manifiesto, auditoria, datasets, entrenamiento ni evaluacion del clasificador.
- Comprobaciones realizadas: 26-09-2026, `make check` OK con 8 pruebas web y 50 Python, manifiesto de 8 fuentes y estructura; `git diff --check` OK. Despliegue Actions correcto, HTTPS publico HTTP 200 y calculadora comprobada en navegador. En la migracion previa se verificaron sesion, referencia, geometria, finalizacion, historial y recarga offline local. El host iOS historico constaba compilado para simulador con 6 XCTest. Camara fisica, instalacion PWA e iPhone/Android: NO VERIFICADOS.
- Artefactos disponibles: `web/` aporta la experiencia principal instalable y offline, formato `olivar-web-field-session` v1, originales RGB, SHA-256, TAR, historial y calculo experimental. Se conserva el motor Python de L1-L3 y el prototipo Swift como referencia de captura ARKit. La sesion web declara `source_type: web_rgb_manual`, no contiene profundidad ni representa volumen completo. No se descargaron ni anadieron datasets, capturas, nubes, imagenes, pesos o datos privados.
- Riesgos abiertos: no hay exportacion local autorizada de Roboflow v3; sus nombres reales de carpetas y procedencia clinica siguen por comprobar; revision manual por clase pendiente; faltan IDs de arbol, sesion y finca; continúan los bloqueos de licencia/acceso de las demas fuentes y la ausencia de fotos etiquetadas del olivar.
- Publicacion verificada: commit `e1f2e48`, repositorio publico y [Actions 36257916471](https://github.com/PabloSainz98/olivar-vision/actions/runs/36257916471) completado correctamente. `make check`: 8 pruebas web + 50 Python OK; manifiesto y estructura OK; `git diff --check` OK. HTTPS devuelve HTTP 200. En navegador de escritorio, contexto seguro, IndexedDB y calculo sintetico DB 20 cm verificados: 75,91 kg AGB, 35,68 kg C y 130,82 kg CO2e. La cache offline queda aislada por proyecto para no afectar a otros sitios de Pages. Esto sustituye el estado previo de HTTPS no verificado; camara fisica e iPhone/Android siguen pendientes.
- Siguiente accion: abrir la URL publicada y probar camara, persistencia, offline y exportacion en iPhone/Android; decidir una fuente externa para datos 3D si se mantiene L1. El clasificador permanece en pausa.

## Registro de fases

| Fase | Estado | Fecha | Evidencia y resultado | Pendiente |
| --- | --- | --- | --- | --- |
| 0 | VALIDADA | 22-09-2026 | Directorio real inspeccionado: vacio, sin Git y sin AGENTS.md/README.md previos. `git init` ejecutado. `make setup` OK; primer `make check` detecto una expectativa incorrecta del test de secciones, se corrigio y la repeticion quedo OK con 2 tests y estructura validada; `make status` OK; `make data-audit` fallo explicitamente como fase futura; `git check-ignore -v` valido rutas privadas hipoteticas. | Mantener README actualizado y dejar commit inicial/working tree limpio al cerrar la fase |
| 1 | VALIDADA | 22-09-2026 | Commit `50e6dc9`; `configs/datasets.json` registra 8 fuentes; `reports/datasets.md` resume estado, licencia y cautelas; validador offline exige IDs unicos, URLs, licencias/evidencias, captura y bloqueo de aptas sin licencia; `make check` OK con 6 tests y manifiesto; `make data-audit` sigue fallando con codigo 2 esperado. | Resolver licencias/accesos antes de descargar datos reales |
| 2 | EN CURSO - PENDIENTE DE DATOS | 22-09-2026 | Commit `0851a84`; motor/CLI offline implementados; 18 tests OK, incluido JPEG con `sips`, corrupcion, vacios, etiquetas, rutas inseguras y fugas exactas/perceptuales; `make data-audit` sin raiz autorizada devuelve 2 y no escribe informe | Auditar Roboflow v3 real con acceso permitido, revisar muestra por clase, resolver fugas y congelar splits |
| 3-7 | PLANIFICADAS | - | Sin implementacion | Seguir puertas de avance |
| L0-L4 LiDAR-carbono | L0-L1 ABIERTAS; CAPTURA LIDAR WEB BLOQUEADA; L2-L3 PREPARADAS EN SINTETICO; L4 PLANIFICADA | 26-09-2026 | PWA publicada para RGB/manual y biomasa experimental; 8 tests web + 50 Python. Swift/ARKit queda como referencia historica. Sin profundidad web en iPhone, sesion 3D real, escala, calibracion local ni validacion independiente | Probar iPhone/Android y decidir una fuente 3D externa si se mantiene la puerta L1 |
| Publicacion web | PUBLICADA - MOVIL PENDIENTE | 26-09-2026 | Repositorio y Pages publicos; Actions correcto; HTTP 200 y calculadora verificados; 8 tests web + 50 Python OK. Solo se despliegan recursos del cliente | Probar camara real, dos sesiones, TAR y offline en iPhone/Android; no cierra L0-L4 |

## Decisiones y bloqueos

- D-001 (22-09-2026): prioridad a fotografias cercanas de hojas y ejecucion local en iPhone.
- D-002 (22-09-2026): los espejos del conjunto de 3.400 imagenes no se suman como ejemplos independientes.
- D-003 (22-09-2026): edad, dosis de riego y luz necesaria fuera del alcance de prediccion por foto unica.
- D-004 (22-09-2026): la fase 0 usa solo Python estandar, `make` y Git; no introduce dependencias externas ni red.
- D-005 (22-09-2026): los comandos de fases futuras (`data-audit`, `train`, `evaluate`, `export-coreml`, `check-ios`) existen como interfaz objetivo pero fallan explicitamente hasta que se implementen con comprobaciones reales.
- D-006 (22-09-2026): `configs/datasets.json` es la fuente estructurada para inventario; `reports/datasets.md` es el resumen humano. Ambos deben mantenerse sincronizados.
- D-007 (22-09-2026): una fuente solo puede marcarse `APTO_PARA_AUDITORIA` si declara licencia verificable y enlaza evidencia. En fase 1 solo Roboflow queda apta, y solo para auditoria, no para diagnostico ni entrenamiento definitivo.
- D-008 (22-09-2026): los recuentos de imagenes de fase 1 son declarados, no verificados; la fase 2 debe contarlos desde archivos reales si hay permiso de descarga.
- D-009 (22-09-2026): `make data-audit` es de solo lectura y recibe la raiz privada mediante `OLIVAR_ROBOFLOW_ROOT`; nunca descarga datos ni guarda rutas absolutas en informes.
- D-010 (22-09-2026): los casi duplicados usan `dhash64-luma-nearest-v1` con distancia Hamming maxima 4. Son candidatos para revision manual, no decisiones automaticas de borrado, independencia o calidad clinica.
- D-011 (22-09-2026): los informes reales de auditoria quedan fuera de Git y no se sobrescriben si cambian salvo opcion explicita tras revision. Una auditoria tecnica sin errores no congela splits mientras la revision por clase siga pendiente.
- D-012 (26-09-2026): LiDAR-carbono es una extension independiente L0-L4. No cambia la fase 2 principal ni autoriza entrenamiento, pantalla de CO2 anual o claims de carbono.
- D-013 (26-09-2026): separar volumen envolvente de copa, volumen de madera visible, biomasa seca, carbono almacenado y cambio anual de stock. Una sola captura no produce una tasa anual.
- D-014 (26-09-2026): ninguna ecuacion alometrica se incorpora solo porque sus variables puedan medirse con iPhone; debe coincidir su dominio y superar calibracion/validacion local con incertidumbre.
- D-015 (26-09-2026): poda y escaneo exterior requieren contabilidad explicita de residuos y reservorios excluidos. Raices, madera oculta, suelo y cubierta no se imputan desde la nube exterior.
- D-016 (26-09-2026): el desarrollo L1 que no depende de campo puede avanzar
  con fixtures y grabaciones, pero no cierra L0 ni L1. El formato v1 mantiene
  originales, derivados y validacion separados y nunca denomina volumen completo
  a una superficie parcial.
- D-017 (26-09-2026): la prioridad operativa pasa a LiDAR-carbono y el
  clasificador queda en pausa, sin modificar su pipeline ni su evidencia.
- D-018 (26-09-2026): el modelo experimental v1 usa exclusivamente
  `AGB_kg=0.0538*DB_cm^2.4208` de Brunori et al. (2017), con DB basal a 0,30 m,
  `Leccino`, vaso, secano tradicional, 70-250 arboles/ha y DB 5-45 cm. Fuera de
  ese dominio la salida es `ESTIMATION_NOT_AVAILABLE`.
- D-019 (26-09-2026): ninguna fraccion de carbono se aplica implicitamente. El
  usuario debe registrar valor y fuente; 0,47 de Torrus-Castillo et al. (2026)
  solo puede usarse como proxy explicito, no como validacion de Leccino.
- D-020 (26-09-2026): contraste con el PDF primario de Brunori et al. (2017).
  La ecuacion y sus unidades se confirman. El articulo define DB sobre el tocon
  y cita 0,3 m de Villalobos et al. (2005) sin declarar su propia altura; la
  tolerancia de 0,02 m es convencion del proyecto. El texto dice 70-250
  arboles/ha y DB 5-45 cm, pero sus tablas muestran 70-330 arboles/ha y DB
  observado 1,0-44,5 cm. Se mantiene el dominio restrictivo hasta que el
  usuario decida otra cosa. Detalle en `docs/lidar-carbon.md`.
- D-021 (26-09-2026): las pruebas Swift se compilan con `--scratch-path` en
  `/tmp`, porque la firma ad hoc falla dentro de `~/Desktop` por atributos
  extendidos del Finder.
- D-022 (26-09-2026): el cliente principal pasa a ser una PWA JavaScript sin
  dependencias de runtime. Swift se conserva como referencia historica y de
  paridad; la web no requiere Xcode, firma ni instalacion nativa.
- D-023 (26-09-2026): la sesion web usa el formato separado
  `olivar-web-field-session` v1 y `source_type: web_rgb_manual`. Detectar o
  probar WebXR no autoriza etiquetarla como L1: sin RGB/profundidad/confianza,
  intrinsecos y pose sincronizados no hay equivalencia con ARKit.
- D-024 (26-09-2026): fotos y sesiones permanecen en IndexedDB hasta una
  descarga explicita. La exportacion TAR incluye manifiesto y JPEG con SHA-256;
  las sesiones finalizadas y sus IDs no se reutilizan.
- D-025 (26-09-2026): publicacion solicitada por el usuario en el repositorio
  publico `PabloSainz98/olivar-vision` y GitHub Pages. El workflow publica solo
  recursos del cliente; los datos privados siguen excluidos. Revision de 237
  objetos del historial sin blobs mayores de 5 MB ni coincidencias de los
  patrones de credenciales comprobados; no equivale a una auditoria de seguridad.
- B-001: acceso/licencias de datos y ausencia de fotos propias por verificar; no impide fase 0.
- B-002: avisos de macOS por no poder crear cache temporal de `xcrun` en `/tmp` durante `make`; no bloquearon `setup`, `check` ni `status` en esta sesion.
- B-003: repositorio `https://github.com/optim762-prog/olive_leaf_diseases` indicado por Grati et al. devolvio 404 durante fase 1; no usarlo hasta recuperar acceso o contactar autores.
- B-004: los datasets Kaggle `serhathoca`, `techplusmentor` e `hikmetdurmaz` quedan pendientes de licencia directa; el espejo Kaggle de 3.400 hojas queda pendiente por derechos de origen.
- B-005: no existe una exportacion local autorizada de Roboflow v3 en este entorno; por ello no hay recuentos reales, informe de dataset ni particiones congeladas y la fase 2 no esta validada.
- B-006: el usuario declara un iPhone 16 Pro (26-09-2026). La version de iOS, el identificador de hardware y los cuatro chequeos de capacidad siguen `NO VERIFICADOS` hasta ejecutar la app en el dispositivo real.
- B-007: faltan inventario de arboles, variedades, rangos, medidas de referencia, densidad/fraccion de carbono local, datos de biomasa por componentes, escaneos repetidos y destino de poda; no se puede estimar carbono anual de forma defendible.
- B-008 (resuelto 26-09-2026): Xcode 27.0 instalado y seleccionado; toolchain
  READY, paquete Swift probado y host iOS compilado para simulador. La firma
  personal solo seria necesaria si se recupera la captura nativa auxiliar.
- B-009: L1 carece de sesion real completa, referencias metricas verificadas y
  revision en hardware compatible. Su puerta sigue cerrada aunque pasen los
  tests sinteticos.
- B-010: Safari en iPhone no ofrece WebXR inmersivo y `getUserMedia` no expone
  ARKit scene depth. Si se descarta definitivamente el cliente nativo, L1
  necesita importar datos de otro capturador 3D compatible o redefinir su
  alcance; una PWA RGB/manual no puede cerrar esa puerta.

## Siguiente accion

Accion prioritaria web: abrir https://pablosainz98.github.io/olivar-vision/ en el
iPhone y al menos un Android, comprobar camara/IndexedDB/offline, crear dos
sesiones del mismo grupo, exportar sus TAR y confirmar hashes/contenido. En
campo se pueden registrar fotos, referencias y medidas manuales y calcular un
escenario alometrico acotado. Esto no ejecuta el ensayo LiDAR L0-L1.

Decision pendiente para la linea 3D: elegir entre importar paquetes de un
capturador externo que entregue profundidad, confianza, intrinsecos y pose, o
mantener el prototipo Swift solo como herramienta auxiliar de captura. Si no se
adopta ninguna fuente 3D, documentar L1 como bloqueada y continuar la web con
medicion manual, sin claims de escaneo o volumen.

Accion del clasificador, pausada: conservar el trabajo de fase 2. Cuando se
retome, obtener una exportacion autorizada de Roboflow v3, mantenerla fuera de
Git y ejecutar la auditoria documentada antes de iniciar fase 3.

## Plantilla operativa para encargar una fase a Codex

El ejemplo de FASE 12H del proyecto MBIT ilustra el nivel de detalle deseado. Sus datos, rutas, hashes, inventarios y restricciones son exclusivos de MBIT y no aplican a este proyecto. En Olivar Vision, cada fase se concreta con el estado real encontrado en el repositorio, sin cifras inventadas. Copiar y adaptar este bloque al solicitar cada fase; el README sigue siendo la fuente de verdad para retomar el trabajo.

```text
Lee completamente AGENTS.md (si existe), README.md y el codigo actual antes de modificar nada.
Inspecciona git status, los cinco commits mas recientes, la estructura del repositorio
y las pruebas disponibles. No descartes cambios preexistentes.

ESTADO VERIFICADO ANTES DE EMPEZAR
- Fases terminadas y validadas: [lista, evidencia y fecha].
- Fase activa y estado: [PLANIFICADA/EN CURSO/BLOQUEADA/VALIDADA].
- Ultimo cambio real: [commit o archivos y descripcion].
- Pruebas previas y resultado: [comandos, entorno, fecha].
- Artefactos y datos: [que existe; tamanos/hashes cuando afecten la integridad].
- Pendientes/bloqueos: [hechos comprobados].
Si el README discrepa del repositorio, explica la discrepancia y corrigela.

IMPLEMENTA UNICAMENTE FASE [N] - [NOMBRE]

OBJETIVO
[Resultado observable desde el punto de vista del usuario y entregables concretos.]

ALCANCE Y FUENTE DE VERDAD
[Entradas permitidas, procedencia y licencia de datos, salidas, archivos a modificar.
Que informacion debe estar confirmada y por quien.]

COMPORTAMIENTO Y CLI/UI
[Comandos exactos o pantallas y estados esperados; caso sin datos, entrada mala,
resultado no concluyente y funcionamiento offline.]

VALIDACIONES PREVIAS
[Lista numerada de invariantes comprobables: rutas y derechos de datos,
integridad, splits, consistencia de etiquetas, compatibilidad del modelo, etc.]

SEGURIDAD Y REVERSIBILIDAD
[No sobrescribir datos originales ni fotos privadas. Versionar modelos y
manifiestos; documentar rollback. Operaciones de inspeccion por defecto sin
escritura cuando proceda. Nunca inventar diagnosticos ni resultados.]

NO TOCAR
[Subsistemas, datos de usuario o fases futuras fuera del encargo.]

PRUEBAS
[Casos concretos que cubren exito, error, borde y regresion. Usar fixtures
pequenos, sinteticos y archivos temporales; no requerir el olivar ni red para
make check. Registrar pruebas manuales del iPhone aparte.]

VALIDACION REAL, EN ORDEN
1. Inspeccionar estado y guardar linea base de los artefactos afectados.
2. Ejecutar las pruebas pertinentes y verificaciones de esta fase.
3. Ejecutar el flujo de usuario con entradas de prueba seguras.
4. Comparar artefactos antes/despues y revisar git diff.
5. Actualizar README: Estado vivo, Registro, Decisiones y Siguiente accion.
No ejecutar una accion de campo o de publicacion si esta fase solo prepara su motor.

PUERTA DE AVANCE
[Condiciones medibles para VALIDADA; si faltan fotos propias o etiquetas
expertas, marcar PENDIENTE DE DATOS y limitar las afirmaciones.]

AL TERMINAR, INFORMAR
IMPLEMENTACION: archivos, comandos y comportamiento.
VALIDACION: comandos, recuentos y resultados reales; pruebas omitidas y razon.
INTEGRIDAD: que entradas y artefactos se compararon; antes/despues cuando aplique.
ESTADO: fase validada/en curso/bloqueada, limites y siguiente paso concreto.
README: secciones actualizadas y correspondencia con el estado del repo.
```

## Instruccion concreta de FASE 0

Lee este README completo y `AGENTS.md` si existe. Inspecciona los archivos actuales antes de escribir. Implementa unicamente FASE 0 - Arranque.

ESTADO DOCUMENTADO: no se ha verificado repositorio, datos, app ni pruebas. Confirma el estado real con `git status`, `git log` y listado del proyecto.

OBJETIVO: crear un repositorio reproducible que permita continuar fases sin perder el contexto. Instala este Markdown como `README.md` maestro.

ENTREGABLES: estructura minima, `.gitignore` para fotos/datasets/pesos, `Makefile` con `setup`/`check`/`status`, tests minimos con utilidad real, instrucciones macOS, Estado vivo y Registro de fases ajustados a lo que efectivamente exista.

COMPORTAMIENTO: `make status` muestra fase actual, ultimo hito comprobado y siguiente accion; `make check` funciona localmente y sin red. Los comandos de fases futuras no deben anunciar exito ni simular implementaciones inexistentes.

NO TOCAR: fotos privadas si las hubiera; no descargar datasets, entrenar modelos, crear diagnosticos ni afirmar que la app iOS ya funciona.

PRUEBAS: ejecutar `make setup`, `make check` y `make status`; comprobar con `git status` que las rutas de datos/modelos privados quedan excluidas; corregir problemas hasta que pase la puerta de FASE 0 o documentar un bloqueo real.

AL TERMINAR: informar archivos creados, salidas relevantes de comandos, pruebas, limitaciones y siguiente fase. Actualizar este README en el mismo trabajo con las modificaciones reales, evidencia y fecha. Si no se pudo comprobar algo, marcarlo `NO EJECUTADO` y explicar por que.

## Primer encargo concreto para Codex

Lee este README completo y comprueba el estado real del proyecto antes de editar. Ejecuta exclusivamente la siguiente fase elegible del plan y sus verificaciones. Empieza por la fase 0 si aun no hay repositorio funcional. Al concluir, actualiza el propio `README.md`: estado vivo, registro de fases, decisiones/bloqueos, ultimas modificaciones, resultados exactos de pruebas y siguiente accion. En cada nueva peticion vuelve a leer el README, `git status`, historial reciente y evidencias de la fase anterior; nunca supongas que el estado antiguo sigue vigente. Si la fase esta bloqueada, deja un paso concreto para retomarla y avanza solo trabajo independiente. No inventes resultados de entrenamiento ni declares fases terminadas sin comprobar su puerta de avance.

## Fuentes metodologicas

- MDN `getUserMedia`, WebXR Device API y el modulo WebXR Depth Sensing para
  capacidades web, contexto seguro y degradacion progresiva.
- WebKit: WebXR inmersivo no esta soportado en dispositivos iOS; no usar el
  modelo de iPhone como sustituto de una consulta de capacidad.
- Apple: clasificar imagenes con Vision y Core ML.
- Mohanty et al. (2016), generalizacion de modelos de enfermedad vegetal: prueba de por que evaluar con imagenes nuevas y de campo.
- Grati et al. (2026), generalizacion entre conjuntos de hojas de olivo.
- Apple, ARKit y AVFoundation para profundidad, poses, malla y calibracion en hardware LiDAR compatible.
- Brunori et al. (2017), Ruiz-Peinado et al. (2012), Velazquez-Marti et al. (2014), Fernandez-Sarria et al. (2019) y Torrus-Castillo et al. (2026): metodos de volumen, biomasa y carbono de olivo, con dominios no intercambiables.
- IPCC (2006), metodo de diferencia de stocks: un cambio anual requiere inventarios en al menos dos fechas comparables.
