# Descripciones de 91 repositorios: muestra y decisiones

Fecha de captura: 2026-11-16. **OBSERVADO**: introducciones, estructura del README, rutas de inicio, presentación visual y límites declarados. No se instalaron estos proyectos ni se validaron sus afirmaciones funcionales o licencias. Esta investigación editorial no certifica seguridad, titularidad, marcas ni popularidad.

Muestra intencional: cuatro búsquedas GitHub, máximo 30 resultados por consulta, deduplicación y trece referencias adyacentes. Consultas: `local AI agents stars:>100 archived:false`, `multi agent framework stars:>500 archived:false`, `local llm GUI stars:>200 archived:false`, `workflow automation self hosted stars:>500 archived:false`. Los filtros favorecen proyectos visibles; se incluyen tutoriales, frameworks e interfaces. No es una muestra aleatoria de competidores y no demuestra que el README cause estrellas. Los añadidos pueden tener un estado distinto al filtro inicial.

Se recuperaron 91 README completos. La revisión se centró en apertura, encabezados y recorrido visible; no fue una auditoría de 91 bases de código. El [registro JSON](evidence/README_SAMPLE_91.json) conserva ruta, SHA del blob, fecha, tamaño en líneas y señales detectadas fuera de bloques de código. Son localizadores léxicos: nulo significa patrón no encontrado, no capacidad inexistente. Los enlaces usan la rama observada y pueden cambiar; el SHA identifica el contenido capturado, no un commit.

## Decisiones aplicadas

1. Abrir con resultado y alcance: oficina de agentes locales como visión; auditoría HTML como capacidad probada. Separar futuro y presente.
2. Un recorrido Windows, ejemplo incluido y resultado esperado. No añadir Docker o lanzador Linux sin soporte para los Job Objects usados por el piloto.
3. Captura real etiquetada; sin fabricar demostraciones de funciones futuras ni copiar medios ajenos.
4. Badges de CI, Python y MIT con enlaces comprobables, sin simular certificaciones.
5. Beneficio del usuario y criterio de salida por hito. Experimentar en V6 con un skill declarativo y memoria de solo lectura, sin prometer promoción autónoma.
6. **Contraevidencia a la exclusividad:** `dontbemichael` presenta una oficina; Shannon anuncia presupuesto y aprobación; OpenCollab explica verificación de colaboración. El diferenciador debe ser la combinación implementada y demostrada, no una primacía sin investigar.
7. Privacidad por flujo y componentes. Local, sin claves y sin telemetría no son sinónimos universales. No deducir aislamiento de red del README ajeno.
8. No inventar fechas sin estimación de capacidad. Ordenar hitos por pruebas de aceptación y ofrecer una visión breve para usuarios.

## Registro individual

Inicio, contribución y límites son los primeros encabezados detectados del vocabulario documentado en el registro. Los números indican líneas del README capturado. Observaciones propias: no se redistribuyen README completos, imágenes ni código de terceros.

