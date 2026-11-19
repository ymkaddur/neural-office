---
name: neural-office-durable-interactions
description: Conectar la interfaz de Neural Office con intentos durables sin duplicar trabajo ni mostrar autoridad inventada. Úsala para enviar, reconectar, cancelar, paginar o recuperar; una caché visual no sustituye el ledger.
---

# Interacciones que sobreviven a una respuesta perdida

Identifica primero quién conserva la autoridad y qué identidad enlaza oficina, proyecto, intento y comando. Revisa el contrato vigente antes de cambiar validadores: un identificador histórico textual no es necesariamente un token opaco nuevo. No normalices, recortes o renombres valores aceptados por el núcleo sin una migración explícita.

Consulta [evidencia y regresiones](references/evidence.md) para la frontera modificada. Conserva estos invariantes:

- Persiste la identidad de envío antes de solicitar el efecto. Una respuesta perdida después del commit deja resultado desconocido, no permiso para crear otra clave. Reconectar consulta el recibo de la misma oficina/proyecto/clave; no reinicia la inferencia automáticamente.
- Vincula la clave al contenido y ámbito. La misma clave con contenido incompatible debe producir conflicto, nunca reutilizar silenciosamente la aprobación. Doble clic y reenvío tienen que conservar consumo y número de ejecuciones.
- Cada lectura asíncrona pertenece a oficina, sesión y generación. Tras cambiar de contexto, un resultado viejo no restaura una aprobación ni sobrescribe datos actuales. Una generación de UI evita algunas carreras; no concede autorización.
- Cancelar tiene admisión cerrada, solicitud de parada y confirmación de terminación. Una notificación tardía o continuación pendiente no puede reactivar el intento. Desmontar un componente no prueba que haya cesado un proceso.
- Concilia los datos dependientes antes de publicar una transición que desmonte su propio observador. Prueba respuestas inmediatas y diferidas; no mantengas polling indefinido para ocultar el problema.
- Colecciones con cursores independientes se paginan por separado. Combina páginas solo bajo identidad y revisión compatibles; conserva límites de memoria. Si el proyecto seleccionado no está en la página, su cuota es desconocida, no cero.

Si el historial y el detalle leen el mismo intento a ritmos distintos, comprueba ambos mientras ocurre una transición. Concilia por oficina, sesión, proyecto, intento y revisión. Mantén cada fila archivada vinculada a su propio recibo. Antes de sugerir una acción al usuario por ausencia de modelos, comprueba si el catálogo responde con una lectura vigente o con una copia antigua.

Para el cambio actual, retén una respuesta en la frontera relevante mediante evento/barrera y varía solo su orden. Comprueba estado persistido, representación visible, llamadas y consumo. Incluye reapertura cuando se prometa durabilidad; cierre limpio y muerte abrupta son experimentos diferentes.

Entrega secuencia causal, estado anterior/posterior y prueba de regresión. No prometas ejecución «exactamente una vez» de herramientas externas por tener una tabla de claves: necesita identidad del efecto, recibo y conciliación de su ventana de incertidumbre. Para una investigación de seguridad o fiabilidad completa utiliza la skill forense existente.
