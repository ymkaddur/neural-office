# Especificación de integración completa de Neural Office V5.1

La aplicación deberá convertir un objetivo del usuario en trabajo local verificable, con herramientas y estado recuperable. La experiencia prevista es descargar Neural Office, seleccionar un modelo local compatible y comenzar. Los detalles de configuración que pueda resolver la aplicación no deben trasladarse al usuario.

**Estado: diseño propuesto. Ningún requisito descrito aquí se considera implementado por su inclusión en el documento.** El [contrato de autoridad y contadores](V5_1_AUTHORITY_AND_COUNTERS.md) gobierna todos los componentes.

**Etiquetas de evidencia:** los requisitos, tablas de comportamiento objetivo y casos pendientes son ESCENARIO. Las descripciones del legado son OBSERVADO por lectura estática y citan E01–E36; no equivalen a ejecución verificada. Las decisiones y mediciones que faltan son DESCONOCIDO. El [registro de revisión](V5_1_REVIEW_REPORT.md) separa las comprobaciones documentales VERIFICADAS de los ensayos futuros.

## 1 Alcance y punto de partida

El primer producto piloto será web-auditor: un objetivo acotado sobre un proyecto de prueba, un informe o cambio identificable y una comprobación independiente. Se validará con CPU y una inferencia administrada simultánea.

El legado conserva tres límites de integración relevantes:

- La configuración de OpenCode del workspace mantiene un modelo CPU128k y una URL directa al backend; el candidato V5 exige otro modelo y una cabecera de sesión. Cambiar únicamente la URL no resuelve la integración.
- El director serial de V5 no consulta WorkLedger y envía hashes de las dependencias, sin su contenido. Los mandatos de rol, memoria y skills existen en módulos separados.
- Los operadores instalados de Gate B y Gate C buscan archivos en rutas diferentes a las de la instalación observada.

Referencias: E05, E06, E12, E13, E14, E15, E16, E20 y E35 del [índice de evidencias](evidence/SOURCE_INDEX.md).

## 2 Recorrido del usuario

| Paso | Comportamiento objetivo | Condición verificable |
| --- | --- | --- |
| Instalar | Un paquete de aplicación prepara sus componentes compatibles. | En una máquina limpia no exige editar scripts ni instalar manualmente paquetes Python. |
| Elegir modelo | El asistente detecta modelos locales y muestra compatibilidad y recursos estimados. | La selección identifica digest, proveedor y perfil; un alias mutable no basta. |
| Descargar modelo | Si falta, el asistente explica origen, tamaño, licencia y destino antes de descargar. | La descarga es explícita y verifica integridad; no ejecuta código remoto del repositorio del modelo. |
| Preparar proyecto | El usuario elige carpeta, objetivo y resultado esperado. | La aplicación delimita el workspace y presenta el alcance de acciones. |
| Comenzar | Una acción del usuario admite el objetivo y el perfil de permisos. | El controlador comprueba autoridad, presupuesto y recursos antes de ejecutar. |
| Supervisar | La interfaz muestra progreso, evidencias, presupuesto y decisiones pendientes. | El estado viene del ledger, no de afirmaciones libres del modelo. |
| Parar o reanudar | El usuario puede detener trabajo o recuperar una ejecución. | Se conservan identidad, artefactos, intentos consumidos y resultado de la cancelación. |

La selección de modelo no promete compatibilidad universal. Un modelo que solo cumpla el perfil de conversación puede ofrecer análisis limitado, pero no se presentará como apto para una oficina con herramientas. El usuario recibe un motivo concreto cuando un modelo no satisface el perfil.

La obtención de modelos y las consultas web son operaciones de red explícitas. Tras preparar la aplicación y el modelo, el flujo local básico deberá poder funcionar sin credenciales de un proveedor cloud. La inferencia cloud queda fuera del piloto.

## 3 Componentes y responsabilidad

