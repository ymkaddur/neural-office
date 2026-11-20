# V5.35-POLISHED · verificación local de 5.35.1

La base de esta edición es el commit local dd299ee. El primer resultado del hilo contesta el encargo. Cuando una operación supera lo que puede hacer el lector, esa parte queda escrita en la entrega. Los seis especialistas conservan sus tres rondas de operaciones deterministas. Una consulta al modelo sigue un flujo de autorización separado.

Pasaron 278 pruebas Python y 77 del frontend. Se repitió desde cero el recorrido interactivo en Windows con dos oficinas temporales independientes. Cada ejecución produjo veinte vistas en Edge y forzó un conflicto de revisión entre la parada y la recuperación. En ambas, la llamada quedó interrumpida, el mismo intento acabó cancelado y el saldo registró un solo cargo.

[Director en oscuro](images/v5.35-polished-oscuro.png) · [Director en claro](images/v5.35-polished-claro.png)

## Qué se comprobó

Los identificadores remiten a los 22 hallazgos consolidados de las 30 revisiones de V5.35. La tabla recoge ejemplos reproducibles y distingue las capas de verificación.

| Hallazgos | Cambio y comprobación |
|---|---|
| 01, 02, 07, 08 | Se vincula cada parte del encargo a las capturas nombradas. Con un XML erróneo y un JSON válido, invertir el orden mantiene el diagnóstico del XML. Contar páginas de un Markdown produce un límite explícito. Pedir validar y redactar conserva ambas peticiones. Un saludo delante de la pregunta deja visible el conteo de páginas. Se ensayaron búsquedas con comillas curvas, simples y sin comillas, nombres concretos y solicitudes corteses. |
| 03, 05 | El visor usa la misma separación de líneas que la búsqueda literal y comprueba la cita antes de resaltarla. Un separador U+2028 lleva a la segunda línea correcta. Un PDF con la frase sólo en la página 41 conserva en la evidencia las 40 páginas examinadas y señala la pendiente. Las imágenes incrustadas limitan las afirmaciones de ausencia. |
| 04, 13, 16, 21 | El hilo indica el número de llamadas al modelo, presenta primero la respuesta y permite desplegar la actividad. Cada especialista muestra su última acción. Se abrieron los seis hilos en ambos temas, se comprobó que las rondas y el cierre siguen accesibles al desplazar un panel largo y se volvió desde la fuente a la ronda original. El Integrador muestra las conclusiones junto a sus referencias. |
| 06, 18, 19 | Cada resultado exportado identifica sus fuentes y, cuando existe, la página, línea o campo. PDF y JSON llevan la identidad de la entrega en el nombre de descarga. El PDF se compone al descargar. Poppler recuperó la frase «Αθήνα 東京 😀», una línea de 180 letras W y el texto posterior. Las palabras quedaron dentro del margen en ambas páginas. PDFium volvió a encontrar la misma frase al capturar el PDF desde el producto. |
| 09, 10 | Una nota con evidencia dañada se puede retirar usando su identidad y revisión. La publicación sigue exigiendo un origen verificable. Al usar una skill, el núcleo vuelve a leer la versión aceptada. La prueba retiró la skill mientras su ficha seguía abierta y comprobó el rechazo al copiarla. |
| 11 | Un controlador de prueba autorizó fragmentos de una entrega multiformato. Con el proveedor controlado aún vivo, el escritorio mostró que seguía trabajando. Tras interrumpir ese controlador, se reabrió la consulta, se solicitó la parada y se reconcilió el estado. Se conservó el identificador de la entrega, una llamada admitida y un único intento consumido. Se usaron el núcleo y un Windows Job real. El proveedor de la prueba esperaba una señal. |
| 12, 14, 15, 17, 20 | Ctrl+K enfoca el campo de búsqueda. Se escribieron espacios con un borrador existente, se recuperó un objetivo posterior y se reabrió una entrega de otro hilo tras recargar. A 760 × 540 las horas quedan en una sola línea. La prueba del selector excesivo y la cancelación inyectó las respuestas del transporte y comprobó la conservación del borrador. |
| 22 | El arranque con -Check rechaza una carpeta como destino SQLite antes de informar sobre el ejecutable. |

## Color y lectura

El área de lectura usa #101216, la navegación #0C0E12 y las superficies elevadas #171A20. Los acentos identifican acciones, foco y estados. En Edge se midieron los colores efectivos de los tres niveles de texto sobre seis superficies de cada tema. El mínimo fue 6,45 a 1 en oscuro y 5,10 a 1 en claro. La medición cubre esos 18 pares por tema. La preferencia de alto contraste refuerza el texto secundario, los divisores y el foco.

## Cómo repetir el recorrido

La suite del núcleo se ejecuta desde la raíz con Python 3.12 y los lectores de requirements-readers-windows.txt.

~~~powershell
python -B -m unittest discover -s tests -q
~~~

Desde desktop, npm ci prepara las dependencias fijadas. npm test ejecuta la suite del frontend. npm run build -- --mode native compila el mismo punto de entrada que consume Tauri.

Con Edge y Playwright disponibles, estos comandos usan una oficina temporal con archivos sintéticos. NEURAL_OFFICE_PYTHON puede apuntar al intérprete con los lectores y PLAYWRIGHT_MODULE a la instalación de Playwright. La comprobación de geometría también necesita pdftotext en PATH o su ruta en PDFTOTEXT.

~~~powershell
node tools/verify_v535_workspace.cjs "$env:TEMP/neural-office-polished-recorrido"
node tools/verify_v535_polished.cjs "$env:TEMP/neural-office-polished-pdf"
~~~

El primer recorrido deja veinte capturas, una galería, las mediciones de contraste y evidencia de la reimportación y la recuperación. Ejecuta la interfaz compilada en Edge contra Python por stdio. El arnés proporciona el transporte de escritorio y controla la selección de archivos.

## Frontera nativa

El SDK de Microsoft resolvió el error inicial de enlace con kernel32.lib. Hubo intentos de compilación en los que Windows bloqueó auxiliares de Rust con el código 4551. La compilación final con npm run native:build sí produjo neural-office-desktop.exe en modo release, con versión de producto 5.35.1 y 4 708 864 bytes.

El SHA-256 del ejecutable comprobado es `4313615BB5DE34F06A7065F9DBA466087D1F4D1CE878CCC054F863BFBA412508`. Authenticode informó NotSigned. El lanzador normal intentó abrir ese archivo con una base SQLite separada. Control de aplicaciones devolvió el error 4551 antes de crear el proceso. Los eventos 3033 y 3077 del registro de integridad de código identificaron la misma ruta en ese momento. Para aceptar la ventana WebView2 y el selector nativo queda pendiente ejecutar el artefacto en un Windows cuya política lo admita.