| # | Fuente | Inicio / contribución / límites | Observación editorial |
| --- | --- | --- | --- |
| 1 | [mudler/LocalAI](https://github.com/mudler/LocalAI/blob/master/README.md#L1) | 31 / — / 189 | Resultado y hardware al inicio; distingue builds de desarrollo del recorrido de instalación. |
| 2 | [pguso/ai-agents-from-scratch](https://github.com/pguso/ai-agents-from-scratch/blob/main/README.md#L1) | 48 / 423 / 43 | Propósito educativo y requisitos explícitos; no confundir tutorial con producto instalable. |
| 3 | [amd/gaia](https://github.com/amd/gaia/blob/main/README.md#L1) | 30 / 167 / 124 | Separa usuarios y desarrolladores; declara plataforma y alternativa en nube. |
| 4 | [Kc1t/alethe-agents](https://github.com/Kc1t/alethe-agents/blob/main/README.md#L1) | 288 / 352 / 498 | Presenta plataforma compatible y acceso a instalación, roadmap y contribución. |
| 5 | [dcSpark/shinkai-local-ai-agents](https://github.com/dcSpark/shinkai-local-ai-agents/blob/main/README.md#L1) | 84 / 272 / 92 | Demostración y ejemplos separados; explica uso local o remoto. |
| 6 | [mudler/LocalAGI](https://github.com/mudler/LocalAGI/blob/main/README.md#L1) | 48 / — / 25 | Propuesta local visible; no adoptar promesas absolutas de privacidad sin pruebas. |
| 7 | [kwindla/macos-local-voice-agents](https://github.com/kwindla/macos-local-voice-agents/blob/main/README.md#L1) | — / — / — | Ejemplo concreto de voz con hardware y modelos delimitados. |
| 8 | [nexu-io/open-design](https://github.com/nexu-io/open-design/blob/main/README.md#L1) | 246 / 502 / 91 | Recorrido visual y plataformas; la promoción inicial retrasa la explicación del producto. |
| 9 | [pguso/agents-from-scratch](https://github.com/pguso/agents-from-scratch/blob/main/README.md#L1) | 66 / 153 / 161 | Público y límites del material educativo identificados. |
| 10 | [agentvivekkumar/dontbemichael](https://github.com/agentvivekkumar/dontbemichael/blob/main/README.md#L1) | 274 / 375 / 382 | Oficina para pequeños negocios y memoria como resultado; el concepto oficina tiene precedentes. |
| 11 | [Fosowl/agenticSeek](https://github.com/Fosowl/agenticSeek/blob/main/README.md#L1) | — / 786 / 38 | Demostración y arranque rápido; distinguir operación local de proveedores opcionales. |
| 12 | [localgpt-app/localgpt](https://github.com/localgpt-app/localgpt/blob/main/README.md#L1) | 25 / 226 / 232 | Tabla por plataformas y componentes; el nombre no basta para deducir el producto actual. |
| 13 | [sugarforever/chat-ollama](https://github.com/sugarforever/chat-ollama/blob/main/README.md#L1) | — / — / — | Entrada breve con función principal y componentes locales o alojados. |
| 14 | [yoanbernabeu/grepai](https://github.com/yoanbernabeu/grepai/blob/main/README.md#L1) | 36 / 132 / 136 | Beneficio de búsqueda explicado pronto; no trasladar cifras de ahorro sin medirlas. |
| 15 | [vastsa/PI-Desktop](https://github.com/vastsa/PI-Desktop/blob/main/README.md#L1) | 515 / 689 / 737 | Propuesta, plataformas y descarga visibles antes de los detalles. |
| 16 | [unifapi-agent/agents](https://github.com/unifapi-agent/agents/blob/main/README.md#L1) | 15 / — / 142 | Explicita servicio, autenticación y créditos; no confundirlo con un runtime exclusivamente local. |
| 17 | [zvec-ai/zvec-grep](https://github.com/zvec-ai/zvec-grep/blob/main/README.md#L1) | — / 231 / — | Muestra demo y ejemplo para probar antes de los benchmarks. |
| 18 | [brenpoly/be-more-agent](https://github.com/brenpoly/be-more-agent/blob/main/README.md#L1) | 59 / — / 22 | Delimita un equipo concreto y sus requisitos antes de instalar. |
| 19 | [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp/blob/main/README.md#L1) | 69 / — / 1164 | Distingue servidor MCP y visor opcional; describe descargas adicionales. |
| 20 | [u14app/neo-chat](https://github.com/u14app/neo-chat/blob/main/README.md#L1) | 45 / 111 / 131 | Historial local y proveedores remotos son dimensiones distintas de privacidad. |
| 21 | [sauravpanda/BrowserAI](https://github.com/sauravpanda/BrowserAI/blob/main/README.md#L1) | 61 / 264 / 274 | Demo y quickstart visibles; madurez anunciada requiere evidencia propia. |
| 22 | [PurpleDoubleD/locally-uncensored](https://github.com/PurpleDoubleD/locally-uncensored/blob/master/README.md#L1) | 34 / — / 280 | Recorrido instalar, elegir y comenzar; nube opcional merece etiqueta separada. |
| 23 | [AgriciDaniel/claude-seo](https://github.com/AgriciDaniel/claude-seo/blob/main/README.md#L1) | 198 / 383 / 383 | Resultado comercial y ejemplos visibles; evitar copiar tiempos o resultados prometidos. |
| 24 | [sickn33/agentic-awesome-skills](https://github.com/sickn33/agentic-awesome-skills/blob/main/README.md#L1) | 100 / 183 / 814 | Disponibilidad interrumpida del paquete comunicada pronto; estado operativo útil. |
| 25 | [tickernelz/opencode-mem](https://github.com/tickernelz/opencode-mem/blob/main/README.md#L1) | 118 / 785 / 60 | Requisitos y migraciones accesibles; la captura automática de memoria exige explicar el alcance. |
| 26 | [Generated-Computers/Locals](https://github.com/Generated-Computers/Locals/blob/main/README.md#L1) | 267 / — / 517 | Expone resultados y también escenarios donde no mejora la velocidad. |
| 27 | [microsoft/magentic-ui](https://github.com/microsoft/magentic-ui/blob/main/README.md#L1) | 53 / — / 93 | Control humano, demostración y arranque; nombre visible distinto del identificador del repositorio. |
| 28 | [musistudio/claude-code-router](https://github.com/musistudio/claude-code-router/blob/main/README.md#L1) | 128 / — / 533 | Tagline corto y puesta en marcha; explicar la función de intermediario. |
| 29 | [neuledge/context](https://github.com/neuledge/context/blob/main/README.md#L1) | 47 / 654 / 722 | Problema concreto de documentación desactualizada con contraste de ejemplos. |
| 30 | [MartinDelophy/ai-video-editor](https://github.com/MartinDelophy/ai-video-editor/blob/main/README.md#L1) | 190 / — / 230 | Enumera funciones acotadas y uso responsable; explicita almacenamiento remoto. |
| 31 | [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents/blob/main/README.md#L1) | 112 / 403 / — | Organiza roles y arquitectura, pero las novedades preceden al arranque y las APIs requeridas. |
| 32 | [microsoft/agent-framework](https://github.com/microsoft/agent-framework/blob/main/README.md#L1) | 79 / 223 / — | Pregunta por adecuación al usuario antes de características y quickstart. |
| 33 | [openai/openai-agents-python](https://github.com/openai/openai-agents-python/blob/main/README.md#L1) | 25 / 165 / — | Conceptos mínimos, instalación y primer agente; imagen de trazas en la apertura. |
| 34 | [FoundationAgents/MetaGPT](https://github.com/FoundationAgents/MetaGPT/blob/main/README.md#L1) | 50 / 148 / — | Metáfora de empresa con roles; instalación, configuración y vídeo diferenciados. |
| 35 | [VRSEN/agency-swarm](https://github.com/VRSEN/agency-swarm/blob/main/README.md#L1) | 30 / 237 / 41 | Origen del framework y aviso de migración visibles al comienzo. |
| 36 | [Kocoro-lab/Shannon](https://github.com/Kocoro-lab/Shannon/blob/main/README.md#L1) | 38 / 479 / 40 | Presupuestos, aprobación y depuración ya aparecen en otros proyectos; evitar exclusividad. |
| 37 | [agentuniverse-ai/agentUniverse](https://github.com/agentuniverse-ai/agentUniverse/blob/master/README.md#L1) | 61 / — / — | Definición directa, ejemplo inicial y plataforma visual posterior. |
| 38 | [fastclaw-ai/fastclaw](https://github.com/fastclaw-ai/fastclaw/blob/dev/README.md#L1) | 57 / — / 426 | Tagline, captura y recorrido por consola; distingue primer uso y arquitectura. |
| 39 | [SciSharp/BotSharp](https://github.com/SciSharp/BotSharp/blob/master/README.md#L1) | 34 / — / — | Define utilidad para aplicaciones de negocio; módulos, plugins y FAQ separados. |
| 40 | [openai/openai-agents-js](https://github.com/openai/openai-agents-js/blob/main/README.md#L1) | 23 / 110 / — | Entornos compatibles antes de instalar y ejemplos por modalidad. |
| 41 | [oxwhirl/pymarl](https://github.com/oxwhirl/pymarl/blob/master/README.md#L1) | 18 / — / 100 | Advertencia de comparabilidad experimental antes de instalar; benchmark depende de versiones. |
| 42 | [ageerle/ruoyi-ai](https://github.com/ageerle/ruoyi-ai/blob/main/README.md#L1) | — / 215 / 229 | Demo, arquitectura y despliegue; imágenes fijadas merecen explicación explícita. |
| 43 | [openai/swarm](https://github.com/openai/swarm/blob/main/README.md#L1) | 10 / 350 / — | Estado experimental y sustitución por otro SDK declarados en la apertura. |
| 44 | [Mnehmos/mnehmos.multi-agent.framework](https://github.com/Mnehmos/mnehmos.multi-agent.framework/blob/main/README.md#L1) | 51 / — / 233 | Metáfora memorable con tabla de componentes y plantillas por nivel. |
| 45 | [kyegomez/swarms](https://github.com/kyegomez/swarms/blob/master/README.md#L1) | 54 / 740 / 819 | Instalación por varios gestores; demasiadas rutas pueden diluir el primer recorrido. |
| 46 | [sdi2200262/agentic-project-management](https://github.com/sdi2200262/agentic-project-management/blob/main/README.md#L1) | 22 / 86 / 92 | Problema del contexto explicado antes de documentación y contribución. |
| 47 | [sentient-agi/ROMA](https://github.com/sentient-agi/ROMA/blob/main/README.md#L1) | 138 / — / 928 | Beta explícita; separa evaluación mínima y despliegue completo. |
| 48 | [camel-ai/camel](https://github.com/camel-ai/camel/blob/master/README.md#L1) | 232 / 559 / 588 | Organiza casos por resultados: datos, automatización y simulación. |
| 49 | [heurist-network/heurist-agent-framework](https://github.com/heurist-network/heurist-agent-framework/blob/main/README.md#L1) | 92 / 240 / 236 | Interfaces y requisito de clave aparecen antes de la arquitectura modular. |
| 50 | [microsoft/agent-framework-go](https://github.com/microsoft/agent-framework-go/blob/main/README.md#L1) | 97 / 191 / 216 | Selección por adecuación y ejemplos; lenguaje compatible se explicita. |
| 51 | [Pan-Chera/Multi-Agent-CAD](https://github.com/Pan-Chera/Multi-Agent-CAD/blob/main/README.md#L1) | 161 / — / 349 | Resultado de ingeniería y galerías; tecnología preliminar etiquetada. |
| 52 | [microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator](https://github.com/microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator/blob/main/README.md#L1) | 70 / — / 92 | Separa valor empresarial, arquitectura, requisitos y costes. |
| 53 | [trypromptly/LLMStack](https://github.com/trypromptly/LLMStack/blob/main/README.md#L1) | 21 / 114 / — | Resultado sin código y conexiones a datos; oferta alojada separada. |
| 54 | [LazyAGI/LazyLLM](https://github.com/LazyAGI/LazyLLM/blob/main/README.md#L1) | 177 / — / — | Ejemplos de aplicaciones antes de requisitos e instalación. |
| 55 | [datawhalechina/handy-multi-agent](https://github.com/datawhalechina/handy-multi-agent/blob/main/README.md#L1) | — / 160 / 207 | Tutorial con audiencia, objetivos y recorrido de capítulos. |
| 56 | [raga-ai-hub/RagaAI-Catalyst](https://github.com/raga-ai-hub/RagaAI-Catalyst/blob/main/README.md#L1) | 21 / — / — | Catálogo de operaciones con configuración previa a ejemplos. |
| 57 | [mll-lab-nu/RAGEN](https://github.com/mll-lab-nu/RAGEN/blob/main/README.md#L1) | 104 / 192 / — | Diagnóstico de fallos y cambios del algoritmo como eje de la descripción. |
| 58 | [InternLM/MindSearch](https://github.com/InternLM/MindSearch/blob/main/README.md#L1) | 31 / — / 150 | Demo temprana y pasos separados para backend, frontend y buscador. |
| 59 | [RISE-X-Lab/OpenCollab](https://github.com/RISE-X-Lab/OpenCollab/blob/main/README.md#L1) | 49 / — / 183 | La verificación de colaboración es una propuesta existente; documentación muestra cómo comprobarla. |
| 60 | [darrenhinde/OpenAgentsControl](https://github.com/darrenhinde/OpenAgentsControl/blob/main/README.md#L1) | 119 / 788 / 820 | Aviso temprano de transición incompatible; no tomar garantías repetibles como mediciones. |
| 61 | [HelgeSverre/ollama-gui](https://github.com/HelgeSverre/ollama-gui/blob/main/README.md#L1) | 41 / — / 126 | Captura y definición simple; sección expresa sobre ubicación de conversaciones. |
| 62 | [techjarves/Portable-Local-Studio](https://github.com/techjarves/Portable-Local-Studio/blob/main/README.md#L1) | 184 / — / 223 | Galería y motores por modalidad; validar cada afirmación multiplataforma por separado. |
| 63 | [KunAgent/Kun](https://github.com/KunAgent/Kun/blob/master/README.md#L1) | 57 / 135 / 80 | Beneficio local, comienzo en tres pasos, permisos y ejecución desde fuentes. |
| 64 | [ImDarkTom/LlamaPen](https://github.com/ImDarkTom/LlamaPen/blob/main/README.md#L1) | 19 / — / 103 | Vista previa junto a definición; proveedores, uso local y nube separados. |
| 65 | [moly-ai/moly-ai](https://github.com/moly-ai/moly-ai/blob/main/README.md#L1) | 13 / 306 / 79 | Madurez temprana declarada antes de descargas; construcción por plataforma. |
| 66 | [LangGraph-GUI/LangGraph-GUI](https://github.com/LangGraph-GUI/LangGraph-GUI/blob/main/README.md#L1) | 19 / 51 / 9 | Requisitos separados por sistema; despliegue incluye componentes adicionales. |
| 67 | [hogeheer499-commits/strix-halo-guide](https://github.com/hogeheer499-commits/strix-halo-guide/blob/main/README.md#L1) | 24 / 3 / 134 | Audiencia y estado de la evidencia explícitos; tutorial de hardware específico. |
| 68 | [See-Sol-Lab/DeepSeekGUI](https://github.com/See-Sol-Lab/DeepSeekGUI/blob/main/README.md#L1) | 50 / 217 / 163 | Descarga, comienzo y capturas antes de la lista detallada de capacidades. |
| 69 | [aivrar/portable-hermes-agent](https://github.com/aivrar/portable-hermes-agent/blob/main/README.md#L1) | 76 / — / 188 | Organiza herramientas por grupos, módulos y modo guiado; no basta enumerar cantidades. |
| 70 | [BIGPPWONG/EdgeBox](https://github.com/BIGPPWONG/EdgeBox/blob/main/README.md#L1) | 162 / — / 158 | Sandbox de escritorio y herramientas MCP; promoción de otro proyecto ocupa la apertura. |
| 71 | [lukaszliniewicz/Pandrator](https://github.com/lukaszliniewicz/Pandrator/blob/main/README.md#L1) | — / — / 347 | Resultados comprensibles y primer flujo; ayuda a elegir el primer modelo. |
| 72 | [n8n-io/n8n](https://github.com/n8n-io/n8n/blob/master/README.md#L1) | 18 / 61 / 49 | Captura, capacidades y quickstart breves; distingue licencia fair-code de otras etiquetas. |
| 73 | [langgenius/dify](https://github.com/langgenius/dify/blob/main/README.md#L1) | 66 / 150 / 178 | Acceso alojado, autohospedado y documentación diferenciados. |
| 74 | [8gears/n8n-helm-chart](https://github.com/8gears/n8n-helm-chart/blob/main/README.md#L1) | 68 / — / 19 | Requisitos operativos antes del chart; contribución solicitada con alcance concreto. |
| 75 | [datawranglerai/self-host-n8n-on-gcr](https://github.com/datawranglerai/self-host-n8n-on-gcr/blob/main/README.md#L1) | — / — / 30 | Guía de despliegue con persistencia, requisitos y pasos; no equiparar autohospedado con offline. |
| 76 | [Git-Agni/prod-FARM-IOS-Core](https://github.com/Git-Agni/prod-FARM-IOS-Core/blob/main/README.md#L1) | — / — / — | Alcance de aplicación y condiciones de autenticación definidos al inicio. |
| 77 | [himovo/movo](https://github.com/himovo/movo/blob/main/README.md#L1) | — / 245 / 150 | Demo y comienzo rápido; edición comunitaria y operaciones delimitadas. |
| 78 | [bytechefhq/bytechef](https://github.com/bytechefhq/bytechef/blob/master/README.md#L1) | 75 / 274 / 280 | Tagline y quickstart; alcance comunitario y empresarial visible en licencia. |
| 79 | [crewAIInc/crewAI](https://github.com/crewAIInc/crewAI/blob/main/README.md#L1) | 152 / 554 / 621 | Roles, flows y plataforma comercial separados; la marca no identifica toda la distribución. |
| 80 | [open-webui/open-webui](https://github.com/open-webui/open-webui/blob/main/README.md#L1) | 42 / — / 114 | Propuesta sencilla distingue modelos locales y APIs compatibles, incluyendo nube. |
| 81 | [ollama/ollama](https://github.com/ollama/ollama/blob/main/README.md#L1) | 11 / — / — | Descargas por plataforma y primer uso; no ejecutar instaladores ajenos durante esta revisión. |
| 82 | [nomic-ai/gpt4all](https://github.com/nomic-ai/gpt4all/blob/main/README.md#L1) | 31 / 116 / — | Resultado para equipos cotidianos con enlaces de descarga antes de la API. |
| 83 | [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/README.md#L1) | 20 / 121 / — | Quickstart antes del detalle; backends compatibles y contribución accesibles. |
| 84 | [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph/blob/main/README.md#L1) | — / — / — | Orquestación con estado: presenta el nivel de abstracción y enlaces al ecosistema. |
| 85 | [langflow-ai/langflow](https://github.com/langflow-ai/langflow/blob/main/README.md#L1) | 36 / 99 / 85 | Aplicación de escritorio, instalación local y despliegue como rutas distintas. |
| 86 | [FlowiseAI/Flowise](https://github.com/FlowiseAI/Flowise/blob/main/README.md#L1) | 39 / 229 / 95 | Quickstart para uso y recorrido para desarrolladores separados. |
| 87 | [Mintplex-Labs/anything-llm](https://github.com/Mintplex-Labs/anything-llm/blob/master/README.md#L1) | — / 260 / 213 | Resumen de producto, compatibilidad y sección dedicada a telemetría y privacidad. |
| 88 | [continuedev/continue](https://github.com/continuedev/continue/blob/main/README.md#L1) | — / 47 / 61 | Estado de mantenimiento y versión final visibles; no recomendar por fama histórica. |
| 89 | [Aider-AI/aider](https://github.com/Aider-AI/aider/blob/main/README.md#L1) | 103 / — / — | Resultado y screencast preceden capacidades; cubre modelos locales y alojados. |
| 90 | [OpenHands/OpenHands](https://github.com/OpenHands/OpenHands/blob/main/README.md#L1) | 49 / — / — | Nombre de producto actualizado y opciones con o sin sandbox; fronteras de repositorio explícitas. |
| 91 | [simstudioai/sim](https://github.com/simstudioai/sim/blob/main/README.md#L1) | 21 / 174 / 51 | Separa nube, autohospedado y escritorio; seguridad y gobierno tienen sección propia. |
