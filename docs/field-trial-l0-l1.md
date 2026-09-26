# Ensayo de dispositivo y campo L0-L1

Fecha de preparacion: 26 de septiembre de 2026.

Estado: `NO EJECUTADO - CAPTURA LIDAR BLOQUEADA PARA EL CAMINO WEB`. Ninguna
celda de resultados se ha rellenado con datos reales ni sinteticos. Este
protocolo conserva los criterios de la primera evidencia fisica; no valida L0,
L1, L2 ni L3 por existir.

La decision vigente es usar la PWA de `web/` y no exigir una app iOS. Safari en
iPhone no expone la captura ARKit requerida por este ensayo. La PWA puede
registrar fotos, contexto, referencias externas y medidas manuales, pero no
ejecuta los pasos de profundidad. Las instrucciones nativas de este documento
quedan como referencia suspendida hasta elegir un capturador 3D externo o
recuperar expresamente el prototipo Swift como herramienta auxiliar.

## Dispositivo

| Campo | Valor | Procedencia |
| --- | --- | --- |
| Modelo comercial | iPhone 16 Pro | Declarado por el usuario el 26-09-2026; `NO VERIFICADO` en dispositivo |
| Identificador de hardware esperado | `iPhone17,1` | Identificador publico conocido para este modelo; debe coincidir con `device.hardware_identifier` de `session.json` |
| Version y compilacion de iOS | `PENDIENTE` | Ajustes > General > Informacion |
| `sceneDepth` | `PENDIENTE` | Pantalla "Compatibilidad real" de la app |
| `smoothedSceneDepth` | `PENDIENTE` | Idem |
| Malla de escena (`mesh`) | `PENDIENTE` | Idem |
| Camara LiDAR (`builtInLiDARDepthCamera`) | `PENDIENTE` | Idem |

Que el modelo comercial incluya un escaner LiDAR no sustituye a los cuatro
chequeos en tiempo de ejecucion. Si cualquiera sale en rojo, anotar el motivo
mostrado y detener el ensayo.

## Material

- iPhone 16 Pro cargado, cable y Mac con Xcode para instalar la app.
- Cinta metrica flexible (perimetros) y cinta o metro rigido (distancias).
- Calibre forestal si esta disponible; anotar cual se usa en cada medida.
- Objeto rigido con tres dimensiones medidas (caja o marco, >= 0,5 m).
- Dos reglas o listones rigidos de longitud conocida (p. ej. 1,00 m), con
  marcas visibles en ambos extremos. Son las dos referencias metricas.
- Estacas o conos para marcar 1, 2 y 4 m, y para el recorrido alrededor del arbol.
- Pertiga o hipsometro para la altura; nivel para marcar 0,30/0,80/1,30 m.
- Hoja de campo impresa (seccion final) y lapiz.

## Parte A. Banco: objeto rigido a 1, 2 y 4 m

1. Medir con cinta las tres dimensiones del objeto (largo, ancho, alto) dos
   veces y anotar la media y la diferencia.
2. En la app, rellenar arbol `banco-objeto-1`, operador y finca. Pulsar
   "Nuevo grupo" para crear un grupo de repeticiones exclusivo del banco.
3. Abrir "Captura LiDAR", anotar los cuatro indicadores y capturas de pantalla.
4. Para cada distancia (1, 2 y 4 m, medida con cinta del iPhone a la cara
   frontal): iniciar captura, barrer lentamente el objeto, registrar una
   referencia tocando los dos extremos de una arista medida e introducir su
   distancia real, y finalizar. Una sesion por distancia; no reutilizar sesiones.
5. Anotar el nombre de cada carpeta de sesion que muestra la app.

## Parte B. Olivo pequeno, tres repeticiones

Preparacion:

1. Elegir un olivo pequeno, de tronco unico si es posible, sin vecinos que se
   toquen y sin viento apreciable. Anotar ID persistente, variedad (si se
   conoce), fecha de ultima poda, riego y danos visibles.
2. Marcar 0,30, 0,80 y 1,30 m sobre el suelo en el lado de mayor pendiente
   hacia arriba (o el criterio que se use, siempre el mismo) y medir perimetro
   con cinta en cada altura. Diametro = perimetro / pi. Anotar bifurcaciones o
   irregularidades a esa altura. **No sustituir el DB a 0,30 m por otra altura.**
3. Medir altura total, altura de base de copa y dos diametros de copa
   ortogonales (N-S y E-O).
4. Colocar las dos reglas rigidas en el suelo a ambos lados del arbol, visibles
   desde el recorrido, y anotar su longitud medida.
5. Marcar un recorrido circular a distancia estable (1,5-2,5 m) y un punto de
   inicio.

Capturas:

1. En la app, pulsar "Nuevo grupo" una sola vez; las tres repeticiones deben
   compartir ese grupo. Rellenar arbol, operador, finca, tiempo, viento y poda.
