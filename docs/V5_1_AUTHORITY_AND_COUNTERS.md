# Contrato de autoridad y contadores de Neural Office V5.1

Este contrato define la autoridad, los límites y las transiciones que deberá cumplir la siguiente implementación. Su estado es **especificación propuesta, no implementada**. Documentar una transición no modifica los registros existentes ni autoriza inferencias.

**Etiquetas:** OBSERVADO describe la inspección histórica; VERIFICADO identifica una comprobación ejecutada y acotada; ESCENARIO identifica requisitos propuestos; DESCONOCIDO identifica evidencia que falta. Las secciones 2 a 9 son ESCENARIO, salvo indicación expresa. No describen garantías del runtime actual.

El piloto propuesto limita a dos proyectos activos, una inferencia administrada simultánea en toda la oficina y tres intentos consumidos por proyecto. La primera validación funcional utilizará un solo proyecto. El máximo acumulativo de tres es una decisión conservadora de este diseño; no se presenta como equivalencia demostrada entre las distintas políticas históricas de versiones y autorizaciones.

## 1 Autoridad observada

**OBSERVADO.** El recibo histórico de Gate A declara seis proyectos aparcados en V1 y V4, con contadores de certificación de V1 y versiones de V4 a cero. E34 identifica el recibo, su rango y su hash. Es una observación histórica fechada, no una consulta del estado actual ni una autorización permanente; ese recibo no demuestra el estado de las bases de V4.2, V4.5 o V5.

| Componente | Autoridad observada | Límite de interpretación |
| --- | --- | --- |
| V1 | Catálogo de proyectos y activación histórica. | Una carpeta de trabajo existente no equivale a un proyecto activo. |
| V4 Polished | Armado, presupuesto y registro de tareas en sombra. | Su estado no se sincroniza automáticamente con todos los contadores de V1. |
| V4.1 | Conciliación entre V1 `active` y V4 `armed`. | Un resultado diagnóstico no concede permisos. |
| V4.2 | Estado de grafos, leases y recibos revisados. | Una tarea reclamada no implica acceso autorizado al modelo. |
| V5 WorkLedger | Plan local con intentos y evidencias. | Acepta una afirmación del llamante sobre la autoridad externa; el director serial no lo consulta. |
| OpenCode, roles y LLM | Solicitudes de trabajo y producción de propuestas. | No son fuente de autoridad ni pueden autoaprobar resultados. |

Fuentes de la tabla: E01, E02, E03, E04, E05 y E06 del [índice de evidencias](evidence/SOURCE_INDEX.md). Las limitaciones proceden de lectura estática, no de una nueva ejecución.

## 2 Reglas de precedencia

| ID | Regla normativa propuesta |
| --- | --- |
| AUT-01 | La política de la aplicación fija el máximo permitido. Una instrucción del usuario puede reducirlo; un modelo, documento, skill o herramienta no puede ampliarlo. |
| AUT-02 | Una acción del usuario autoriza un objetivo, un proyecto, un perfil de ejecución y un alcance de herramientas. No concede permiso genérico para actuar fuera de ese alcance. |
| AUT-03 | Durante la compatibilidad con el legado, el arranque real exige evidencia consistente de V1 y V4, además del presupuesto local disponible. Un booleano suministrado por un llamante no sirve como evidencia suficiente. |
| AUT-04 | El planificador propone y el controlador decide la admisión. El LLM no modifica directamente estados, presupuestos, autorizaciones o registros de verificación. |
| AUT-05 | Cada efecto externo pasa por el ejecutor de herramientas y cada inferencia por el servicio de admisión. Los adaptadores de framework no pueden eludirlos. |
| AUT-06 | Publicar en GitHub, desplegar, enviar mensajes o modificar recursos externos requiere una acción del usuario que identifique ese destino y alcance. Un autoprompt no amplía ese permiso. |
| AUT-07 | Se deniega una nueva ejecución cuando faltan registros, hay divergencia de autoridad o no se puede resolver una operación anterior de resultado desconocido. |
| AUT-08 | Los límites se aplican en el controlador y en la admisión. Su inclusión en un prompt es informativa y no sustituye la imposición técnica. |
| AUT-09 | Antes de cada nueva operación se revalidan capacidad, revisión de política y autoridad. Una revocación bloquea nuevas operaciones y solicita detener las que estén en curso; no borra sus posibles efectos ni libera exclusión sin reconciliarlos. |

El cliente recibe una capacidad temporal vinculada al proyecto, ejecución, digest del objetivo, perfil, herramientas, revisión de política y vencimiento. Se emite tras la admisión mediante aleatoriedad del sistema y se conserva fuera de los prompts. Su formato definitivo es parte de la implementación futura. No se publican tokens ni se usan literales fijos como credenciales.