| Componente | Entrada | Salida y responsabilidad |
| --- | --- | --- |
| Interfaz | Objetivo y decisiones del usuario. | Solicitudes identificadas; nunca modifica contadores directamente. |
| Controlador | Solicitud, autoridad y perfil. | Reserva intentos, planifica estados y emite capacidades limitadas. |
| Adaptador de autoridad | Registros V1/V4 o proveedor futuro autorizado. | Snapshot con revisiones y resultado de conciliación. |
| Registro de modelos | Metadatos del backend y elección del usuario. | Identidad inmutable, perfil calificado y capacidades. |
| Servicio de admisión | Petición vinculada a ejecución y capacidad. | Valida, serializa, limita y registra cada inferencia. |
| Adaptador de proveedor | Petición canónica validada. | Traducción al protocolo admitido y respuesta normalizada. |
| Ejecutor de herramientas | Acción tipada y alcance. | Efecto acotado y recibo verificable, con idempotencia declarada. |
| Coordinador de roles | Objetivo, grafo aprobado y evidencias. | Turnos con contratos; no emite permisos ni ejecuta shell arbitrario. |
| Verificador | Artefacto congelado y criterios. | Pruebas independientes y veredicto vinculado al artefacto. |
| Memoria | Evidencias elegibles y consulta. | Recuperación con procedencia, aislamiento, presupuesto y versión. |
| Registro de skills | Candidatos, evaluación y aprobación. | Versiones inmutables elegibles para un alcance concreto. |
| Observabilidad | Eventos de todos los componentes. | Trazas locales redactadas y métricas derivadas de eventos. |

La biblioteca o framework de agentes es un adaptador del coordinador. CrewAI puede evaluarse para ese puesto; no será una segunda autoridad, un segundo contador o una ruta alternativa al backend. No hay una implementación Flow verificada en el legado de Plus a V5.

## 4 Identidad y compatibilidad del modelo

**MOD-01.** El registro conserva proveedor y versión, identificador solicitado, digest resuelto, arquitectura declarada, cuantización, licencia declarada, contexto admitido, salida máxima, requisitos de herramientas y revisión del perfil.

**MOD-02.** Un perfil de capacidad distingue metadatos observados de resultados medidos. Declarar una ventana de contexto no demuestra que esa ventana esté asignada ni que la calidad se conserve al llenarla.

**MOD-03.** El piloto usa CPU con `num_gpu=0`. Contexto máximo inicial: 65536 tokens; salida máxima por petición: 4096. El presupuesto de contexto incluye entradas, resultados de herramientas, memoria y espacio para la salida. No se usará una estimación por caracteres como medida exacta de tokens.

**MOD-04.** Un modelo con menos capacidad efectiva puede usar un perfil menor validado. El sistema no aumenta un límite porque un nombre contenga `64k` o `128k`.

**MOD-05.** Cambiar de modelo invalida la calificación y las capacidades ligadas al perfil anterior. No reinicia el presupuesto del proyecto.

**MOD-06.** La calificación se realiza como operación delimitada, con conocimiento del usuario y un perfil de sonda fijo con cuotas finitas, sin permisos sobre proyectos. Utiliza fixtures sintéticos identificados; no puede ejecutar objetivos del usuario ni curación de sus datos bajo la etiqueta de calibración. Comparte la admisión global de inferencia. Una calificación desconocida solo permite esas sondas restringidas, no trabajo de proyecto. V5.1 documental no realiza esa inferencia. La medición futura incluirá herramientas, formato de salida, seguimiento de instrucciones, RAM, tiempo hasta primer token y duración total.

**MOD-07.** Una restricción dura de 4500000000 bytes de VRAM no se declarará demostrada por un parámetro del modelo. Mientras no haya una garantía aplicable y probada, la ruta soportada será CPU.

**MOD-08.** Una URL local no demuestra que la inferencia sea local: un backend puede ofrecer acceso a modelos remotos. El perfil del piloto exige comprobar el modo de ejecución y la presencia e identidad de los pesos locales, y excluye modelos cloud aunque se anuncien mediante un servidor en loopback.

El modelo de referencia histórico sirve para reproducir observaciones; el producto no debe quedar ligado permanentemente a su nombre. La interfaz de proveedor permitirá otros modelos mediante perfiles de capacidad probados.

## 5 Integración de transporte

### 5.1 Petición canónica

Cada petición administrada contiene:

