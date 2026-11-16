# V5.3 — referencia reproducible de rendimiento

Fecha: 2026-11-16. **OBSERVADO:** seis intentos sintéticos aceptados, dos por perfil 1/3/7; seis arranques sin inferencia. **VERIFICADO:** todos terminaron su Job propio. La calidad semántica de los comentarios, GPU, energía y tiempo al primer token no se evaluaron.

## Resultado de referencia

| Roles | Aceptados / intentados | Tiempo total mín.–máx. | Mediana total | Mayor pico residente muestreado¹ | CPU acumulada, rango² |
| --- | --- | --- | --- | --- | --- |
| 1 | 2/2 | 28,37–29,23 s | 28,80 s | 5,88 GiB | 97,45–99,13 s |
| 3 | 2/2 | 56,59–58,19 s | 57,39 s | 6,25 GiB | 347,08–347,27 s |
| 7 | 2/2 | 108,59–110,33 s | 109,46 s | 6,90 GiB | 766,55–767,84 s |

¹ Suma de working sets de procesos propios, cada 0,5 s. Puede contar páginas compartidas varias veces y perder picos breves. No incluye interfaz, controlador Python ni PowerShell usado para consultar el propietario del listener. No equivale a RAM total de Neural Office ni a memoria mínima necesaria.

² Tiempo de CPU de los procesos del Job, sumado entre núcleos; puede superar el tiempo de reloj. La media normalizada sobre 20 procesadores lógicos fue aproximadamente 17%, 30% y 35% por perfil. No mide saturación de cada núcleo, eficiencia energética ni capacidad libre para otros modelos.

**OBSERVADO:** 22 llamadas totales, digest de modelo constante, contexto observado 8.192, VRAM asignada al modelo igual a cero en todas las respuestas. Primera carga por intento: aproximadamente 6,88–7,89 s; generación: 9,39–9,92 tokens/s en estas respuestas. Las cargas siguientes del mismo intento fueron menores; un proceso nuevo por intento impide equiparar esa diferencia a un experimento de caché controlado. [Recibo completo sin texto privado](evidence/V5_3_BASELINE.json).

**INFERIDO, limitado a este caso:** siete roles aumentan tiempo y memoria observada, sin multiplicar por siete los pesos cargados. No se ha demostrado mejora de calidad ni causalidad exclusiva del número de roles: cada perfil usa prompts y salidas distintos, y el orden 1→3→7 no se aleatorizó.

## Entorno y trazabilidad

Windows; Python 3.12.10; Ollama 0.40.16; Intel Core Ultra 7 255HX, 20 procesadores lógicos, 32 GiB instalados. Hay una RTX 5070 Laptop de 8.151 MiB, pero el perfil de prueba obliga CPU. `num_ctx=8192`, `num_predict=128`, `num_gpu=0`, `stream=false`, `think=false`, `temperature=0`; las comprobaciones de propiedad y digest permanecen activas.

La referencia final se repitió con **V5.3 y el colector corregido** después de detectar la frontera de PID obsoleto. El recibo identifica por SHA-256 diagnósticos, colector, runner y backend; los cuatro coinciden con las fuentes publicadas. `ollama.py` y `runner.py` mantienen la política de V5.2.1. Los seis intentos exploratorios anteriores se conservan privadamente y no se mezclan con esta tabla. Las diferencias entre series no demuestran una mejora de rendimiento causada por el arreglo. La serie de seis arranques sin inferencia es anterior: su recibo conserva versión 5.2.1 y los hashes del núcleo, sin un hash inicial completo del colector.

Entrada: [audit-sample.html](../examples/audit-sample.html), SHA-256 `d209bb2b4a7c4e4db25e7bd57f6ce02739e00bda8c1bc685167ed966e2e0da34`. Tres proyectos experimentales nuevos; dos intentos cada uno; se aparca cada proyecto al terminar. Los logs, SQLite, respuestas y alias locales permanecen privados. El resumen publica métricas, hashes, estados y veredicto estático, sin esos contenidos.

## Repetición explícita

Desde la raíz del checkout, con Windows, Python 3.12, Ollama y un modelo local compatible ya disponibles. Sustituir el alias y elegir carpetas **nuevas** fuera del árbol histórico; los comandos no usan el ledger habitual. El segundo comando sí hace inferencias.