La protección cubre clientes administrados por Neural Office. No se atribuye resistencia frente a un administrador del equipo que altere archivos, procesos o red.

## 3 Entidades y contadores

| Entidad o campo | Significado | Invariante |
| --- | --- | --- |
| `project_id` | Identidad estable del proyecto y de su espacio de trabajo autorizado. | Cambiar nombre, ruta o sesión no crea presupuesto nuevo. |
| `objective_id` y `objective_digest` | Objetivo aceptado por el usuario y hash de su representación canónica. | Su contenido recuperable se conserva en un artefacto local; un hash aislado no permite reanudar. |
| `run_id` | Ejecución persistida del objetivo. | Reanudar mantiene la identidad; una reconexión de UI no crea un run. |
| `attempt_id` y `attempt_ordinal` | Unidad admitida de planificación, producción y evaluación de un candidato. | Ordinal único y creciente dentro del proyecto; como máximo un intento no terminal por proyecto. |
| `attempts_consumed` | Intentos reservados mediante una transacción confirmada. | Entero entre 0 y 3 en el piloto; nunca disminuye. |
| `verified_versions` | Número de intentos distintos con veredicto final aceptado. | Derivado de aceptaciones únicas; no supera `attempts_consumed` ni cuenta mensajes, commits o roles. |
| `model_requests_admitted` | Solicitudes admitidas al proveedor, incluidas las de reparación y herramientas. | Tiene presupuesto finito por intento, establecido en un perfil validado. |
| `tool_actions_admitted` | Acciones de herramienta admitidas. | Tiene presupuesto finito y registra clase de efecto e idempotencia. |
| `elapsed_budget` | Tiempo máximo del intento y de cada operación. | Los valores dependen del perfil medido; la ausencia de perfil impide ejecutar. |
| `revision` | Revisión de estado para comparar y actualizar de forma condicionada. | Un escritor con revisión obsoleta no sobrescribe cambios nuevos. |

### 3.1 Qué consume un intento

**CTR-01.** Admitir trabajo sobre un objetivo aceptado reserva y consume un intento antes de la primera inferencia del director, planificador, autoprompt o cualquier otro rol, y antes de la primera herramienta del intento. La planificación con modelo ya es trabajo del intento. La reserva, el incremento y el evento de auditoría pertenecen a una sola transacción; preparar formularios sin ejecutar trabajo no consume un intento.

**CTR-02.** La reserva usa una clave de idempotencia con ámbito `(project_id, tipo_operacion, client_request_id)`, vinculada al digest de la petición canónica y a su versión de esquema. Una repetición con el mismo contenido devuelve el resultado original sin incrementar el contador. La misma clave con contenido distinto produce conflicto y ningún efecto. La transacción fija un único ganador; los registros o tombstones se conservan durante todo el periodo en que pueda llegar una repetición. Cambiar la clave no permite abrir un segundo intento mientras el anterior no sea terminal.

**CTR-03.** Un error, rechazo, cancelación o fallo del backend posterior a la reserva no devuelve el intento. Una validación rechazada antes de confirmar la reserva no consume presupuesto.

**CTR-04.** Los siete roles trabajan dentro del intento. Cada turno, llamada de herramienta y reparación consume su presupuesto correspondiente. No se contabiliza cada rol como una versión.

**CTR-05.** Modificar el artefacto después del veredicto terminal exige un intento nuevo. Las correcciones dentro de un intento siguen sujetas a cuotas de llamadas, acciones y tiempo.

**CTR-06.** El tercer intento puede terminar su evaluación, pero la aplicación no admite un cuarto. Al resolverlo registra el estado terminal y el aparcado en una transacción durable.

**CTR-07.** Actualizar la aplicación, cambiar de modelo, reabrir la UI o crear otro objetivo no reinicia los contadores del proyecto. Una restauración gestionada exige conciliar la copia con una marca máxima de consumo y un registro de operaciones conservados fuera del conjunto restaurado. Si faltan o discrepan, el consumo queda DESCONOCIDO y se bloquea la admisión. Una reversión coherente de todos los archivos, incluidos esos testigos, no puede detectarse solo a partir del estado revertido: queda fuera de esta garantía. Un restablecimiento administrativo no forma parte del piloto.

El máximo de tres se mantiene por proyecto en esta primera política. Un producto de uso continuado probablemente necesitará presupuestos por mandatos sucesivos. Ese cambio exige una nueva decisión de política, con historial acumulativo y sin borrado de intentos; no queda autorizado por este contrato.

