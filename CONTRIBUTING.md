# Contribuir a Neural Office

Empieza con una reproducción pequeña y un resultado esperado. Las áreas prioritarias son el arranque local, continuidad del estado, claridad de la interfaz y casos HTML representativos.

## Entorno

Windows y Python 3.12 con Tk. La suite no necesita Ollama, modelos ni credenciales:

```powershell
py -3.12 -B -m unittest discover -s tests -v
```

Usa una carpeta temporal y datos sintéticos. Una base nueva es adecuada para un proyecto de prueba independiente; no debe usarse para devolver presupuesto a un proyecto existente.

## Incidencias y cambios

1. Describe contexto, comportamiento observado y propiedad esperada. Indica versión/commit, comando y caso mínimo.
2. Etiqueta evidencia como OBSERVADO, VERIFICADO, INFERIDO, ESCENARIO o DESCONOCIDO. Para fallos intermitentes, conserva orden de eventos y marcas temporales.
3. Contrasta la explicación con una alternativa y una prueba que pueda refutarla.
4. Propón el cambio local más pequeño y una regresión que falle antes y pase después.
5. Separa mediciones con fixtures de ejecuciones con un modelo real. Incluye riesgos residuales.

Los cambios de autoridad, cuotas, recuperación y procesos requieren pruebas de error y concurrencia, además del caso correcto. CI ejecuta la suite pública en Windows; las pruebas opcionales del legado requieren una copia histórica separada y no se contabilizan como CI pública.

## Privacidad y procedencia

No adjuntes bases SQLite, prompts privados, conversaciones, claves, rutas personales, logs completos ni pesos. Publica una reproducción sintética y campos de diagnóstico depurados. Revisa también el historial del commit y su email.

Incluye origen y licencia de cualquier aporte externo, conserva sus avisos y declara asistencia de IA cuando resulte relevante para la revisión. No copies recursos de otro repositorio porque su README resulte atractivo. Al enviar una contribución debes tener derecho a ofrecerla bajo la licencia MIT del proyecto; esto no garantiza por sí solo la titularidad de todo material generado por IA.

No cambies límites, actives proveedores remotos ni amplíes herramientas con efectos como parte incidental de otra corrección. Describe esas propuestas como cambios de alcance separados.
