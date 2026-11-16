# V5.2.1 — continuidad, restauración y conciliación

**VERIFICADO dentro del alcance indicado.** Usa Windows, Python 3.12 y una sesión de usuario. Cierra los controladores anteriores antes de migrar. Los comandos se ejecutan desde la carpeta del código en PowerShell.

## Actualizar un estado V5.2 existente

```powershell
.\run.bat protect
.\run.bat status
```

Con un estado elegido explícitamente:

```powershell
.\run.bat --state "D:\NeuralOfficeState\office.sqlite3" protect
```

`protect` adopta el esquema 1 solo cuando la oficina está inactiva; conserva intentos, entradas, informes y eventos. Comprueba nuevamente la inactividad dentro del bloqueo de escritura SQLite y valida integridad/cadena de eventos. No migra bases históricas V1/V4 a la fuerza ni crea una identidad nueva para reemplazar un historial existente.

Los estados nuevos creados con `init` ya usan esquema 2. Los binarios V5.2 anteriores no deben seguir utilizándose sobre ellos. Una adopción interrumpida puede dejar un testigo incompleto y bloquear; conserva ambos archivos para investigar, no borres el testigo para reiniciar cuotas.

## Respaldar y restaurar

```powershell
.\run.bat backup "D:\NeuralOfficeBackups\office-copy.sqlite3"
.\run.bat restore "D:\NeuralOfficeBackups\office-copy.sqlite3"
.\run.bat status
```

El destino del respaldo debe ser nuevo y su carpeta existir. Con `--state`, colócalo antes de `backup` o `restore`.

Cada ledger tiene un testigo separado llamado `<archivo>.witness.sqlite3`. Guarda la imagen lógica más reciente y hashes de revisiones conocidas. El respaldo del ledger **no incluye el testigo**. La restauración comprueba que la copia pertenece al historial retenido y recupera la revisión más reciente del testigo: no vuelve deliberadamente al contenido antiguo ni devuelve presupuesto.

Se conserva también un intento pendiente. Si su Job Object aún tiene procesos activos, la restauración se deniega. Tras una caída con el árbol ya terminado, el intento pendiente exige `recover <identificador>`; recuperar no repite un POST ni devuelve el intento.

El testigo y el ledger contienen datos privados. Conserva el testigo vigente fuera del conjunto que decidas reemplazar. **La ubicación predeterminada es adyacente: no proporciona redundancia frente a pérdida del disco o copia completa de la carpeta.** Si se revierte o pierde todo el conjunto de copias, no existe una observación local que permita reconstruir el consumo desaparecido. Se requiere otro testigo confiable retenido para ampliar esa garantía.

Se rechazan testigos ausentes, copias de otra oficina, copias alteradas y estados divergentes no conocidos. Esta versión no es una herramienta general de reparación de SQLite corrupto ni un almacén resistente a un administrador malicioso.

La atomicidad usa bases adjuntas SQLite, journal DELETE y synchronous FULL; WAL no se adopta silenciosamente. Un mutex Windows coordina los controladores cooperantes de la misma sesión y ruta normalizada. No cubre alias por hardlink, otros controladores que escriban fuera del protocolo, múltiples sesiones ni sistemas de archivos de red. El límite de imagen retenida es 64 MiB.

## Inspeccionar y conciliar el legado

La inspección no crea el ledger destino ni activa agentes:

```powershell
.\run.bat legacy-inspect "D:\Historico\BTD_AUTOLAB_R1"
```

Para un destino preparado de conciliación:

```powershell
.\run.bat --state "D:\NeuralOfficeState\office.sqlite3" init
.\run.bat --state "D:\NeuralOfficeState\office.sqlite3" legacy-reconcile "D:\Historico\BTD_AUTOLAB_R1"
.\run.bat --state "D:\NeuralOfficeState\office.sqlite3" status
```

`init` es idempotente sobre el mismo esquema 2; no sustituye `protect` para un esquema 1. Mantén el mismo destino una vez conciliado.

