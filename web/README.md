# Cliente web Olivar Vision

PWA movil sin dependencias de runtime. Es el cliente principal para contexto de
campo, fotografias RGB, repeticiones, medidas manuales, historial local y
estimacion experimental de biomasa/carbono.

## Ejecutar

```bash
make check-web
make web-serve
```

Abrir `http://127.0.0.1:8788/`. `localhost` cuenta como contexto seguro para
desarrollo. En un telefono se debe publicar exactamente la carpeta `web/` bajo
HTTPS; una URL HTTP de la red local no puede solicitar la camara.

No hay compilacion, cuenta Apple, firma ni instalacion desde Xcode. Tras la
primera carga, el service worker conserva la aplicacion para uso sin red. Las
sesiones y fotografias se guardan en IndexedDB del navegador y solo salen del
dispositivo cuando el usuario descarga un manifiesto JSON o un archivo TAR.

## Publicacion en GitHub Pages

- URL configurada: https://pablosainz98.github.io/olivar-vision/
- Codigo: https://github.com/PabloSainz98/olivar-vision
- `.github/workflows/pages.yml` ejecuta `make check-web` con Node.js 24 y
  publica solo HTML, CSS, manifiesto, service worker, `assets/` y `src/`.
  No publica el repositorio completo, fixtures ni directorios de datos.
- Un push a `main` que cambie la web activa el despliegue; tambien puede
  ejecutarse desde Actions mediante `workflow_dispatch`.
- Incrementar la version de cache en `service-worker.js` al cambiar recursos
  del cliente. La cache queda aislada por ruta de proyecto, sin borrar caches
  de otros sitios de Pages que compartan el mismo dominio.
- Las capturas se quedan en el navegador. GitHub Pages no recibe las fotos ni
  los registros de campo; descargar los TAR antes de borrar los datos del sitio.

## Capacidades portadas

- Camara tras permiso mediante `MediaDevices.getUserMedia`, preferentemente la
  camara trasera.
- Sesiones nuevas e inmutables, grupos de repeticion y fotografias JPEG con
  tamano y SHA-256.
- Referencias metricas externas, geometria manual con cobertura/calidad y
  comparacion pareada de sesiones del mismo grupo.
- Estimador Brunori v1 con el mismo fixture de paridad que Python y Swift.
- Deteccion real de contexto seguro, camara, IndexedDB, WebXR AR y prueba
  explicita de la feature `depth-sensing` cuando el navegador la ofrece.

## Limite LiDAR

La API estandar de camara web no expone los mapas ARKit `sceneDepth`, confianza,
intrinsecos ni pose mundial. Safari en iPhone tampoco ofrece WebXR inmersivo. La
PWA informa ese bloqueo y guarda `source_type: web_rgb_manual`; no denomina LiDAR
a una foto RGB ni inventa compatibilidad a partir del modelo del telefono.

Aunque otro navegador acepte una sesion WebXR con `depth-sensing`, esa prueba de
capacidad no equivale al paquete L1: faltan una ruta portable para RGB crudo
sincronizado, confianza e intrinsecos con el mismo contrato. La captura nativa
Swift se conserva como referencia historica para producir paquetes L1 ARKit,
pero no es necesaria para usar las funciones web portadas.

## Integridad

Cada exportacion TAR contiene una raiz con el ID de sesion, `session.json` y
los JPEG bajo `captured/<frame>/color.jpg`. El manifiesto declara que la
geometria manual no representa volumen completo y que L3 sigue pendiente. Una
sesion finalizada no se puede modificar; una nueva repeticion crea otro ID.

IndexedDB pertenece al origen HTTPS. Borrar los datos del sitio o el navegador
elimina el historial local, por lo que se deben descargar los TAR antes de
limpiar Safari/Chrome o cambiar de dominio.
