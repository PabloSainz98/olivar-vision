# Linea prioritaria LiDAR, biomasa y carbono

Fecha de revision: 26 de septiembre de 2026.

Estado: `L0 y L1 EN CURSO - PENDIENTE DE DISPOSITIVO Y CAMPO`; `L2 y L3
PREPARADAS EN SINTETICO - PUERTAS PENDIENTES`; `L4 PLANIFICADA`. Esta linea es
la prioridad actual. El clasificador de hojas queda en pausa en fase 2, sin
eliminar ni modificar su trabajo.

## Objetivo y limite de la primera prueba

Evaluar si un iPhone con LiDAR puede producir medidas 3D repetibles de un olivo
y si esas medidas pueden servir, tras validacion local, como variables de una
estimacion de biomasa y carbono. La primera prueba fisica solo debe demostrar
captura, trazabilidad y calidad geometrica. El codigo puede comprobar calculos
con entradas sinteticas o diametro manual, pero eso no valida el olivar ni debe
mostrar `kg CO2/arbol/ano`.

No se descargaran datasets, no se entrenara ningun modelo y no se modificaran
la auditoria de imagenes ni el clasificador foliar en esta linea.

## Distinciones obligatorias

- **Volumen envolvente de copa:** espacio exterior ocupado por la copa segun
  una envolvente, voxeles o una forma alfa. Incluye huecos, hojas y aire. No es
  volumen de madera.
- **Volumen de madera visible:** volumen geometrico de tronco y ramas que el
  sensor alcanza y que un algoritmo segmenta. Omite madera ocluida y ramas por
  debajo de la resolucion efectiva.
- **Biomasa seca:** masa seca de componentes biologicos. No se obtiene
  multiplicando sin mas el volumen envolvente por densidad de madera.
- **Carbono almacenado:** fraccion de carbono de la biomasa seca en un momento.
  Debe declarar componentes incluidos y factor de carbono medido o justificado.
- **Cambio de stock:** diferencia de carbono entre dos fechas comparables. Una
  sola captura solo estima, como maximo, un stock puntual.
- **Captura anual de CO2:** cambio neto anualizado, con crecimiento y perdidas,
  convertido de C a CO2. Requiere al menos dos inventarios, intervalo conocido,
  trazabilidad de poda/mortalidad y propagacion de incertidumbre.

Para un reservorio definido, el metodo de diferencia de stocks usa
`delta_C_anual=(C_t2-C_t1)/(t2-t1)`. La conversion estequiometrica posterior es
`delta_CO2=delta_C*44/12`. Aun asi, el resultado es cambio neto del reservorio
medido, no fotosintesis bruta ni absorcion total del ecosistema.

La variacion de volumen de copa tras una poda no equivale a perdida de carbono:
hay que pesar o estimar la biomasa retirada y registrar si se quema, tritura,
incorpora al suelo, se usa como combustible o queda almacenada. Un escaneo
exterior tampoco observa raices, ramas ocultas, carbono del suelo, cubierta
vegetal, fruto ni otros reservorios del sistema.

## Compatibilidad del dispositivo

El repositorio no documenta el modelo de iPhone ni su version de iOS. Por ello,
la compatibilidad real esta `NO VERIFICADA`.

La puerta documental situa estos chequeos antes de validar L1. En este entorno
no se dispone del iPhone ni de Xcode completo, por lo que solo se implementaron
las partes de L1 comprobables con fixtures o grabaciones. Esto no satisface L0:
antes de validar L1 se debe registrar:

1. Modelo comercial e identificador de hardware del iPhone.
2. Version y compilacion de iOS.
3. Resultado en el dispositivo de
   `ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth)` y
   `.smoothedSceneDepth`.
4. Resultado de `supportsSceneReconstruction(.mesh)` y disponibilidad de
   `AVCaptureDevice.DeviceType.builtInLiDARDepthCamera`.
5. Resolucion, frecuencia y formatos reales de profundidad y color.

La muestra de Apple para acceso directo a la camara LiDAR usa iOS 15.4 o
posterior y hardware compatible. La aplicacion no debe decidir compatibilidad
solo por el nombre del telefono: los chequeos en tiempo de ejecucion son la
fuente de verdad.

## APIs Apple candidatas

### Ruta principal: ARKit