| Fuente | Regla |
| --- | --- |
| V1 + V4 | Catálogos completos; cualquier discrepancia activo/armado o exceso global bloquea admisión. Importar deja los proyectos aparcados y sin aprobación local. |
| Plus | Operaciones iniciadas se contabilizan conservadoramente; varias invocaciones bajo una misma autorización requieren un mapeo adicional y se bloquean; un recibo no se convierte en informe verificado ni demuestra por sí solo inferencia real. |
| Director V4.5/V5 | `attempted` y filas de tareas deben concordar; `completed` es el último ordinal verificado, no el número de éxitos. |
| WorkLedger V5 | Contador de verificados contrastado con sus filas. El presupuesto histórico se conserva sin copiar informes como certificados nuevos. |
| V4.2, historial mixto o esquemas no mapeados | Bloqueo explícito, sin inventar equivalencias entre grafos, tareas de rol y versiones. |

La selección de archivos está cerrada en [legacy.py](../neural_office/legacy.py#L18). La captura retiene handles Windows que impiden escritores/reemplazos de los archivos existentes; copia main/WAL a un directorio temporal y lee las copias. Cambios en fuentes, fuentes ausentes o escritores abiertos impiden nueva autoridad y pueden interrumpir un trabajo administrado.

El modelo de confianza presupone fuentes históricas quiescentes y cooperantes: una fuente opcional ausente no puede bloquearse como archivo, por lo que no se garantiza atomicidad frente a un programa ajeno que cree un nuevo ledger durante la captura. El legado se debe detener antes de conciliar o ejecutar con ese vínculo.

Para admitir trabajo posteriormente se requieren V1 activo, V4 armado, autorización local, ausencia de operaciones pendientes y presupuesto combinado disponible. La traducción automática de una autorización V4 parcial (0/1/2 versiones) se deniega: no equivale a tres intentos. Esta revisión soporta la ventana completa de tres con contadores certificados originales a cero; historiales certificados no cero requieren otro mapeo explícito.

El presupuesto es `consumo histórico reconocido + intentos locales`. Reconciliar no lo reduce. El origen lógico se identifica con metadata y el evento de inicialización; no es una firma de identidad externa. Importar una copia alterada o registrar el mismo proyecto bajo otra identidad no está autorizado.

## Cambiar la carpeta de trabajo conservando la identidad

```powershell
.\run.bat --state "D:\NeuralOfficeState\office.sqlite3" legacy-rebind web-auditor "D:\Trabajo\web-auditor"
```

Se conserva el identificador, presupuesto e historial; se retiran activación y aprobación locales. La ruta anterior sigue reservada y no puede reutilizarse como otro proyecto, tampoco mediante carpetas padre/hijas. Esto cambia la carpeta de trabajo, no reescribe rutas dentro de las bases históricas ni traslada sus fuentes. No detecta copias arbitrarias fuera de las raíces conocidas.

## Diagnóstico de arranque

Los eventos distinguen creación del bootstrap, consulta de metadata, propiedad del listener y comprobación de identidad del modelo. Incluyen reloj de pared y contador de alta resolución; no registran prompts ni variables de entorno. Los archivos siguen siendo privados y pueden contener PID/puerto: depúralos antes de compartir.

El timeout histórico R13 sigue sin causa atribuida. El siguiente experimento es capturar **un arranque fallido con estas etapas y su commit exacto**, comparándolo con uno correcto en el mismo entorno. Aumentar arbitrariamente el timeout no se publica como solución.

## Fundamento técnico y límites de prueba

La [documentación de SQLite sobre commit atómico](https://www.sqlite.org/atomiccommit.html) describe la coordinación de bases adjuntas con journals de rollback. Las pruebas cubren rollback de transacción y muerte de proceso antes de commit; no simulan todos los fallos eléctricos, discos o drivers. La [API Python 3.12 de SQLite](https://docs.python.org/3.12/library/sqlite3.html) sustenta las operaciones de backup y serialización. Los [mutex Windows](https://learn.microsoft.com/en-us/windows/win32/sync/using-mutex-objects) coordinan acceso; un mutex abandonado no convierte por sí solo los datos en válidos.
