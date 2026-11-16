# Auditoría V5.4.1: de una colección de piezas a un recorrido fiable

**Base:** [1c622031](https://github.com/ymkaddur/neural-office/tree/1c622031ccdec1bf5b8724808af2fed44f0ee960). Consulta y experimentos: 16 de noviembre de 2026. Núcleo corregido: **5.3.1**; interfaz conservada: **V5.4.1**, sin conexión al motor. El commit que contiene este informe fija el diff completo. [Evidencia estructurada](evidence/V5_4_1_FORENSIC.json) · [Frontera de confianza](../SECURITY.md).

## Fase 0 y alcance

**OBSERVADO:** hay un piloto Python operativo y una interfaz que representa ejemplos fijos. El contrato de escritorio valida mensajes pero declara que no implementa transporte, autorización ni replay: [desktop_contract.py:1](../neural_office/desktop_contract.py#L1). La integración pendiente es conocida; no constituye por sí misma una vulnerabilidad.

**Problema:** bajo interrupción de la protección inicial o recuperación concurrente con el arranque, el piloto puede bloquear una continuidad legítima o liberar la reserva antes de que un controlador vivo deje de poder crear procesos, en lugar de preservar un único propietario y una recuperación repetible. Las entradas explícitamente excluidas de red también deben rechazarse antes de una operación de resolución.

Se inspeccionaron autoridad, continuidad, procesos, rutas, importación histórica, HTTP local, reporte, CLI/UI y contrato de escritorio; se hicieron experimentos sintéticos en estado temporal. Tres revisores cubrieron autoridad, fronteras y referencias, con revisión cruzada posterior. No se ejecutaron modelos, no se modificó el estado personal y no se atacaron servicios de terceros. La investigación no cubre toda instalación histórica ni los binarios internos de Ollama.

**VERIFICADO:** se encontraron tres defectos concretos. **No se demostraron tres vulnerabilidades graves.** Su gravedad no se deduce de una cuota solicitada ni de una probabilidad intuitiva. Dos afectan principalmente disponibilidad/continuidad; el tercero incumple el orden de un rechazo de seguridad, con consecuencias de red todavía no demostradas.

## Diario de laboratorio y modelos causales

### F1 · Recuperación durante un arranque todavía vivo

**Firma observada:** el primer controlador adquiere lease y se pausa antes de construir el backend; `recover` devuelve `FAILED`; un segundo intento adquiere la reserva; el primero continúa y crea procesos propios con una reserva que ya no le pertenece. La traza sintética registró `old_job_active=2`, `second_lease=true` y finalmente `STALE_LEASE` en el primero. Los dos procesos pertenecen a la fixture de Job; no equivalen a dos inferencias ni prueban memoria de dos modelos.

**Modelos rankeados** — puntuación ordinal de priorización, no probabilidad estadística:

| Modelo | Prioridad inicial (plausibilidad × impacto, 1–3) | Predicción / discriminante | Resultado |
| --- | --- | --- | --- |
| No hay dueño vivo que abarque acquire→constructor→start | 3 × 3 | Pausar en el constructor y recuperar permite liberar lease antes del lanzamiento | VERIFICADO |
| La reserva admite dos llamadas concurrentes válidas | 2 × 3 | El controlador viejo consigue admitir otra inferencia | Refutado en la reproducción: `start_call` rechaza generación vieja |
| La salida se explica solo por terminación lenta de un proceso existente | 1 × 2 | Haría falta un Job activo antes de recuperar | Refutado: aún no había Job; el dueño vivo podía crearlo después |

**Cadena causal:** lease durable → constructor pendiente → `Job.active()==0` o Job inexistente → recuperación interpreta ausencia actual como ausencia de un futuro lanzamiento → reserva liberada → controlador antiguo crea procesos. El primer error es usar una observación de procesos como prueba suficiente de que no existe un controlador vivo. [Base runner:46–73](https://github.com/ymkaddur/neural-office/blob/1c622031ccdec1bf5b8724808af2fed44f0ee960/neural_office/runner.py#L46-L73), [base recover:107–117](https://github.com/ymkaddur/neural-office/blob/1c622031ccdec1bf5b8724808af2fed44f0ee960/neural_office/runner.py#L107-L117).

**Corrección mínima:** propietario de ejecución mediante mutex Windows por ledger, retenido desde antes de adquirir lease hasta cierre/finalización. `run`, recuperación y restauración participan; el mutex de continuidad sigue separado para permitir cancelar y consultar. Un dueño muerto permite recuperación, pero aún debe comprobarse el Job. [run_guard](../neural_office/continuity.py#L30), [runner](../neural_office/runner.py#L40), [restore](../neural_office/continuity.py#L210).

**Ataque adversarial a nuestra primera corrección:** el bloqueo también impedía reproducir una respuesta terminal mientras otro intento ejecutaba. La revisión independiente lo reprodujo y se corrigió antes de publicar: leer un terminal no adquiere propiedad de ejecución; el no terminal se relee dentro del bloqueo. Además, Windows posee el mutex por hilo y permite reentrada: `Context().run` podía saltar el primer control basado en ContextVar. Se sustituyó por estado del hilo y se probó ese contraejemplo. No había un caller de producción que usara esa ruta; no se presenta como exploit remoto.

**Verificación:** barrera en el constructor; rechazo de recuperación, restore y segundo runner sin cambiar estado/cuota; cancelación disponible; fallo del constructor; replay terminal concurrente; muerte real del propietario con un handle retenido al mutex abandonado. [Regresiones](../tests/test_forensic_authority.py#L26).

**Impacto:** prioridad alta de fiabilidad antes de integrar escritorio; fallo operacional condicionado a recuperación concurrente. No se demostró escalada de privilegios, ejecución remota ni doble inferencia. Refutaría el diagnóstico que el controlador original no pudiera crear procesos después de la recuperación en la reproducción de la base.

### F2 · Primera protección interrumpida deja una puerta sin reintento

**Firma observada:** interrupción después de sellar pero antes del primer commit deja primaria esquema 1 y testigo vacío. La siguiente protección entra por «el archivo existe» y falla con `CONTINUITY_UPGRADE_REQUIRED_RUN_PROTECT`. Repetir la operación no completa la protección.

| Modelo | Prioridad inicial | Predicción / discriminante | Resultado |
| --- | --- | --- | --- |
| Existencia de archivo se confunde con enrollment confirmado | 3 × 3 | Rollback conserva archivo vacío y fuerza la ruta equivocada | VERIFICADO |
| Cuota o cadena de eventos ya corrupta | 2 × 3 | El fallo exige alterar historia | Refutado: historia sintética íntegra y consumo conservado |
| Solo es un bloqueo temporal de SQLite | 1 × 2 | Cerrar proceso/conexión permite reintentar en la base | Refutado: persiste la clasificación errónea del testigo |

**Cadena causal:** crear archivo del testigo fuera de la transacción → preparar enrollment → caída/rollback → archivo persiste pero identidad no → siguiente llamada asume protección existente. [Base protect:109–154](https://github.com/ymkaddur/neural-office/blob/1c622031ccdec1bf5b8724808af2fed44f0ee960/neural_office/continuity.py#L109-L154).

**Corrección:** permitir reintento exclusivamente para primaria esquema 1 y testigo sin identidad, versión ni tablas, después de que SQLite pueda recuperar sus journals y bajo transacción. Un testigo válido nunca se borra o sustituye. Esquema 2 con testigo ausente/vacío sigue rechazado. [protect](../neural_office/continuity.py#L128).

**Verificación:** rollback antes de commit; salida real del proceso dejando journals; commit confirmado seguido de excepción que simula pérdida del acuse; primaria antigua con testigo válido; esquema 2 sin testigo válido. [Cinco regresiones de enrollment](../tests/test_forensic_authority.py#L165). Una caída eléctrica del dispositivo físico no se simuló.

**Impacto:** prioridad alta de continuidad para inicialización/migración, sin pérdida de datos ni privilegios demostrada. No es prueba de resistencia a un administrador que sustituya juntos primaria y testigos. Refutaría el modelo un reintento exitoso de la base con el mismo par esquema1/testigo vacío.

### F3 · Resolver una fuente de red antes de rechazarla

**Firma observada:** cinco escenarios de entrada alcanzan el resolver antes del rechazo; la sonda falla con `RESOLUTION_BEFORE_DENIAL`. Incluye captura, puntos de entrada históricos y ubicación remota dentro de un manifiesto local.

| Modelo | Prioridad inicial | Predicción / discriminante | Resultado |
| --- | --- | --- | --- |
| El rechazo UNC llega después de `Path.resolve` | 3 × 2 | Sonda del resolver se ejecuta antes de `Denied` | VERIFICADO |
| La comprobación es puramente léxica y no toca filesystem | 2 × 2 | Construir `Path` y resolver serían equivalentes | Refutado por el orden/API: la construcción léxica no invoca `resolve` |
| Ya se ha demostrado fuga de credenciales | 1 × 3 | Haría falta traza de red/autenticación real | No demostrada; no se realizó esa prueba |

**Cadena:** ruta explícita UNC → resolución del filesystem → rechazo de red. [Base files:12–16](https://github.com/ymkaddur/neural-office/blob/1c622031ccdec1bf5b8724808af2fed44f0ee960/neural_office/files.py#L12-L16). La selección Tkinter resolvía también antes de llamar a la captura: [base ui:68](https://github.com/ymkaddur/neural-office/blob/1c622031ccdec1bf5b8724808af2fed44f0ee960/neural_office/ui.py#L68).

**Corrección:** rechazo léxico de UNC/namespaces de dispositivo antes de cualquier resolución en las entradas afectadas. La captura revisa ambos argumentos antes de resolver cualquiera. Se conservan comprobaciones de ruta resuelta e identidad del handle abierto. [files](../neural_office/files.py#L9), [legacy](../neural_office/legacy.py#L56), [regresiones](../tests/test_forensic_paths.py#L16).

**Verificación:** cinco reproducciones fallaban antes y pasan después; cinco tests públicos cubren variantes de barra/namespace, manifiesto remoto, argumentos de captura y conservación de rutas locales con Unicode. No se envió una petición SMB/DNS ni se usaron credenciales reales.

**Impacto:** defecto de orden de una barrera de seguridad, prioridad media/contextual. El posible acceso SMB o autenticación depende del entorno y queda **DESCONOCIDO**. No se certifican junctions, unidades mapeadas ni comportamiento del selector nativo. Refutaría el diagnóstico que la base rechazase la ruta antes de la sonda de resolución.

## Contraevidencia y candidatos que no convertimos en vulnerabilidades

- **OBSERVADO:** un servidor HTTP sintético en loopback entregó una respuesta válida en 6,500 s con timeout de socket 5 s. Eso no viola por sí solo un timeout de inactividad. [La prueba existente](../tests/test_v53_startup_scenarios.py#L57) y los informes V5.3 ya distinguían ventana de reintentos y deadline total. No se modificaron los timeouts ni se declaró resuelto R13.
- **VERIFICADO EN CÓDIGO:** el servidor Ollama propio escucha loopback y se comprueba la pertenencia a un Windows Job. Esto no autentica clientes ni aísla disco/red. Es un límite declarado del piloto, no una nueva prueba de bypass remoto. [Contrato histórico](V5_2_AUTHORITY_AND_COUNTERS.md).
- **OBSERVADO:** `npm audit` devolvió cero avisos conocidos para el lock consultado. No acredita seguridad del código ni descubre carreras. Las dependencias de ejecución no cambiaron.
- **OBSERVADO:** una fixture del backend afirmó «no hay hallazgos» cuando existían cuatro; el estado fue `ACCEPTED` y el comentario siguió marcado `UNVERIFIED_ASSISTANCE`. El comprobador hace lo que declara: verifica consistencia e integridad, no verdad semántica. [make_report/verify_report](../neural_office/audit.py#L59), [finalize](../neural_office/ledger.py#L367). Una comparación basada solo en `ACCEPTED` no demostraría utilidad de siete roles.
- **INSPECCIÓN LIMITADA:** no se promovieron a hallazgo shell injection, ejecución de HTML ni incorporación directa del HTML al prompt: el código inspeccionado usa argumentos de proceso, parser y hallazgos acotados. Esto no prueba ausencia de todas las vulnerabilidades posibles.

## Qué hemos hecho mal más allá de estos defectos

| Estado de evidencia | Error o carencia | Qué cambia la decisión |
| --- | --- | --- |
| VERIFICADO | La primera revisión verde no cubría las ventanas acquire→constructor ni archivo de testigo→commit | Invariantes y puntos de interrupción antes de contar tests |
| VERIFICADO | Nuestro primer parche de ownership rompió replay terminal; una variable de contexto no correspondía al dueño de un mutex por hilo | Revisión independiente del fix y prueba diferencial del comportamiento correcto previo |
| VERIFICADO | README conservaba «12 tests» tras entregar 18; CLI/ventana seguían mostrando etiquetas antiguas | Resultados fechados en evidencia; versión del núcleo única y descarga de la revisión corregida |
| VERIFICADO | Interfaz, protocolo de forma y piloto siguen separados | No declarar completada una tarea hasta observar la misma identidad/entrada/resultado a través de todas las capas |
| VERIFICADO | El informe se genera y recomputa con el mismo checker | Mantener la afirmación de integridad; evaluar utilidad con corpus y rúbrica externos al generador |
| OBSERVADO | Cada conexión valida una firma del contenido completo | Medir coste según historia; no resolver la lentitud quitando continuidad sin una sustitución probada |
| INFERIDO | Refinamos pantallas y planes más deprisa que el recorrido que debía hacerlos creíbles | Priorizar un encargo que se complete, cierre y recupere sobre otra capa de presentación |
| INFERIDO | «90 % de confianza» y muchos tests pueden sonar a una garantía que no existe | Dar alcance, contraejemplos y puertas de salida; el porcentaje subjetivo no reemplaza cobertura |
| DESCONOCIDO | Que nuestra estética, siete roles o promesa de oficina produzcan preferencia real | Pruebas formativas con personas y comparación de utilidad/coste; no opiniones de otros modelos como sustituto |

**Responsabilidad de esta revisión:** haber explicitado límites era correcto, pero no bastaba para descubrir las ventanas de fallo. Añadir más protocolo escrito sin experimentos discriminantes habría mantenido el problema. Tampoco sería correcto llamar «críticas» a tres observaciones para satisfacer una expectativa.

## Idempotencia: qué existe y qué falta

| Frontera | Evidencia actual | Puerta pendiente |
| --- | --- | --- |
| Reserva del intento | Clave ligada al contenido y transacción; pruebas existentes de replay/conflicto | Pérdida de respuesta del futuro transporte después del commit, reinicio y consulta por la misma clave |
| Llamada al modelo | Recibo durable, generación y respuesta; resultado incierto bloquea repetición | No prometer exactamente una vez para una inferencia cuyo resultado se perdió |
| Propietario del proceso | Esta revisión cubre controlador vivo, abandono y recuperación | Integrar el host manteniendo esa propiedad; no permitir que una confirmación visual certifique terminación real |
| Enrollment/restore | Reintento de enrollment y testigo conservado; recuperación sin reembolso | Mantener la política ante actualizaciones, instalación real y fallos físicos no simulados |
| UI | Estado de fixtures y controles de interacción | Concesiones reales, secuencia durable, snapshot al detectar hueco y reconexión |
| Efectos externos | No existen herramientas de escritura/envío en este piloto | Definir recibo, consulta/reconciliación y ambigüedad antes de añadirlos; no prometer undo universal |

Fuente de implementación: [ledger reserve/start_call](../neural_office/ledger.py#L181). Diseño pendiente: [contrato de escritorio](V5_3_DESKTOP_CONTRACT.md#L41). La UI debe representar la autoridad, no volver a implementarla como otro contador.

## Qué aprender de cuatro referentes

**VERIFICADO EN FUENTES, NO EN EJECUCIÓN:** se inspeccionaron los mecanismos enlazados. No se corrieron sus productos ni suites, no se comparó RAM/velocidad ni se auditó todo su código. Claude se contrasta con documentación pública, no con código interno. No se copió implementación ni material visual.

| Referente y fuente fijada | Qué hace con precisión | Qué debemos adoptar | Límite de la comparación |
| --- | --- | --- | --- |
| [T3 Code, EventSink](https://github.com/pingdotgg/t3code/blob/6e650b384906ffa1dd28645a68d5295c06a18af9/apps/server/src/orchestration-v2/EventSink.ts#L820-L862) | Recibos, eventos y efectos pendientes coordinados transaccionalmente; publicación posterior. [Prueba la carrera de commandId](https://github.com/pingdotgg/t3code/blob/6e650b384906ffa1dd28645a68d5295c06a18af9/apps/server/src/orchestration-v2/Orchestrator.receipt-race.test.ts#L69-L111) | Probar commit→respuesta perdida→retry, y pertenencia de la petición | No copiar su volumen de abstracciones ni inferir exactamente una vez para efectos externos |
| [Claude Code: sandbox](https://code.claude.com/docs/en/sandboxing), [checkpoints](https://code.claude.com/docs/en/checkpointing) | Distingue permiso, aislamiento y alcance de recuperación | Declarar qué capa impide cada acción y qué se puede deshacer | Sandbox shell optativo y sin Windows nativo según documentación consultada; MCP/hooks y muchos efectos no quedan cubiertos por él/checkpoints |
| [OpenClaw: wrapper idempotente](https://github.com/openclaw/openclaw/blob/bd25e9ef60cc886dc6c0512927bf1cf425e364df/src/gateway/server-methods/session-create-idempotency.ts#L32-L121), [frontera](https://docs.openclaw.ai/gateway/security/trust-model) | Liga identidad, petición y permisos; diferencia operador confiable de adversarios compartiendo host | Fijar amenaza y ámbito de la clave antes de implementar retry | El wrapper inspeccionado usa WeakMap en memoria; no prueba durabilidad tras reinicio |
| [Dusk: contrato](https://github.com/DuskBotAI/duskbot/blob/750caf446d0417b95971e7bb2c7ac98ba76f94e0/docs/runtime-contract.md#L11-L47), [invariantes](https://github.com/DuskBotAI/duskbot/blob/750caf446d0417b95971e7bb2c7ac98ba76f94e0/server/runtime/invariants.ts#L37-L123) | Dueño explícito, estado/evento transaccionales y condiciones comprobables de reinicio | Una única autoridad por transición y coherencia después de cada operación | Su [política de reinicio](https://github.com/DuskBotAI/duskbot/blob/750caf446d0417b95971e7bb2c7ac98ba76f94e0/docs/runtime-contract.md#L70-L85) depende del conocimiento de efectos del host; no es exactly-once universal |

**INFERIDO:** la lección útil es coherencia entre intención, acción y resultado, no copiar un tema oscuro. Tampoco se ha demostrado que ellos hagan «todo mejor». Neural Office reduce superficie al no ejecutar el HTML ni dar herramientas al modelo; es una ventaja de alcance, no superioridad general de seguridad. Dusk ya tiene controles y trazabilidad; no podemos atribuirnos su exclusividad.

## Consumo: el problema que no arregla cambiar de framework

**OBSERVADO:** la conexión del ledger recalcula la firma lógica completa: [signature/validate](../neural_office/continuity.py#L75). En cuatro estados sintéticos con 0/8/32/64 intentos y snapshots de aproximadamente 240 KB, cinco muestras por estado pasaron de una mediana de **1,46 ms a 122,80 ms** entre una primaria de 90.112 bytes y otra de 15.556.608 bytes. El observador de cancelación vuelve a consultar tras cada espera de 100 ms: [runner](../neural_office/runner.py#L68).

**INFERIDO:** el coste crece con la historia y puede retrasar observación/cancelación. No se midió aquí CPU porcentual, RAM pico, latencia completa de parada ni un DoS remoto. No quitamos esa validación: sustituirla exige demostrar que no rompe continuidad. El experimento de escala usa filas sintéticas insertadas bajo transacción, no 64 sesiones reales ni una medición de usuarios.

La interfaz no cambió sus assets ni dependencias en esta auditoría. Su heap de muestras cortas sigue sin equivaler a RAM total. La próxima optimización necesita trazas del proceso real y una tarea útil equivalente; no un nuevo número de roles o un framework elegido por su tamaño anunciado.

## Herramientas y secuencia de trabajo

| Cuándo | Herramienta | Pregunta que debe resolver |
| --- | --- | --- |
| Usadas aquí | unittest, tests Node, barreras, subprocesos y SQLite temporales | ¿La ventana causal falla antes y conserva el invariante después? |
| Usada aquí | npm audit sobre lock existente | ¿Hay avisos conocidos en esa consulta? No valida lógica ni recuperación |
| Siguiente, si aporta minimización | [Hypothesis stateful](https://hypothesis.readthedocs.io/en/latest/stateful.html) | ¿Qué secuencia mínima de reservar/cancelar/restaurar/reintentar rompe el modelo? No se añadió como dependencia |
| Antes de ampliar superficie | [CodeQL](https://docs.github.com/en/code-security/concepts/code-scanning/code-scanning-alerts) | ¿Aparece una ruta estática de riesgo que merezca reproducción? No sustituye la prueba causal; no se activó aquí |
| Antes de prometer eficiencia del escritorio | [WPR/WPA](https://learn.microsoft.com/en-us/windows/apps/develop/performance/profiling-tools) | ¿Qué proceso, pila y fase consumen CPU/memoria realmente? Conservar trazas privadas y publicar solo resultados depurados |

Se crearon dos skills: [auditoría forense](../skills/neural-office-forensic-audit/SKILL.md) y [revisión de evidencias](../skills/neural-office-evidence-review/SKILL.md). Pasaron validación de estructura y un ejercicio independiente de decisiones con evidencia insuficiente. Ese ejercicio no demuestra descubrimiento automático de cualquier fallo. Son instrucciones para desarrollo/auditoría, no un sistema de skills ya conectado al producto.

## Identidad y progreso hasta V6

**HIPÓTESIS de identidad:** «Tu trabajo local, con fuentes y continuidad». Un Director recibe un encargo acotado, devuelve una entrega revisable y permite detener/cerrar/retomar sin perder el origen ni repetir a escondidas. No se anuncia como algo único en el mercado hasta validarlo con personas.

| Puerta, en orden | Entrega demostrable | Qué se pospone o elimina del camino crítico |
| --- | --- | --- |
| Auditoría actual | Fallos reproducidos corregidos, frontera explícita y regresiones | Añadir roles, red, memoria o cambios estéticos para aparentar avance |
| Aceptación V5.4.1 | Una persona ajena al desarrollo encuentra objetivo, fuentes, resultado y parada; feedback registrado | Puntuar la calidad solo con modelos o número de referencias |
| V5.5: un recorrido real | Elegir HTML/modelo → autorizar → ejecutar → detener o recibir informe → cerrar/abrir → recuperar la misma identidad/cuota | Nuevas herramientas con efectos y nuevas definiciones de autoridad en frontend |
| V5.6–5.8: utilidad y coste | Corpus con expectativas externas; comparar un rol y varios; reducir trabajo sin perder utilidad; medir host/core/modelo | Siete roles por defecto como señal de calidad; más loops sin ganancia medida |
| V5.9: fallos y uso | Muerte/reinicio, respuesta perdida, restauración, sesiones largas, accesibilidad y usuarios; R13 resuelto o contenido | Proclamar estabilidad por unos segundos de heap o CI verde |
| V6: dos trabajos acotados | HTML y síntesis de TXT/Markdown seleccionados, con fuentes, resultados, límites y continuidad verificables | Oficina generalista, distribución universal o privacidad absoluta |

Purgar significa retirar afirmaciones y opciones sin evidencia del recorrido principal, reconciliar estados y dejar de duplicar contadores manuales. No significa borrar historia, backups o reescribir módulos. El [roadmap general](../ROADMAP.md) conserva V7–V10 como visión, no como capacidades adquiridas.

## Verificación, duda residual y confianza

**VERIFICADO localmente:** base de 125 pruebas Python verde; revisión completa de 140 pruebas verde, incluidas 15 nuevas; 18 pruebas frontend y build verde. La versión de mantenimiento se verifica además por el launcher; la publicación debe comprobar CI del commit final. El JSON conserva comandos, alcance y resultados. Los tests nuevos usan procesos sintéticos y estado temporal, no un modelo real.

El [reproductor público](../tests/repro_v541_boundaries.py) se ejecutó contra la base y la corrección. En `baseline`, salida 0 significa que reprodujo las firmas antiguas; en `fixed`, que confirmó las tres propiedades corregidas. Utiliza únicamente archivos temporales y procesos sintéticos. Para repetir desde esta revisión en Windows:

```powershell
git worktree add --detach ..\neural-office-audit-base 1c622031ccdec1bf5b8724808af2fed44f0ee960
py -3.12 -B tests/repro_v541_boundaries.py --repo ..\neural-office-audit-base --expect baseline
py -3.12 -B tests/repro_v541_boundaries.py --repo . --expect fixed
```

**Error de nuestra instrumentación, corregido:** la primera versión de ese reproductor dejaba abierta una conexión SQLite y fallaba al limpiar su carpeta temporal en Windows. Se usó cierre explícito y se repitieron ambos modos con éxito. No se atribuyó ese fallo de la fixture al motor ni se silenció la excepción. CI incluye el modo `fixed`.

**DESCONOCIDO:** aceptación humana, rendimiento comparado de productos, aislamiento de otras cuentas/sesiones Windows, efectos de junctions/unidades mapeadas, fallos físicos del almacenamiento, CPU/RAM/GPU del futuro escritorio, calidad de modelos en corpus independiente y exclusividad de mercado. Los locks requieren controladores cooperantes de esta revisión: cerrar controladores antiguos antes de usar el núcleo corregido. No se repara automáticamente ningún estado personal.

**Confianza de ingeniería: 95 % en los tres mecanismos reproducidos y sus correcciones acotadas**, valoración subjetiva, no probabilidad de que el producto esté libre de errores. Asunción crítica: aplicación personal Windows con estado y controladores cooperantes; no extrapolarlo a un adversario con control de programa/disco ni a la futura integración. La explicación de la sensación de fragilidad tiene confianza media y necesita prueba de usuarios.

**Siguiente acción concreta:** cerrar la aceptación de las cinco pantallas y ejecutar después una prueba vertical de un solo encargo con pérdida de respuesta, cierre/reinicio y conservación de identidad/cuota. Antes de extenderla, medir la validación del ledger dentro de la latencia de cancelación. Ninguna conexión del nuevo frontend se activa en esta entrega.