- `ARSession` y `ARWorldTrackingConfiguration` para seguimiento de pose.
- `frameSemantics = .sceneDepth` para profundidad instantanea y
  `.smoothedSceneDepth` para datos promediados temporalmente. La metrologia debe
  conservar la profundidad instantanea y comparar el suavizado, no sustituirla
  silenciosamente.
- `ARFrame.capturedImage`, `timestamp`, `camera.transform`,
  `camera.intrinsics`, `camera.imageResolution`, `sceneDepth.depthMap` y
  `sceneDepth.confidenceMap` para un registro reproducible.
- `sceneReconstruction = .mesh` y `ARMeshAnchor.geometry` como malla auxiliar.
  La malla de ARKit es una aproximacion mutable del entorno; no se tratara como
  verdad de volumen de ramas.

Para cada pixel de profundidad valido, una nube en coordenadas de camara puede
reconstruirse con `X=(u-cx)z/fx`, `Y=(v-cy)z/fy`, `Z=z`, y transformarse al
sistema de la sesion con la pose del frame. Deben conservarse intrinsecos,
orientacion y convencion de ejes junto a cada captura.

### Ruta de control: AVFoundation

La API `builtInLiDARDepthCamera`, con `AVCaptureVideoDataOutput`,
`AVCaptureDepthDataOutput` y `AVCaptureDataOutputSynchronizer`, permite capturar
video y `AVDepthData` sincronizados. `AVCameraCalibrationData` aporta los
intrinsecos. Esta ruta sirve para probar el sensor y la sincronizacion, pero no
proporciona por si sola el mapa mundial y las poses acumuladas de ARKit.

`RoomPlan` y Object Capture no son la base del piloto: estan orientados a otros
dominios y no resuelven la no rigidez, oclusion y ramas finas de una copa. Solo
podrian compararse como experimentos secundarios.

## Contrato de captura L1

Cada sesion privada se guardara fuera de Git, por ejemplo bajo
`data/field/lidar/<arbol>/<fecha-sesion>/`, con:

- `session.json`: dispositivo, iOS, app, operador, arbol, variedad, finca,
  fecha, hora, clima, viento cualitativo, poda reciente y protocolo.
- Frames de color y profundidad sin recomprimir, mapa de confianza, timestamp,
  intrinsecos, resolucion y pose.
- Malla ARKit opcional identificada como derivada.
- Puntos de control visibles, sus distancias medidas y una regla de escala.
- Registro de frames descartados y motivo, nunca solo el resultado filtrado.
- Hash SHA-256, tamano y version de formato de cada artefacto.

La exportacion sera local y requerira consentimiento. El prototipo debe poder
funcionar sin red y no depender de subir el olivar a un servicio externo.

### Formato v1 implementado

El formato `olivar-lidar-capture`, `schema_version: 1`, usa una raiz nueva por
captura y no permite reutilizarla:

- `session.json`: identidad de sesion y grupo de repeticion, tipo de fuente,
  contexto, dispositivo/iOS, capacidades consultadas, unidades, ejes, frames,
  descartes y referencias metricas.
- `captured/<frame>/`: planos RGB crudos, `depth.f32le`, `confidence.u8` y
  `frame.json`; cada artefacto declara formato, tamano y SHA-256.
- `derived/`: `points.f32le` y `geometry.json`, creados sin modificar los
  originales. La nube usa metros y el sistema ARKit de la sesion.
- `validation/report.json`: campos ausentes, motivos de rechazo, cobertura por
  muestra/frame, calidad, integridad de originales y estado de la puerta.

La camara optica se define como `x` derecha, `y` abajo y `z` hacia delante. La
pose almacenada la transforma al mundo ARKit de mano derecha con `y` hacia
arriba. Los intrinsecos se escalan explicitamente a la resolucion de profundidad.
La salida fija `surface_completeness: unknown` y
`represents_complete_tree_volume: false`; L1 no cierra superficies ni calcula
volumen, biomasa, carbono o CO2.

Flujo privado:

```bash
make lidar-process SESSION=data/field/lidar/<arbol>/<sesion>
make lidar-compare LEFT=/ruta/repeticion-1 RIGHT=/ruta/repeticion-2 \
  OUTPUT=/ruta/privada/comparacion.json
```