### 3.2 Versiones y llamadas no equivalen

Si un proyecto consume tres intentos y solo el segundo supera la verificación, termina con `attempts_consumed=3` y `verified_versions=1`. La cantidad de turnos del modelo se registra aparte.

El perfil debe fijar cuotas finitas antes del arranque. Sus valores se calibrarán en el piloto; no se presentan cifras de rendimiento o tiempos por defecto sin medición. La selección del perfil puede quedar integrada en la interfaz para evitar configuración manual innecesaria.

## 4 Estados y transiciones

El proyecto y el intento son entidades distintas. El proyecto está `PARKED` o `ACTIVE`. Pasar a `ACTIVE` exige autoridad y presupuesto, y reserva uno de los dos lugares de proyecto activo dentro del dominio de admisión. Un proyecto activo puede estar sin intento o tener exactamente uno no terminal. Esperar al usuario o entrar en recuperación mantiene ese lugar ocupado. Solo se aparca cuando todas sus operaciones están reconciliadas y detenidas. Al resolver el tercer intento se confirman juntos su resultado y el aparcado del proyecto.

| Estado del intento | Entrada | Salidas permitidas y condiciones |
| --- | --- | --- |
| `QUEUED` | Reserva confirmada, sin operación enviada. | `RUNNING` tras adquirir admisión; `CANCELLED` si la cancelación gana la transacción antes del envío. |
| `RUNNING` | Planificación, rol o herramienta del intento. | `VERIFYING` al congelar el candidato; `WAITING_USER` solo sin operaciones en curso; `STOPPING` por cancelación o agotamiento; `RECOVERY_REQUIRED` ante resultado desconocido; `FAILED` solo con operaciones resueltas y detenidas. |
| `VERIFYING` | Evaluación sobre una instantánea inmutable. | `ACCEPTED` mediante recibo válido si la entrega no exige otro efecto; `INTEGRATING` si exige aplicar el resultado autorizado; `REJECTED` por criterios incumplidos; `FAILED` por error conocido del verificador; `STOPPING` por cancelación o agotamiento; `RECOVERY_REQUIRED` si su resultado queda desconocido. |
| `INTEGRATING` | Candidato verificado; aplicación exacta pendiente dentro del mismo intento. | `ACCEPTED` con recibo de aplicación y terminación comprobada; `FAILED` por conflicto o error conocido; `STOPPING` por cancelación o agotamiento; `RECOVERY_REQUIRED` ante efecto desconocido. No admite generar o editar otro candidato. |
| `WAITING_USER` | Checkpoint durable, sin operaciones en curso, decisión pendiente. | Reanudar en `QUEUED` con la etapa pendiente registrada y autorización revalidada; `CANCELLED` si se cancela; `FAILED` al vencer el presupuesto de espera del perfil. |
| `STOPPING` | Se ha pedido detener; todavía puede haber efectos en curso. | `CANCELLED` o `FAILED` al confirmar terminación y reconciliar efectos, según el motivo registrado; `RECOVERY_REQUIRED` si esa confirmación no se obtiene. |
| `RECOVERY_REQUIRED` | Resultado de operación o terminación desconocido. | `QUEUED` con checkpoint reconciliado, o resultado terminal respaldado por recibos y terminación comprobada. El tiempo transcurrido o una afirmación del operador no bastan. |
| `ACCEPTED / REJECTED / FAILED / CANCELLED` | Resultado final confirmado. | Ninguna transición del mismo intento. Si queda presupuesto, el proyecto activo puede reservar otro ID y ordinal; nunca se reabre el anterior. |

Cada salida terminal exige ausencia de operaciones sin resolver. Las etapas pendientes de un checkpoint pertenecen a un catálogo versionado; reanudar no vuelve a ejecutar una acción ya confirmada. Varias UI comparten la misma autoridad durable. El controlador impone exclusión del escritor y revisiones condicionadas; otro proceso no decide contadores a partir de su caché.

**STA-01.** El verificador consume una instantánea inmutable identificada por digest y el recibo identifica los bytes efectivamente consumidos. Comprobar hashes antes y después de leer un archivo mutable no basta: podría cambiar y volver a su valor original entre ambas comprobaciones. El artefacto a integrar debe ser idéntico al verificado.

**STA-02.** Un cambio de estado y su evento se confirman juntos. No se devuelve éxito al cliente antes de confirmar la transacción.

**STA-03.** Un hash de auditoría detecta inconsistencias bajo su modelo de confianza; no prueba por sí solo autoría, identidad del operador o resistencia a un administrador local.

