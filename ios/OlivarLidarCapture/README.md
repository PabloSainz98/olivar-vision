# Prototipo LiDAR, geometria, biomasa y carbono

Estado desde 26-09-2026: referencia historica/auxiliar. El cliente principal es
la PWA de `../../web/`; este paquete se conserva porque documenta el contrato
ARKit L1 que una web no puede obtener en Safari. No es requisito para usar el
producto web.

Paquete Swift offline para iOS 15.4 o posterior. Compilar no valida L0/L1. El
host instalable esta en `../OlivarVisionLidarApp/` y enlaza este paquete local.
`SystemLidarCapabilityDetector` consulta en tiempo de ejecucion
`sceneDepth`, `smoothedSceneDepth`, reconstruccion de malla y la camara LiDAR;
un host no compatible devuelve `unsupported` con un motivo visible.

`ARKitCaptureController` conserva por frame los planos de color sin recomprimir,
profundidad `Float32` en metros, confianza ARKit, intrinsecos escalados a la
resolucion de profundidad, timestamp y pose optica-a-mundo. El
`OfflineSessionWriter` crea una raiz nueva y nunca reutiliza una sesion. El
componente `LidarCaptureView` muestra las capacidades reales, el motivo de
bloqueo y el estado de inicio/finalizacion; cada inicio usa un ID nuevo. El
componente `BiomassCarbonView` ofrece un calculo manual restringido al dominio
publicado y mantiene separadas geometria, biomasa seca aerea, carbono y CO2e
almacenado. El 47 % de Torrus-Castillo et al. (2026) no se aplica por defecto:
si se usa, hay que registrarlo expresamente como proxy con su fuente.

El formato `olivar-lidar-capture` tiene `schema_version: 1` y separa:

- `captured/`: originales y metadatos por frame;
- `derived/`: reservado al procesador offline;
- `validation/`: validaciones y motivos de rechazo.

Compilacion del nucleo Swift, sin afirmar compatibilidad iOS:

```bash
make check-lidar-swift
```

Compilacion para un destino iOS Simulator, que requiere Xcode completo:

```bash
make check-ios
```

Diagnostico previo y correccion del toolchain:

```bash
make check-apple-toolchain
sudo xcode-select --switch /Applications/Xcode.app/Contents/Developer
sudo xcodebuild -license accept
sudo xcodebuild -runFirstLaunch
make check-apple-toolchain check-lidar-swift check-ios
```

El simulador debe informar que LiDAR no esta disponible. Solo un iPhone real
compatible puede producir evidencia para las puertas L0/L1. Un diametro LiDAR
no alimenta el estimador hasta que L2 lo marque `VALIDATED_REAL_DEVICE`; mientras
tanto, la ruta permitida es una medida manual con cinta a 0,30 m.
