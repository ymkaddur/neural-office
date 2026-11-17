# V5.8 en Windows · recuperar el mismo encargo

**VERIFICADO.** El ejecutable Tauri V5.8.0 para Windows x64 recuperó el mismo encargo después de dos cortes consecutivos. La ventana siguió abierta. Iniciar el encargo consumió un intento y ambas reconexiones juntas añadieron **cero intentos y cero llamadas al proveedor de prueba**. [Ejecución nativa en GitHub Actions](https://github.com/ymkaddur/neural-office/actions/runs/44200455347/job/134452879727) · [Mediciones](evidence/V5_8_RECONNECTION.json).

## Incidente y secuencia observada

**OBSERVADO · V5.7.** En Windows, al perder el canal con el núcleo durante un intento registrado, la ventana mantuvo «Núcleo local conectado», mostró `HOST_DISCONNECTED` y dejó deshabilitado el encargo anterior. Pulsar «Actualizar» volvió a consultar el canal cerrado. Cerrar y abrir la aplicación recuperó el intento original. El proyecto ya tenía otro encargo fallido. El proceso que mantenía el trabajo de prueba seguía vivo. [Ensayo de Windows](../tests/e2e_v58_reconnect.py) · [código de partida](https://github.com/ymkaddur/neural-office/tree/31e85868a5b07500e7de131c49e6d9b4e051572a).

| Pregunta | Experimento discriminante | Resultado |
| --- | --- | --- |
| ¿Había desaparecido la reserva? | Leer oficina, identidad, clave, ordinal y llamadas antes y después de cortar el canal. Volver a abrir el ejecutable anterior. | **VERIFICADO.** Se conservó la misma reserva. El texto de conexión dependía de la existencia de una sesión anterior. |
| ¿Se podía perder el diagnóstico al cerrar el proceso? | Provocar un fallo conocido, abrir un segundo servicio sobre el mismo registro y repetir con un fallo privado y con un recibo del formato antiguo. | **VERIFICADO.** V5.8 conserva el código público junto al cierre. Un fallo imprevisto conserva `EXECUTION_FAILED`. La lectura de un recibo antiguo muestra que falta el motivo. [Regresiones de diagnóstico](../tests/test_v55_service.py#L95). |
| ¿La selección de historial podía controlar el encargo equivocado? | Mantener un intento en ejecución, abrir el anterior, volver al activo y detenerlo. Repetir con el activo fuera de la página visible. | **VERIFICADO.** El anterior siguió en `FAILED` y el activo terminó en `CANCELLED`. La lectura filtró los eventos antes de paginar. [Selección](../desktop/src/connected/ConnectedWorkspace.tsx#L375) · [paginación](../tests/test_v55_service.py#L134). |
| ¿Qué ocurría si también moría el ejecutor? | Finalizar el proceso dueño de una llamada sintética ya admitida. Abrir otro servicio y solicitar la recuperación dos veces. | **VERIFICADO.** La llamada pasó de `STARTED` a `INTERRUPTED` con el mismo número. El intento terminó en `FAILED` con `ATTEMPT_INTERRUPTED`. Volver a recuperar conservó un cargo y una llamada. [Pérdida del ejecutor](../tests/test_v55_service.py#L164). |

## Qué cambia en la ventana

- **Estado.** Durante el corte se ve el último estado confirmado, su hora y «Reconectar». La sincronización contrasta oficina y sesión. Recupera la identidad pendiente antes de habilitar otro envío. La autorización de archivo de una sesión caducada requiere una nueva selección. [Conciliación](../desktop/src/connected/ConnectedWorkspace.tsx#L20).
- **Historial.** Se puede consultar un encargo anterior mientras el actual sigue abierto. «Volver al trabajo en curso» devuelve el control al destinatario de la parada. Se muestra el nombre guardado con la reserva cuando está disponible. Las reservas antiguas se identifican por la huella de su fuente. [Servicio de lectura](../neural_office/desktop_service.py#L270).
- **Actividad y coste.** Abrir la actividad lee hasta 24 eventos del encargo visible. La página indica el número de filas que contiene. El listado permanece bajo demanda durante el sondeo del trabajo activo. La cuota del proyecto sigue visible en ventanas estrechas. [Actividad](../desktop/src/connected/AttemptActivity.tsx#L32) · [consulta por intento](../neural_office/desktop_service.py#L330).
- **Puente nativo.** Una consulta de identificación puede sustituir al proceso que perdió el canal cuando se comprueba su salida. Las operaciones de envío o parada carecen de esa facultad. El cierre de la ventana impide abrir otro puente. Ocho consultas simultáneas obtuvieron una única instancia en la prueba con procesos simulados. [Código de sustitución](../desktop/src-tauri/src/peers.rs#L6) · [prueba concurrente](../desktop/src-tauri/tests/peer_lifecycle.rs#L52).

## Medición del cargo

**VERIFICADO.** Cada ejecución empieza en una oficina temporal. El encargo anterior consumió un intento y falló antes de llamar al proveedor. El siguiente mantuvo su primera llamada en curso. Se interrumpió el proceso de comunicación de la ventana dos veces, mientras seguía vivo el proceso dueño del encargo. En cada corte apareció `HOST_DISCONNECTED`. «Reconectar» abrió un nuevo proceso de comunicación y mostró la misma identidad. Se compararon las reservas, sus claves y ordinales en SQLite, la secuencia de llamadas y el contador independiente del proveedor. [Prueba nativa](../tests/e2e_v58_reconnect.py#L170).

| Momento | Reservas totales del proyecto | Llamadas registradas del encargo activo | Invocaciones observadas al proveedor de prueba |
| --- | ---: | ---: | ---: |
| Antes del primer corte | 2 | 1 | 1 |
| Primer corte y primera reconexión | 2 | 1 | 1 |
| Segundo corte y segunda reconexión | 2 | 1 | 1 |
| Tras consultar el historial y detener el encargo activo | 2 | 1 | 1 |

**VERIFICADO.** Las pruebas de acuse perdido cubrieron espera agotada y canal cerrado, cada uno con reserva presente y ausente. Se conservó la clave original y el contador de envíos fue uno en los cuatro casos. [Pruebas de acuse perdido](../desktop/src/connected/adversarial.test.ts).

## Verificación y alcance

- **VERIFICADO.** Pasaron 210 pruebas Python, 54 pruebas de escritorio con Node y 2 pruebas Rust del ciclo de vida del puente. TypeScript y Vite compilaron la interfaz de producción. El ensayo de integración abrió una ventana Windows con el SDK WebView2 de Microsoft 1.0.4314.35, cortó su proceso de comunicación y ejercitó la ventana mediante UI Automation. El adaptador de ensayo conecta ese visor con el núcleo por entrada y salida estándar. [Dependencias de ensayo](../tests/requirements-native-ci.txt) · [adaptador](../tests/WebView2-V58TestHost.ps1).
- **VERIFICADO.** En las cuatro geometrías de Edge, de 390 a 1440 píxeles de ancho, el contador quedó dentro de la ventana. A 768 × 540 el cuarto hallazgo requirió desplazamiento y fue alcanzable con el teclado. Se midió geometría con datos sintéticos. Estas pruebas tampoco miden RAM o latencia de un modelo real. [Resultados por tamaño](evidence/V5_8_RECONNECTION.json).
- **OBSERVADO.** En la estación de desarrollo, Windows App Control bloqueó el auxiliar de `quote 1.0.47` con el error 4551. Cargo terminó con 101 antes de compilar la aplicación. [Registro local](evidence/V5_8_RECONNECTION.json).
- **VERIFICADO.** GitHub Actions compiló el código de producto `66fa7278cadc7ebb1329cce38059e4c4525e17c3` con los recursos de producción y ejecutó la prueba por UI Automation sobre ese binario. El historial conservó el diagnóstico `MODEL_METADATA_UNAVAILABLE` del encargo previo. Al volver al encargo en curso y detenerlo, sólo éste pasó a `CANCELLED`. La copia recuperada en local mide 4 636 672 bytes y coincide con el SHA-256 registrado por el runner, `89bbcb48778df2ab82ab81d392a6152558b9c5a2a1fdfee8c288bac3393aaee3`. El proveedor de prueba permite contar cada entrada. La prueba mide la cuota interna de Neural Office. [Trabajo de Windows](https://github.com/ymkaddur/neural-office/actions/runs/44200455347/job/134452879727) · [Lectura del historial y parada](../tests/e2e_v58_reconnect.py#L207).

Para repetir el recorrido del ejecutable desde la raíz del proyecto, usa Python 3.12 con las dependencias de ensayo indicadas arriba. El destino de salida debe ser nuevo. El ensayo crea la oficina, la fuente HTML y el perfil WebView2 dentro de esa carpeta.

```powershell
python -B tests/e2e_v58_reconnect.py --executable desktop/src-tauri/target/release/neural-office-desktop.exe --output "$env:TEMP/neural-office-v58-reconnect-01" --cycles 2
```