**STA-04.** Un único cambio terminal por intento se confirma mediante comparación de revisión y restricciones de unicidad, junto con su recibo y el evento. Repetir el mismo veredicto devuelve el resultado existente; un veredicto incompatible produce conflicto, incluso con otra clave de operación. Una cancelación confirmada antes del veredicto impide aceptar después una respuesta tardía. Si la aceptación ya fue confirmada, cancelar devuelve el resultado terminal sin reescribirlo.

**STA-05.** Verificar un candidato no concede permiso para aplicarlo. Si la entrega exige un efecto adicional autorizado, ocurre en `INTEGRATING`, consume las cuotas restantes y se reconcilia antes del terminal. No se devuelve una aceptación final ni se libera el lugar de proyecto antes de completar esa entrega. Tras el terminal solo se permite consultar y recuperar el resultado ya persistido; ninguna acción productiva se oculta como cierre administrativo.

## 5 Serialización y recuperación

**CON-01.** El límite de una inferencia es global para un `admission_domain_id` estable de la oficina administrada. Todos sus proyectos, workspaces, procesos, modelos y backends comparten esa admisión. Cambiar de ruta o proveedor no crea otro dominio. Pueden existir restricciones adicionales por recurso, pero no sustituyen el límite global. Procesos ajenos a esa oficina quedan fuera de la garantía.

**CON-02.** El lease contiene propietario, ejecución, petición y generación de cercado. Un propietario antiguo no puede completar o liberar trabajo de una generación posterior.

**CON-03.** Una desconexión de UI no cancela implícitamente el trabajo. Una solicitud de cancelación sí se registra y se propaga al backend.

**CON-04.** Cerrar el socket no basta para demostrar que el modelo ha dejado de calcular. La admisión global y el lease de recurso solo se liberan con terminación comprobada o recuperación del backend que demuestre esa terminación. Un estado ambiguo bloquea nuevas inferencias del dominio.

**CON-05.** Un timeout o lease vencido inicia reconciliación. No concede automáticamente el recurso a otro cliente.

**CON-06.** Una acción de herramienta con efectos no idempotentes y resultado desconocido no se repite automáticamente. El controlador busca su recibo y reconcilia el recurso; puede solicitar al usuario un dato o una acción concreta de recuperación. Una decisión humana no convierte por sí sola un efecto desconocido en ausencia de efecto. Una transacción del ledger no garantiza ejecución exactamente una vez de un sistema externo; cada adaptador debe declarar su garantía y sus límites.

**CON-07.** Reanudar requiere objetivo, entradas, artefactos, revisiones, presupuesto y checkpoints persistidos. El contenido se revalida; una colección de hashes sin artefactos recuperables no cumple este requisito.

## 6 Autoridad durante la migración

La V5.1 documental conserva V1/V4 como autoridad observada. El controlador futuro no utilizará una cadena de booleanos de confianza entre scripts.

| Fase propuesta | Quién decide | Condición de avance |
| --- | --- | --- |
| Observación | V1/V4 existentes; V5 no ejecuta. | Inventario y snapshots consistentes. |
| Compatibilidad | El controlador admite trabajo únicamente con evidencia de activación V1 y armado V4, además de sus propios límites. | Adaptadores y casos de divergencia probados; la UI agrupa la decisión del usuario sin ocultar fallos parciales. |
| Transferencia explícita | Un proveedor de autoridad nuevo, identificado por versión de política y recibo de migración. | Mapeo de identidades y contadores, fuentes congeladas, reversión documentada y ausencia de escritores antiguos en el flujo administrado. |

**MIG-01.** El recibo de migración incluye fuentes y hashes, revisiones, correspondencia de proyectos, contadores importados, política destino y resultado de validación. La ausencia de una base nueva no demuestra que el proyecto nunca haya consumido intentos.

**MIG-02.** V1, V4, V4.2 y los dos esquemas de director no se fusionan por semejanza de nombres. Cada campo recibe una regla explícita. Las versiones certificadas no se convierten automáticamente en intentos consumidos.

**MIG-03.** El catálogo del piloto comprende los cinco productos definidos por V4.5/V5. El sexto proyecto histórico queda aparcado y fuera de alcance hasta resolver su mapeo; no se elimina.

**MIG-04.** La retirada de un componente antiguo exige identificar y reemplazar sus consumidores. Las carpetas históricas se conservan como evidencia; ningún paso de este documento las borra.

**MIG-05.** Un fallo parcial de activación detiene la admisión y conserva un registro recuperable. La reparación solo puede afectar transiciones realizadas por la propia operación y con revisión coincidente.

## 7 Verificación independiente

