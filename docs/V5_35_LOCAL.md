# V5.35 · Oficina local de archivos

La prueba parte de una pregunta, un conjunto de archivos elegidos por la persona y un proyecto local. El Director deja el informe, los archivos de salida y los límites de lectura en el hilo. Para una inspección efectiva se pueden recorrer las instrucciones, las aportaciones y las tres rondas de los seis especialistas.

## Qué ocurre con cada fuente

| Fuente | Qué se puede comprobar |
|---|---|
| Texto, Markdown, código, CSV, TSV, XML y texto sin extensión | Texto recuperado y búsqueda de una expresión entre comillas. Una coincidencia lleva la línea de la captura. Se admiten UTF-8 y UTF-16/32 con marca de orden de bytes. |
| PDF | Páginas, extracción de texto y citas. La búsqueda devuelve la página encontrada. Una página escaneada requiere otra fuente de texto para comprobar su contenido. |
| DOCX, XLSX, PPTX, ODT, ODS y ODP | Texto de las partes compatibles. En hojas XLSX se conserva la referencia de celda. La numeración de líneas del texto extraído pertenece al lector. |
| JSON e inventario ZIP | Sintaxis, campos o inventario según el encargo. Las entradas compatibles se abren dentro del paquete. |
| PNG, JPEG, GIF, WebP, TIFF y BMP | Dimensiones y vista previa cuando la decodificación termina. Una medición de píxeles por sí sola deja abierta la legibilidad. |
| WAV | Canales, frecuencia y duración del audio PCM que puede abrir el lector. |
| Otro formato o extensión propia | Se intenta recuperar texto si su codificación lo permite. Para contenido opaco quedan nombre, tamaño, firma inicial y SHA-256. |

Se admiten hasta ocho archivos por selección. El umbral de lectura integral es 8 MiB por archivo y 24 MiB por selección. Hasta 512 MiB por archivo y 1 GiB por selección, el lector puede calcular la huella completa por bloques y guardar solo la cabecera y la identidad. Los lectores también limitan páginas, texto, partes de Office y expansión de paquetes. Una búsqueda que agota su cobertura deja el resultado abierto. La captura y la comprobación se ejecutan en modo de lectura.

## Recorrido que permite reproducir el resultado

1. Selecciona un Markdown con «primera respuesta en 24 horas», un CSV que declare 48 y un archivo binario de formato propio. Envía **Inspecciona los archivos de la entrega**. El Director identifica las dos fuentes legibles y señala el binario por su nombre.
2. Envía **Busca «24 horas» en los archivos**. Abre la cita del Markdown. El binario conserva su limitación. Para comprobar la navegación por páginas, usa un PDF donde la frase figure solo en la segunda.
3. Abre **Escéptico** y alterna las tres iteraciones. En la última aparece la limitación que llega al informe del Director. **informe.pdf**, **evidencia.json** y el Markdown del especialista se generan a partir de esa entrega.
4. En **Memoria y skills** crea y modifica una instrucción. La aprobación registra otra revisión. **Usar en un borrador** coloca el texto en el compositor para que la persona decida si lo envía.
5. Con adjuntos en el hilo, envía **Hola**. El Director ofrece orientación y guarda el intercambio. La respuesta se puede reabrir sin atribuir ninguna intervención a los especialistas.
6. Cambia a tema claro u oscuro en **Ajustes**, abre un especialista y ciérralo con Escape. El foco regresa al control de origen. A anchuras estrechas el botón **Ver equipo** da acceso al mismo contenido.

## Qué garantiza la evidencia

Los 18 recibos de una inspección documentan operaciones deterministas sobre capturas locales. Cada recibo enlaza al anterior mediante SHA-256. El núcleo contrasta los datos guardados al reabrir la entrega. La hora y la duración pertenecen a la ejecución que la creó. La consulta opcional al modelo tiene aprobación y saldo propios. La autonomía generativa de seis agentes y la comparación de CPU/RAM con Ollama siguen en la hoja de ruta.

La memoria y las skills son locales por proyecto. Una modificación exige la revisión esperada y una entrega válida como origen. El historial conserva la propuesta, la aceptación, la retirada y su procedencia. Las fuentes, notas y recibos guardados en la máquina requieren la misma protección local que los documentos originales.

## Verificación

### Resultado en Windows el 20 de noviembre de 2026

| Componente | Resultado observado |
|---|---|
| Núcleo Python | Pasaron las 273 pruebas. El lanzador y Tauri declaran la versión 5.35.0. |
| Frontend | Pasaron las 77 pruebas. El recorrido con Edge y el servicio Python guardó diez vistas por tema, reabrió la entrega y descargó el PDF y el JSON. |
| Primera compilación Tauri | Windows abrió el ejecutable y mostró el hilo del Investigador. Durante esa prueba un saludo llegó a producir 18 pasos. La corrección posterior se verificó en el núcleo y en Edge. |
| Compilación Tauri final | Cargo terminó la compilación de producción. El archivo tiene 4 706 304 bytes. Windows lo identificó como `NotSigned` y rechazó el arranque con el error 4551. Code Integrity registró los eventos 3033 y 3077 a las 12:48:38 UTC. |
| Pruebas de Rust | Cargo compiló el ejecutable de pruebas. El mismo control bloqueó su arranque. La ejecución de esas pruebas sigue pendiente. |

La huella SHA-256 del ejecutable final es `001221902f7f19faa6d7ae449658426e6709bd94dafbd01fb58cc5292355b1c9`. Para cerrar la verificación nativa en este equipo, Windows debe admitir el artefacto conforme a su directiva. Entonces corresponde repetir el recorrido en ese ejecutable y ejecutar las pruebas de Rust. El PDF exportado se abrió con PDFium y se comprobó una muestra con acentos, griego, cirílico y caracteres japoneses.

### Reproducir las pruebas

Se probaron una extensión desconocida, archivos sin sufijo, texto multilingüe, las seis familias de documentos de oficina, audio, un binario de nueve MiB, una cita de la segunda página de un PDF, la integridad de los recibos, la reapertura, la concurrencia al aceptar una propuesta y el saldo de la inspección. El recorrido en Edge usa los assets de producción y el servicio Python real con un selector de tres muestras aisladas. Produce diez vistas en ambos temas. Comprueba la descarga, el foco, el historial, la lectura en ventana estrecha y la inserción de una skill.

Desde la raíz del repositorio, usa el Python de escritorio con los lectores instalados para las pruebas del núcleo. Para el recorrido visual, señala ese mismo Python mediante `NEURAL_OFFICE_PYTHON` y una instalación de Playwright con Edge mediante `PLAYWRIGHT_MODULE`.

```powershell
py -3.12 -B -m unittest discover -s tests
npm --prefix desktop test
npm --prefix desktop run build -- --mode native
node tools/verify_v535_workspace.cjs "$env:TEMP\oficina-v535-vistas"
```

[Compilar y abrir Tauri en Windows](../desktop/README.md) · [Plan de inferencia y presupuesto de recursos](../ROADMAP.md)