- `request_id`, `run_id`, `attempt_id`, `project_id` y clave de idempotencia.
- Referencia de capacidad y revisión de política, fuera del contenido enviado al modelo.
- Digest del modelo, perfil y configuración efectiva.
- Mensajes normalizados, declaraciones de herramientas permitidas y formato esperado.
- Cuotas de entrada, salida, tiempo y tamaño; modo de streaming.
- Referencias a objetivo, plantilla, skills y evidencias utilizadas.

La serialización no incluye secretos del controlador en los mensajes. Las respuestas separan contenido generado, solicitudes de herramientas, métricas del proveedor y errores de transporte.

| Registro | Campos obligatorios | Validación |
| --- | --- | --- |
| Estado de ejecución | Versión de esquema, IDs de proyecto/run/intento, estado, revisión, cuotas consumidas y restantes, motivo de parada. | Enumeraciones cerradas, contadores no negativos y correspondencia con eventos confirmados. |
| Resultado de rol | ID de nodo, rol, intento, objetivo, referencias de entrada, contenido estructurado, afirmaciones, evidencias, incertidumbres y digest. | Campos exigidos por el nodo; referencias resolubles; sin ampliar el alcance del objetivo. |
| Recibo de herramienta | ID de acción, herramienta y versión, referencia privada de entradas efectivas, workspace, efecto, inicio/fin, resultado, salida y artefactos. | Emitido por el ejecutor; correspondencia con la acción admitida y con los argumentos realmente consumidos. La proyección exportable se identifica por separado. |
| Recibo de verificación | ID de verificación, intento, objetivo, artefacto y digest, criterios, entorno, herramienta, resultados y conclusión. | No sustituible por texto del implementador; criterios y artefacto coincidentes. |
| Evidencia de gate | Gate, alcance, fuente, versión, configuración y digests, fecha de observación, condiciones de caducidad. | Una evidencia de otro entorno, modelo o configuración no satisface el gate actual. |

Las operaciones internas serán: preparar proyecto, admitir objetivo, reservar intento, consultar estado, cancelar, reanudar, entregar artefacto, registrar verificación y solicitar integración. Toda mutación exige identidad de operación, revisión esperada y clave de idempotencia. Consultar estado no inicializa una base ni modifica el proyecto.

La clave de idempotencia está vinculada al contenido según CTR-02; conocerla no sustituye la autorización vigente para consultar o repetir una operación. La representación canónica fija esquema, tipos, codificación y tratamiento de campos ausentes, nulos, números y texto Unicode antes de calcular el digest. No se normaliza texto de una forma que cambie la semántica de la herramienta. Un payload distinto con la misma clave produce conflicto.

El registro privado vincula los argumentos efectivos mediante su representación canónica protegida; las credenciales se resuelven por referencias de identidad y versión fuera de los argumentos visibles. No se exportan secretos ni hashes de secretos de baja entropía. La proyección redactada tiene identidad y digest propios: dos acciones distintas pueden producir la misma proyección y eso no las convierte en una sola acción. Tampoco permite reproducir una acción si faltan sus entradas privadas.

Los errores se clasifican como validación, autoridad, presupuesto, recurso ocupado, incompatibilidad, transporte, evidencia inválida o ejecución desconocida. La clasificación determina si se puede repetir la solicitud; un mensaje de error del modelo no controla esa decisión. El cliente recibe un motivo legible y un ID de diagnóstico sin secretos.

### 5.2 Rutas y configuración

**NET-01.** La aplicación utiliza una autoridad de admisión para todo el dominio de oficina, con máximo de una inferencia global y límites adicionales por recurso si fueran necesarios (CON-01). El puerto 11555 es una referencia del legado, no una constante que el futuro usuario deba configurar manualmente.

**NET-02.** El asistente identifica la configuración realmente resuelta: políticas administradas del sistema, capas globales, directorios ascendentes, proyecto, carpetas de configuración, entorno, opciones de lanzamiento y proveedor. Rechaza combinaciones ambiguas para la sesión administrada y muestra el origen del valor efectivo. La precedencia se comprueba para la versión fijada del cliente.

**NET-03.** La transición de OpenCode comprende URL, modelo, contexto, salida, autenticación, herramientas y streaming. Se aplica mediante comparación de revisión/hash y respaldo verificable, sin reemplazos globales de strings.

