# Evidencia y límites de transferencia

Investigación consultada el 16–17 de noviembre de 2026. Los mecanismos externos se inspeccionaron en los archivos enlazados; no se ejecutaron sus repositorios. Las aplicaciones propuestas a Neural Office requieren prueba propia. Las licencias se indican para evitar confundir observación con permiso de copia.

## Lección aplicada al proyecto

VERIFICADO en la investigación V5.5: se reprodujeron tres defectos de integración con cambios de orden o entradas legales; no eran tres vulnerabilidades graves. Los localizadores siguientes corresponden a los archivos de la entrega V5.5 y deben cotejarse con el commit que se esté revisando:

| Mecanismo reproducido | Localizador de regresión | Observación discriminante |
|---|---|---|
| Publicar estado terminal disparaba cleanup antes de conciliar historial | `desktop/src/connected/adversarial.test.ts:44`, test `terminal polling reconciles saved history…` | Eventos inmediatos pasaban; diferidos dejaban historial «trabajando» con vista principal detenida. |
| Sustituir snapshot al avanzar intentos borraba la página de proyectos | `desktop/src/connected/adversarial.test.ts:66`, test `paging attempts retains…` | 34 proyectos visibles pasaban a cero; el presupuesto persistido no se reinició. |
| Validación opaca rechazaba proyectos históricos textuales legales | `tests/test_v55_adversarial.py:12,31`; `desktop/src/connected/adversarial.test.ts:95` | ASCII de 65/80 caracteres, Unicode y otros valores admitidos por Ledger fallaban en desktop antes de reservar. |

