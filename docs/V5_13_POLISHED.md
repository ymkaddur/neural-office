# V5.13-Polished · Revisar una entrega local

La prueba representa la entrega de un portal de soporte. La especificación dice «Primera respuesta en 24 horas» en la segunda página. El manifiesto declara 48 en `/response_sla_hours`, línea 4. La regla local compara los valores y sus unidades. El informe conserva el texto, la ubicación y la identidad de ambas capturas. El objetivo escrito orienta el encargo, pero la regla implementada sólo compara este requisito de primera respuesta.

## Repetir el recorrido en Windows

1. Usa el código del mismo commit que el ejecutable. Prepara los lectores con `./Start-NeuralOffice-Desktop.ps1 -PrepareReaders`. El lanzador comprueba las versiones de PDFium y Pillow en su entorno privado. [Instalación y arranque](../desktop/README.md)
2. Genera los cinco archivos de ejemplo con el Python que tiene los lectores instalados. El directorio de destino puede estar vacío o contener otra copia idéntica. [Generador de fuentes sintéticas](../examples/multiformat/build_example.py)

   ```powershell
   $huella = (Get-FileHash -LiteralPath .\requirements-readers-windows.txt).Hash.Substring(0, 12)
   $lector = Join-Path $env:LOCALAPPDATA "NeuralOffice/desktop-runtimes/py312-$huella/Scripts/python.exe"
   & $lector examples/multiformat/build_example.py "$env:TEMP/NeuralOffice-ejemplo-portal"
   ```

3. Abre el escritorio. Crea el proyecto **Portal de soporte**, selecciona **Adjuntar archivos** y elige los cinco archivos generados. Escribe «Compara el plazo de primera respuesta del portal». Pulsa **Inspeccionar · 0 intentos**.
4. Abre las dos citas del hallazgo. El inspector permite leer la página del PDF y la línea del JSON. Desde **Ver adjuntos** puedes abrir el ZIP, elegir la imagen móvil dentro del paquete y ampliar la vista.
5. Abre **Apariencia** con Ctrl+, para probar Arena, Azul noche, tamaño, densidad y contraste. Ctrl+K busca en los proyectos, hilos y encargos cargados en la vista.
6. Si quieres una segunda opinión, **Consultar al modelo** te permite revisar el modelo y los fragmentos. La reserva al autorizar consume un intento del proyecto. La lectura, el historial y abrir una imagen consumen cero. El resultado del modelo lleva su propia atribución.

## Qué se verificó

