# Evidencia y límites de transferencia

Investigación consultada el 16–17 de noviembre de 2026. Los mecanismos externos se inspeccionaron en los archivos enlazados; no se ejecutaron sus repositorios. Las aplicaciones propuestas a Neural Office requieren prueba propia. Las licencias se indican para evitar confundir observación con permiso de copia.

## Lección aplicada al proyecto

Protocolo mínimo propuesto, que debe adaptarse a la duda:

1. Declarar persona/contexto, tarea y éxito antes de mostrar el diseño.
2. Fijar contenido, capacidad real o simulada y condición de comparación.
3. Definir errores, ayudas, tiempo y comprensión que se recogerán; pedir consentimiento y limitar datos.
4. Ejecutar un piloto para detectar defectos del protocolo. No contar al creador o a agentes como participantes representativos.
5. Registrar incidentes con tiempo y resultado, incluyendo contraevidencia, abandonos y métricas faltantes.
6. Separar inferencia de desempeño, preferencia y generalización; proponer la siguiente comparación que cambiaría la decisión.

F15 y F16 de la investigación fueron intentos de acceso a X con HTTP 403. No se reutiliza su contenido indexado ni se atribuye opinión a sus autores. Dos páginas del mismo profesional no son dos expertos independientes. La selección de 20 instituciones de la investigación no se presenta como ranking de prestigio ni aval institucional.


## Mecanismos externos

### actualbudget/actual