2. Repeticion 1: iniciar captura en el punto de inicio, recorrer la vuelta
   completa a paso lento, apuntando al tronco y la copa, cerrar el recorrido en
   el punto de inicio. Durante la captura registrar las dos reglas como
   referencias (dos puntos por regla, con su distancia). Finalizar.
3. Salir a la pantalla principal (sin cambiar el grupo), volver a entrar y
   repetir para las repeticiones 2 y 3. Anotar hora y viento de cada una.
4. Anotar el nombre de las tres carpetas de sesion.

## Exportacion

En el flujo web, finalizar la sesion y descargar su TAR desde `Sesiones`. El
archivo usa `olivar-web-field-session` y debe guardarse fuera de Git. No se pasa
a `make lidar-process`, porque no contiene profundidad, confianza, intrinsecos
ni pose y no es un paquete L1.

La exportacion nativa siguiente solo aplica si se reactiva ese capturador:

1. Conectar el iPhone al Mac o usar Archivos > En mi iPhone > Olivar Vision
   LiDAR > lidar. Copiar **cada carpeta de sesion por separado**, sin renombrar
   ni editar, a:

   ```text
   data/field/lidar/<id-arbol>/<carpeta-de-sesion>/
   ```

   `data/field/` esta excluido de Git; no mover capturas a otra ruta del repo.
2. No borrar las sesiones del iPhone hasta haber comprobado los hashes.

## Procesado (en el Mac)

Para cada sesion; ningun comando sobrescribe salidas existentes:

```bash
make lidar-process SESSION=data/field/lidar/<id-arbol>/<sesion>
```

Comparar repeticiones del olivo (1-2, 1-3, 2-3):

```bash
make lidar-compare LEFT=data/field/lidar/<id>/<s1> RIGHT=data/field/lidar/<id>/<s2> OUTPUT=data/field/lidar/<id>/comparacion-s1-s2.json
```

Geometria experimental: `TREE_ISOLATED`, `VERTICAL_COVERAGE` y `GROUND_Y_M`
son **declaraciones del operador**, no valores calculados. Anotar en la hoja
como se decidieron; un valor optimista hace pasar las guardas sin que la
cobertura sea real.

```bash
make lidar-geometry SESSION=data/field/lidar/<id>/<s1> OUTPUT=data/field/lidar/<id>/geometria-s1.json TREE_ISOLATED=1 VERTICAL_COVERAGE=<fraccion> GROUND_Y_M=<y-suelo>
```

## Criterios de lectura

- **L0** se cumple si el modelo e iOS quedan registrados desde el dispositivo,
  los cuatro indicadores estan documentados y `sceneDepth` + camara LiDAR son
  compatibles.
- **L1** solo se cumple si: la app compila e instala; cada sesion tiene todos los
  campos sin ausencias silenciosas; `make lidar-process` valida hashes; y el
  error de escala de las referencias queda dentro de 0,02 m en banco y olivo.
- **L2 no se evalua con este ensayo**: tres repeticiones de un arbol permiten ver
  fallos y dispersion, no aceptar precision. Anotar diferencias sin convertirlas
  en validacion.
- Estimacion alometrica: puede calcularse con el DB manual a 0,30 m si el arbol
  cae en el dominio (Leccino, vaso, secano, 70-250 arboles/ha, DB 5-45 cm).
  Si no es Leccino, el resultado correcto es `ESTIMACION NO DISPONIBLE`.

## Hoja de campo

Rellenar a mano en campo; transcribir despues sin corregir valores.

### Banco

| Distancia | Dimension de referencia (m, cinta) | Distancia medida en app (m) | Error (m) | Carpeta de sesion | Observaciones |
| --- | --- | --- | --- | --- | --- |
| 1 m | NO EJECUTADO | | | | |
| 2 m | NO EJECUTADO | | | | |
| 4 m | NO EJECUTADO | | | | |

### Olivo: medidas manuales

| Variable | Valor | Instrumento | Observaciones |
| --- | --- | --- | --- |
| ID arbol / variedad / formacion / riego | NO EJECUTADO | | |
| Densidad de plantacion (arboles/ha) y marco | NO EJECUTADO | | |
| Fecha de ultima poda | NO EJECUTADO | | |
| Perimetro a 0,30 m (cm) -> DB | NO EJECUTADO | | |
| Perimetro a 0,80 m (cm) -> D80 | NO EJECUTADO | | |
| Perimetro a 1,30 m (cm) -> DBH | NO EJECUTADO | | |
| Altura total (m) | NO EJECUTADO | | |
| Altura base de copa (m) | NO EJECUTADO | | |
| Diametro de copa N-S / E-O (m) | NO EJECUTADO | | |
| Longitud regla 1 / regla 2 (m) | NO EJECUTADO | | |

### Olivo: repeticiones

| Repeticion | Hora | Viento | Carpeta de sesion | Error regla 1 (m) | Error regla 2 (m) | Frames descartados | Fallos |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | NO EJECUTADO | | | | | | |
| 2 | NO EJECUTADO | | | | | | |
| 3 | NO EJECUTADO | | | | | | |