`SystemLidarCapabilityDetector` consulta las APIs ARKit y AVFoundation. Fuera de
iOS, o sin `sceneDepth` y camara LiDAR, devuelve `unsupported` con motivo; no
genera compatibilidad simulada. `ARKitCaptureController` solo arranca si el
chequeo real es compatible y registra frames descartados por tracking,
profundidad o confianza ausentes. `LidarCaptureView` presenta esas capacidades,
el motivo de bloqueo, una vista AR y el estado de una captura, generando una
sesion nueva en cada inicio. Durante la captura permite seleccionar dos
`featurePoint` de una referencia, introducir la distancia medida y conservar
ambos puntos mundiales, tolerancia e ID en `scale_references`. La seleccion se
debe contrastar con la cinta; registrarla no demuestra por si sola la escala.

### Preparacion sintetica de L2 y L3

L1 sigue siendo captura y trazabilidad. Dos modulos separados preparan trabajo
posterior sin cambiar sus puertas:

- `lidar_geometry.py` lee una nube L1 verificada por hash, conserva sus limites
  observados y solo publica altura, extensiones de copa y diametro basal si el
  arbol esta aislado, hay referencia de suelo y las coberturas operativas se
  cumplen. El diametro ajusta un circulo en el plano XZ a 0,30 m, informa
  cobertura angular y RMSE radial. Siempre declara superficie abierta y nunca
  publica volumen completo.
- `biomass_carbon.py` implementa un unico modelo versionado y bloquea entradas
  ausentes, LiDAR no validado o dominio incompatible. Biomasa seca aerea,
  carbono y CO2e almacenado se guardan como resultados distintos. La salida
  fija la puerta L3 en
  `PENDING_LOCAL_CALIBRATION_AND_INDEPENDENT_VALIDATION`.

Comandos, todos sin sobrescritura:

```bash
make lidar-geometry SESSION=/ruta/sesion OUTPUT=/ruta/geometria.json \
  TREE_ISOLATED=1 VERTICAL_COVERAGE=0.9 GROUND_Y_M=0
make lidar-geometry-compare LEFT=/ruta/geometria-1.json \
  RIGHT=/ruta/geometria-2.json OUTPUT=/ruta/comparacion-geometria.json
make biomass-estimate INPUT=configs/biomass-carbon.example.json \
  OUTPUT=/ruta/nueva/estimacion.json
```

Los umbrales operativos v1 de geometria son al menos 12 puntos, cobertura de
muestras 0,50, cobertura vertical 0,80, cobertura angular basal 0,75 y RMSE
radial basal maximo 0,02 m. Son guardas de software para no publicar medidas
obviamente incompletas, no umbrales de aceptacion de L2 ni evidencia de campo.
La comparacion geometrica exige dos sesiones del mismo grupo de repeticion y
registra diferencias absolutas y relativas sin sobrescribir los informes. No
convierte esas diferencias en una validacion de precision o repetibilidad.

## Limites observados y consecuencias

- Una evaluacion del iPhone 12 Pro midio un alcance maximo cercano a 5 m, una
  fuerte caida de densidad con la distancia y un limite de deteccion de objetos
  de unos 5 cm. Ramas finas y la parte alta de una copa pueden faltar.
- En 18 olivos `Ascolana Tenera`, un iPhone 14 Pro Max subestimo el volumen de
  copa frente a un escaner movil profesional: RMSE 15,66 m^3 y RMSE relativo
  40,23 %. El error crecio con el tamano de la copa y las nubes necesitaron
  filtrado manual.
- Hojas movidas por viento rompen la hipotesis de escena rigida; hojas y ramas
  producen oclusiones y multiples superficies a una misma direccion de vista.
- La malla o una envolvente puede cerrar huecos no observados. Todo volumen debe
  indicar algoritmo, resolucion de voxel/parametros, cobertura y porcentaje de
  puntos por nivel de confianza.
- Los chequeos deben separar error de escala, deriva de pose, falta de cobertura,
  segmentacion del arbol y error del modelo alometrico.

Por estas razones, la primera salida 3D sera una medicion experimental con mapa
de cobertura e incertidumbre, no una representacion completa del arbol.

## Modelo v1 implementado y alternativas

Solo la ecuacion DB de Brunori se implementa como calculo experimental. No esta
aprobada como modelo local L3. Las demas siguen siendo referencias para evaluar;
que usen variables medibles con un movil no demuestra que sean validas para otra
variedad, manejo, edad, densidad o clima.

### Brunori et al. (2017), cultivar Leccino

