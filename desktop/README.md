# Escritorio Neural Office · V5.13-Polished en pruebas

El escritorio reúne el objetivo, los adjuntos, los pasos registrados y las entregas de cada hilo. Abre una cita para leer su fuente en el inspector. Apariencia ofrece Arena y Azul noche. El ejemplo del portal permite recorrer el flujo con cinco archivos y sin un modelo instalado. [Ejemplo y verificaciones de V5.13](../docs/V5_13_POLISHED.md) · [Historial de V5.12](../docs/V5_12_REVIEW.md) · [Hoja de ruta](../ROADMAP.md).

## Abrir el recorrido conectado

La comprobación estática requiere Windows x64, Python 3.12 y WebView2. Para consultar al Director instala también Ollama y descarga un modelo local. El host no descarga modelos ni configura proveedores cloud. Para compilar hacen falta Node 24, el toolchain Rust fijado y las herramientas MSVC/SDK de Windows; son requisitos de desarrollo, no el onboarding prometido para V10.

Desde esta carpeta, compila los assets y el host de producción:

```powershell
npm ci --ignore-scripts
npm test
npm run build -- --mode native
Set-Location src-tauri
cargo test --locked --features custom-protocol
cargo build --locked --release --features custom-protocol
Set-Location ../..
.\Start-NeuralOffice-Desktop.ps1 -PrepareReaders
.\Start-NeuralOffice-Desktop.ps1 -Check
.\Start-NeuralOffice-Desktop.ps1
```

`custom-protocol` es necesario para este comando Cargo directo: usar assets de producción forma parte de la regresión, no basta con que exista un exe. No hace falta arrancar Vite para usar el binario construido. Las instrucciones se ejecutan desde el árbol del repositorio; Python no va embebido en este paquete.

El lanzador conserva por defecto el estado existente del piloto. Para PDF, PNG y JPEG, `-PrepareReaders` instala los paquetes fijados por huella en un entorno local de Python 3.12. Comprueba PDFium y la decodificación de imágenes. Las siguientes aperturas usan ese entorno. HTML, JSON y el inventario ZIP usan la biblioteca estándar. `-Check` comprueba las capacidades antes de abrir el escritorio.

Si utilizas otro estado, pasa `-State` con esa misma base y conserva su testigo. `-Python` y `-Executable` permiten señalar instalaciones de confianza desde el lanzador.

Windows puede bloquear el ejecutable no firmado: se ha observado con App Control en el equipo de desarrollo. No desactives esa protección para probarlo. Firma, distribución e instalación en equipos limpios son una puerta pendiente. Los artefactos de CI incluyen avisos; acompañan al exe y deben conservarse al redistribuirlo. [Licencias](THIRD_PARTY_NOTICES.md).

## Revisión de HTML con roles

Desde el inspector, elige **Abrir revisión de HTML con roles**.

1. Escribe tu pregunta y adjunta un HTML UTF-8 de hasta 256 KiB. **Comprobar HTML** localiza los hallazgos por páginas de 24 y conserva la pregunta. Capturar el archivo registra el proyecto. Comprobar y paginar consumen cero intentos y cero llamadas.
2. **Consultar al Director** abre el selector de modelos. Si el catálogo confirma que está vacío, la pantalla conserva el borrador y muestra cómo instalar un modelo y actualizar la lista para continuar. El perfil inicial usa una llamada. Los perfiles de tres y siete roles hacen llamadas secuenciales. El modelo recibe el objetivo y las ubicaciones detectadas. La asistencia admite hasta 24 hallazgos.
3. Pulsa **Revisar encargo**, comprueba fuente/modelo/alcance/consumo y después **Autorizar y ejecutar**. Preparar no consume un intento; la reserva sí.
4. Revisa hallazgos y sugerencias por separado. **Evidencia y alcance** permite inspeccionar identidades y el informe original; no ejecuta HTML generado.
5. **Detener** solicita parada y mantiene el estado pendiente hasta confirmación. Error o cancelación conserva consumo. Reabre para consultar el mismo intento; una respuesta perdida se concilia por su identidad.

Los límites actuales son tres intentos por proyecto, dos proyectos activos y una inferencia administrada. Eventos visibles e historia están acotados; un dato de cuota ausente se muestra por confirmar, no como cero. El snapshot, no el estado local del navegador, es la autoridad.

## Revisar sólo las escenas históricas

```powershell
npm run dev -- --port 5316 --strictPort
```

Abre `http://127.0.0.1:5316/?preview=1&screen=ready`. Las escenas `ready`, `running`, `result`, `error` y `stopping` son ejemplos sintéticos V5.4.1, disponibles sólo en desarrollo; los builds de producción no los incorporan. No generan contenido ni comprueban cierre de procesos. La ruta principal en un navegador explica cómo abrir el escritorio; no finge conectarse al núcleo.

La galería conserva la [revisión visual histórica](../docs/V5_4_1_UI_REVIEW.md) y sus limitaciones. La UI conectada mantiene paneles ajustables, temas y controles de teclado; esa reutilización no implica que haya superado un estudio de usuarios o lector de pantalla.

## Verificación y consumo

La suite Node incluye regresiones de React con IPC simulado para cleanup terminal, cursores independientes e identificadores históricos. Las pruebas Python cubren reserva, cancelación, fuente, mensajes, muerte del controlador y respuesta perdida. Rust prueba frontera y assets. Ninguna por separado acredita el recorrido nativo.

El [harness Windows CI](../tests/e2e_v55_native_uia.py) prueba el ejecutable, selector, aprobación, modelo real, informe, cierre/reapertura y parada con datos sintéticos. V5.7 comprueba primero las cuatro ubicaciones con el teclado y el servidor de modelos apagado. Después contrasta los contadores con la consulta asistida, el cierre, la reapertura y la cancelación. [Resultados de V5.7](../docs/V5_7_REVIEW.md). Usa herramientas de test fuera del producto; no añade un puerto de depuración al host distribuido.

Una prueba optativa del servicio real sin GUI usa un estado sintético nuevo y publica sólo métricas saneadas:

```powershell
# Desde la raíz; el modelo debe estar instalado y la carpeta de salida no existir.
py -3.12 -B -m tools.smoke_v55_real --model qwen2.5:0.5b --output D:/NeuralOfficeExperiments/v55-new
```

La salida local del experimento también contiene su SQLite y logs: publica únicamente `result.json` tras revisar su contenido, no toda la carpeta. Un modelo pequeño verifica integración, no calidad general. El timeout de arranque R13 conserva evidencia fallida; no se oculta repitiendo hasta lograr éxito. RAM de backend, memoria webview, tamaño del bundle y CPU acumulada son medidas distintas.

Pendientes: aceptación de diseño con personas, lector de pantalla, sesiones largas, perfiles GPU y distribución firmada. El Job de Windows controla el árbol propio; no es un sandbox de disco/red. [Frontera de confianza](../SECURITY.md).