**VER-01.** El implementador no puede registrar su propia afirmación como comprobación suficiente. El ejecutor de pruebas emite un recibo con comando o procedimiento, versión de herramienta, entorno, entradas, artefacto, resultados y código de salida.

**VER-02.** El verificador reproduce el problema y comprueba criterios de aceptación adecuados al producto. Un LLM puede interpretar evidencias, pero no reemplaza la observación de la herramienta.

**VER-03.** El recibo vincula la instantánea consumida y su digest, el objetivo, los criterios y el intento. El controlador valida esa correspondencia y registra como máximo una aceptación por intento según STA-04. `verified_versions` se deriva de esas aceptaciones, o se actualiza como proyección en la misma transacción. Entregar el recibo dos veces no produce dos versiones.

**VER-04.** Una aprobación humana se registra como aprobación humana. No se etiqueta como prueba automática ni como resultado de un verificador independiente.

## 8 Casos de aceptación

Todos los casos están **pendientes de implementación y ejecución**.

| Caso | Escenario | Resultado exigido |
| --- | --- | --- |
| A01 | Dos clientes reservan simultáneamente el mismo intento. | Una reserva y un incremento; respuesta idempotente para el duplicado. |
| A02 | Tres proyectos solicitan activación. | Como máximo dos activos; el tercero no obtiene capacidad de ejecución. |
| A03 | Se solicita un cuarto intento tras tres fallos. | Denegado; contador e historial intactos. |
| A04 | La UI se cierra tras reservar y vuelve a abrirse. | Mismo intento, sin reinicio de presupuesto. |
| A05 | El proceso cae después de enviar una petición al backend. | Resultado desconocido reconciliado antes de repetir o liberar el recurso. |
| A06 | Un verificador recibe un artefacto cambiado. | Veredicto rechazado por discrepancia de digest. |
| A07 | V1 está activo y V4 aparcado, o viceversa. | Nueva admisión denegada con motivo visible. |
| A08 | Un documento o skill ordena elevar permisos o reiniciar contadores. | Tratado como contenido; ninguna transición de autoridad. |
| A09 | Se rechaza el tercer candidato. | Intento terminal y proyecto aparcado de forma durable. |
| A10 | La base destino está vacía y el legado tiene historial. | No se inicializa el proyecto a cero sin conciliación. |
| A11 | Un cliente conserva un lease antiguo. | No puede completar, liberar ni sobrescribir trabajo nuevo. |
| A12 | Un rol declara éxito sin recibo independiente. | No aumenta `verified_versions`. |
| A13 | Misma clave de reserva con objetivos distintos; claves distintas para el mismo proyecto aún ocupado. | Conflicto en el primer caso; no hay segundo intento concurrente en el segundo. |
| A14 | Mismo veredicto repetido con otra clave, o veredicto incompatible tras el terminal. | Una sola aceptación; resultado previo o conflicto, nunca otro incremento. |
| A15 | Cancelación compite con aceptación, envío o verificación; respuesta tardía. | La revisión confirmada determina el orden; no se libera exclusión con trabajo desconocido ni se cambia un terminal. |
| A16 | Dos modelos/backends y dos workspaces solicitan inferencia. | Un solo permiso global en el dominio administrado. |
| A17 | Restauración con testigo más reciente, sin testigo o con todas las copias revertidas. | Conciliación en el primer caso, bloqueo en el segundo; el tercero se documenta como límite no detectable sin evidencia externa. |
| A18 | Director, planner o curación solicitados antes de reservar un intento. | Trabajo del proyecto denegado; ninguna vía auxiliar obtiene presupuesto implícito. |
| A19 | Artefacto cambia de A a B y vuelve a A durante la verificación. | El verificador consume su instantánea inmutable A; un archivo mutable compartido no satisface el contrato. |
| A20 | Intento terminal, espera agotada o tercer intento en recuperación. | Terminal inmutable; espera falla sin nuevo intento; recuperación conserva el lugar activo hasta resolver operaciones. |
| A21 | Autoridad revocada tras planificar o capacidad vencida antes de una herramienta. | Nueva acción bloqueada; la renovación autorizada conserva el intento y la recuperación conserva sus posibles efectos. |
| A22 | Verificación correcta seguida de integración fallida, cancelada o desconocida. | No se acepta antes de confirmar la entrega; no aumenta `verified_versions` por un efecto todavía indeterminado. |

## 9 Decisiones abiertas

La ampliación a presupuestos por mandatos sucesivos, los valores de cuotas por modelo y la transferencia definitiva de autoridad requieren decisiones posteriores. Mantenerlas explícitas evita que una actualización de interfaz o framework cambie los límites sin revisión.