- Datos: 14 arboles de seis olivares de Umbria, Toscana y Sicilia; secano
  tradicional, formacion en vaso y 70-250 arboles/ha. Diametro basal `DB` entre
  5 y 45 cm. Solo 12 arboles tenian diametro `D80` a 80 cm.
- Componentes: biomasa seca aerea, radical, total, ramas, ramillas y follaje;
  volumen de copa, volumen aereo y area foliar.
- Implementada como `brunori-2017-leccino-db-agb-v1`:
  `AGB_seca_aerea_kg = 0.0538 * DB_cm^2.4208`. `DB` es diametro basal sobre el
  tocon; la referencia practica del articulo lo situa a 0,30 m. La ecuacion D80
  `0.1202 * D80_cm^2.2159` no se implementa en v1.
- Validacion: ajuste destructivo, seleccion por AIC/MAE/RMSE y bootstrap de
  parametros con 1.000 remuestreos. El RMSE de ajuste publicado para la ecuacion
  elegida es 9,6909 kg; no es un intervalo individual. No consta validacion
  externa independiente y los autores indican mayor fiabilidad desde DB 10 cm.
- Limite: muestra pequena y de una sola variedad; poda y forma alteran altura y
  arquitectura. El codigo bloquea otra variedad, sistema de formacion, regimen,
  densidad, altura de medida o DB fuera de 5-45 cm. La sensibilidad incluida
  solo propaga `DB +/- incertidumbre de cinta`; no es un intervalo de confianza.

#### Contraste con el PDF primario (26-09-2026)

Se leyo el texto completo de la copia CNR-IBE (paginas 1859-1874). Resultado:

- **Confirmado:** Tabla 2a, DB -> biomasa aerea en materia seca (kg), ley
  potencial directa `y = 0.0538 x^2.4208`, ajustada sin transformacion
  logaritmica ni factor de correccion. La Tabla 3a da el coeficiente con mas
  cifras (`0.05379`); la diferencia relativa con `0.0538` es de 0,02 % y se
  mantiene el valor de la Tabla 2a. El articulo nombra `a` al exponente y `b`
  al coeficiente (`y = b*x^a`), al reves que la notacion habitual.
- **Estadisticos:** RMSEabs 9,6909 kg, r 0,997 (no publica R^2), "MAE"
  -2,0512 kg (con signo, es un sesgo medio) y AIC 102. El bootstrap de 1.000
  remuestreos da rangos min-max del exponente 1,8821-2,5764 y del coeficiente
  0,029975-0,28775; los autores califican esa incertidumbre de grande. No hay
  errores estandar ni intervalos de confianza de los parametros.
- **Definicion de DB:** el articulo la define como diametro medible sobre el
  tocon y **cita** a Villalobos et al. (2005) para medir a 0,3 m; no declara la
  altura usada en sus propios arboles ni una tolerancia. La altura de
  0,30 +/- 0,02 m es por tanto una **convencion operativa del proyecto**.
  Tampoco documenta si usaron cinta o calibre, ni troncos multiples.
- **Dominio inconsistente dentro del articulo:** el texto dice 70-250
  arboles/ha, pero la Tabla 1 lista 330, 277, 300, 285, 70 y 286 arboles/ha.
  El texto dice clases de DB de 5 a 45 cm, pero la Tabla 4 lista DB observados
  de 1,0 a 44,5 cm y el texto restringe las estimaciones a DB mayor de 1 cm.
  El codigo mantiene la interpretacion mas restrictiva (70-250 arboles/ha y
  DB 5-45 cm). Ampliarla es una decision pendiente del usuario, no un cambio
  silencioso.
- **Fiabilidad bajo 10 cm:** la conclusion situa la mayor fiabilidad desde
  10 cm, pero la seccion de resultados indica que la ecuacion de AGB
  concretamente estima correctamente tambien por debajo. Se conserva el aviso.
- **Fraccion de carbono:** el articulo no publica ninguna; la fraccion sigue
  siendo una entrada externa obligatoria.
- **Componentes:** la AGB suma follaje, ramillas, ramas, tronco y tocon
  (la Figura 5 incluye el tocon en el tronco). Los arboles se arrancaron tras la
  poda invernal, por lo que la ecuacion describe biomasa posterior a poda.

### Ruiz-Peinado, Montero y del Rio (2012), acebuche

- Datos: `Olea europaea var. sylvestris` en rodales del sur de Cadiz; 17 arboles
  para biomasa aerea y 5 para raices. DAP `d` 10,0-40,5 cm, altura `h`
  4,9-11,0 m y biomasa aerea observada 25-426 kg.