```powershell
py -3.12 -B -m neural_office.diagnostics startup --model "ALIAS_LOCAL" --output "D:\NeuralOfficeExperiments\startup-01" --trials 6
py -3.12 -B -m neural_office.diagnostics benchmark --model "ALIAS_LOCAL" --output "D:\NeuralOfficeExperiments\cpu-01" --repeats 2 --roles 1 3 7
```

La carpeta debe ser nueva; no reutilizarla ni borrar estado para recuperar presupuesto. El runner crea el estado experimental, consume intentos reales de ese experimento y se detiene ante un fallo o terminación no confirmada. No reintenta automáticamente una inferencia fallida. Un error temprano puede dejar evidencia parcial; conservarla y analizarla. La ruta bajo una fuente histórica V1 se rechaza antes de crear estado de benchmark. [Implementación](../neural_office/diagnostics.py#L195).

El subcomando `startup` arranca/verifica/detiene sin inferir ni cargar pesos mediante chat. “Arranque” no significa “modelo listo para el primer token”. Los tiempos de esa serie no pueden sumarse a otra serie como si fueran una misma ejecución.

## Qué mide cada campo

| Campo | Definición y límite |
| --- | --- |
| `wall_seconds` del intento | Reloj monotónico alrededor de `run`, incluyendo arranque, llamadas, verificación y limpieza; excluye registro del proyecto y reserva inicial |
| `wall_seconds` de llamada | Envoltorio completo de inferencia: identidad, propietario, petición y verificaciones posteriores |
| `load_duration`, `eval_duration`, etc. | Enteros reportados por Ollama, en nanosegundos; no son cronómetros externos independientes |
| `generated_tokens_per_second` | `eval_count × 1e9 / eval_duration`; ausente si los campos no son válidos o la duración es cero |
| `cpu_seconds` | Contabilidad acumulada del Job propio; lectura final obligatoria para publicar el total |
| `cpu_percent_machine_average` | `100 × cpu_seconds / segundos observados / procesadores lógicos`; media de la ventana, no pico |
| `sampled_peak_working_set_sum_bytes` | Mayor suma residente observada; muestreo y posible doble conteo |
| `sampled_peak_private_commit_sum_bytes` | Mayor suma de compromiso privado observado; no memoria física residente |
| `job_peak_commit_bytes` | Máximo de compromiso que informa Windows para el Job; no es pico de RAM física |
| `complete` | Sin errores registrados ni PIDs ilegibles durante las observaciones; no implica captura de todos los picos |
| `model_allocated_vram_bytes` | Allocación reportada por `/api/ps` para el digest; no uso global de GPU del equipo |
| `first_token_ms` | `null`: el backend actual no transmite tokens en streaming |

[Métricas de Ollama](https://docs.ollama.com/api/usage); contabilidad de [Job](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_accounting_information), [compromiso máximo](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information) y [memoria por proceso](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters_ex). [Colector propio](../neural_office/measurements.py#L45).

## Lo que esta referencia no prueba

**DESCONOCIDO:** sobrecoste del colector frente a la misma corrida sin él; TTFT; calidad comparada; energía, temperatura, throttling; rendimiento GPU y memoria del futuro escritorio. Un proceso nuevo no vacía la caché de archivos de Windows. Otros programas y condiciones térmicas no estuvieron controlados. Dos muestras no justifican p95/p99, márgenes estadísticos ni requisitos universales de hardware.

El perfil existente tiene prompts cortos y salida máxima 128 tokens; no representa agentes generalistas de contexto largo. No se ejecutaron herramientas externas ni loops abiertos. Una auditoría aceptada acredita la estructura y las cuatro heurísticas del verificador, no cada afirmación generada.

## Siguiente experimento V5.4

Comparar una variable cada vez: contexto, modelo/tamaño/cuantización, CPU frente a GPU con reserva de VRAM, precarga/reutilización dentro de la frontera de propiedad y coste de consultas del propietario. Antes de mantener un modelo entre intentos, probar aislamiento, cancelación, consumo y recuperación. No eliminar esas comprobaciones para obtener un benchmark mejor.

Definir un pequeño corpus con respuestas esperadas, entrada pública y evaluador independiente; registrar calidad junto con tiempo, RAM/VRAM y tokens. Alternar orden de perfiles y repetir frío/caliente con definición explícita de caché. Un perfil se promueve solo si conserva utilidad y límites, no por tokens/s aislados. La [FAQ de Ollama](https://docs.ollama.com/faq) explica que contexto y paralelismo afectan memoria; no proporciona un ahorro garantizado para este equipo.
