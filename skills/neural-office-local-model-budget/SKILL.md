---
name: neural-office-local-model-budget
description: Medir y optimizar llamadas, contexto, RAM, CPU y GPU de modelos locales de Neural Office conservando utilidad. Úsala para perfiles, límites, caché o comparación de roles; no infiere rendimiento de estrellas, tamaño del bundle o parámetros solicitados.
---

# Optimizar trabajo útil, no actividad aparente

Define tarea, resultado aceptable y línea base antes de ajustar recursos. Cuando una comprobación determinista resuelva parte de la tarea, compárala sin modelo; después mide un rol y solo añade coordinación si mejora un resultado relevante. Siete roles no exigen siete modelos residentes ni demuestran siete perspectivas independientes.

Consulta [mecanismos medidos y por medir](references/evidence.md). Para cada ensayo fija commit, modelo/digest, runtime, hardware, fuente sintética, perfil efectivo y estado frío/caliente. Conserva separadas estas magnitudes:

- Intentos durables, iteraciones, roles, envíos reales, respuestas y tokens. Un retry de transporte puede no sumar al contador de un framework. Uso omitido significa desconocido o cota inferior, nunca cero.
- Límite ejecutable y estimación de capacidad. Un recorte usado por un scheduler para admitir trabajo no limita necesariamente la generación. Comprueba reserva antes del envío y conciliación posterior, con casos 0, N−1, N y N+1.
- Pesos, contexto/KV, caché, runtime, Python y UI. Menor VRAM por offload puede subir RAM y latencia. Heap JS y bytes del bundle no son memoria total del escritorio.
- Tiempo de CPU, tiempo de pared, working set, memoria comprometida y VRAM. Declara alcance de procesos, intervalo y duración; sumar working sets puede contar páginas compartidas varias veces.

Mide inicio frío, ejecución, espera, cancelación y cierre en el conjunto de procesos que realmente poseemos. No descargues ni termines modelos ajenos para mejorar cifras. Cerrar la ventana o cambiar `keep_alive` no prueba liberación inmediata. Verifica cancelación durante carga y llegada tardía de trabajo antes de afirmar recuperación de recursos.

No uses respuesta cacheada como otra muestra de calidad. Repetir una clave operacional debe recuperar el mismo recibo; repetir una evaluación estocástica necesita ensayos independientes y declarar caché de respuesta frente a caché de prefijos/pesos.

Entrega una comparación con calidad, latencia, llamadas y picos bajo el mismo alcance, junto a regresiones y costes. No promociones una optimización que pierde corrección o calidad para mejorar una cifra. Una muestra corta no acredita ausencia de fugas; define un ensayo sostenido si esa es la afirmación que se quiere realizar.