- Componentes, en kg de materia seca: fuste con corteza
  `Ws=0.0114*d^2*h`; ramas mayores de 7 cm `Wb7=0.0108*d^2*h`; ramas de
  2-7 cm `Wb2_7=1.672*d`; ramas menores de 2 cm mas hojas
  `Wb2_l=0.0354*d^2+1.187*h`; raices `Wr=0.147*d^2`.
- Validacion: ecuaciones aditivas ajustadas por regresion SUR; eficiencia de
  modelo de 0,54-0,93 segun componente. Compararon el ajuste con modelos
  anteriores, no con un olivar cultivado independiente.
- Limite: acebuche forestal, DAP y alturas superiores a muchos olivares podados;
  no representa automaticamente cultivares ni marcos agricolas.

### Velazquez-Marti, Lopez-Cortes y Salazar-Hernandez (2014)

- Metodo: modela ramas como solidos de revolucion y relaciona volumen aparente
  de copa con volumen real de madera mediante un factor de ocupacion.
- Resultado publicado: cerca de 40 % de la madera en tronco y 60 % en copa; el
  mejor predictor del volumen de madera de copa fue su diametro (`R^2=0,74`).
- Limite: la ficha accesible no documenta aqui variedad, rango dimensional ni
  validacion externa. Hay que revisar el articulo completo y reproducir sus
  definiciones antes de implementar cualquier coeficiente.

### Fernandez-Sarria et al. (2019), residuo de poda con TLS

- Datos: 32 olivos de dos olivares y tres clases de edad en Viver, Castellon.
- Variables: altura total/de copa, diametro de copa, cuatro volumenes de copa y
  estadisticos de altura de la nube TLS.
- Resultado: biomasa de poda pesada, no biomasa total. Los volumenes lograron
  `R^2=0,86`, RMSE 2,78 kg; al anadir varianza de alturas, `R^2=0,92`, RMSE
  2,01 kg.
- Limite: no transferir coeficientes de TLS profesional al iPhone sin validacion;
  el destino del residuo sigue siendo necesario para contabilizar carbono.

### Torrus-Castillo et al. (2026), referencia de carbono

- Datos: tres arboles por cultivar, `Arbosana` y `Picual`, de 7,5 anos, regadio
  deficitario y alta densidad (1.000 arboles/ha) en Granada.
- Componentes: tronco, ramas, hojas, raices por clase y suelo hasta 1,30 m;
  medicion destructiva y geometrica. Carbono medio medido: 47 % en biomasa
  aerea y 42 % en raices.
- Validacion: la comparacion no destructiva uso densidades obtenidas de los
  mismos arboles, por lo que los autores advierten circularidad y que no es una
  validacion independiente.
- Limite: seis arboles y sistema en seto. Su tasa anual es stock total dividido
  por edad, no una medicion repetida de absorcion anual; sus factores no son
  valores por defecto para otro olivar. El software exige valor y fuente; el
  ejemplo usa 0,47 marcado como proxy explicito y no como validacion de Leccino.

## Protocolo del piloto geometrico

El piloto inicial propuesto usa 12 arboles como prueba de ingenieria, no como
validacion estadistica de carbono: cuatro pequenos, cuatro medianos y cuatro
grandes dentro del olivar. Si no hay inventario previo, las clases se definen
por cuantiles del perimetro basal medido antes de elegir los arboles.

1. Asignar ID persistente y registrar variedad, marco, manejo, fecha de ultima
   poda, riego y danos visibles. No inferir edad si no esta documentada.
2. Medir con cinta perimetros a 0,30 m, 0,80 m y 1,30 m cuando la forma lo
   permita; anotar bifurcaciones y criterio exacto. Medir altura total, altura
   de base de copa y dos diametros ortogonales con instrumento de referencia.
3. Colocar al menos dos referencias metricas rigidas alrededor del arbol y
   registrar sus distancias con cinta. Delimitar una zona segura de recorrido.
4. Capturar tres vueltas independientes por arbol, reiniciando la sesion entre
   vueltas. Alternar operador o repetir un subconjunto con segundo operador.
5. Escanear a distancia corta y estable, con velocidad lenta, cerrando el
   recorrido. Registrar viento, luz, oclusiones y zonas no alcanzables.
