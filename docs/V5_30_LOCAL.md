# V5.30 · ejecución durable del núcleo local

El encargo de prueba fue revisar el HTML de ejemplo, verificar sus hallazgos y entregar el informe después de poder cerrar y reabrir el proceso en cualquier paso. El último informe conservó los cuatro hallazgos en línea y columna, tres recibos de ejecución y un único intento consumido. El proceso del servicio que usa el escritorio devolvió los mismos recibos y la misma huella de informe que la CLI. Las pruebas y mediciones usaron oficinas temporales en Windows. [Recorrido completo y regresiones](../tests/test_v530_protocol.py).

## Qué se autorizó y qué se entregó

| Operación | Trabajo ejecutado en el proceso receptor | Prueba que queda al reabrir |
|---|---|---|
| R1 · Director · inspeccionar | Lee los bytes capturados del HTML y aplica las reglas estáticas. | Huellas de fuente y hallazgos, cantidad total y hasta doce ejemplos con ubicación. |
| R2 · Verificador · verificar | Vuelve a calcular los hechos y comprueba que coinciden con la salida exacta de R1. | Identificador de paso, identificador de transporte y SHA-256 del resultado que comprobó. |
| R3 · Director · entregar | Produce el informe y contrasta sus hechos con la salida de R2. El núcleo vuelve a verificar el artefacto al aceptarlo. | Informe consultable, vínculo al recibo de R2 y huella del artefacto final. |

Con el archivo del repositorio, el informe identificó el título vacío en 1:1, el idioma ausente en 2:1, una imagen sin texto alternativo en 6:3 y un control candidato sin etiqueta en 7:3. El informe de las siete muestras tuvo la misma huella. El criterio de aceptación cubre esas reglas de HTML. El objetivo escrito acompaña al encargo. El receptor ejecuta un procedimiento fijo y usa cero llamadas al modelo. La versión autónoma para instrucciones abiertas y seis especialistas corresponde a V5.40. [HTML empleado](../examples/audit-sample.html) · [Receptor](../neural_office/office_receiver.py).

El verificador repite el análisis con el mismo motor de reglas. Esto comprueba que se usaron la fuente y la salida correctas. Un defecto de una regla puede reproducirse en las dos pasadas. La prueba del ejemplo contrasta por eso los códigos y las cuatro ubicaciones con valores esperados fijados en el instrumento.

## Autoridad, corte y recuperación

La reserva del encargo congela proyecto, hilo, fuente y su SHA-256, objetivo, receptor, pasos, dependencias, topes y política de reintento. Cada intervención se identifica por ronda, rol y operación. Cada intento de entrega tiene su propia identidad. Las aperturas posteriores encuentran la reserva por proyecto, hilo y clave original. Una misma clave con otros bytes, otro hilo u otro permiso produce un conflicto. El tope histórico de tres intentos por proyecto es compartido por ambos protocolos.

La intención de despacho se confirma en SQLite antes de abrir el proceso. El receptor guarda su propia respuesta dentro del grupo de procesos Windows que le corresponde. La confirmación del emisor y la aceptación final son puntos de compromiso distintos. `office-show` devuelve el estado persistido y la siguiente acción. Un estado `RUNNING` acredita que se registró un despacho. Para saber si hace falta recuperar un controlador interrumpido se usa `office-reconcile`. Si todavía tiene el control otro proceso, la reconciliación avisa y deja que termine.

| Momento observado | Efecto comprobado |
|---|---|
| Corte antes de comprometer la reserva | La cuota y la versión del esquema conservan su valor previo. Dos clientes que vuelven a presentar la misma autorización obtienen el mismo encargo. |
| Paso reservado, despacho pendiente | Reabrir conserva la identidad de transporte. La siguiente petición comprueba de nuevo la autoridad. Una autorización caducada cierra el encargo con su causa. |
| Intención de despacho persistida, respuesta incierta | El siguiente paso queda bloqueado. Reconciliar exige obtener el control y comprobar la terminación del receptor. El receptor de esta versión solo publica su resultado al comprometer el recibo local. |
| Respuesta calculada y recibo aún sin confirmar en SQLite | Tras un corte del proceso, la respuesta volátil se pierde. Si se comprueba la ausencia del recibo, solo una nueva acción explícita puede despachar otro transporte y debe caber en el permiso original. |
| Recibo comprometido y emisor interrumpido | Reconciliar recupera la misma respuesta y su huella. La cuenta de despachos permanece igual. |
| Última confirmación guardada, entrega pendiente de cierre | Reconciliar verifica y acepta el informe guardado. La prueba prohíbe arrancar un proceso durante esta recuperación. |
| Parada durante el trabajo o tras guardar una respuesta aún sin confirmar por el emisor | La solicitud entra en `STOPPING`. Tras comprobar la terminación, queda `CANCELLED`. El recibo existente sigue siendo auditable. La salida pendiente queda excluida de la entrega. El proyecto conserva el cargo. |
| Windows impide arrancar un receptor después de registrar la intención | El emisor deja `RECOVERY_REQUIRED` y mantiene la exclusión sobre el despacho. La prueba inyectó el fallo al arrancar y comprobó el cierre por agotamiento cuando el permiso admitía un solo intento de transporte. |

La batería incluye tres interrupciones alrededor de la reserva del proyecto, once puntos alrededor del primer paso y tres alrededor de la aceptación final. El instrumento termina el proceso controlador abruptamente. En los puntos internos del receptor se espera una barrera del proceso real y se comprueba su terminación por PID. Otra prueba cancela un trabajador vivo mientras un segundo cliente intenta reabrirlo. El permiso ordinario autoriza tres despachos y un intento de transporte por paso. Al autorizar se pueden fijar de uno a seis despachos y uno o dos intentos por paso. El agotamiento deja el resultado parcial y su causa. [Implementación del protocolo](../neural_office/office_protocol.py).

