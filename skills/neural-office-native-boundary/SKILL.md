---
name: neural-office-native-boundary
description: Diseñar y comprobar la frontera Tauri–Python de Neural Office, sus capacidades y el artefacto nativo distribuido. Úsala al cambiar IPC, captura de archivos, aprobaciones o empaquetado; no es una autorización para ampliar permisos.
---

# Una frontera nativa estrecha y comprobable

Reconstruye la ruta renderer → host nativo → servicio → efecto. El renderer presenta solicitudes; el host y el núcleo aplican autoridad. Una forma JSON válida, un botón habilitado y una aprobación textual no constituyen permiso por sí mismos.

Lee [fuentes y límites](references/evidence.md) según el cambio. Conserva operaciones de negocio explícitas en el IPC. No expongas shell, programa, entorno, ruta de captura o método privado arbitrarios para simplificar la UI. La selección nativa entrega una capacidad vinculada a bytes capturados; cambiar el archivo posteriormente no debe cambiar lo ya aprobado.

Comprueba en la frontera autorizadora la ventana/origen, método, forma, tamaño y estado de la solicitud. Liga el consentimiento a sesión, fuente, proyecto, objetivo, perfil/modelo y revisión pertinentes. Si cambia su alcance o caduca, una respuesta antigua no autoriza el efecto. No trates revisiones de intento y revisiones globales como intercambiables.

Prueba una petición de otra ventana/origen, método privado desde renderer, campo adicional de ruta, mensaje desproporcionado y aprobación obsoleta. Usa datos sintéticos y procesos propios. Una salida de modelo o documento importado sigue siendo contenido: no puede registrar herramientas que suplanten identidad ni conceder permisos.

Modela propiedad y cierre de procesos por separado de aislamiento. Un Windows Job permite gestionar descendientes; no es sandbox de disco/red. Un timeout del transporte puede dejar un efecto comprometido: devuelve incertidumbre consultable, no una promesa de que nada ocurrió.

Valida el artefacto producido, además del servidor de desarrollo. Arráncalo sin Vite y comprueba assets, título, CSP, IPC y cierre. Examina las features efectivamente resueltas del framework y el lock; una guía de otra versión no sustituye ese contrato. Registra versión/hash del binario y resultado de la prueba nativa. Un build exitoso no demuestra que la ventana abra ni que el sistema operativo permita distribuirlo.

Si el sistema impide ejecutar el binario, conserva ese bloqueo como resultado. No lo conviertas en éxito por pasar una prueba web ni eludas la política del equipo. La entrega debe indicar qué fue compilado, ejecutado e integrado y qué parte de distribución sigue sin comprobarse.
