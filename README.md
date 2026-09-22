# Olivar Vision

Fecha: 22 de septiembre de 2026.

## Problema y objetivo

Quiero monitorizar mi olivar tomando fotos con mi iPhone. Todavia no dispongo de imagenes aereas, inventario de arboles, distancias entre ellos ni fotos etiquetadas del campo. Primero quiero desarrollar y evaluar modelos visuales; las fichas y el mapa llegaran despues. La app debe funcionar sin cobertura para las inferencias basicas y conservar la foto original y el resultado para revisarlos.

Una imagen RGB permite reconocer algunos sintomas visibles, pero no mide directamente edad, humedad del suelo, estado hidrico, disponibilidad de luz ni presencia de todas las enfermedades. La interfaz debe distinguir observacion, sospecha y diagnostico confirmado; nunca recomendar una cantidad de riego ni afirmar "arbol sano" por una foto aparentemente normal.

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

## Alcance de la primera version

1. Entrada: una fotografia cercana de hojas de olivo, tomada o importada en iPhone; orientacion y recorte correctos, control de desenfoque y aviso si no hay hoja util.
2. Salida: `posible_repilo`, `posibles_sintomas_aculus`, `sin_sintomas_visibles_del_catalogo`, `otra_anomalia_o_no_concluyente`. Estas etiquetas son de sintomas visibles, no prueba de agente causal. Si el entrenamiento inicial solo cubre tres clases, implementar rechazo/abstencion y dejar claro que "otra anomalia" no esta clasificada etiologicamente.
3. Mostrar foto, resultado, version del modelo y puntuacion calibrada cuando haya calibracion valida; texto "posible" y aviso de revision para cualquier sospecha. No presentar un softmax bruto como probabilidad clinica.
4. Guardar localmente imagenes y resultados, con consentimiento explicito para cualquier exportacion. Interfaz en espanol y usable sin red. Sin necesidad de mapa, cuentas ni servidor.
5. Incluir un flujo sencillo para marcar "correcto", "incorrecto" o "pendiente de confirmar", sin convertir una opinion del usuario en diagnostico verificado.

## Plan tecnico para Codex

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

Requisitos actuales de fase 0 en macOS:

- `git`
- `make`
- `python3` 3.9 o superior
- Sin red, sin datasets, sin Xcode obligatorio y sin dependencias Python externas para `make check`.

Comandos disponibles:

```bash
make help
make setup
make check
make status
```

Los comandos de fases futuras existen como interfaz objetivo y fallan de forma explicita hasta que se implementen:

```bash
make data-audit
make train
make evaluate
make export-coreml
make check-ios
```

## Contrato de ejecucion y autoevaluacion

Los comandos siguientes son la interfaz objetivo, no afirmaciones sobre codigo existente. Implementar cada comando en la fase correspondiente, mediante `Makefile` o scripts documentados; `make help` listara los disponibles. En macOS, `make check` ejecutara solo comprobaciones locales sin datos privados, red, descargas ni Xcode obligatorio. Separar dependencias opcionales: `make check-ios` requiere Xcode y un simulador compatible; `make check-data` requiere datasets descargados y derechos verificados. Los tests deben comprobar comportamiento real, no solo que una funcion devuelve el valor que ella misma fija. Registrar tambien tamanos y hashes de datasets/modelos en un manifiesto, sin subir fotos ni pesos al Git por defecto.

- `make setup`: crear entorno reproducible y documentar versiones.
- `make check`: lint/formato cuando se configure, pruebas unitarias e integracion local sin red, validacion offline del manifiesto de datasets cuando exista, y comprobacion de estructura del proyecto.
- `make data-audit`: generar `reports/dataset_audit.json` y resumen legible con recuentos, fuentes, licencias y duplicados; fallar si hay fuga entre particiones.
- `make train`: entrenar con configuracion versionada y guardar metricas, semilla, manifiesto y modelo fuera de Git.
- `make evaluate`: evaluar sobre particiones selladas, producir matriz de confusion, metricas por clase y abstencion.
- `make export-coreml`: convertir el modelo y comparar predicciones con la implementacion original sobre un conjunto fijo.
- `make check-ios`: compilar y ejecutar pruebas pertinentes en simulador cuando exista app iOS.
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

## Estado vivo

- Estado documentado: VALIDADA (22-09-2026). Fase 1 completada tras contrastar fase 0 en Git (`20a5593`), revisar README/codigo/scripts/tests existentes e inventariar fuentes sin descargar datos. Implementacion registrada en commit `50e6dc9`.
- Fase activa: 2 - auditoria de imagenes.
- Ultimo hito completado: fase 1 - inventario formal de datasets y licencias. Entregados `configs/datasets.json`, `reports/datasets.md`, validador offline de manifiesto y tests de esquema.
- Ultimas modificaciones: 22-09-2026, anadidos `configs/datasets.json`, `reports/datasets.md`, `src/olivar_vision/dataset_manifest.py`, `scripts/validate_dataset_manifest.py` y `tests/test_dataset_manifest.py`; `make check` integra la validacion offline del manifiesto; `scripts/check_structure.py` reconoce los entregables de fase 1.
- Comprobaciones realizadas: linea base `git status --short` limpio y `git log -5 --oneline` con `20a5593`; `make check` inicial OK con 2 tests antes de editar; tras fase 1, `python3 -m unittest discover -s tests -p 'test_*.py'` OK con 6 tests; `python3 scripts/validate_dataset_manifest.py configs/datasets.json` OK con 8 fuentes y 1 apta para auditoria; `make check` OK con 6 tests, manifiesto y estructura; `make data-audit` fallo de forma esperada con codigo 2 y mensaje de fase futura; `git diff --check` OK. Los comandos siguieron emitiendo avisos no bloqueantes de macOS por cache temporal de `xcrun` en `/tmp`.
- Artefactos disponibles: README maestro, estructura de proyecto, manifiesto versionado de fuentes, informe `reports/datasets.md`, validador offline y tests. No se han descargado datasets, imagenes, RAR/ZIP, pesos ni fotos privadas.
- Riesgos abiertos: derechos del repositorio original de 3.400 imagenes; licencia/origen del espejo Kaggle; acceso 404 al repositorio de Grati et al.; licencias no verificadas de Kaggle `serhathoca`, `techplusmentor` e `hikmetdurmaz`; Roboflow apto solo para auditoria y con procedencia clinica por revisar; falta de fotos etiquetadas del olivar.
- Siguiente accion: iniciar fase 2 - auditoria de imagenes solo para fuentes con permiso/acceso suficiente o fixtures sinteticos. Antes de descargar datos reales, resolver licencias pendientes; mantener `make data-audit` como fase futura hasta implementar hashes, recuentos, integridad y fugas con tests.