VERIFICADO en la regresión de cancelación: una parada sobre un Job vacío no impedía una admisión posterior. El parche conserva un latch de parada y cubre bootstrap aún no asignado. Fuente publicada: [tests de cancelación V5.5](https://github.com/ymkaddur/neural-office/blob/278cb51610cebaf0c9ab10a1c201c1e7368c06bf/tests/test_v55_cancellation.py#L81). La prueba no acredita un plazo absoluto frente a un kernel bloqueado ni una inferencia extra: el ledger la denegaba.


## Mecanismos externos

### pingdotgg/t3code

[Archivo en el commit inspeccionado](https://github.com/pingdotgg/t3code/blob/747ed9c5b1d9b2d41638ef94003bda1d996f4353/apps/server/src/orchestration-v2/Orchestrator.receipt-race.test.ts#L69). Líneas 69-111; nivel: `source-inspected`.

OBSERVADO: el test fuerza la llegada concurrente de dos comandos con el mismo commandId y distinto threadId; exige un éxito, un conflicto tipado y que el modelo del thread perdedor no cambie. APLICACIÓN PROPUESTA V5.5: vincular commandId a payload y ámbito, y probar la carrera con barreras deterministas antes de permitir reenvíos desde la UI.

**Límite:** Se inspeccionó un test, no se ejecutó. No acredita por sí solo atomicidad del almacenamiento ni idempotencia de efectos externos. El escenario observado cambia selección de modelo, no realiza una escritura irreversible.

**Licencia observada:** MIT; LICENSE:1-21 verificado en el commit indicado.

### openclaw/openclaw

[Archivo en el commit inspeccionado](https://github.com/openclaw/openclaw/blob/6a6007663b36db8badd6967e7f2bed5c6b3a724e/src/gateway/server-methods/session-create-idempotency.ts#L32). Líneas 32-35,58-75,91-136,139-198; nivel: `source-inspected`.

OBSERVADO: deduplicación por propietario autenticado, hash estable de parámetros, control de role/scopes, coalescencia de inflight y límite de entradas; instala la reserva antes de comenzar el handler. APLICACIÓN PROPUESTA V5.5: rechazar reutilización de clave con payload o autoridad incompatible; no cobrar ni arrancar dos veces por doble clic o reconexión.

**Límite:** El registro reside en WeakMap por contexto; este mecanismo aislado no es durable al reinicio. Las respuestas fallidas liberan la clave: no prueba que sea seguro reintentar si un efecto ocurrió antes del fallo. No ejecutado.

**Licencia observada:** MIT; LICENSE:1-21 verificado en el commit indicado.

### TanStack/query

[Archivo en el commit inspeccionado](https://github.com/TanStack/query/blob/d63a027c26b2489b8be065ad76f638e36216854a/packages/query-core/src/mutation.ts#L239). Líneas 239-268,301-330; nivel: `source-inspected`.

OBSERVADO: continue reanuda un retryer existente o vuelve a ejecutar las variables de una mutación pending restaurada; execute usa retry=0 por defecto y delega serialización a canRun. APLICACIÓN V5.5: tras perder una respuesta, consultar primero el recibo durable mediante la misma clave y oficina; no conectar un resume genérico a attempt.start con una clave nueva. Prueba: confirmar reserva, perder ACK, recargar y comprobar identidad, consumo y número de llamadas.

**Límite:** Inspección de código, sin ejecutar tests. La caché o la serialización por scope no demuestran idempotencia durable del efecto remoto. retry=0 no impide que otra ruta de reanudación vuelva a invocar la mutación.

**Licencia observada:** MIT; LICENSE:1-21 leído en el SHA indicado.

### pmndrs/zustand

[Archivo en el commit inspeccionado](https://github.com/pmndrs/zustand/blob/9fed2eb2f3af672da9f7bf694b996df3831fc207/src/middleware/persist.ts#L250). Líneas 250-259,285-325,340-342; nivel: `source-inspected`.

OBSERVADO: cada hidratación incrementa una generación; los resultados, callbacks y errores atrasados comprueban esa generación; clearStorage también la invalida. APLICACIÓN V5.5: al cambiar de oficina/sesión o descartar una operación pendiente, invalidar lecturas antiguas antes de que restauren estado o aprobaciones. Prueba: dos hidrataciones resueltas en orden inverso y borrado mientras una lectura está pendiente.

**Límite:** La generación evita determinadas carreras de hidratación en esa instancia; no valida el contenido persistido ni concede autoridad. Un store persistido del renderer no debe convertirse en ledger de cuota o recibo de ejecución. No se ejecutó la biblioteca.

**Licencia observada:** MIT; LICENSE:1-21 leído en el SHA indicado.

### vercel/ai

[Archivo en el commit inspeccionado](https://github.com/vercel/ai/blob/3bea041f28e65f371e640d2c70c302776a46387f/packages/ai/src/ui/chat.ts#L1040). Líneas 1040-1082; 1084-1142; nivel: `source-inspected`.

OBSERVADO: detener incrementa una generación, cancela preparación y peticiones, espera finalización y vaciado de trabajos, y pausa la cola; una decisión automática iniciada antes de detener se invalida por generación. PROPUESTA V5.5/V6: Detener debe bloquear tanto trabajo activo como continuación pendiente. Prueba discriminante: retener una decisión automática asíncrona, detener y liberarla después; el contador de nuevas ejecuciones debe seguir en cero.

**Límite:** La semántica observada es del cliente; abortar un stream no demuestra que haya cesado el proceso del modelo. La interfaz debe mostrar detención solicitada hasta confirmación del dueño del proceso. No hay benchmark ni ejecución externa en esta investigación.

**Licencia observada:** Apache-2.0 según LICENSE:1-13; metadato GitHub NOASSERTION, resuelto leyendo el archivo.

### sqlite/sqlite

[Archivo en el commit inspeccionado](https://github.com/sqlite/sqlite/blob/2439a84bbd1304c4b93184da04370f5ce32801c0/src/pager.c#L26). Líneas 26-35,49-85,101-107; nivel: `source-inspected`.

OBSERVADO: el contrato del pager distingue página journalizada y sincronizada de página modificada, ordena sync antes de eliminar journal y especifica invariantes de rollback. APLICACIÓN V5.5: conservar los PRAGMA/modo de journal dentro de la evidencia y probar muerte antes/después del commit con ledger y testigo; una comprobación de integridad posterior no sustituye la prueba de orden de persistencia.

**Límite:** La propia fuente excluye WAL, MEMORY y OFF de esos invariantes; synchronous=OFF cambia la noción de sync del comentario. Se leyó el contrato interno del pager, no se ejecutó SQLite ni se demostró protección frente a almacenamiento que incumple flush. Licencia de src no se extrapola a cada archivo auxiliar del repositorio.

**Licencia observada:** Dominio público para src según LICENSE.md:4-22; GitHub NOASSERTION no se interpretó como MIT.


## Feedback público

### F09: OpenClaw: una salida multimedia representada dos veces

[Fuente pública](https://github.com/openclaw/openclaw/issues/78885). Publicación: 2026-05-07T09:33:46Z. Consulta: 2026-11-17. Localizador: GitHub issue body; Bug Description, Root Cause, Steps to Reproduce.

OBSERVADO: el reporte atribuye duplicación visual a mostrar tanto el mensaje original como la representación multimedia insertada por gateway. Incluye receta y un mecanismo propuesto por el autor.

HIPÓTESIS: identidad estable por resultado y separación entre evento canónico y representación evitan duplicados tras transformación o reconexión.

PENDIENTE: reproducir evento, retransmisión y representación enriquecida del mismo resultado; verificar una salida visible y una contabilización, conservando eventos de auditoría.

**Límite:** Causa declarada por el reportante, no reproducida aquí. Issue cerrado; no afirmar fallo vigente. Este duplicado visual no demuestra una acción externa duplicada.

### F10: Cursor: Stop, trabajo en segundo plano y notificaciones reencoladas

[Fuente pública](https://forum.cursor.com/t/agent-chat-stop-unpredictable-and-broken/171659). Publicación: 2026-09-14T19:28 (hora mostrada por el foro; zona no acreditada). Consulta: 2026-11-17. Localizador: Entradas 1, 9, 12 y 16; especialmente explicación y corrección del 18/09/2026.

OBSERVADO: usuario describe reanudaciones tras Stop. La respuesta de soporte del 18/09 atribuye un caso a notificaciones de trabajo finalizado reencoladas al cancelar; además corrige su consejo anterior porque Stop All no existía en ese layout.

HIPÓTESIS: cancelación durable debe impedir reactivar el trabajo por eventos tardíos; las instrucciones de recuperación deben corresponder a la superficie realmente mostrada.

PENDIENTE: cancelar antes/durante/después de finalizar un hijo, repetir notificación y reiniciar UI; verificar estado terminal monotónico, ninguna llamada adicional y consistencia entre historial y proceso.

**Límite:** Leímos el intercambio público, no los logs internos. No generalizar el diagnóstico a todo Cursor. El formulario dice CLI, pero versión y soporte lo sitúan en panel IDE.


## Método docente

### University of Oxford

[Computer-Aided Formal Verification 2026–2027](https://www.cs.ox.ac.uk/teaching/courses/2026-2027/computeraidedverification/). Computer-Aided Formal Verification, Michaelmas 2026. Nivel: Currículo público detallado; no se inspeccionaron las notas protegidas del curso. Localizador: Secciones Overview, Learning outcomes y Syllabus; extracción web, líneas 22–48. Consulta: 2026-11-16.

OBSERVADO: describe modelos secuenciales y paralelos, propiedades temporales, contraejemplos, verificación acotada, umbrales de completitud y abstracción.

PROPUESTA: modelar iniciar, detener, reintentar y restaurar mediante estados y propiedades explícitas antes de añadir coordinación; distinguir prueba del modelo de ejecución real.

**Comprobación propuesta:** Enumerar intercalaciones acotadas y buscar violaciones de unicidad, autoridad y parada; reproducir cada contraejemplo relevante en el motor.

**Límite:** Se inspeccionó currículo sustantivo, no una demostración aplicada. La abstracción puede omitir condiciones del sistema operativo.
