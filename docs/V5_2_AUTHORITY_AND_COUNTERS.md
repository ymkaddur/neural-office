# V5.2: autoridad y contadores implementados en el piloto

Estado: **vista previa técnica para Windows**, revisada el 16 de noviembre de 2026. Este documento describe el código de esta entrega. V5.1 permanece como diseño histórico; la matriz de aceptación indica qué partes siguen sin implementarse.

## Autoridad real y continuidad histórica

**OBSERVADO.** La genealogía y las autoridades del histórico se conservan en el [índice E01–E36](evidence/SOURCE_INDEX.md). V1/V4 y sus historiales no se sustituyen ni se importan al arrancar V5.2. El número de versión no concede autoridad sobre ellos.

**VERIFICADO, alcance acotado.** El piloto tiene un ledger nuevo para proyectos de prueba expresamente admitidos. La acción de usuario `audit` o «Autorizar y auditar» admite y reserva dentro de la misma transacción. Un duplicado conserva el intento anterior y no renueva una autorización revocada. Véanse [reserva](../neural_office/ledger.py#L168), [CLI](../neural_office/__main__.py#L19) y las pruebas de repetición y revocación en [fronteras](../tests/test_v52_boundaries.py).

**LÍMITE / DESCONOCIDO.** No existe un adaptador de migración V1/V4 ni una conciliación de presupuestos históricos. No se deben registrar proyectos históricos como proyectos nuevos para reiniciar su saldo. La aplicación no puede detectar por sí sola todas las copias o renombrados de esos proyectos. A07, A10 y A17 no están cerrados. Este piloto no es la nueva autoridad operativa del legado.

## Dominio de exclusión y actores confiables

El dominio administrado es un archivo de estado de oficina. El valor predeterminado es uno por usuario, bajo su directorio local de aplicación. `--state` crea o selecciona un dominio explícito distinto para pruebas. No es un mecanismo de migración ni demuestra exclusión entre archivos de estado diferentes.

El código Python del controlador, el backend elegido por el usuario y el sistema operativo forman parte de la base de confianza. El LLM recibe datos y mandatos limitados; no dispone de shell, navegador, instalador, API de administración ni herramienta para editar archivos. Las API Python internas no son una frontera de seguridad frente a otro programa ejecutado con los mismos privilegios.

**VERIFICADO.** SQLite `BEGIN IMMEDIATE` serializa reservas y transiciones entre participantes del mismo ledger. Cuatro procesos concurrentes repiten una solicitud y obtienen un solo intento. La unicidad de raíz impide registrar la misma carpeta con otro identificador dentro de ese dominio. [Transacciones](../neural_office/ledger.py#L57), [registro](../neural_office/ledger.py#L125), [prueba multiproceso](../tests/test_v52_boundaries.py).

**LÍMITE.** Un administrador o proceso con acceso de escritura al ledger puede alterarlo. La cadena de hashes detecta ciertas modificaciones no reconciliadas; no autentica al autor ni detecta la reversión conjunta de todos los registros. La eliminación, restauración y copia de bases quedan fuera del flujo admitido. El archivo no está cifrado por la aplicación.

## Definiciones de presupuesto

| Dato | Definición implementada | Fuente |
| --- | --- | --- |
| Proyecto activo | Registro admitido y no aparcado; máximo dos por ledger. | [Activación](../neural_office/ledger.py#L140). |
| Intento consumido | Fila persistida antes de iniciar el backend; máximo tres por proyecto. Los fallos y cancelaciones consumen. | [Reserva](../neural_office/ledger.py#L168). |
| Informe verificado | Intento real ACCEPTED cuyo informe estático y vinculación a recibos pasaron el verificador. No certifica los comentarios del modelo. | [Veredicto](../neural_office/ledger.py#L329), [estado](../neural_office/ledger.py#L369). |
| Simulación | Perfil `fixture`, contabilizado por separado de informes reales. | [Estado](../neural_office/ledger.py#L369), prueba `simulation_not_counted_as_real`. |
| Llamada | Admisión durable previa a un POST de inferencia; máximo doce por intento. | [Llamadas](../neural_office/ledger.py#L239). |
| Duración | Una hora desde la reserva, reloj de pared persistido y límite monotónico durante la ejecución. Regresión detectada o agotamiento detienen trabajo. | [Autoridad](../neural_office/ledger.py#L204), [ejecutor](../neural_office/runner.py#L40). |
| Contexto y salida | Perfil fijo: 8.192 tokens de contexto, hasta 128 tokens de salida, CPU. El prompt se limita además a 6.144 bytes UTF-8; los bytes no se presentan como un conteo exacto de tokens. | [Adaptador](../neural_office/ollama.py#L121). |

No hay devolución de intentos al reiniciar, renovar autorización o cancelar. Una tercera terminación aparca el proyecto. Una tercera operación indeterminada mantiene el bloqueo hasta reconciliarla. No hay mandato sucesivo automático que conceda otros tres intentos.

En el director histórico, `completed` resultó ser el **ordinal del último intento verificado**, no el número de éxitos. V5.2 conserva esa semántica y añade `verified_count` y `latest_verified_attempt` al estado histórico. Cambiar `completed` a un recuento rompía una prueba previa; esa propuesta fue retirada. [Diff exacto](legacy/V5_2_LEGACY_FIXES.patch).

## Estados y orden causal

| Estado | Propiedad y transición permitida |
| --- | --- |
| QUEUED | Reserva durable; aún sin permiso de inferencia. Puede cancelarse o adquirir el permiso global. |
| RUNNING | Posee permiso con generación y nombre de Job Object. Admite llamadas limitadas. |
| STOPPING | Cancelación solicitada; conserva el permiso hasta comprobar terminación. |
| RECOVERY_REQUIRED | No se pudo demostrar terminación; conserva el permiso. No reintenta el POST. |
| VERIFYING | El árbol propio terminó y el permiso se liberó; falta comprobar el informe. Puede reanudarse esa comprobación sin volver a inferir. |
| ACCEPTED / REJECTED / FAILED / CANCELLED | Terminales inmutables. Repetir el mismo resultado no produce otra aceptación. |

La cancelación y la aceptación compiten mediante transacciones: el orden confirmado decide. Una respuesta tardía puede guardarse como evidencia de una llamada ya admitida, pero no convierte una cancelación confirmada en aceptación. No se usa una desconexión HTTP como prueba de terminación.

**VERIFICADO en Windows.** Cada ejecución crea un Job Object con `KILL_ON_JOB_CLOSE`. El bootstrap se asigna antes de iniciar Ollama; los descendientes quedan dentro del job. Antes de inferir se comprueba que el proceso que escucha en el puerto pertenece a ese job. El cierre del propietario termina sus descendientes. [Propiedad](../neural_office/windows_job.py#L54), [bootstrap](../neural_office/windows_job.py#L110), [dueño del listener](../neural_office/ollama.py#L97).

**VERIFICADO en el ensayo real acotado.** POST enviado → petición de cancelación → `ActiveProcesses=0` mientras el lease seguía retenido → liberación → puerto sin respuesta. No se afirma haber probado por separado carga, prefill, generación y streaming. [Recibo público](evidence/V5_2_EXECUTION.json).

`recover` solo reconcilia un job ausente o sin procesos; no mata una ejecución saludable ni repite una llamada de resultado desconocido. En ese caso conserva el consumo y termina el intento como fallido o cancelado. No recupera una conversación de modelo a mitad de respuesta. [Recuperación](../neural_office/runner.py#L107).

## Artefacto, recibos y significado de aceptar

La entrada es un HTML UTF-8 seleccionado expresamente, de hasta 256 KiB. Se abre en Windows negando escritura y borrado concurrentes, se verifica la ruta final del handle y se guarda una instantánea de bytes en SQLite. El modelo recibe hallazgos limitados y comentarios previos, no instrucciones ejecutables extraídas del HTML. [Captura](../neural_office/files.py#L9), [prompt](../neural_office/runner.py#L25).

El informe fija digest de entrada, hallazgos y comentarios con sus hashes. La aceptación exige representación canónica, hallazgos recalculados, roles completos y comentarios iguales a los recibos persistidos. `true`, `1` y `1.0` no se aceptan como representaciones intercambiables de los campos numéricos. [Verificador](../neural_office/audit.py#L65).

El verificador es independiente de la afirmación del LLM, pero reutiliza el mismo algoritmo de análisis estático que produjo los hallazgos: puede compartir sus errores. «Verificado» se limita a ese contrato; no acredita conformidad WCAG, seguridad web, exhaustividad, calidad semántica ni corrección del texto generado.

## Fronteras que esta entrega no resuelve

No hay autenticación de terceros frente al puerto interno de Ollama, sandbox contra programas del mismo usuario, exclusión de clientes ajenos, memoria compartida, promoción de skills dinámicas, publicación automática ni integración de parches. El servicio original de Ollama y OpenCode permanecen fuera de la exclusión del piloto. La matriz de [integración](V5_2_INTEGRATION_AND_ACCEPTANCE.md) conserva las obligaciones pendientes de V5.1.
