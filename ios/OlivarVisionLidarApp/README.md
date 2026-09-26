# Host iOS Olivar Vision LiDAR

Destino SwiftUI instalable que enlaza el paquete local `../OlivarLidarCapture`.
Permite registrar IDs de arbol, operador y finca; crear un grupo de repeticiones;
abrir la captura LiDAR; consultar el calculo experimental manual; y recuperar
las sesiones desde Archivos.

## Preparar Xcode

```bash
sudo xcode-select --switch /Applications/Xcode.app/Contents/Developer
sudo xcodebuild -license accept
sudo xcodebuild -runFirstLaunch
make check-apple-toolchain check-lidar-swift check-ios
```

## Instalar en un iPhone

1. Conectar el iPhone por cable, desbloquearlo, aceptar la confianza y activar
   Developer Mode si iOS lo solicita.
2. Abrir
   `ios/OlivarVisionLidarApp/OlivarVisionLidarApp.xcodeproj` en Xcode.
3. En el target `OlivarVisionLidarApp`, seleccionar el equipo de firma personal
   y cambiar el bundle identifier si Xcode indica que no es unico.
4. Elegir el iPhone como destino y pulsar Run. No usar el simulador para validar
   LiDAR: debe informar capacidad no disponible.
5. En la app, completar los tres IDs, abrir la captura y anotar los cuatro
   indicadores de compatibilidad antes de iniciar una sesion.
6. Tras finalizar, exportar cada carpeta desde
   `Archivos > En mi iPhone > Olivar Vision LiDAR > lidar`. No reutilizar ni
   renombrar una raiz de sesion.

Durante la captura, la vista AR permite tocar dos puntos de una referencia y
registrar su distancia medida. Use al menos dos reglas u objetos rigidos, repita
la seleccion para cada uno y compruebe despues el error contra la tolerancia de
0,02 m. La seleccion por `featurePoint` tambien debe validarse frente a la cinta;
su presencia en el manifiesto no cierra L1 por si sola.
