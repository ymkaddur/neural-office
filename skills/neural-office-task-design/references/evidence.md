# Evidencia y límites de transferencia

Investigación consultada el 16–17 de noviembre de 2026. Los mecanismos externos se inspeccionaron en los archivos enlazados; no se ejecutaron sus repositorios. Las aplicaciones propuestas a Neural Office requieren prueba propia. Las licencias se indican para evitar confundir observación con permiso de copia.

## Lección aplicada al proyecto

La propuesta de identidad es propia: encargo con fuente explícita, alcance comprensible y entrega revisable. Es una HIPÓTESIS de valor, no un resultado de mercado.

La observación pública F01 contradice una regla de «máxima densidad para todos». F02 dirige la atención a conservar contexto en la aprobación. La comparación pertinente mide si la persona comprende y completa la tarea, no cuánto se parece una captura a Claude.


## Mecanismos externos

### assistant-ui/assistant-ui

[Archivo en el commit inspeccionado](https://github.com/assistant-ui/assistant-ui/blob/b33fbf124896e5c8343890036775dc8458ae8cb7/packages/core/src/runtime/base/base-composer-runtime-core.ts#L357). Líneas 357-395; 431-458; 520-536; nivel: `source-inspected`.

OBSERVADO: el envío captura un borrador identificado, excluye adjuntos cuya retirada está pendiente, comprueba la generación al finalizar su preparación y recupera el borrador solo bajo condiciones de entrega concretas. PROPUESTA V5.5/V6: separar borrador, envío pendiente y mensaje aceptado; al fallar un envío antiguo no sobrescribir el texto nuevo. Pruebas: retirada de adjunto durante preparación, cancelación antes de completarla y rechazo tardío después de editar el siguiente borrador.

**Límite:** Inspección estática de segmentos y utilidad de conciliación, sin ejecutar sus tests. El guardado y matching en memoria no equivalen a idempotencia durable del motor ni certifican la cancelación del proveedor. No se propone importar el paquete.

**Licencia observada:** MIT; LICENSE:1-21 inspeccionado.

### lobehub/lobehub

[Archivo en el commit inspeccionado](https://github.com/lobehub/lobehub/blob/7157b954fd0f9eab60691b14757b35474c951148/src/features/ChatInput/hooks/useChatInputDraft.ts#L13). Líneas 13-43; 48-68; 87-107; nivel: `source-inspected`.

OBSERVADO: el hook recuerda la revisión del borrador cargado, limita borrados a esa revisión, cancela el debounce al cambiar conversación y guarda el contenido bajo la clave anterior. PROPUESTA V5.5: los borradores deben pertenecer al proyecto y no perderse al navegar. Pruebas: editar A, cambiar a B antes del guardado diferido, volver a A; y desmontar un compositor vacío después de que otro haya actualizado la misma clave.

**Límite:** La revisión mostrada es updatedAt y no se ha auditado su almacenamiento; no se afirma exclusión mutua ni seguridad entre procesos. El repositorio solicitado lobehub/lobe-chat redirige a esta identidad canónica. No se copia código bajo su licencia comunitaria.

**Licencia observada:** LobeHub Community License, basada en Apache-2.0 con condiciones adicionales para derivados comerciales; LICENSE:1-24 inspeccionado. No tratar como Apache-2.0 sin restricciones.

### ag-ui-protocol/ag-ui

[Archivo en el commit inspeccionado](https://github.com/ag-ui-protocol/ag-ui/blob/79530a25f3476d0abb93cb00761906fda757a2d5/docs/spec/1.0/basic/patterns/interrupt-resume.mdx#L13). Líneas 13-42; 46-115; nivel: `contract-inspected`.

OBSERVADO: el contrato distingue interrupción que solicita respuesta, cancelación y éxito; reanudar crea otra ejecución vinculada a interrupciones identificadas. Exige cobertura explícita de las respuestas o abandonos; no interpreta una omisión como consentimiento. PROPUESTA V6: representar esperando decisión como estado propio; pruebas de aprobación obsoleta, respuesta omitida, doble resolución y reanudación con nuevo identificador sin volver a cobrar el intento previo.

**Límite:** Especificación leída, no garantía de implementación. Parte de las obligaciones recae en el consumidor y admite productores sin estado; Neural Office debe conservar validación autoritativa en su host para permisos y presupuesto. No adoptar el protocolo completo solo para mostrar estados.

**Licencia observada:** MIT; LICENSE:1-21 y docs/LICENSE:1-8 inspeccionados.

### DuskBotAI/duskbot

[Archivo en el commit inspeccionado](https://github.com/DuskBotAI/duskbot/blob/750caf446d0417b95971e7bb2c7ac98ba76f94e0/server/runtime/invariants.ts#L37). Líneas 37-99; nivel: `source-inspected`.

OBSERVADO: checkInvariants cruza estado durable, turnos vivos, eventos, informes, outcome y reinicios; compara replayStatus con el estado y detecta reconciliaciones repetidas sin turno intermedio. APLICACIÓN PROPUESTA V5.5: un diagnóstico de consistencia que compruebe owner vivo, terminal con resultado y replay concordante; mostrar estados inciertos en vez de simular éxito.

**Límite:** Este archivo es un detector, no una demostración de que todas las mutaciones hagan cumplir las propiedades. No ejecutado. La licencia no es MIT: PolyForm Noncommercial y aviso de licencia comercial separada; aprender el principio no autoriza copiar su implementación.

**Licencia observada:** PolyForm Noncommercial License 1.0.0; LICENSE:1-5,31-43. Metadato GitHub NOASSERTION, resuelto leyendo LICENSE.


## Feedback público

### F01: Preferencias enfrentadas sobre la nueva interfaz de Claude Code

[Fuente pública](https://www.reddit.com/r/ClaudeCode/comments/1x74gg2/anyone_else_hate_the_new_ui/). Publicación: 2026-10-16 (fecha de calendario del índice; la página abierta muestra fechas relativas). Consulta: 2026-11-17. Localizador: Publicación; comentarios sobre Session Rail, contexto, subagentes y monitor vertical (página leída, líneas 22-23, 66-107, 303-320).

OBSERVADO: el autor prefiere esfuerzo, uso y contexto agrupados. Otros participantes valoran el panel lateral persistente y la visibilidad de tareas/subagentes; otro informa mala adaptación a monitor vertical. Hay desacuerdo explícito, no consenso a favor de mayor densidad.

HIPÓTESIS: una franja compacta y estable para estado/presupuesto, con detalles laterales plegables, funcionará mejor que imponer máxima densidad y tres columnas a todos.

PENDIENTE: comparar tareas idénticas a 1280x800 y 900x1200; medir tiempo para identificar estado, presupuesto restante y siguiente acción; registrar errores y preferencias por separado.

**Límite:** Muestra autoseleccionada y no representativa; identidad/condición de cliente de pago no comprobadas. Fecha relativa varió entre capturas del servicio; no se obtuvo timestamp de Reddit.

### F02: Aprobaciones modales ocultan el contexto de la decisión

[Fuente pública](https://www.reddit.com/r/ClaudeCode/comments/1w1j8uj/ccs_modal_dialog_decision_boxes_to_exit_plan_mode/). Publicación: 2026-08-29 (fecha de calendario del índice; página con fechas relativas). Consulta: 2026-11-17. Localizador: Publicación y comentarios leídos, líneas 21-26 y 48-78.

OBSERVADO: participantes describen dificultades para leer el plan detrás del diálogo; uno considera ambiguo Skip y otro usa Esc para leer antes de aprobar. Un comentario propone conservar decisión, acción y comprobación juntas.

HIPÓTESIS: la aprobación debe permitir inspeccionar su alcance sin perder historial; cerrar o escapar jamás debe equivaler a aceptar.

PENDIENTE: abrir aprobación con historial largo, desplazar, reducir ventana, pulsar Escape/cerrar y reconectar; comprobar autoridad sin cambios y ausencia de ejecución hasta aprobación explícita.

**Límite:** Relatos no reproducidos aquí. El hilo enlaza issues de Claude; no contar esos enlaces como tres incidentes independientes ni diagnosticar el proveedor desde comentarios.

### F07: T3 Code: capacidad habilitada sin flujo visible de permisos

[Fuente pública](https://github.com/pingdotgg/t3code/issues/2156). Publicación: 2026-04-18T04:05:35Z. Consulta: 2026-11-17. Localizador: GitHub issue body; Problem or use case, Smallest useful scope, Risks or tradeoffs.

OBSERVADO: el autor no puede distinguir si Computer Use es incompatible, carece de permiso del sistema o necesita una aprobación que la UI no muestra; propone como mínimo informar explícitamente de incompatibilidad.

HIPÓTESIS: mostrar la capacidad realmente disponible, su bloqueo concreto y el próximo paso evita botones que aparentan ejecutar funciones ausentes.

PENDIENTE: probar capacidad ausente, denegada y disponible; cada estado debe dar una explicación y acción distinta; ningún evento desconocido debe quedar esperando invisible.

**Límite:** Issue cerrado; no acredita un defecto vigente ni equivalencia entre Codex Desktop y app-server. Propuesta de usuario, no diseño validado experimentalmente.


## Método docente

### Massachusetts Institute of Technology (MIT)

[Reading 1: Usability](https://web.mit.edu/6.813/www/sp18/classes/01-usability/). 6.813/6.831 User Interface Design and Implementation, Spring 2018. Nivel: Material docente: lectura con ejemplos de interfaces e interpretación. Localizador: Ejemplos de selector de color y ajuste del reloj; extracción web, líneas 23–66. Consulta: 2026-11-16.

OBSERVADO: analiza controles cuyo aspecto sugiere una operación distinta de la disponible; muestra cómo una selección lineal dificulta el acceso repetido y cómo la ayuda añadida no elimina el problema de interacción.

PROPUESTA: el selector de modelo, las aprobaciones y Detener deben expresar operaciones reales. Corregir la interacción antes de cubrirla con instrucciones permanentes.

**Comprobación propuesta:** Comparar primera utilización y uso repetido: completar selección por teclado, interpretar estado y cancelar; registrar errores, ayudas y tiempo.

**Límite:** Lectura histórica, no experimento con agentes ni resultado validado de Neural Office.

### Harvard University

[Design Arguments](https://pl-hci-seminar.seas.harvard.edu/design_arguments.pdf). Recurso enlazado por CS179 Design of Useful and Usable Interactive Systems. Nivel: Material docente: plantilla argumentativa de necesidades y solución. Localizador: PDF, páginas 1–3; enlace institucional desde https://glassmanlab.seas.harvard.edu/cs179_sp20.html. Consulta: 2026-11-16.

OBSERVADO: conecta persona, contexto, objetivo, obstáculos, restricciones y costes con una propuesta; pide evidencia de la necesidad, de las diferencias frente a alternativas y de la respuesta de los interesados.

PROPUESTA: expresar identidad como argumento falsable de valor, no como semejanza visual con un competidor.

**Comprobación propuesta:** Documentar una necesidad, alternativa actual y resultado esperado; observar si usuarios pueden lograrlo con el prototipo y qué evidencia refutaría la propuesta.

**Límite:** Plantilla, no evidencia de mercado. Otro PDF de Harvard devolvió 403 y no se contó como inspeccionado.
