# V5.14 · verificación local del Director

El caso de aceptación es el portal de soporte. La especificación fija 24 horas en la página 2 y el manifiesto declara 48 en la línea 4. El hilo permite elegir cualquiera de los dos valores o aplazar la decisión. La pregunta «¿Qué decidimos?» recupera la última decisión del mismo hilo y de las mismas fuentes y enlaza con la inspección original. Una selección diferente puede cambiar la respuesta.

## Alcance probado en Windows

- 248 pruebas Python, 77 pruebas del escritorio y compilación TypeScript/Vite de producción. La suite del núcleo incluye recuperación después de reabrir, revisión concurrente, reintento y aislamiento entre hilos.
- En Microsoft Edge, el frontend de producción habló por stdio con el núcleo Python real. La prueba sustituyó el transporte Tauri y el selector del sistema. Abrió las cinco fuentes, citó la página y la línea, eligió 48 h, recargó el hilo y recuperó la decisión con una pregunta nueva. Se comprobó que usar el teclado para repetir el mismo encargo no duplicó la inspección.
- El recorrido de pago se probó con Ollama y qwen2.5:0.5b. Una reserva dejó dos intentos disponibles. El modelo contradijo los extractos. La entrega principal conserva las dos cifras con su procedencia. El comentario original se puede desplegar para contrastarlo. La prueba demuestra que se presentó la observación local y se conservó la decisión humana.
- Se midieron doce muestras de texto y tres de foco por paleta en un estado de escritorio. Mínimos del texto normal de 5,924:1 en Arena y 8,042:1 en Azul noche. La prueba cubrió escalas de 100, 115 y 125 %, los dos lados del cambio de columna y una ventana de 390 píxeles.
- El 20 de noviembre de 2026 la construcción de Tauri en este Windows se interrumpió con el error 4551. Cargo devolvió 101 al intentar ejecutar auxiliares recién compilados. Code Integrity registró, entre otros, el evento 3077 de la directiva VerifiedAndReputableDesktop para el auxiliar de serde_json. El bloqueo ocurrió antes de generar el ejecutable de Neural Office. La verificación del binario de V5.14 y de su selector de archivos sigue pendiente.

## Reproducción

El registro incluye huellas del bundle y del ejemplo, los resultados de las interacciones, dos salidas originales del modelo local y la huella del auxiliar que bloqueó Windows. [Registro de verificación local](evidence/V5_14_LOCAL.json)

Ejecuta la suite con un intérprete que tenga instalados los lectores del proyecto. Desde el directorio raíz usa `python -m unittest discover -s tests`. Desde `desktop` usa `npm ci`, `npm test` y `npm run build -- --mode native`. El recorrido en Edge está en `tests/verify_v513_renderer.cjs` y escribe capturas y mediciones en el directorio que se le pasa como primer argumento. `PLAYWRIGHT_MODULE` y `NEURAL_OFFICE_PYTHON` permiten seleccionar los componentes instalados. El modelo opcional se selecciona con `NEURAL_OFFICE_TEST_MODEL` y utiliza la oficina aislada de esa prueba.

La inspección gratuita reconoce un conjunto acotado de preguntas sobre los formatos admitidos. Un resultado sobre dimensiones de una imagen no acredita su legibilidad. Los tres intentos son una cuota por proyecto. El visor de actividad presenta operaciones registradas. La validación con usuarios y lector de pantalla sigue pendiente.