## Registro de fases

| Fase | Estado | Fecha | Evidencia y resultado | Pendiente |
| --- | --- | --- | --- | --- |
| 0 | VALIDADA | 22-09-2026 | Directorio real inspeccionado: vacio, sin Git y sin AGENTS.md/README.md previos. `git init` ejecutado. `make setup` OK; primer `make check` detecto una expectativa incorrecta del test de secciones, se corrigio y la repeticion quedo OK con 2 tests y estructura validada; `make status` OK; `make data-audit` fallo explicitamente como fase futura; `git check-ignore -v` valido rutas privadas hipoteticas. | Mantener README actualizado y dejar commit inicial/working tree limpio al cerrar la fase |
| 1 | VALIDADA | 22-09-2026 | Commit `50e6dc9`; `configs/datasets.json` registra 8 fuentes; `reports/datasets.md` resume estado, licencia y cautelas; validador offline exige IDs unicos, URLs, licencias/evidencias, captura y bloqueo de aptas sin licencia; `make check` OK con 6 tests y manifiesto; `make data-audit` sigue fallando con codigo 2 esperado. | Resolver licencias/accesos antes de descargar datos reales |
| 2 | SIGUIENTE | 22-09-2026 | Sin implementacion; `make data-audit` sigue fallando explicitamente como fase futura | Implementar auditoria con fixtures sinteticos y permisos resueltos antes de datos reales |
| 3-7 | PLANIFICADAS | - | Sin implementacion | Seguir puertas de avance |

## Decisiones y bloqueos

- D-001 (22-09-2026): prioridad a fotografias cercanas de hojas y ejecucion local en iPhone.
- D-002 (22-09-2026): los espejos del conjunto de 3.400 imagenes no se suman como ejemplos independientes.
- D-003 (22-09-2026): edad, dosis de riego y luz necesaria fuera del alcance de prediccion por foto unica.
- D-004 (22-09-2026): la fase 0 usa solo Python estandar, `make` y Git; no introduce dependencias externas ni red.
- D-005 (22-09-2026): los comandos de fases futuras (`data-audit`, `train`, `evaluate`, `export-coreml`, `check-ios`) existen como interfaz objetivo pero fallan explicitamente hasta que se implementen con comprobaciones reales.
- D-006 (22-09-2026): `configs/datasets.json` es la fuente estructurada para inventario; `reports/datasets.md` es el resumen humano. Ambos deben mantenerse sincronizados.
- D-007 (22-09-2026): una fuente solo puede marcarse `APTO_PARA_AUDITORIA` si declara licencia verificable y enlaza evidencia. En fase 1 solo Roboflow queda apta, y solo para auditoria, no para diagnostico ni entrenamiento definitivo.
- D-008 (22-09-2026): los recuentos de imagenes de fase 1 son declarados, no verificados; la fase 2 debe contarlos desde archivos reales si hay permiso de descarga.
- B-001: acceso/licencias de datos y ausencia de fotos propias por verificar; no impide fase 0.
- B-002: avisos de macOS por no poder crear cache temporal de `xcrun` en `/tmp` durante `make`; no bloquearon `setup`, `check` ni `status` en esta sesion.
- B-003: repositorio `https://github.com/optim762-prog/olive_leaf_diseases` indicado por Grati et al. devolvio 404 durante fase 1; no usarlo hasta recuperar acceso o contactar autores.
- B-004: los datasets Kaggle `serhathoca`, `techplusmentor` e `hikmetdurmaz` quedan pendientes de licencia directa; el espejo Kaggle de 3.400 hojas queda pendiente por derechos de origen.

## Siguiente accion

Iniciar fase 2: implementar `make data-audit` con fixtures sinteticos primero y, solo si hay permisos resueltos, preparar auditoria de imagenes reales. No descargar fuentes pendientes de licencia/acceso. La primera auditoria real permitida por el manifiesto es Roboflow, limitada a revision de calidad/procedencia y con atribucion CC BY 4.0; los demas origenes requieren resolver bloqueos.

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

- Apple: clasificar imagenes con Vision y Core ML.
- Mohanty et al. (2016), generalizacion de modelos de enfermedad vegetal: prueba de por que evaluar con imagenes nuevas y de campo.
- Grati et al. (2026), generalizacion entre conjuntos de hojas de olivo.