6. Repetir cuatro arboles el mismo dia tras 30 minutos para repetibilidad y en
   otra fecha comparable para reproducibilidad. No podar entre ambas visitas.
7. Segmentar suelo, arbol objetivo y vecinos conservando la nube original.
   Calcular cobertura angular/vertical y huecos antes de producir volumen.
8. Obtener por separado dimensiones, volumen envolvente por al menos dos
   metodos y volumen de madera visible. No convertirlos aun a biomasa.

Metricas minimas: sesgo, MAE, RMSE, error relativo y limites de acuerdo frente a
referencias; coeficiente de variacion entre repeticiones; cobertura; porcentaje
de profundidad de confianza alta/media/baja; tiempo, fallos y temperatura del
dispositivo. Los resultados se estratifican por tamano, viento y operador.

## Entregables y puertas L0-L4

| Nivel | Estado actual | Entregable | Puerta de avance |
| --- | --- | --- | --- |
| L0. Factibilidad | EN CURSO - PENDIENTE DE DISPOSITIVO Y CAMPO | Este estudio, matriz de APIs, modelo exacto de iPhone, chequeos de capacidad y protocolo aprobado | Dispositivo identificado; depth/mesh probados en el hardware real; variables objetivo y referencias de campo acordadas |
| L1. Captura trazable | EN CURSO - PENDIENTE DE DISPOSITIVO Y CAMPO | Prototipo iOS offline y paquete versionado de RGB, profundidad, confianza, intrinsecos y poses; exportacion privada | Tests sinteticos de proyeccion y transformacion; sesion real completa sin campos silenciosamente ausentes; escala verificada con referencias |
| L2. Geometria validada | PREPARADA EN SINTETICO - PUERTA PENDIENTE | Codigo de altura/copa/diametro con cobertura y calidad; falta informe del piloto con nubes originales/derivadas, repetibilidad, sesgo, MAE/RMSE e incertidumbre | Umbrales de uso de campo pre-registrados y cumplidos para cada variable aceptada; si el volumen de copa falla, reducir alcance a diametro/altura |
| L3. Biomasa local | PREPARADA EN SINTETICO - PUERTA PENDIENTE | Ecuacion Brunori DB v1 y conversion de stock aisladas; faltan calibracion local por componente, variedad/manejo, validacion por arbol/finca e intervalos | Referencia destructiva o profesional independiente suficiente; error e incertidumbre aceptables; ningun modelo se valida solo porque sus entradas caben en el movil |
| L4. Cambio de carbono | PLANIFICADA | Dos o mas inventarios comparables, registro de poda/destino, factores de carbono y reporte de cambio de stock por intervalo | Un ciclo temporal valido, balance de ganancias/perdidas, propagacion de incertidumbre y revision experta; solo entonces evaluar un claim anual limitado |

L0-L4 son independientes de las fases 0-7 de hojas. Avanzar aqui no abre la
puerta de la fase 3 principal ni permite marcar como validada la fase 2.

## Pruebas y criterios de rechazo

- Unitarias: proyeccion profundidad-a-punto con fixture conocido, transformacion
  de coordenadas, unidades, orientacion, serializacion y hashes.
- Integracion: sincronizacion de color/profundidad, monotonia de timestamps,
  intrinsecos compatibles con resolucion, poses finitas y exportacion/importacion
  sin cambiar recuentos ni hashes.
- Geometria: objeto rigido de dimensiones conocidas a varias distancias antes
  de escanear arboles; prueba de bucle y escala al cerrar el recorrido. Las
  pruebas sinteticas de cilindro/copa solo verifican las matematicas.
- Biomasa/carbono: ecuacion y unidades conocidas, dominio, entradas ausentes,
  factor de carbono y fuente, bloqueo de diametro LiDAR no validado, conversion
  `44/12` y sensibilidad de la medida. Ninguna fixture valida el modelo agronomico.
- Campo: tres repeticiones, cobertura declarada y comparacion ciega con cinta o
  instrumento de referencia.
- Regresion: conservar sesiones congeladas de banco y campo; toda nueva version
  debe comparar sesgo/MAE/RMSE y no solo una visualizacion atractiva.

Se rechaza una sesion si faltan intrinsecos/poses, cambia la escala, hay movimiento
fuerte de copa, no se cierra suficiente cobertura o el arbol no puede aislarse.
Se rechaza una ecuacion si especie/variedad, manejo, rango o componente no son
comparables, si carece de referencia independiente o si no puede propagarse su
incertidumbre.

