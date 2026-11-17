---
name: neural-office-task-design
description: Diseñar el flujo de encargo, Director y entrega de Neural Office a partir de una tarea concreta. Úsala para jerarquía, compositor y estados del producto; no para imponer una estética universal ni auditar el motor.
---

# Diseñar una oficina que se entienda

Convierte una tarea del usuario en una secuencia reconocible: fuente y objetivo → alcance aprobado → trabajo observable → entrega revisable → recuperación. La identidad propuesta es un encargo bajo control, con evidencia accesible. Su utilidad y diferenciación son hipótesis que deben probarse, no atributos ganados por tener cinco pantallas.

Antes de cambiar componentes, identifica el resultado que busca la persona, qué decisión necesita tomar ahora y qué dato la permite. Mantén esas tres cosas en la superficie principal; deja detalles de ejecución a un nivel desplegable. Director designa el punto de coordinación, no demuestra que exista un agente adicional ni debe añadir una llamada al modelo por decoración.

Para compositor, aprobaciones y recuperación, consulta [mecanismos y contrapruebas](references/evidence.md). Conserva estas distinciones:

- Borrador, envío pendiente y encargo aceptado son entidades o estados distintos; el recibo conserva el vínculo con la misma clave operacional, sin rotarla al aceptar. Un fallo tardío de A no puede borrar o reemplazar el borrador B. Un resultado abierto con compositor vacío no es una orden de reenviar.
- La aprobación conserva a la vista fuente, acción y límite que se autorizan. Escape o cerrar devuelven al encargo sin ejecutar. No ocultes contexto indispensable detrás de la decisión.
- Muestra lo que el usuario puede hacer en ese estado. Una capacidad inexistente necesita explicación; un botón que simula ejecutarla crea una promesa falsa.
- Estado, intento consumido, llamadas y resultado son magnitudes distintas. Si falta el dato autoritativo, muestra incertidumbre y cómo conciliarla; no inventes cero o éxito.
- La densidad se decide por tareas y tamaños de ventana. No conviertas dark mode, tres columnas, monospace o radios pequeños en requisitos de calidad. Usa color, espacio y movimiento para priorizar acciones y cambios, conservando lectura y foco.

Entrega el flujo con estados vacíos, activo, esperando decisión, detenido, fallo parcial y resultado. Para cada cambio material, señala qué decisión facilita y recorre la misma tarea con teclado, ventana estrecha y reapertura. Registra qué parte es fixture y cuál realiza trabajo. Si falta observación de usuarios, formula el experimento que podría refutar la jerarquía propuesta; no anuncies preferencia del mercado.