[Archivo en el commit inspeccionado](https://github.com/actualbudget/actual/blob/9cb9b72c4ce19a5cfa0ca53e952ea600c2987cd2/packages/loot-core/src/server/sync/sync.property.test.ts#L242). Líneas 242-310; 315-385; nivel: `test-source-inspected-skipped-not-executed`.

OBSERVADO: el test genera mensajes, entrega lotes, añade mensajes durante fullSync y compara árboles Merkle; conserva el esquema para reducir un contraejemplo. PROPUESTA V6: comprobar convergencia con orden permutado, duplicados y eventos tardíos, además de igualdad del contador autoritativo y del resultado. En V5.5, un evento terminal seguido de snapshot retrasado no puede revertir la sesión.

**Límite:** Ambos casos inspeccionados son it.skip (316, 361). Existencia del fichero no demuestra cobertura activa ni éxito del motor de sincronización. El generador descarta timestamps duplicados; no basta como prueba de doble entrega. No copiar la escala de 100 pruebas como presupuesto sin duración medida y semilla reproducible.

**Licencia observada:** LICENSE.txt:1-7 inspeccionado, MIT; no excepción antecesora para esta ruta. No se ha ejecutado ni incorporado código de terceros.

### vibrantlabsai/ragas

[Archivo en el commit inspeccionado](https://github.com/vibrantlabsai/ragas/blob/8c63f10d500c44efbf24fdb9e2920de2104c321c/src/ragas/metrics/collections/faithfulness/metric.py#L102). Líneas 102-161; nivel: `source-inspected`.

OBSERVADO: Faithfulness valida entradas, genera afirmaciones atómicas y luego veredictos contra el contexto; devuelve NaN cuando no hay afirmaciones o veredictos. PROPUESTO V6: representar evaluación indeterminada separada de aprobado/rechazado; probar respuesta vacía, extracción vacía, contexto ausente y afirmación no sustentada. Registrar cobertura de afirmaciones, no sólo una media.

**Límite:** Que un contexto respalde una afirmación no demuestra verdad del contexto ni calidad de extracción del juez. No se ejecutó. Identidad canónica verificada: vibrantlabsai/ragas, antes explodinggradients/ragas.

**Licencia observada:** Apache-2.0; LICENSE:1-5 y metadato GitHub verificados.

### promptfoo/promptfoo

[Archivo en el commit inspeccionado](https://github.com/promptfoo/promptfoo/blob/ccafd6daf4c760e25a7e688c6a8b57ebedb3c5fd/test/evaluator/repeatCache.test.ts#L25). Líneas 25-74,76-117,119-183; nivel: `test-source-inspected-not-executed`.

OBSERVADO: los tests distinguen repeticiones mediante namespaces de caché y verifican que una segunda evaluación reutiliza resultados; desactivar caché viaja también en el contexto del proveedor. PROPUESTO V6: registrar cache hit/miss y separar repeticiones estocásticas de replay durable. Prueba: mismo corpus, repeticiones independientes con caché de respuesta desactivada frente a repetición de una clave operacional que nunca debe volver a inferir.

**Límite:** Tests inspeccionados, no ejecutados. El proveedor es un mock. No demuestra independencia estadística del modelo real ni control de caché de pesos, prompt/KV o sistema operativo.

**Licencia observada:** MIT; LICENSE:1-19 y metadato GitHub verificados.


## Feedback público

### F01: Preferencias enfrentadas sobre la nueva interfaz de Claude Code

[Fuente pública](https://www.reddit.com/r/ClaudeCode/comments/1x74gg2/anyone_else_hate_the_new_ui/). Publicación: 2026-10-16 (fecha de calendario del índice; la página abierta muestra fechas relativas). Consulta: 2026-11-17. Localizador: Publicación; comentarios sobre Session Rail, contexto, subagentes y monitor vertical (página leída, líneas 22-23, 66-107, 303-320).

OBSERVADO: el autor prefiere esfuerzo, uso y contexto agrupados. Otros participantes valoran el panel lateral persistente y la visibilidad de tareas/subagentes; otro informa mala adaptación a monitor vertical. Hay desacuerdo explícito, no consenso a favor de mayor densidad.

HIPÓTESIS: una franja compacta y estable para estado/presupuesto, con detalles laterales plegables, funcionará mejor que imponer máxima densidad y tres columnas a todos.

PENDIENTE: comparar tareas idénticas a 1280x800 y 900x1200; medir tiempo para identificar estado, presupuesto restante y siguiente acción; registrar errores y preferencias por separado.

**Límite:** Muestra autoseleccionada y no representativa; identidad/condición de cliente de pago no comprobadas. Fecha relativa varió entre capturas del servicio; no se obtuvo timestamp de Reddit.

### F10: Cursor: Stop, trabajo en segundo plano y notificaciones reencoladas

[Fuente pública](https://forum.cursor.com/t/agent-chat-stop-unpredictable-and-broken/171659). Publicación: 2026-09-14T19:28 (hora mostrada por el foro; zona no acreditada). Consulta: 2026-11-17. Localizador: Entradas 1, 9, 12 y 16; especialmente explicación y corrección del 18/09/2026.

OBSERVADO: usuario describe reanudaciones tras Stop. La respuesta de soporte del 18/09 atribuye un caso a notificaciones de trabajo finalizado reencoladas al cancelar; además corrige su consejo anterior porque Stop All no existía en ese layout.

HIPÓTESIS: cancelación durable debe impedir reactivar el trabajo por eventos tardíos; las instrucciones de recuperación deben corresponder a la superficie realmente mostrada.

PENDIENTE: cancelar antes/durante/después de finalizar un hijo, repetir notificación y reiniciar UI; verificar estado terminal monotónico, ninguna llamada adicional y consistencia entre historial y proceso.

**Límite:** Leímos el intercambio público, no los logs internos. No generalizar el diagnóstico a todo Cursor. El formulario dice CLI, pero versión y soporte lo sitúan en panel IDE.

### F11: Cursor: recuperación poco visible y límites de las reglas escritas

[Fuente pública](https://forum.cursor.com/t/very-ineffcient-constant-crashing-taking-forever/169219). Publicación: 2026-08-23T11:57 (hora mostrada por el foro; zona no acreditada). Consulta: 2026-11-17. Localizador: Entradas 8-9, 13-14 y 20-26; lectura incluye la recaída y la rectificación sobre planes separados.

OBSERVADO: usuario no encuentra restauración y describe fallos de una refactorización larga. Soporte reconoce controles de checkpoint que no se muestran en algunos chats y distingue instrucciones de bloqueos. Una mejora inicial relatada por el usuario no se mantiene en mensajes posteriores.

HIPÓTESIS: restauración debe ser descubrible fuera del hover y funcionar sin depender de un chat sano; las pausas de revisión deben imponerse por estado, no por prosa del plan.

PENDIENTE: historial paginado/reabierto, sesión cancelada y proyecto recuperado; localizar restauración sin ayuda y validar alcance antes de aplicar. Probar que el motor no atraviesa una puerta de revisión.

**Límite:** No tomar las explicaciones de RAM/contexto como causalidad probada: soporte pide logs adicionales. Parte final contiene una autodescripción del modelo, que tampoco es una autopsia técnica verificada.

### F13: Simon Willison: Agentic manual testing

[Fuente pública](https://simonwillison.net/guides/agentic-engineering-patterns/agentic-manual-testing/). Publicación: fecha no acreditada. Consulta: 2026-11-17. Localizador: Introducción; Using browser automation for web UIs; Have them take notes with Showboat.

OBSERVADO: Willison distingue pasar pruebas de ver el comportamiento real, recomienda ejercitar interfaces en navegador y conservar comandos con sus salidas y capturas como evidencia.

HIPÓTESIS: una entrega con pruebas automáticas y una secuencia real de uso reproducible reducirá afirmaciones de funcionamiento basadas solo en mocks.

PENDIENTE: demostración desde inicio limpio hasta resultado, cancelación y reanudación de historial; artefacto con versión, comando, salida y capturas. Registrar por separado lo bloqueado.

**Límite:** Experiencia y recomendación de un profesional; no muestra poblacional ni evidencia de que sus herramientas concretas sean las únicas válidas. Fecha de publicación no visible en el contenido obtenido.

### F14: Simon Willison: Anti-patterns, unreviewed code

[Fuente pública](https://simonwillison.net/guides/agentic-engineering-patterns/anti-patterns/). Publicación: fecha no acreditada. Consulta: 2026-11-17. Localizador: Inflicting unreviewed code on collaborators, lista y párrafo final.

OBSERVADO: Willison critica enviar cambios generados sin revisar y pide cambios pequeños, contexto verificable y evidencia de que quien entrega ha comprobado su funcionamiento y su descripción.

HIPÓTESIS: el criterio de avance debe ser una capacidad demostrada y revisable, no el número de archivos, skills, agentes o revisiones retóricas.

PENDIENTE: por PR enlazar un requisito, fallo reproducible cuando aplique, diff mínimo y prueba ejecutada; otro revisor debe poder repetirlo sin depender del relato del autor.

**Límite:** Mismo autor que F13: son dos páginas, no dos expertos independientes. Prescripción profesional, no ensayo controlado ni estudio de satisfacción. Fecha no visible.


## Método docente

### University of Cambridge

[Lecture 8: Usability evaluation methods](https://www.cl.cam.ac.uk/teaching/1011/HCI/HCI2010-lecture8.pdf). Human-Computer Interaction 2010–2011. Nivel: Material docente: diapositivas de métodos de evaluación. Localizador: PDF, páginas 1–3, 9, 11 y 13–15. Consulta: 2026-11-16.

OBSERVADO: distingue evaluación analítica y empírica; el recorrido cognitivo depende del conocimiento del usuario supuesto. Advierte contra introspección del creador, preguntas sesgadas y confundir significación con relevancia.

PROPUESTA: la revisión de agentes genera hipótesis de usabilidad; no equivale a observar personas ni a certificar preferencias.

**Comprobación propuesta:** Tras el recorrido cognitivo, observar tareas sin sugerencias; registrar intervenciones, variabilidad y tamaño del efecto cuando el diseño permita comparación.

**Límite:** Material histórico; no adoptar automáticamente sus ejemplos estadísticos ni umbrales. No hay participantes de Neural Office en esta investigación.

### University of California, Berkeley

[CS160 Pilot Usability Study Assignment — Grading Guidelines](https://people.eecs.berkeley.edu/~jfc/mattkam/cs160/pilotguidelines.pdf). CS160, rúbrica archivada del estudio piloto de usabilidad. Nivel: Material docente: rúbrica de método, resultados y discusión. Localizador: PDF, páginas 1–2. Consulta: 2026-11-16.

OBSERVADO: pide participantes y selección, tareas, procedimiento, medidas justificadas y resultados correspondientes. Requiere explicitar las interacciones simuladas y registrar incidentes críticos.

PROPUESTA: separar claramente simulación y funcionamiento real; cada medida prometida en el protocolo debe aparecer en resultados o figurar como no obtenida.

**Comprobación propuesta:** Predefinir tareas, errores, asistencia y tiempos; ejecutar el piloto, conservar los incidentes y comparar los datos obtenidos con las medidas declaradas.

**Límite:** Rúbrica histórica sin fecha inequívoca en el PDF; no atribuirle vigencia actual ni tratarla como estudio realizado.

### Princeton University

[COS 436 / ELE 469 — P6: Pilot Usability Test (Spring 2013)](https://www.cs.princeton.edu/courses/archive/spring13/cos436/project/P6.pdf). Guía de proyecto y protocolo piloto de usabilidad. Nivel: assignment_material. Localizador: The Assignment, apartados 1–4; texto extraído, líneas 12–75. Consulta: 2026-11-17.

Exige tareas significativas de distinta dificultad, consentimiento, métricas previas e incidentes con tiempo. Advierte que tres participantes y un prototipo preliminar difícilmente producen conclusiones estadísticas sólidas.

INFERIDO: usar pilotos para localizar fallos de comprensión; separar esos hallazgos de afirmaciones sobre superioridad o adopción.

**Comprobación propuesta:** PROPUESTO: observar crear una sesión, detenerla y recuperar un resultado; registrar errores, ayudas y tiempo por participante.

**Límite:** Guía archivada de 2013; su muestra académica no constituye una recomendación universal. No se ejecutó nuestro piloto.

### ETH Zürich

[Quantitative User Experience Research: Surveys and Logs Analysis](https://www.vvz.ethz.ch/Vorlesungsverzeichnis/lerneinheit.view?ansicht=KATALOGDATEN&lang=en&lerneinheitId=195819&semkez=2025W). 851-0257-00L, Autumn Semester 2025. Nivel: Currículo público detallado: objetivos, métodos y proyecto final. Localizador: Catalogue data, Abstract, Learning objective y Content; extracción web, líneas 28–41. Consulta: 2026-11-16.

OBSERVADO: relaciona preguntas de investigación con encuestas y logs; enseña consentimiento, selección, sesgo, inferencia y límites del análisis masivo. El proyecto debe evaluar y comunicar resultados.

PROPUESTA: instrumentar únicamente preguntas definidas, sin convertir la telemetría en vigilancia ni asumir que más muestras eliminan sesgos.

**Comprobación propuesta:** Definir evento mínimo, finalidad, consentimiento y retención; contrastar tareas observadas con logs y declarar qué población no está representada.

**Límite:** Currículo, no dataset, estudio ejecutado ni aval de una práctica concreta de telemetría.

### University College London (UCL)

[Interaction Design (COMP0021) — UCL Module Catalogue, 2026/27](https://www.ucl.ac.uk/module-catalogue/modules/interaction-design-COMP0021). Descripción curricular, resultados y organización de COMP0021. Nivel: catalog_description. Localizador: Description: Intended learning outcomes, Transferrable skills, Indicative content; líneas 39–76. Consulta: 2026-11-17.

Incluye seleccionar críticamente métodos, investigar usuarios, diseñar, prototipar y evaluar; separa investigación semanal de talleres prácticos vinculados al trabajo evaluado.

INFERIDO: elegir el método por la duda concreta, en lugar de acumular referencias y convertirlas en reglas estéticas universales.

**Comprobación propuesta:** PROPUESTO: justificar para cada duda si requiere observación de tareas, inspección heurística o medición de recursos, con criterio de salida.

**Límite:** Catálogo detallado; las previsualizaciones de clases requieren cuenta Moodle. No se inspeccionaron esas clases ni sus trabajos.
