# Inventario formal de datasets

Fecha de consulta: 2026-09-22.

Este informe corresponde a la fase 1. No descarga imagenes, archivos RAR/ZIP, pesos ni datos privados. Los recuentos indicados son declarados por las fuentes o por articulos secundarios; no son recuentos verificados. La verificacion de archivos, duplicados, corrupcion y fugas entre particiones queda para la fase 2.

## Resumen ejecutivo

| Fuente | Estado de uso | Licencia | Decision |
| --- | --- | --- | --- |
| `github_sinanuguz_cnn_olive_dataset` | `PENDIENTE_DE_LICENCIA` | Sin licencia visible | Candidato base, bloqueado hasta resolver permiso/origen |
| `kaggle_habibulbasher_olive_leaf_image_dataset` | `PENDIENTE_DE_LICENCIA` | CC0 declarado por espejo | Posible espejo; no cuenta como fuente independiente |
| `github_optim762_olive_leaf_diseases` | `PENDIENTE_DE_ACCESO` | Dataset sin licencia verificada | Alta prioridad si reaparece el repositorio o responden autores |
| `roboflow_hahmedai_olive_s_leaf_diseases` | `APTO_PARA_AUDITORIA` | CC BY 4.0 declarado | Puede auditarse en fase 2 con atribucion y revision de procedencia |
| `kaggle_serhathoca_zeytin` | `PENDIENTE_DE_LICENCIA` | No verificada | Util para repilo/peacock eye si se resuelve licencia |
| `zenodo_8144164_uav_verticillium` | `FUERA_DE_DOMINIO` | No verificada en pagina | Solo referencia futura de dron; no usar para modelo movil terrestre |
| `kaggle_techplusmentor_olive_leaf_disease_datasets` | `PENDIENTE_DE_LICENCIA` | No verificada | Fuente citada para 6971 imagenes; auditar solo tras licencia |
| `kaggle_hikmetdurmaz_zeytin_yaprak_224_aug` | `PENDIENTE_DE_LICENCIA` | No verificada | Fuente procesada/augmented citada; baja prioridad |

## Fichas por fuente

### `github_sinanuguz_cnn_olive_dataset`

- URL: https://github.com/sinanuguz/CNN_olive_dataset
- Evidencia consultada: repositorio GitHub, listado con README y archivos `Train1.rar`, `Train2.rar`, `train3.rar`, `train4.rar`, `test.rar`.
- Contenido declarado: 3400 imagenes de hojas de olivo de Denizli, Turquia; clases `healthy`, `olive_peacock_spot` y `aculus_olearius`.
- Licencia: `NO_LICENSE_FOUND`; no se observo licencia explicita en la pagina consultada.
- Estado: `PENDIENTE_DE_LICENCIA`.
- Razon: es probablemente la fuente original del conjunto de 3400 imagenes, pero no debe descargarse ni redistribuirse sin permiso verificable.
- Requisito fase 2: resolver derechos, registrar hashes de los RAR, preservar la division original y comprobar solapamientos.

### `kaggle_habibulbasher_olive_leaf_image_dataset`

- URL: https://www.kaggle.com/datasets/habibulbasher01644/olive-leaf-image-dataset
- Evidencia consultada: pagina Kaggle indexada con licencia `CC0: Public Domain`, 3400 archivos, 2720 entrenamiento y 680 prueba.
- Contenido declarado: mismas tres clases y mismo origen Denizli que el dataset original.
- Licencia: `CC0-1.0` declarada por el espejo; derechos del origen no resueltos.
- Estado: `PENDIENTE_DE_LICENCIA`.
- Razon: tratar como espejo sospechoso, no como datos independientes ni como permiso suficiente sobre el original.
- Requisito fase 2: comparar hashes exactos/perceptuales contra la fuente GitHub y no sumar recuentos.

### `github_optim762_olive_leaf_diseases`

- URL articulo: https://link.springer.com/article/10.1007/s44163-026-01441-7
- URL repo indicada por articulo: https://github.com/optim762-prog/olive_leaf_diseases
- Evidencia consultada: articulo de Grati et al. 2026 y apertura directa del repositorio, que devolvio 404 durante esta fase.
- Contenido declarado: dataset de campo de Tunez y Libano; muestra externa de 180 imagenes anotadas por expertos; clases `healthy`, `olive_peacock_spot` y `aculus_olearius`.
- Licencia: articulo bajo CC BY-NC-ND 4.0, pero licencia del dataset/repositorio no verificada.
- Estado: `PENDIENTE_DE_ACCESO`.
- Razon: es la candidata mas valiosa para validacion externa si se recupera acceso y licencia, pero ahora no hay artefacto verificable.
- Requisito fase 2: reintentar acceso, revisar `LICENSE`, datos reales, etiquetas y posible contacto con autores.

### `roboflow_hahmedai_olive_s_leaf_diseases`

