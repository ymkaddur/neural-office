# Evidencia y límites de transferencia

Investigación consultada el 16–17 de noviembre de 2026. Los mecanismos externos se inspeccionaron en los archivos enlazados; no se ejecutaron sus repositorios. Las aplicaciones propuestas a Neural Office requieren prueba propia. Las licencias se indican para evitar confundir observación con permiso de copia.

## Lección aplicada al proyecto

La línea base sin LLM y el perfil serial de un rol son propuestas de comparación, no resultados de calidad ya demostrados. Un modelo pequeño sirve para probar integración bajo un presupuesto de recursos; no representa automáticamente la calidad de un modelo mayor.

Antes de comparar perfiles, decide qué resultado cuenta como útil y conserva los casos fallidos. No filtres silenciosamente NaN, falta de uso, timeout u OOM del denominador de éxito. Registra por separado caché de respuesta, prompt/KV, pesos y sistema operativo.


## Mecanismos externos

### ollama/ollama

[Archivo en el commit inspeccionado](https://github.com/ollama/ollama/blob/db5266a71d6413c4568208a768757b16ffd7a021/server/sched.go#L123). Líneas 123-131,240-253,280-283,426-509; nivel: `source-inspected`.

OBSERVADO: el scheduler limita la cola, descarta solicitudes ya canceladas y distingue expiración del runner, referencias activas, PID y recuperación de VRAM. PROPUESTA V5.5/V6: mantener la admisión acotada y mostrar «parada solicitada» hasta confirmar procesos; antes de reutilizar un modelo entre encargos, probar carga fría/caliente, cancelación durante carga y expiraciones duplicadas sin afectar al nuevo propietario.

**Límite:** Inspección de rutas, no ejecución. keep_alive o una ventana cerrada no prueban liberación inmediata de RAM/VRAM. No transferir su política de varios runners al piloto de una inferencia ni prometer menor consumo sin medir UI, Python y modelo por separado.

**Licencia observada:** MIT; LICENSE:1-21 verificado.

### ggml-org/llama.cpp

[Archivo en el commit inspeccionado](https://github.com/ggml-org/llama.cpp/blob/e8fbcad855c5d8c315aa1dde231836ae472f5779/tools/server/server-context.cpp#L660). Líneas 660-684,1600-1618,4634-4665; nivel: `source-inspected`.

OBSERVADO: la caché de prompts admite desactivación, tamaño explícito o ausencia de límite; liberar ciertos slots limpia su contexto. Ante falta de espacio KV, la ruta inspeccionada intenta limpiar slots inactivos o reducir batch; distingue errores que obligan a limpiar contexto y detenerse. PROPUESTA: presupuestar caché además de pesos/contexto y ensayar saturación con resultado y contador conservados.

**Límite:** No se ejecutó el servidor. No equivale a recuperación universal de OOM ni autoriza repetir efectos externos. Las políticas dependen del tipo de modelo; el propio archivo mantiene rutas de aborto pendientes. No afirmar rendimiento de llama.cpp frente a Ollama a partir del código.

**Licencia observada:** MIT; LICENSE:1-21 verificado.

### huggingface/transformers

[Archivo en el commit inspeccionado](https://github.com/huggingface/transformers/blob/36e937ae761dea806a5b9fbb382e880378ad5435/src/transformers/cache_utils.py#L104). Líneas 104-157,1460-1517; nivel: `source-inspected`.

OBSERVADO: DynamicLayer crece al concatenar K/V y declara no tener máximo propio. La caché puede descargar capas a CPU y preparar su retorno con stream separado; distingue capas deslizantes y lineales. PROPUESTA: fijar contexto y perfiles compatibles antes de admitir trabajo; en ensayos de offload medir RAM, VRAM y latencia conjuntamente, sin vender menor VRAM como menor memoria total.

**Límite:** No se ejecutó Transformers. El límite de secuencia puede imponerse en otra capa; este extracto no prueba crecimiento ilimitado de toda aplicación ni fuga. Las capas/arquitecturas tienen comportamientos distintos; trasladar un perfil entre modelos exige verificarlo.

**Licencia observada:** Apache-2.0; LICENSE:1-26 y metadato SPDX verificados.

### sgl-project/sglang

[Archivo en el commit inspeccionado](https://github.com/sgl-project/sglang/blob/f6de13a0c26697382a1bb7969e24ea59f089365e/python/sglang/srt/managers/schedule_policy.py#L80). Líneas 80-85,903-955,1049-1057,1874-1936; nivel: `source-inspected`.

OBSERVADO: recortar max_new_tokens para estimar capacidad no modifica la condición real de parada; resta tokens ya generados antes de recortar, evitando subreservar ventanas largas. La admisión comprueba presupuesto de memoria/estado antes de cargar prefijos. PROPUESTA: etiquetar RAM estimada y límites ejecutables como magnitudes distintas; probar 0, máximo, prefijo reutilizado y generación ya superior al recorte.

**Límite:** No se ejecutó SGLang. Estas fórmulas son propias de su planificador y arquitectura de caché; no copiar constantes como 4096 a Neural Office. Una estimación favorable no autoriza superar presupuesto ni acredita ausencia de OOM. La selección de un candidato tampoco prueba que se haya materializado en memoria.

**Licencia observada:** Apache-2.0; LICENSE:1-26 y metadato SPDX verificados.

### pydantic/pydantic-ai

[Archivo en el commit inspeccionado](https://github.com/pydantic/pydantic-ai/blob/04f27ffdc8d364f9376fad17d6115b31070fa8dc/pydantic_ai_slim/pydantic_ai/usage.py#L426). Líneas 426-438,547-595,633-654,681-736; nivel: `source-inspected`.

OBSERVADO: request_limit limita respuestas comprometidas/turnos, excluyendo ciertos fallbacks, continuaciones y retries del transporte; tokens se comprueban después de responder. Uso omitido se identifica como cota inferior; tool_calls_limit comprueba consumo proyectado. PROPUESTA V6: separar intentos, turnos, envíos efectivos y tokens; denegar próxima llamada con reserva de presupuesto y probar telemetría ausente.

**Límite:** No ejecutado. Contadores del framework no son facturación ni límite duro de todos los envíos. La comprobación posterior puede detectar un límite ya superado; el aviso de uso ausente no completa lo desconocido. No usar esta evidencia para prometer cuotas de proveedores externos.

**Licencia observada:** MIT; LICENSE:1-21 inspeccionado.

### promptfoo/promptfoo

[Archivo en el commit inspeccionado](https://github.com/promptfoo/promptfoo/blob/ccafd6daf4c760e25a7e688c6a8b57ebedb3c5fd/test/evaluator/repeatCache.test.ts#L25). Líneas 25-74,76-117,119-183; nivel: `test-source-inspected-not-executed`.

OBSERVADO: los tests distinguen repeticiones mediante namespaces de caché y verifican que una segunda evaluación reutiliza resultados; desactivar caché viaja también en el contexto del proveedor. PROPUESTO V6: registrar cache hit/miss y separar repeticiones estocásticas de replay durable. Prueba: mismo corpus, repeticiones independientes con caché de respuesta desactivada frente a repetición de una clave operacional que nunca debe volver a inferir.

**Límite:** Tests inspeccionados, no ejecutados. El proveedor es un mock. No demuestra independencia estadística del modelo real ni control de caché de pesos, prompt/KV o sistema operativo.

**Licencia observada:** MIT; LICENSE:1-19 y metadato GitHub verificados.


## Feedback público

### F04: Codex: dificultad para interpretar consumo de cuota frente a tokens

[Fuente pública](https://github.com/openai/codex/issues/28879). Publicación: 2026-06-18T08:02:01Z. Consulta: 2026-11-17. Localizador: GitHub issue body; Summary, Evidence, What I ruled out, Ask.

OBSERVADO: el autor compara registros de tokens y porcentajes de cuota de dos días y pregunta si cambió su ponderación. El reporte distingue ventana de cinco horas y semanal.

HIPÓTESIS: separar llamadas locales, tokens medidos, estimaciones y cuotas del proveedor evita que el usuario interprete magnitudes distintas como un mismo presupuesto.

PENDIENTE: mostrar fixture con tokens disponibles pero cuota desconocida; comprobar etiqueta de origen, instante, unidad y desconocido, sin convertirlo a euros o porcentaje inventado.

**Límite:** No se verificaron logs privados, causalidad, precio ni cambio de política. El issue está cerrado; ello no acredita una corrección ni justifica afirmar que el problema sigue vigente.

### F12: Anthropic: Building effective agents

[Fuente pública](https://www.anthropic.com/research/building-effective-agents). Publicación: 2024-12-19. Consulta: 2026-11-17. Localizador: When (and when not) to use agents; Agents; Combining and customizing these patterns.

OBSERVADO: el equipo recomienda comenzar con la solución más simple, añadir complejidad al demostrar mejora, usar feedback del entorno y condiciones de parada. Distingue workflows predefinidos de agentes que deciden dinámicamente.

HIPÓTESIS: un rol y un ciclo útil verificable deben ser la línea base antes de imponer seis agentes o tres iteraciones para todas las tareas.

PENDIENTE: comparar uno frente a varios roles sobre la misma batería; medir resultado aceptado, llamadas, latencia y memoria máxima. Promocionar complejidad solo con ventaja relevante.

**Límite:** Consejo de proveedor basado en su experiencia, no ensayo de la UI de Neural Office. La propia página advierte que el panorama técnico cambió desde 2024.


## Método docente

### Carnegie Mellon University

[Lecture 13: Evaluation of APIs and UI Tools, API Usability, Cognitive Dimensions](https://www.cs.cmu.edu/~bam/uicourse/05631fall2022/SSUI-13-eval.pdf). 05-431/631 Software Structures for User Interfaces, Fall 2022. Nivel: Material docente: diapositivas sobre evaluación de herramientas y APIs. Localizador: PDF, páginas 3, 10–11 y 13. Consulta: 2026-11-16.

OBSERVADO: distingue rendimiento, memoria, robustez y complejidad de la utilidad, errores humanos y aprendizaje. Examina barreras de selección, coordinación, utilización, comprensión e información.

PROPUESTA: una UI elegante no compensa un protocolo confuso ni recursos excesivos. Hacer comprensibles inicio, progreso, cancelación y recuperación a través de la frontera UI–motor.

**Comprobación propuesta:** Medir consumo y latencia durante tareas concretas, junto con capacidad del usuario para interpretar estados y recuperarse de un fallo.

**Límite:** Diapositivas docentes; los estudios citados no fueron replicados ni sustituyen medidas locales.
