# V5.12 · Seguir y detener una revisión

Adjunta [el formulario de ejemplo](../examples/audit-sample.html) y pulsa **Comprobar HTML**. La lectura local muestra cuatro hallazgos y la ubicación del campo sin etiqueta. Puedes repetirla después de consultar un catálogo de Ollama vacío. La consulta al Director tiene su propia aprobación y consume un intento en el momento de la reserva.

Durante la ejecución, **Actividad** muestra el documento, el rol y sus llamadas registradas. Despliega **Actividad del encargo** para leer los eventos, con 24 registros como máximo por página. **Informe** y **Evidencia y alcance** siguen accesibles. Si estás inspeccionando una pestaña cuando llega la entrega, puedes terminar de leerla.

El saldo de la cabecera pertenece al proyecto identificado junto a él. Si abres el historial de otro proyecto mientras el Director trabaja, la franja **Trabajo en curso** conserva el proyecto al que se aplicará **Detener trabajo**. Un error al leer un informe tiene un botón de reintento propio. Detener después de reservar conserva ese cargo.

## Verificación

| Recorrido | Lo que se reprodujo en V5.11 | Lo que se comprobó en el ejecutable V5.12 de Windows |
| --- | --- | --- |
| Abrir el ejemplo después de consultar el catálogo | Un catálogo vacío deshabilitaba **Comprobar HTML**. | Con Ollama apagado y, por separado, con un catálogo vacío confirmado, cada uno de dos proyectos mostró cuatro hallazgos. El campo sin etiqueta apareció en la línea 7, columna 3. Se contaron cero reservas y cero llamadas. |
| Pasar de A a B durante una revisión | La cabecera seguía mostrando los dos intentos disponibles de A. | A mostró dos y B uno. El control de parada siguió identificando A. Al volver al borrador de B, su selector aceptó el documento de B. |
| Abrir un informe de B que tarda demasiado | **Detener trabajo** quedó deshabilitado en A hasta la siguiente lectura correcta. | Con esa lectura aún retenida, una pulsación detuvo A. El registro pasó de tres reservas a tres y de dos llamadas a dos. Se añadió un solo recibo de parada para A. El reintento de lectura recuperó el informe aceptado de B. |

La comprobación sin Ollama usó el núcleo habitual con el puerto local libre. Para provocar el fallo del informe en el momento preciso, la prueba de dos proyectos usó un modelo de prueba y controló el orden de las respuestas. El ejecutable, el selector de archivos, el proceso de trabajo y el registro SQLite participaron en el recorrido. Por separado, con Ollama y `qwen2.5:0.5b`, pasaron 13 comprobaciones nativas. El recorrido de entrega, reapertura y cancelación acabó con un intento aceptado, otro cancelado y una llamada en total. [Resultados y huellas](evidence/V5_12_WINDOWS.json) · [Prueba nativa reproducible](../tools/verify_v512_desktop.py) · [Regresiones del escritorio](../desktop/src/connected/adversarial.test.ts).

## Legibilidad y actividad

La captura procede del ejecutable de Windows durante la llamada controlada. El tiempo visible corresponde a la última lectura del núcleo. El detalle de eventos se abre a petición. Las flechas, Inicio y Fin recorren las pestañas. Si estás leyendo Actividad con el teclado cuando llega el informe, esa pestaña conserva el foco. [Captura nativa](images/v5.12-actividad.png).

En Edge para Windows se midieron seis estilos de texto de Actividad y Evidencia. Los tamaños fueron de 12 a 13 px. El contraste mínimo observado fue 8,82:1 en grafito oscuro, 6,26:1 en grafito claro, 9,14:1 en mineral oscuro y 6,28:1 en mineral claro. Un ensayo intermedio mostró que, a 1024 px de ancho, la huella del informe quedaba por debajo del borde del panel. Etiquetas y valores comparten fila cuando hay espacio. La prueba nativa volvió a encontrar visibles las tres huellas completas al abrir la pestaña. Queda pendiente evaluar la lectura con personas y lectores de pantalla. [Mediciones por elemento](evidence/V5_12_WINDOWS.json).

## Abrir el ejecutable probado

Extrae el código y el archivo del ejecutable para Windows x64. Desde la carpeta del código, usa `Start-NeuralOffice-Desktop.ps1 -Executable` con la ruta al `neural-office-desktop.exe` extraído. El archivo de Actions incluye las licencias y `SHA256SUMS`. La huella SHA-256 del ejecutable probado empieza por `e70b85667f39`. [Código exacto](https://github.com/ymkaddur/neural-office/archive/e34b8d6178b11816eb0980336113e86096096926.zip) · [Ejecutable de prueba y licencias](https://github.com/ymkaddur/neural-office/actions/runs/44506523357/artifacts/14520740879) · [Ejecución de Windows](https://github.com/ymkaddur/neural-office/actions/runs/44506523357).

Un segundo equipo Windows reprodujo los tres defectos en V5.11 y comprobó su corrección en un primer candidato de V5.12. Su directiva de Control de aplicaciones bloqueó el ejecutable final antes de abrir la ventana con el error 4551. La verificación del binario final corresponde al Windows de GitHub Actions. [Identidad de cada binario y alcance de las pruebas](evidence/V5_12_WINDOWS.json).