- URL proyecto: https://universe.roboflow.com/hahmedai-whou6/olive-s-leaf-diseases
- URL version v3: https://universe.roboflow.com/hahmedai-whou6/olive-s-leaf-diseases/dataset/3
- Evidencia consultada: Roboflow Universe indica dataset de clasificacion con licencia CC BY 4.0, 2849 imagenes base visibles en el proyecto, version v3 generada el 2025-02-12 y export v3 con 5549 imagenes tras aumento; split 80/13/7.
- Contenido declarado: clases `healthy`, `aculus_olearius`, `knot_disease` y `olive_peacock_spot`; auto-orient, resize 640x640 y flip horizontal en version exportada.
- Licencia: `CC-BY-4.0` declarada.
- Estado: `APTO_PARA_AUDITORIA`.
- Razon: hay licencia declarada suficiente para planear una auditoria de metadatos/calidad en fase 2, con atribucion. No equivale a aprobacion clinica ni a entrenamiento definitivo.
- Requisito fase 2: distinguir originales de aumentos, revisar calidad y duplicados, documentar atribucion y verificar si `knot_disease` requiere fotos de ramas/gallas.

### `kaggle_serhathoca_zeytin`

- URL: https://www.kaggle.com/datasets/serhathoca/zeytin
- Evidencia secundaria: https://www.mdpi.com/2073-4395/16/11/1057
- Contenido declarado por literatura: 954 muestras de Edincik/Bandirma/Balikesir, Turquia; 572 sanas y 382 con peacock eye; hojas recogidas en campo pero fotografiadas en caja de luz.
- Licencia: no verificada en fase 1.
- Estado: `PENDIENTE_DE_LICENCIA`.
- Razon: util para repilo/peacock eye si la licencia se confirma; no representa fotos iPhone directas en arbol.
- Requisito fase 2: confirmar licencia directa en Kaggle, estructura, clases, resolucion y duplicados.

### `zenodo_8144164_uav_verticillium`

- URL: https://zenodo.org/records/8144164
- Evidencia consultada: Zenodo record con DOI `10.5281/zenodo.8144164`, ZIP de 4.5 GB, md5 `6acdd0261790bda07193d0b0679bb0f2`, UAV RGB de tres olivares griegos.
- Contenido declarado: deteccion de Verticillium en imagenes aereas RGB.
- Licencia: campo de licencia no capturado con valor visible en fase 1.
- Estado: `FUERA_DE_DOMINIO`.
- Razon: cambia completamente el punto de vista y la tarea; no debe entrenar el primer clasificador de hojas con iPhone.
- Requisito fase futura: solo reconsiderar cuando exista linea de trabajo aerea independiente.

### `kaggle_techplusmentor_olive_leaf_disease_datasets`

- URL: https://www.kaggle.com/datasets/techplusmentor/olive-leaf-disease-datasets
- Evidencia secundaria: Grati et al. 2026 usa este dataset como benchmark in-distribution.
- Contenido declarado por articulo: 6971 imagenes; clases `healthy`, `olive_peacock_spot`, `aculus_olearius`; conteos 1926 sanas, 3257 repilo/peacock spot y 1778 Aculus.
- Licencia: no verificada en fase 1.
- Estado: `PENDIENTE_DE_LICENCIA`.
- Razon: puede servir como benchmark controlado, pero no debe sustituir validacion externa ni asumirse independiente.
- Requisito fase 2: confirmar licencia Kaggle, procedencia, relacion con otros conjuntos y si contiene aumentos.

### `kaggle_hikmetdurmaz_zeytin_yaprak_224_aug`

- URL: https://www.kaggle.com/datasets/hikmetdurmaz/zeytin-yaprak-224-aug
- Evidencia secundaria: citado por Grati et al. 2026 como `Zeytin_Yaprak_224_Aug`.
- Contenido declarado: no verificado; el nombre sugiere imagenes 224x224 aumentadas/procesadas.
- Licencia: no verificada en fase 1.
- Estado: `PENDIENTE_DE_LICENCIA`.
- Razon: baja prioridad para una linea base honesta porque puede ser procesado/aumentado y no se confirmo independencia.
- Requisito fase 2: revisar solo si se resuelven licencia, origen y necesidad real.

## Decisiones de fase 1

- No se descarga ningun dato: ni imagenes, ni RAR, ni ZIP, ni pesos.
- Los recuentos declarados no son recuentos verificados.
- Solo `roboflow_hahmedai_olive_s_leaf_diseases` queda como `APTO_PARA_AUDITORIA`, y solo para auditoria de fase 2, no para entrenamiento definitivo.
- El dataset original `github_sinanuguz_cnn_olive_dataset` y su espejo Kaggle quedan bloqueados por licencia/origen.
- El repositorio de Grati et al. queda bloqueado por acceso pese a que el articulo declara disponibilidad.
- Zenodo UAV queda fuera del dominio del primer modelo movil terrestre.

## Fuentes consultadas

- https://github.com/sinanuguz/CNN_olive_dataset
- https://www.kaggle.com/datasets/habibulbasher01644/olive-leaf-image-dataset
- https://link.springer.com/article/10.1007/s44163-026-01441-7
- https://github.com/optim762-prog/olive_leaf_diseases
- https://universe.roboflow.com/hahmedai-whou6/olive-s-leaf-diseases
- https://universe.roboflow.com/hahmedai-whou6/olive-s-leaf-diseases/dataset/3
- https://www.kaggle.com/datasets/serhathoca/zeytin
- https://www.mdpi.com/2073-4395/16/11/1057
- https://zenodo.org/records/8144164
- https://www.kaggle.com/datasets/techplusmentor/olive-leaf-disease-datasets
- https://www.kaggle.com/datasets/hikmetdurmaz/zeytin-yaprak-224-aug