## Primer ensayo de campo ejecutable

Antes del piloto de 12 arboles, hacer un ensayo de banco y un solo arbol:

1. Confirmar el modelo de iPhone y los cuatro chequeos de capacidad de L0.
2. Escanear una caja o marco rigido con tres dimensiones medidas, a 1, 2 y 4 m.
3. Escanear un olivo pequeno tres veces, sin viento apreciable, con dos reglas
   metricas visibles y medidas manuales en 0,30/0,80/1,30 m y copa.
4. Exportar datos crudos, reconstruir la nube y emitir un informe de cobertura,
   repetibilidad y error. Puede calcularse el escenario experimental con el
   diametro manual si se cumple el dominio, pero no cuenta como validacion L2/L3.

El ensayo solo autoriza L1 si los artefactos son completos y la escala se
mantiene. No autoriza L2-L4.

Estado del ensayo a 26-09-2026: `NO EJECUTADO`. Modelo de iPhone, iOS,
capacidades, medidas a 1/2/4 m y tres repeticiones del olivo: `NO VERIFICADOS`.

## Registro de implementacion

Archivos principales cambiados:

- `src/olivar_vision/lidar_capture.py` y `scripts/lidar_session.py`: validacion,
  proyeccion, transformacion, integridad, geometria parcial y comparacion.
- `src/olivar_vision/lidar_geometry.py` y `scripts/olive_metrics.py`: medidas
  de formas aisladas, calidad/cobertura, diametro basal y CLI sin sobrescritura.
- `src/olivar_vision/biomass_carbon.py` y
  `configs/biomass-carbon.example.json`: ecuacion v1, dominio, sensibilidad y
  stock de C/CO2e con factor explicito.
- `ios/OlivarLidarCapture/`: contrato Swift, deteccion del sistema, escritor
  offline, controlador ARKit, estimador equivalente y vistas separadas.
- `ios/OlivarVisionLidarApp/`: host SwiftUI instalable, contexto de sesion,
  grupos de repeticion y exportacion local mediante Archivos.
- `tests/test_lidar_capture.py`, `tests/test_lidar_geometry.py`,
  `tests/test_biomass_carbon.py` y `tests/test_apple_toolchain.py`: captura,
  formas conocidas, dominios/rechazos y diagnostico del host.
- `scripts/check_apple_toolchain.py`: diagnostico reproducible de Xcode, Swift
  y SDK antes de intentar compilaciones iOS.
- `.gitignore`, `Makefile`, `scripts/check_structure.py`,
  `src/olivar_vision/status.py`, `tests/test_status.py`, `README.md`,
  `docs/README.md` y este documento: comandos, exclusiones, guardas y estado
  real.

Resultados locales del 26-09-2026:

- `make check`: OK, 49 pruebas totales; 8 fuentes del manifiesto y estructura OK.
- `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 -m unittest
  tests.test_lidar_capture tests.test_lidar_geometry tests.test_biomass_carbon
  tests.test_apple_toolchain`: OK, 31 pruebas.
- `make biomass-estimate INPUT=configs/biomass-carbon.example.json
  OUTPUT=/tmp/olivar-biomass-example-20260926.json`: OK; ejemplo sintetico de
  DB 20 cm produjo 75,912919 kg de AGB seca, 35,679072 kg C y 130,823263 kg
  CO2e con proxy 0,47. La repeticion contra la misma salida fallo con codigo 2
  y no la sobrescribio.
- `swiftc -frontend -parse ...`: OK para las fuentes y pruebas Swift.
- `plutil -lint` del proyecto/Info.plist y `xmllint` del esquema: OK.
- `make check-apple-toolchain`: BLOQUEADO de forma explicita; directorio activo
  `/Library/Developer/CommandLineTools`, sin Xcode completo.
- `swift test --package-path ios/OlivarLidarCapture`: BLOQUEADO al inicializar
  XCBuild (`Unknown error parsing property list`); `swiftc -typecheck` confirma
  ademas Swift 6.4.0.34.1 frente a SDK 6.4.0.31.4. No compilo el paquete.
- `make check-ios`: BLOQUEADO antes de compilar por falta de Xcode completo.