**NET-04.** Las configuraciones y clientes históricos fuera de la sesión administrada se inventarían como rutas no cubiertas. La aplicación no afirmará exclusividad de todo el equipo mientras existan accesos no controlados.

**NET-05.** El servicio escucha solo en loopback durante el piloto y autentica a sus clientes. Loopback delimita exposición de red; no sustituye autenticación entre procesos locales.

**NET-06.** El adaptador solo admite rutas y campos probados. Un campo desconocido se rechaza con motivo; no se elimina silenciosamente si cambia la semántica.

### 5.3 Matriz de protocolo

| Flujo | Situación observada | Exigencia de integración |
| --- | --- | --- |
| Ollama nativo chat | El normalizador legado permite mensajes simples; el backend V5 no opera un ciclo de herramientas. | Implementar y probar mensajes, solicitudes y resultados de herramientas requeridos por el perfil. |
| Ollama nativo generate | Existe normalización acotada. | Admitirlo solo para tareas compatibles; no simular capacidades de chat/herramientas inexistentes. |
| Chat compatible con OpenAI | El normalizador admite un subconjunto de mensajes y herramientas y limita salida. | Probar el subconjunto exacto emitido por el cliente y el control efectivo de contexto/CPU en el backend. |
| Streaming | Existe reenvío en el gateway legado. | Preservar orden, fragmentos, terminación, errores y cancelación; una respuesta parcial no es un artefacto verificado. |
| Metadatos y salud | Los gateways legados no son proxys generales de todos los endpoints. | Implementar solo descubrimiento necesario y sanitizado, sin exponer configuración o secretos. |
| Dos clientes | Hay un mutex cooperativo corregido. | Probar admisión común, colisiones, cancelación, caída y recuperación; no inferirlo de pruebas con un único cliente. |

