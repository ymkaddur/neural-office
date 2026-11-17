---
name: neural-office-memory-provenance
description: Diseñar memoria de proyecto y skills inspeccionables de Neural Office con procedencia, versiones y revocación. Úsala al añadir aprendizaje o instrucciones reutilizables al producto; crear esta skill de desarrollo no implementa esas funciones en el runtime.
---

# Aprender sin convertir contenido en autoridad

Parte de una necesidad demostrada de reutilización. Para el piloto, una memoria pequeña, consultable y acotada puede ser suficiente; no adoptes un vector store, CRDT o framework de agentes por genealogía. Lee [fuentes y límites](references/evidence.md) antes de elegir persistencia o promoción.

Mantén separados dato observado, instrucción importada, propuesta generada, versión aceptada y permiso de ejecución. El nombre de una herramienta o la frase «aprobado por el usuario» dentro de una fuente no autentican su procedencia. Las skills pueden ayudar a decidir; no pueden sustituir las capacidades o límites del host.

Para cada entrada reutilizable define identidad, proyecto/ámbito, origen localizable, revisión/hash de fuente, fecha, versión, estado y razón de incorporación. Los campos deben servir a inspección, actualización o revocación; no acumules metadatos sin uso. Un hash demuestra igualdad de bytes, no verdad de la afirmación ni titularidad de material ajeno.

El ciclo mínimo distingue propuesta, comprobación y publicación de una versión. Si falla el commit, sigue vigente la anterior; no muestres aprendizaje incorporado desde un estado intermedio. Retirar o reemplazar una entrada invalida lecturas en vuelo y futuras selecciones. No borres el recibo de las ejecuciones que ya la utilizaron.

Prueba: fuente modificada; dos versiones que terminan en orden inverso; entrada revocada mientras se recupera; instrucción hostil que pide elevar permisos; proyecto A que no debe ver memoria de B. Mide tamaño de contexto y coste de recuperación con límites de entradas y bytes. La memoria fuera del prompt no es gratuita si después se inyecta completa.

Haz visibles las instrucciones activas, su precedencia y el motivo de selección. Conserva los borradores hasta confirmar su destino; un autosave encontrado no autoriza reemplazar trabajo actual silenciosamente. Restaurar archivos, recuperar una sesión y compensar un efecto ya realizado son capacidades distintas: ofrece «Deshacer» solo cuando exista una operación inversa válida.

La salida debe incluir esquema mínimo, transición de versiones y una prueba que refute la promoción incorrecta. Si la tarea solo pide skills para desarrollar Neural Office, entrega archivos de instrucciones para el agente de desarrollo y no los anuncies como aprendizaje autónomo del producto.