## Datos anteriores y vuelta a V5.20

Sobre una oficina temporal creada por el código V5.20 `9b356b8`, la primera admisión V5.30 actualizó el esquema de 2 a 3 dentro de la misma transacción que la reserva y su testigo de continuidad. Se conservó el primer encargo histórico, cancelado, con su identidad y ordinal. El nuevo recibió el ordinal 2 y quedó un intento disponible. Un encargo del protocolo histórico siguió rechazando la decimotercera llamada después de actualizar el esquema.

El núcleo V5.20 rechazó la base actualizada. Una copia aislada y coherente de la base previa y su testigo sí volvió a abrirse con V5.20. Restaurar la copia anterior con el testigo actual recuperó la última revisión, incluido el cargo de V5.30. Volver al commit anterior solo revierte código. Para conservar una oficina anterior se necesita una copia previa coherente de sus almacenes y testigos con la oficina cerrada. Este ensayo de migración abarcó el ledger y su testigo. El ejemplo siguiente crea su propia base.

## Reproducir el encargo

Desde la raíz de esta rama, en PowerShell 7 con Python 3.12 para Windows. La orden `office-start` autoriza un intento en la oficina temporal. La orden histórica `check` sigue disponible para obtener los hallazgos sin reservar un encargo.

```powershell
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$ensayo = Join-Path ([IO.Path]::GetTempPath()) ("neural-office-530-" + [guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $ensayo
$db = Join-Path $ensayo 'review.sqlite3'
$root = (Resolve-Path 'examples').Path
$html = Join-Path $root 'audit-sample.html'
$estado = python -m neural_office --state $db office-start --project Portal --thread entrega --root $root --file $html --objective "Verificar los hallazgos HTML del portal" --key revision-1 | ConvertFrom-Json
$id = $estado.attempt
foreach ($paso in $estado.permit.steps) {
    $estado = python -m neural_office --state $db office-step $id $paso.id | ConvertFrom-Json
}
if ($estado.state -ne 'ACCEPTED' -or $estado.receiver_receipts -ne 3) { throw 'Entrega incompleta' }
python -m neural_office --state $db office-output $id r2.verifier.verify
python -m neural_office --state $db report $id
```

Para reabrir con otro cliente se usa `office-lookup --project Portal --thread entrega --key revision-1`. Para una interrupción se usa `office-reconcile <id>`. Se puede solicitar la parada con `cancel <id>`. `office-output` identifica las dependencias exactas de cada salida confirmada.

## Coste del recorrido local

Windows 11 x64, compilación 26200, Python 3.12.10 y 20 procesadores lógicos. Una ejecución de calentamiento y siete medidas, cada una sobre una oficina nueva. Se midió el grupo Windows del controlador y sus receptores, desde el arranque hasta la salida. El muestreador externo quedó fuera del grupo. Cada ejecución incluye la verificación de los cuatro hallazgos, los recibos y la aceptación.

| Magnitud del recorrido completo | Mediana | Intervalo observado |
|---|---:|---:|
| Tiempo de pared | 1,656 s | 1,241–1,839 s |
| CPU acumulada del grupo | 1,219 s | 0,859–1,516 s |
| Pico de RAM muestreada, suma de conjuntos de trabajo | 120,38 MiB | 118,55–121,21 MiB |
| Pico de memoria comprometida del grupo, contador de Windows | 53,46 MiB | 53,38–53,89 MiB |

Se obtuvieron 186 muestras en las siete ejecuciones, con intervalo objetivo de 50 ms. En una muestra de la séptima ejecución Windows no pudo leer la memoria de todos los procesos. La suma de memoria de ese instante quedó desconocida. Los picos de conjuntos de trabajo de la tabla son los observados, y las páginas compartidas pueden contarse varias veces. El contador de compromiso de Windows conserva por separado el máximo durante la vida del grupo. Las siete lecturas finales de CPU fueron válidas. Cada receptor lleva un límite de 256 MiB de memoria comprometida, 10 segundos de CPU en modo usuario y 20 segundos de pared hasta solicitar la terminación. La prueba leyó los dos primeros límites del Job activo.

Estos datos miden la coordinación y la auditoría de HTML. El trabajo de seis especialistas, el modelo residente y Tauri/WebView2 quedan fuera de esta serie. La comparación pareada con un agente en PowerShell y el objetivo de 1,50× requieren la oficina con inferencia real. [Mediciones por ejecución](evidence/V5_30_PROTOCOL.json) · [Instrumento reproducible](../tools/measure_v530_protocol.py) · [Referencia individual de V5.20](V5_20_LOCAL.md).

## Pruebas y límite del escritorio

La suite de Windows pasó 264 pruebas Python y 77 del frontend. Un cliente del proceso real de `desktop_stdio` leyó el informe y la actividad. Cada evento de recepción identificó el paso, el transporte y la huella de la salida registrada. Los recursos de producción del escritorio se compilaron. El flujo nuevo se inicia desde la CLI.

El 20 de noviembre de 2026, a las 10:49:13 UTC, la construcción local de Tauri se detuvo al cargar `@tauri-apps/cli-win32-x64-msvc` 2.12.5. El evento 3077 identificó la directiva `VerifiedAndReputableDesktop`, el estado `0xc0e90002` (Win32 4551) y la huella plana `f3232d5f5a8b4fc5ef1186752dbd6132c7d12c32cf26772b6c6155fcf2bf193f`, idéntica a la del archivo. El evento 3089 asociado indicó cero firmas. La compilación se interrumpió antes de generar el ejecutable de Neural Office. La prueba de la ventana Tauri queda pendiente en este equipo.