Estos resultados validan logica sintetica y sintaxis, no el sensor, la escala ni
la precision. L0 y L1 siguen abiertos. El siguiente ensayo concreto es corregir
el toolchain, compilar para iOS, identificar iPhone/iOS/capacidades, medir un
objeto rigido a 1, 2 y 4 m y capturar tres veces un olivo pequeno con referencias.

## Datos que faltan antes de validar una estimacion de carbono

- Modelo de iPhone/iOS y capacidad real del sensor.
- Inventario de arboles, IDs persistentes, variedad, edad o ano de plantacion,
  marco, manejo, historial de poda, riego y estado.
- Rangos locales de diametro/altura/copa y cobertura LiDAR alcanzable.
- Medidas de referencia y, para volumen complejo, un subconjunto con TLS/MLS o
  fotogrametria metrica independiente.
- Densidad basica, humedad, fraccion seca y fraccion de carbono por componente,
  variedad y protocolo de laboratorio, o una justificacion documentada de los
  factores usados.
- Referencia local de biomasa por componentes y validacion independiente.
- Dos o mas fechas comparables; poda, mortalidad, cosecha y destino de residuos.
- Definicion explicita de reservorios incluidos: biomasa aerea, raices, suelo,
  cubierta, residuos y productos. Los no medidos se reportan como excluidos.
- Presupuesto de incertidumbre desde sensor, segmentacion y geometria hasta
  alometria, materia seca, fraccion de C y conversion a CO2.

Sin estos datos solo se puede informar geometria experimental y un escenario
alometrico explicitamente no validado. Tras cumplir L3 se podra informar un
stock parcial con incertidumbre. L4 sigue siendo imprescindible para cualquier
cambio temporal, y no se informa absorcion anual.

## Referencias

- Apple, [Capturing depth using the LiDAR camera](https://developer.apple.com/documentation/AVFoundation/capturing-depth-using-the-lidar-camera).
- Apple, [ARFrame](https://developer.apple.com/documentation/arkit/arframe) y
  [scene reconstruction](https://developer.apple.com/documentation/ARKit/ARWorldTrackingConfiguration/sceneReconstruction).
- Apple, [Visualizing and interacting with a reconstructed scene](https://developer.apple.com/documentation/arkit/visualizing-and-interacting-with-a-reconstructed-scene).
- Luetzenburg, Kroon y Bjork (2021), [Evaluation of the Apple iPhone 12 Pro LiDAR for an Application in Geosciences](https://doi.org/10.1038/s41598-021-01763-9), *Scientific Reports* 11, 22221.
- Chiappini et al. (2024), [Comparing the accuracy of 3D urban olive tree models detected by smartphone using LiDAR sensor, photogrammetry and NeRF](https://doi.org/10.5194/isprs-annals-X-3-2024-61-2024), *ISPRS Annals* X-3, 61-68.
- Brunori et al. (2017), [Biomass and volume modeling in Olea europaea L. cv. Leccino](https://doi.org/10.1007/s00468-017-1592-9), *Trees* 31, 1859-1874; [copia primaria de CNR-IBE](https://webibe.ibe.cnr.it/IBE/personale/cantini-claudio/copie-delle-pubblicazioni/trees-31-1859-1874-2017.pdf).
- Ruiz-Peinado, Montero y del Rio (2012), [Biomass models to estimate carbon stocks for hardwood tree species](https://doi.org/10.5424/fs/2112211-02193), *Forest Systems* 21(1), 42-52.
- Velazquez-Marti, Lopez-Cortes y Salazar-Hernandez (2014), [Dendrometric analysis of olive trees for wood biomass quantification in Mediterranean orchards](https://doi.org/10.1007/s10457-014-9718-1), *Agroforestry Systems* 88, 755-765.
- Fernandez-Sarria et al. (2019), [Estimating residual biomass of olive tree crops using terrestrial laser scanning](https://doi.org/10.1016/j.jag.2018.10.019), *International Journal of Applied Earth Observation and Geoinformation* 75, 163-170.
- Torrus-Castillo et al. (2026), [Quantification of aboveground and belowground biomass and associated organic carbon in two olive cultivars](https://doi.org/10.1007/s00468-026-02760-z), *Trees*.
- IPCC (2006), [AFOLU, Chapter 2: Generic Methodologies Applicable to Multiple Land-Use Categories](https://www.ipcc-nggip.iges.or.jp/public/2006gl/pdf/4_Volume4/V4_02_Ch2_Generic.pdf), especialmente el metodo de diferencia de stocks entre dos fechas.
