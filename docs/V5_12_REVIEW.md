# V5.12 · Seguir y detener una revisión

Adjunta [el formulario de ejemplo](../examples/audit-sample.html) y pulsa **Comprobar HTML**. La lectura local muestra cuatro hallazgos y la ubicación del campo sin etiqueta. Puedes repetirla después de consultar un catálogo de Ollama vacío. La consulta al Director tiene su propia aprobación y consume un intento en el momento de la reserva.

Durante la ejecución, **Actividad** muestra el documento, el rol y sus llamadas registradas. Despliega **Actividad del encargo** para leer los eventos, con 24 registros como máximo por página. **Informe** y **Evidencia y alcance** siguen accesibles. Si estás inspeccionando una pestaña cuando llega la entrega, puedes terminar de leerla.

El saldo de la cabecera pertenece al proyecto identificado junto a él. Si abres el historial de otro proyecto mientras el Director trabaja, la franja **Trabajo en curso** conserva el proyecto al que se aplicará **Detener trabajo**. Un error al leer un informe tiene un botón de reintento propio. Detener después de reservar conserva ese cargo.

## Verificación

Las [regresiones del escritorio](../desktop/src/connected/adversarial.test.ts) controlan el orden de las respuestas. La [prueba nativa](../tools/verify_v512_desktop.py) utiliza el selector de Windows, dos proyectos y registros SQLite aislados. El caso de parada mantiene pendiente la siguiente lectura del trabajo activo mientras se pulsa el botón.

El [flujo de Windows](https://github.com/ymkaddur/neural-office/actions/workflows/windows-tests.yml?query=branch%3Afeat%2Fv5.12-control) genera el ejecutable y su archivo de huellas. Para abrirlo, usa el código del mismo commit y pasa la ruta del ejecutable extraído a `Start-NeuralOffice-Desktop.ps1 -Executable`.