Fuentes: E11, E12 y E13. La documentación vigente del proveedor deberá contrastarse con la versión fijada antes de implementar los adaptadores: [API de Ollama](https://docs.ollama.com/api) y [configuración de OpenCode](https://opencode.ai/docs/config/).

### 5.4 Cancelación y tiempos

El timeout ascendente de 12 segundos del gateway legado no se adopta como valor adecuado sin medir el perfil CPU. La interfaz distingue espera de recurso, carga del modelo, prefill, generación y ejecución de herramientas.

Los límites serán finitos y configurados por perfil. Cancelar revoca admisión de nuevas acciones y solicita terminar la operación en curso. Hasta confirmar la terminación o reconciliar el backend, el recurso conserva exclusión. Se aplica CON-04 del contrato de autoridad.

La UI distingue solicitud de parada (`STOPPING`) de parada confirmada. El presupuesto comprende planificación, verificación y espera de decisiones; el perfil define sus límites. El tiempo en una misma vida de proceso se mide con reloj monotónico. Reiniciar no devuelve tiempo consumido: la recuperación reconcilia el presupuesto persistido; si no puede establecer el saldo con la política de reloj prevista, bloquea la reanudación. La limpieza y reconciliación siguen permitidas para detener efectos, pero no admiten nuevo trabajo del objetivo con presupuesto agotado.

## 6 Herramientas y ejecución

**TOOL-01.** Cada herramienta declara nombre y versión, esquema de argumentos y resultado, permisos, workspace, acceso de red, clase de efecto, idempotencia y verificador del resultado.

**TOOL-02.** El ejecutor valida argumentos fuera del LLM. Resolver una ruta y abrirla después no elimina una carrera si cambian enlaces simbólicos, junctions o el destino. La operación debe quedar vinculada a la identidad validada del recurso mediante mecanismos de la plataforma y comprobar también sus salidas. Cuando el adaptador no pueda imponer ese límite, deniega la acción; no promete aislamiento por una comparación textual de prefijos.

**TOOL-03.** Las acciones de proceso utilizan ejecutable y argumentos tipados permitidos. No se acepta shell arbitrario porque un modelo lo proponga. Las herramientas del piloto tendrán capacidades mínimas para leer, producir un artefacto aislado y verificarlo.

**TOOL-04.** El implementador trabaja en un espacio aislado del original. El integrador prepara el candidato antes de congelarlo. Cuando la entrega exija aplicarlo, solo aplica sus bytes o diff verificados en `INTEGRATING`, contra una revisión base coincidente y dentro de la autorización y cuotas del mismo intento (STA-05). Si el destino cambió, detiene esa aplicación; no resuelve conflictos alterando el candidato bajo un veredicto anterior. Un intento ya terminal no admite nuevas acciones productivas. Despliegues y publicación externa no forman parte implícita de la tarea local.

**TOOL-05.** Las respuestas de herramientas y páginas son datos no confiables. No alteran política, presupuesto, destino de publicación ni permisos.

**TOOL-06.** Cada ejecución produce un recibo privado vinculado a sus entradas y resultado efectivos; la versión exportable aplica la separación definida en 5.1. Identifica herramienta, entorno, salida, código de resultado y artefactos. Una frase del modelo no sustituye el recibo. La falta de recibo después de un posible efecto exige reconciliación, no inventar un resultado fallido sin efecto.

## 7 Roles y transferencia de contexto

| Rol | Trabajo | Entrega mínima |
| --- | --- | --- |
| Director | Delimitar objetivo y criterio de finalización. | Objetivo, restricciones, criterios y presupuesto referenciado. |
| Planner | Preparar tareas y dependencias. | Plan acotado, entradas, salidas y condiciones de parada. |
| Researcher | Obtener evidencia pertinente. | Afirmaciones, fuentes, incertidumbres y restricciones de uso. |
| Implementer | Producir el artefacto del candidato. | Artefacto o diff, fundamento y recibos de herramientas. |
| Skeptic | Intentar refutar las afirmaciones del candidato. | Fallos reproducibles, riesgos y evidencia contradictoria. |
| Verifier | Comprobar aceptación con herramientas independientes. | Recibos, resultados y correspondencia con el artefacto congelado. |
| Integrator | Preparar la entrega aceptada. | Artefacto final, veredicto y resumen derivado del ledger. |

**ROLE-01.** El grafo aprobado define dependencias reales. La salida de cada nodo se valida contra su contrato antes de habilitar consumidores.

**ROLE-02.** Cada traspaso incluye contenido necesario, referencias, hashes, estado de validación y presupuesto. Si no cabe, se produce un resumen verificable que conserva criterios y referencias, o se detiene el paso. No basta con entregar un digest.

**ROLE-03.** Los mandatos versionados de rol se utilizan realmente en la construcción del prompt. No basta con que existan archivos de perfiles.

**ROLE-04.** El contenido de otro rol se trata como datos; no hereda autoridad del controlador.

**ROLE-05.** El grafo inicial es serial respecto de la inferencia. Las tareas de sistema que no infieren pueden ejecutarse según sus propios permisos y límites.

Se reutilizará como referencia el traspaso de evidencia de V4.2, que revalida contenido y hash. El contrato de V5 requiere ampliar su validación de respuestas más allá de comprobar que aparece el nombre del rol. Fuentes: E04, E06 y E20.

## 8 Loops y autoprompts

**LOOP-01.** Un loop parte de un objetivo aceptado y conserva su identidad. Cada iteración tiene una hipótesis o criterio concreto, evidencia de entrada, acción permitida y condición de parada.

**LOOP-02.** Un autoprompt se construye con plantilla versionada, objetivo, hechos verificados, fallos observados, presupuesto y skills aprobadas. Se conserva su digest y la procedencia de cada componente para explicar decisiones.

**LOOP-03.** La generación de un autoprompt consume presupuesto si usa un modelo. No se coloca un metaplanificador fuera del contador.

**LOOP-04.** El loop termina por éxito verificado, agotamiento, cancelación, permiso insuficiente, resultado desconocido o ausencia de progreso según el criterio fijado para la tarea.

**LOOP-05.** Repetir el mismo candidato sin evidencia nueva no se considera progreso. La aplicación detecta repeticiones y evita ciclos de autoaprobación entre roles.

**LOOP-06.** Cambiar de rol, sesión, framework o modelo no abre otro presupuesto. Las llamadas de reparación y los reintentos de transporte admitidos quedan registrados.

**LOOP-07.** Una propuesta de ampliar el objetivo se presenta al usuario. No se incorpora como nueva tarea ejecutable por aparecer en una respuesta del modelo.

La calidad de uno, tres y siete roles se comparará sobre las mismas tareas y criterios. Siete roles no constituyen una promesa de superioridad.

## 9 Memoria y skills

### 9.1 Memoria

Cada entrada tendrá proyecto, ámbito, contenido, fuente, digest, fechas, revisión, estado de validación y política de caducidad. La recuperación debe justificar relevancia y citar la fuente.

Las escrituras serán atómicas y coordinadas entre hilos y procesos participantes. Se conservarán versiones para resolver conflictos; el bloqueo no decide cuál de dos afirmaciones contradictorias es verdadera.

La selección tendrá presupuesto por perfil. Las omisiones se registrarán para que un criterio obligatorio no desaparezca silenciosamente. Los datos de otro proyecto requieren un permiso de compartición explícito.

La curación de datos de un proyecto será trabajo autorizado dentro de un intento y sus cuotas; se detiene al agotarlas y comparte la admisión global. No existe un loop de fondo con presupuesto implícito. Su eventual funcionamiento entre mandatos queda fuera del piloto hasta definir una política específica. No borrará evidencia primaria ni convertirá resúmenes generados en hechos verificados.

### 9.2 Skills

El ciclo propuesto es `CANDIDATE -> QUARANTINED -> EVALUATED -> APPROVED -> AVAILABLE`, con `REJECTED` y `REVOKED` como salidas. Cada versión es inmutable.

La promoción exige procedencia y licencia, análisis de capacidades, casos de evaluación independientes y aprobación para un alcance. Una lista de substrings prohibidos no certifica seguridad o utilidad.

Una skill no instala dependencias, ejecuta comandos ni comparte datos por el mero hecho de ser leída. Sus herramientas deben estar registradas y admitidas separadamente. Cambiar una skill invalida su evaluación anterior.

Los módulos de memoria, cuarentena y promoción del legado son material reutilizable, pero su conexión al director y su beneficio siguen pendientes. Fuentes: E17, E18, E19 y E20.

## 10 Evidencia y observabilidad

Cada evento incluye esquema, dominio, proyecto, ejecución, intento, actor técnico, operación, revisión, secuencia confirmada, timestamps, resultado, referencias y digest del evento anterior. La secuencia y las relaciones de solicitud/recibo establecen el orden parcial; un reloj de pared entre procesos no demuestra por sí solo precedencia causal. Los logs públicos o exportados pasan por una política de minimización y redacción; el contenido bruto queda local por defecto. El acceso, conservación y borrado de esos registros privados requieren una política explícita; estar en disco local no garantiza confidencialidad.

Las métricas distinguen solicitudes admitidas, respuestas completadas, tokens informados por el proveedor, estimaciones, tiempo por fase, RAM y resultados de aceptación. Los valores desconocidos se muestran como desconocidos. Coste monetario, independencia del verificador y cobertura global no se deducen de un hash.

Los modos de simulación y backend real quedan separados en interfaz, recibos y almacenamiento. Un resultado simulado no incrementa versiones verificadas de una ejecución real.

La telemetría remota no forma parte del piloto. Cualquier incorporación posterior deberá especificar datos, destino, finalidad y control del usuario.

## 11 Secuencia de implementación propuesta

| Orden | Cambio futuro | Dependencia para avanzar |
| --- | --- | --- |
| I1 | Identificar puntos de entrada y reparar rutas de empaquetado de Gates B/C. | Comprobación nativa de instalación sin inferencia. |
| I2 | Integrar autoridad, reserva de intentos, revisiones e idempotencia. | Casos A01 a A22 del contrato. |
| I3 | Resolver modelo, configuración efectiva y transporte autenticado. | Matriz de protocolo y perfil CPU calificados. |
| I4 | Conectar herramientas acotadas y recibos. | Pruebas de alcance y recuperación de efectos. |
| I5 | Conectar contenido entre roles y verificación independiente. | Artefacto reproducible y veredicto ligado al digest. |
| I6 | Completar un ciclo de web-auditor. | Resultado útil, parada y reanudación probadas. |
| I7 | Medir variantes de roles e integrar memoria y skills. | Beneficio demostrado sobre baseline; sin degradar límites. |
| I8 | Preparar instalador y selección guiada de modelos. | Revisión de distribución y recorrido en máquina limpia. |

Los Gates A a E son evidencias con alcance definido: A autoridad; B perfil del modelo; C ruta efectiva; D exclusión y cancelación con clientes reales; E admisión de un proyecto concreto. Un gate documental no satisface una comprobación dinámica.

## 12 Matriz de aceptación

Todos los casos están **pendientes**. Esta tabla no es un informe de pruebas ejecutadas.

| Caso | Escenario | Resultado exigido |
| --- | --- | --- |
| I01 | Instalación en Windows limpio con rutas que contienen espacios. | Componentes localizados sin editar scripts; desinstalación no borra proyectos. |
| I02 | Modelo ausente o incompatible con herramientas. | Asistente útil y bloqueo del perfil completo; sin falsas capacidades. |
| I03 | Alias de modelo cambia de digest entre admisión y ejecución. | Petición detenida; capacidad y calificación anteriores invalidadas. |
| I04 | OpenCode tiene capas de configuración contradictorias. | Configuración efectiva identificada y conflicto resuelto antes de inferir. |
| I05 | Cliente envía modelo, cabecera o campo no autorizado. | Rechazo previo a la llamada al proveedor. |
| I06 | Un resultado de herramienta se transmite entre roles. | El siguiente rol recibe contenido acotado y procedencia, con hash revalidado. |
| I07 | El implementador declara que una prueba pasa, sin ejecutarla. | No se acepta el artefacto ni aumenta el contador verificado. |
| I08 | Dos clientes solicitan inferencia simultánea. | Una inferencia administrada; espera o rechazo explícito para la otra. |
| I09 | Cancelación durante carga, prefill, generación y streaming. | Estado y lease coherentes; sin liberar por una mera desconexión. |
| I10 | Caída después de una herramienta con efecto no idempotente. | Reconciliación por recibo; no repetición automática ciega. |
| I11 | Autoprompt solicita permisos extra o cambia el destino de una entrega. | No adquiere autoridad; decisión del usuario si procede. |
| I12 | Skill intenta leer fuera del proyecto o instalar una dependencia. | Acción bloqueada por el ejecutor, aunque el modelo la solicite. |
| I13 | Memoria contiene información de otro proyecto o evidencia caducada. | Aislamiento y política de vigencia aplicados. |
| I14 | Un resumen omite un criterio obligatorio para caber en contexto. | Omisión detectada; no continúa como si el criterio se hubiese satisfecho. |
| I15 | Reanudar una tarea tras reiniciar UI y controlador. | Identidades, objetivos y contadores conservados; estado reconciliado. |
| I16 | Comparación de uno, tres y siete roles. | Mismas tareas y criterios, con resultados, latencia y consumo comparables. |
| I17 | Exportación de diagnóstico y paquete de publicación. | Sin tokens, conversaciones, rutas personales o artefactos no autorizados. |
| I18 | Primer usuario completa el recorrido previsto. | Descarga, selección de modelo, tarea y evidencia sin configuración manual oculta. |
| I19 | Dos entradas efectivas distintas producen la misma proyección redactada. | Recibos privados distintos; la proyección no se usa para deduplicar ni acreditar argumentos efectivos. |
| I20 | Junction o enlace cambia entre validar y usar una ruta; prefijos vecinos y salida fuera del workspace. | Operación ligada a la identidad autorizada o denegada; ninguna escritura fuera de alcance. |
| I21 | Calibración, curación y un intento compiten por inferencia. | Una inferencia global; sondas sin datos de proyecto y curación con intento reservado. |
| I22 | Reloj retrocede o proceso reinicia durante espera/cancelación. | No aumenta el presupuesto; saldo desconocido bloquea nueva ejecución y permite reconciliar. |
| I23 | El destino cambia después de verificar el candidato. | Integración rechazada por revisión; no se publica un resultado distinto usando el veredicto anterior. |

## 13 Límite de esta entrega

V5.1 documental fija el diseño y permite revisar cambios futuros. No inicia un servidor, importa bases, cambia rutas, crea modelos ni ejecuta estas pruebas. La siguiente autorización de implementación deberá identificar los cambios y conservar la referencia auditada del legado.
