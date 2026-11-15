# Hoja de ruta de Neural Office hasta V10

Cada versión representa una capacidad demostrada. El número de versión no sustituye evidencias de instalación, funcionamiento, calidad o derechos de distribución.

| Hito | Resultado buscado | Evidencia para cerrarlo |
| --- | --- | --- |
| V5.1 documental | Contrato de autoridad, integración y procedencia. | Documentos coherentes, referencias comprobadas y paquete público sin código operativo ni datos privados. |
| V5.1 implementación | Corregir integración y hacer cumplir los contratos acordados. | Validación nativa Windows, rutas y perfiles consistentes, presupuesto conectado al ejecutor. Requiere autorización de cambios de código. |
| V6 | Un ciclo útil completo de web-auditor en CPU. | Artefacto reproducible, verificación independiente, parada y reanudación sin pérdida de presupuesto. |
| V7 | Coordinación de roles justificada. | Comparación controlada de uno, tres y siete roles; calidad, latencia y consumo por tarea. |
| V8 | Memoria y skills con mejora medible. | Recuperación relevante, procedencia, aislamiento, promoción basada en evidencia y regresiones controladas. |
| V9 | Dos proyectos y recuperación ante fallos. | Concurrencia administrada limitada a una inferencia; pruebas de cancelación, reinicio, idempotencia y fallos parciales. |
| V10 | Aplicación distribuible para usuarios nuevos. | Instalación en máquina limpia, selección guiada de modelo, actualización y desinstalación verificadas, documentación y revisión de licencias del paquete real. |

La experiencia objetivo es descargar la aplicación, seleccionar un modelo local compatible y comenzar una tarea. El empaquetado debe encargarse del entorno necesario para que el usuario no tenga que gestionar scripts, versiones de Python o archivos de configuración manualmente.

Durante el piloto, Ollama y OpenCode son integraciones de referencia del legado. La distribución futura decidirá qué runtime gestionar o incluir después de revisar compatibilidad y licencias. No se presupone que toda dependencia histórica deba viajar en el instalador.

Las primeras tareas de implementación serán: resolver los operadores con rutas incorrectas; conectar autoridad y contadores; entregar contenido entre roles; vincular herramientas y verificación; probar la ruta completa del modelo. Solo después se ampliarán memoria, skills y autonomía.

La publicación del repositorio documental y la publicación de un instalador son hitos distintos. No habrá una descarga presentada como aplicación funcional antes de superar el recorrido de instalación y trabajo en una máquina limpia.