| Superficie | Experimento | Qué puede concluirse |
| --- | --- | --- |
| Lectores Windows | PDF con texto, PDF protegido y escaneado, JSON con campos ambiguos o fuera del primer fragmento, ZIP con miembros, PNG y JPEG con orientación | El visor presenta los bytes capturados y señala los límites del lector. La regla distingue discrepancia, coincidencia y evidencia insuficiente. |
| Núcleo y procesos Windows | Retener una lectura de B, solicitar dos veces la parada de A, perder una respuesta y reconectar. Un observador independiente lee la reserva y el cierre antes de liberar B. | En 30 ensayos, desde el envío al primer recibo de parada observado, p50 23,877 ms, p95 42,514 ms, máximo 47,317 ms. La medida incluye la tubería y SQLite. Se utilizó un modelo de prueba con procesos controlados. [Muestras y método](evidence/V5_13_CONTROL_WINDOWS.json) |
| Ollama en Windows | Cinco archivos, dos extractos autorizados, una llamada real con `qwen2.5:0.5b` y reapertura del informe | Un ensayo agotó el tiempo de arranque. El siguiente completó la llamada en 5,147 s y permitió comprobar la huella del mensaje. El comentario reiteró el encargo. La discrepancia ya estaba demostrada por la regla. [Ambos ensayos](evidence/V5_13_EXCERPTS_WINDOWS.json) |
| React de producción en Microsoft Edge | La interfaz utiliza el núcleo por stdio. El ensayo sustituye el selector nativo y el transporte Tauri para automatizar la selección de las cinco fuentes públicas. | Se ejercitan adjuntar, inspeccionar, abrir citas, leer el ZIP, ampliar el JPEG, cambiar apariencia, recuperar el hilo y conservar un borrador en una ventana estrecha. [Recorrido reproducible](../tests/verify_v513_renderer.cjs) |
| Ejecutable Tauri de Windows | GitHub Actions compila el escritorio con su frontend incorporado y ejecuta pruebas de interfaz mediante UI Automation. | El resultado del paso **Verify the five real attachments…** y los artefactos de cada ejecución identifican el commit probado. El recorrido con Ollama abre y cierra el permiso de los dos extractos, contrasta el saldo previo con SQLite, autoriza una sola llamada y coteja la entrega con la respuesta guardada. [Prueba de permisos y recibos](../tests/v513_excerpt_uia.py). La compilación local de esta candidata fue bloqueada por Control de aplicaciones de Windows, error 4551 al iniciar un auxiliar del compilador. [Ejecuciones de la rama](https://github.com/ymkaddur/neural-office/actions/workflows/windows-tests.yml?query=branch%3Afeat%2Fv5.13-polished) |

La medición de Edge corresponde al frontal de `50f17f5`. La inspección del ejemplo hizo visible el primer hallazgo en 1,890 s. En una ventana de 3,791 s, el navegador acumuló 188 ms de CPU en los ocho procesos presentes en ambas muestras y el núcleo Python con sus descendientes, 94 ms. Al final de esa ventana se midieron 326,25 MiB de memoria privada en Edge y 18,57 MiB en Python. El muestreo por extremos puede omitir picos. El ensayo del ejecutable tiene su propia instrumentación. [Muestras y límites](evidence/V5_13_RENDERER.json)

En las muestras del tema normal, el contraste mínimo del texto ordinario fue 5,92:1 en Arena y 8,04:1 en Azul noche. Para el foco se obtuvieron 5,73:1 y 8,75:1. Las filas cambiaron de 10 a 6 px de relleno al activar la densidad compacta. El tamaño medido en el compositor y el inspector pasó de 15 a 17,25 y 18,75 px al elegir 100, 115 y 125 %. [Captura de evidencia en Arena](images/v5.13-evidencia.png) · [Captura del paquete en Azul noche](images/v5.13-paquete.png)

El conjunto de pruebas del núcleo puede ejecutarse con `python -B -m unittest discover -s tests -v` en el entorno de lectores de Windows. Desde `desktop`, `npm ci --ignore-scripts`, `npm test` y `npm run build` comprueban el cliente y generan el frontend empaquetable.

## Tres revisiones que cambiaron la implementación

**Lectura y control.** En el código de partida, una lectura retenida de B retrasaba la parada de A y una segunda solicitud de parada producía otro evento. La prueba utiliza una barrera que sólo se retira después de que un observador independiente haya visto el cierre. El canal conserva capacidad para las peticiones de control. Un catálogo de modelos retenido permite seguir comprobando HTML.

**Alcance y procedencia.** La primera integración podía saturar el canal al abrir simultáneamente los proyectos, los adjuntos y el historial. Las lecturas repetidas ahora se coordinan por sesión. Si se excluye una fuente después de inspeccionarla, el informe conserva su alcance y se pide una nueva inspección antes de consultar los archivos seleccionados. Para HTML, el mensaje autorizado al modelo se limita al código y la posición del hallazgo cuando la consulta es de extractos. La lectura local puede mostrar la línea completa.

**Navegación y recuperación.** La actividad sigue en el hilo al cambiar el panel lateral. Los borradores sin adjuntos se pueden volver a abrir durante la sesión de ventana. En el primer recorrido nativo a tamaño de portátil, el informe HTML dejaba el cuarto hallazgo fuera de la vista. La cabecera más corta y las coordenadas junto a la guía permiten ver los cuatro. Los botones de actividad de la inspección y del encargo exponen su estado expandido al árbol de accesibilidad. Se pueden manejar con espacio y con Intro. El control de parada identifica el proyecto que está trabajando aunque se navegue por otra entrega. La retirada de una identidad pendiente se vincula a esa petición. Las ventanas actualizadas de un mismo perfil coordinan ese cambio mediante Web Locks o una transacción IndexedDB.

## Criterio de diseño y trabajo pendiente

La barra lateral conserva el destino, el centro reúne el objetivo y los registros, y el inspector abre el documento exactamente donde nació la observación. Tomamos como referencias la revisión en contexto de Claude Code, la navegación por proyecto de Codex y la relación entre proyecto e hilo de T3 Code. La identidad visual de Neural Office combina Arena o Azul noche, acentos funcionales y cifras monoespaciadas en los recibos. [Claude Code Desktop](https://code.claude.com/docs/en/desktop) · [Codex](https://openai.com/index/introducing-the-codex-app/) · [T3 Code](https://t3.codes/)

El flujo muestra el paso registrado, el resultado de cada herramienta local y los comentarios que el modelo efectivamente devuelve. Quedan pendientes la prueba de comprensión con personas nuevas, la lectura con Narrador y la validación de utilidad con más tareas y modelos. La orquestación de tres versiones y las skills revocables siguen en la hoja de ruta. [Criterios hacia V6.5](../ROADMAP.md)
