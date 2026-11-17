# Investigación V5.5–V6: decisiones y contraevidencia

Ventana de consulta: 16–17 de noviembre de 2026. **OBSERVADO:** 80 repositorios distintos consultados mediante la conexión GitHub, 20 instituciones y 14 fuentes públicas leídas sobre experiencia de uso/práctica profesional. Se distribuyó el trabajo entre 20 subagentes distintos, en tandas de hasta tres trabajadores además del coordinador; no hubo veinte procesos simultáneos. La coordinación no elimina la necesidad de revisar sus resultados.

La profundidad es una pieza seleccionada por repositorio: 73 registros `source-inspected`, dos `test-source-inspected-not-executed`, uno `test-source-inspected-skipped-not-executed`, dos `docs-inspected`, un contrato y un contrato propuesto. Ningún test ajeno fue ejecutado. **No son 80 auditorías completas**, 20 avales universitarios ni una muestra representativa de compradores. Dos URLs de X devolvieron 403: se conserva la limitación, no contenido inventado. No se ha consultado un ranking para llamarlas las veinte mejores universidades.

## Qué cambia nuestra manera de trabajar

| Evidencia observada | Error que evita en Neural Office | Decisión y comprobación |
|---|---|---|
| T3 vincula identidad de comando y conflicto de payload; OpenClaw limita su deduplicación al contexto | Confundir doble clic bloqueado con idempotencia durable | La reserva precede al worker; identidad persistida antes de enviar; respuesta perdida se consulta, no se vuelve a ejecutar con una clave nueva. Pruebas de crash y reapertura |
| Codex reevalúa aprobación/cancelación; Claude Code publica reglas de hooks con alcance limitado | Dar autoridad a la UI, al modelo o a una aprobación caducada | Fuente congelada + revisión + alcance + sesión; comprobar autorización en el punto del efecto |
| Dusk detecta desacuerdos entre estado, eventos y resultados | Pintar éxito porque terminó una animación | Estado del ledger y artefacto comprobado; lo desconocido se presenta explícitamente. Su detector no garantiza todas las mutaciones |
| VS Code conserva cancelación anterior a crear el token; Cursor describe notificaciones que reactivaban trabajo | Tratar Detener como un efecto momentáneo | Latch de parada anterior al spawn; evitar resurrección por mensajes tardíos; prueba con barreras |
| Zustand usa generaciones; TanStack distingue rollback optimista de efecto externo | Aceptar una respuesta vieja y borrar presupuesto/resultado nuevos | Identidad/revisión y cursores independientes; pruebas React con respuesta de eventos diferida |
| Radix/React Spectrum distinguen foco, interacción y contenido dinámico | Creer que tener ARIA o aprobar un scanner basta | Teclado, IME, modal, restauración de foco y lector de pantalla por tarea; lo no probado permanece pendiente |
| Ollama/llama.cpp y motores afines administran contexto, colas y memoria con restricciones distintas | Suponer que siete roles requieren siete modelos, o que más contexto siempre ayuda | Un modelo serial de base; comparar 0/1/3/7 por utilidad, carga, CPU, RAM y latencia. GPU sólo tras medir |
| Promptfoo conserva cachés; Ragas admite resultados no evaluables; OTel puede perder telemetría | Contar un cache hit como nuevo ensayo o convertir falta de observación en cero | Experimentos independientes, observaciones incompletas visibles; logs de observación no son el ledger de autoridad |
| Feedback Reddit discrepa sobre la densidad y reporta problemas en monitor vertical | Imponer una estética como supuesto consenso | Misma tarea en dos densidades/tamaños; medir comprensión, errores y recuperación antes de preferencia |
| Currículos y materiales HCI piden tareas, criterios y observación | Confundir opinión del autor o de otro modelo con prueba de usuarios | Protocolo formativo predefinido, consentimiento, fallos y ayudas registrados; sin promesas de cuota de mercado |

**INFERIDO, hipótesis de identidad:** Neural Office puede distinguirse por un encargo con fuente explícita, ejecución controlada y una entrega que se puede revisar y recuperar. No está demostrada su superioridad comercial. La interfaz debe hacer visibles esas propiedades en el compositor, la aprobación, la entrega y el historial; añadir cards, paneles, roles o animaciones no las crea.

## Cómo leer y reutilizar la evidencia

Cada fila del [inventario de repositorios](research/V5_5_REPOSITORIES.json) incluye SHA, archivo, líneas, mecanismo, límite y licencia. Las decisiones finales están en [la hoja de ruta](V5_5_TO_V6.md) y [siete skills nuevas de desarrollo](../skills/README.md). Se toma el principio de ingeniería; no se importan componentes por popularidad. No se copió código o diseño de Dusk, Claude Code, tldraw, AFFiNE ni Outline.

Licencias requieren alcance: Dusk usa PolyForm Noncommercial; Claude Code no equivale a un motor MIT completo; tldraw/editor y Outline tienen condiciones restrictivas; AFFiNE/backend distingue su licencia empresarial. Phoenix distingue raíz y cliente; AutoGen código y documentación; Zed raíz y GPUI. Las entradas detallan las fuentes leídas. No son dependencias del producto por estar en la investigación.

## Los 80 repositorios: mapa de inspecciones


### Agent workflows

| Repositorio / fuente fijada | Alcance leído |
|---|---|
| [pingdotgg/t3code](https://github.com/pingdotgg/t3code/blob/747ed9c5b1d9b2d41638ef94003bda1d996f4353/apps/server/src/orchestration-v2/Orchestrator.receipt-race.test.ts#L69) · `747ed9c5` | source-inspected · `apps/server/src/orchestration-v2/Orchestrator.receipt-race.test.ts`:69-111 |
| [DuskBotAI/duskbot](https://github.com/DuskBotAI/duskbot/blob/750caf446d0417b95971e7bb2c7ac98ba76f94e0/server/runtime/invariants.ts#L37) · `750caf44` | source-inspected · `server/runtime/invariants.ts`:37-99 |
| [openclaw/openclaw](https://github.com/openclaw/openclaw/blob/6a6007663b36db8badd6967e7f2bed5c6b3a724e/src/gateway/server-methods/session-create-idempotency.ts#L32) · `6a600766` | source-inspected · `src/gateway/server-methods/session-create-idempotency.ts`:32-35,58-75,91-136,139-198 |
| [openai/codex](https://github.com/openai/codex/blob/d5a478e31c3296e544d53424a7a6c995e7dfb0f5/codex-rs/core/src/tools/approvals.rs#L525) · `d5a478e3` | source-inspected · `codex-rs/core/src/tools/approvals.rs`:525-547,594-640,687-705,807-864 |
| [anthropics/claude-code](https://github.com/anthropics/claude-code/blob/8a17c18509e5b76f8f3029d47d2538c99f6930ed/mods/sec-default/hooks/policy/managed-tools-restored/managed-tools-restored.ts#L9) · `8a17c185` | source-inspected · `mods/sec-default/hooks/policy/managed-tools-restored/managed-tools-restored.ts`:9-30,32-86 |
| [anomalyco/opencode](https://github.com/anomalyco/opencode/blob/c0a7beb6d9e3f32c7e896bc28998376f04f7306a/packages/core/src/permission.ts#L20) · `c0a7beb6` | source-inspected · `packages/core/src/permission.ts`:20,94-103,141-157,169-209 |
| [cline/cline](https://github.com/cline/cline/blob/146894b6a42a7a554c6ff37f7bb33fe5122cc33d/sdk/packages/core/src/session/checkpoint-restore.ts#L42) · `146894b6` | source-inspected · `sdk/packages/core/src/session/checkpoint-restore.ts`:42-153,156-199 |
| [RooCodeInc/Roo-Code](https://github.com/RooCodeInc/Roo-Code/blob/b867ec9145750d0ae1ff7f02d35406e9bf2a0b16/src/core/webview/checkpointRestoreHandler.ts#L26) · `b867ec91` | source-inspected · `src/core/webview/checkpointRestoreHandler.ts`:26-87,94-103 |
### Desktop and IPC

| Repositorio / fuente fijada | Alcance leído |
|---|---|
| [tauri-apps/tauri](https://github.com/tauri-apps/tauri/blob/4acdc0a2230ced11567a90962b07eedfa53dc3d2/crates/tauri-utils/src/acl/capability.rs#L77) · `4acdc0a2` | source-inspected · `crates/tauri-utils/src/acl/capability.rs`:77-86,128-174 |
| [tauri-apps/plugins-workspace](https://github.com/tauri-apps/plugins-workspace/blob/21f01aa3d5d171f7e5deb5262480bb6ae20e3d0c/plugins/shell/src/commands.rs#L79) · `21f01aa3` | source-inspected · `plugins/shell/src/commands.rs`:79-96,103-163 |
| [electron/electron](https://github.com/electron/electron/blob/ca3e18572bbfa2645a15e7c0e81f2319f1dcb7a7/docs/tutorial/security.md#L743) · `ca3e1857` | docs-inspected · `docs/tutorial/security.md`:743-777,780-799 |
| [microsoft/vscode](https://github.com/microsoft/vscode/blob/a3cabfed1ada486415b1d3b4fff66bb2d47771ac/src/vs/base/common/cancellation.ts#L86) · `a3cabfed` | source-inspected · `src/vs/base/common/cancellation.ts`:86-120,123-167 |
| [zed-industries/zed](https://github.com/zed-industries/zed/blob/482e76524bd33d8cbdfc352f1fef3eefbf2fad92/crates/gpui/src/executor.rs#L144) · `482e7652` | source-inspected · `crates/gpui/src/executor.rs`:144-185,188-234,519-557 |
| [lmstudio-ai/lms](https://github.com/lmstudio-ai/lms/blob/138dcffbc40e5fe3d9c0d38cf75dcdc1d883d849/src/subcommands/load.test.ts#L7) · `138dcffb` | source-inspected · `src/subcommands/load.test.ts`:7-68,130-176 |
| [browser-use/browser-use](https://github.com/browser-use/browser-use/blob/4b5b1b0aa0ab45a1d6a2a31984d37d3e748c0134/browser_use/domains.py#L1) · `4b5b1b0a` | source-inspected · `browser_use/domains.py`:1-19,57-95,101-119,140-175 |
| [continuedev/continue](https://github.com/continuedev/continue/blob/5522c6f44ca0ac3528b37244818fbfa39b5af470/core/tools/policies/fileAccess.ts#L10) · `5522c6f4` | source-inspected · `core/tools/policies/fileAccess.ts`:10-25 |
### Accessibility

| Repositorio / fuente fijada | Alcance leído |
|---|---|
| [radix-ui/primitives](https://github.com/radix-ui/primitives/blob/eb3a2b7091293e27df8f9ba906632d8daa3d81a3/packages/react/focus-scope/src/focus-scope.tsx#L69) · `eb3a2b70` | source-inspected · `packages/react/focus-scope/src/focus-scope.tsx`:69-85,113-160,165-205,207-237 |
| [adobe/react-spectrum](https://github.com/adobe/react-spectrum/blob/360e35170568dfc99a2baaa78e6b7bdd36458d91/packages/react-aria/src/live-announcer/LiveAnnouncer.tsx#L13) · `360e3517` | source-inspected · `packages/react-aria/src/live-announcer/LiveAnnouncer.tsx`:13-55,58-75,121-162 |
| [ariakit/ariakit](https://github.com/ariakit/ariakit/blob/7f394c8d3e9a91b163b2aeff6f6ff07eddf5e908/packages/ariakit-react-components/src/dialog/dialog.tsx#L240) · `7f394c8d` | source-inspected · `packages/ariakit-react-components/src/dialog/dialog.tsx`:240-278,285-296,305-325,353-398 |
| [reach/reach-ui](https://github.com/reach/reach-ui/blob/b3d94d22811db6b5c0f272b9a7e2e3c1bb4699ae/packages/dialog/src/reach-dialog.tsx#L142) · `b3d94d22` | source-inspected · `packages/dialog/src/reach-dialog.tsx`:142-190 |
| [shadcn-ui/ui](https://github.com/shadcn-ui/ui/blob/e62c9435fff729a175f38983dee73b2cb4f6a069/apps/v4/registry/new-york-v4/ui/dialog.tsx#L50) · `e62c9435` | source-inspected · `apps/v4/registry/new-york-v4/ui/dialog.tsx`:50-80,121-143 |
| [tailwindlabs/headlessui](https://github.com/tailwindlabs/headlessui/blob/eea57cf46fd6767ed1059012f7073b88eb159fba/packages/@headlessui-react/src/components/focus-trap/focus-trap.tsx#L51) · `eea57cf4` | source-inspected · `packages/@headlessui-react/src/components/focus-trap/focus-trap.tsx`:51-72,91-121,147-199 |
| [jsx-eslint/eslint-plugin-jsx-a11y](https://github.com/jsx-eslint/eslint-plugin-jsx-a11y/blob/8f75961d965e47afb88854d324bd32fafde7acfe/src/rules/no-static-element-interactions.js#L30) · `8f75961d` | source-inspected · `src/rules/no-static-element-interactions.js`:30-46,63-94,115-121 |
| [dequelabs/axe-core](https://github.com/dequelabs/axe-core/blob/e80f6b797b32b5f9d60ddaa0a7afad6ed864f121/lib/checks/color/color-contrast-evaluate.js#L20) · `e80f6b79` | source-inspected · `lib/checks/color/color-contrast-evaluate.js`:20-80,130-187 |
### Workflow semantics

| Repositorio / fuente fijada | Alcance leído |
|---|---|
| [statelyai/xstate](https://github.com/statelyai/xstate/blob/8e53990c2f9318d2d649b8af1a3c96af970d9bf2/packages/core/src/actors/promise.ts#L455) · `8e53990c` | source-inspected · `packages/core/src/actors/promise.ts`:455-479,482-555 |
| [temporalio/sdk-python](https://github.com/temporalio/sdk-python/blob/968c3c9dcf508ceca3f4e34b9ea910425351f6c5/temporalio/common.py#L37) · `968c3c9d` | source-inspected · `temporalio/common.py`:37-60,77-108 |
| [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph/blob/02f2c2e6c992ffccce9e9129781fdd04f015c6fa/libs/langgraph/langgraph/pregel/_retry.py#L633) · `02f2c2e6` | source-inspected · `libs/langgraph/langgraph/pregel/_retry.py`:633-681,752-807,825-843 |
| [microsoft/autogen](https://github.com/microsoft/autogen/blob/8390985108cb1e3881f5f7297765758d8ad2540c/python/packages/autogen-agentchat/src/autogen_agentchat/conditions/_terminations.py#L62) · `83909851` | source-inspected · `python/packages/autogen-agentchat/src/autogen_agentchat/conditions/_terminations.py`:62-104,235-291 |
| [crewAIInc/crewAI](https://github.com/crewAIInc/crewAI/blob/96c4d85b6423dd06b7f1c38f12dd472399c6ce43/lib/crewai/src/crewai/flow/persistence/sqlite.py#L192) · `96c4d85b` | source-inspected · `lib/crewai/src/crewai/flow/persistence/sqlite.py`:192-215,285-327 |
| [openai/openai-agents-python](https://github.com/openai/openai-agents-python/blob/25e7b2e40258cc0910159f35d463b64582ec83f6/src/agents/run_context.py#L556) · `25e7b2e4` | source-inspected · `src/agents/run_context.py`:556-607,831-872,1341-1366 |
| [pydantic/pydantic-ai](https://github.com/pydantic/pydantic-ai/blob/04f27ffdc8d364f9376fad17d6115b31070fa8dc/pydantic_ai_slim/pydantic_ai/usage.py#L426) · `04f27ffd` | source-inspected · `pydantic_ai_slim/pydantic_ai/usage.py`:426-438,547-595,633-654,681-736 |
| [PrefectHQ/prefect](https://github.com/PrefectHQ/prefect/blob/d9fcfa0815b0885f21e0d0566fcd6027cc1c6869/src/prefect/transactions.py#L299) · `d9fcfa08` | source-inspected · `src/prefect/transactions.py`:299-314,335-395,422-453 |
### Persistence

| Repositorio / fuente fijada | Alcance leído |
|---|---|
| [TanStack/query](https://github.com/TanStack/query/blob/d63a027c26b2489b8be065ad76f638e36216854a/packages/query-core/src/mutation.ts#L239) · `d63a027c` | source-inspected · `packages/query-core/src/mutation.ts`:239-268,301-330 |
| [pmndrs/zustand](https://github.com/pmndrs/zustand/blob/9fed2eb2f3af672da9f7bf694b996df3831fc207/src/middleware/persist.ts#L250) · `9fed2eb2` | source-inspected · `src/middleware/persist.ts`:250-259,285-325,340-342 |
| [reduxjs/redux-toolkit](https://github.com/reduxjs/redux-toolkit/blob/1a7d3b5251ceda61b77928e357a22086b45aaab1/packages/toolkit/src/query/core/buildMiddleware/queryLifecycle.ts#L431) · `1a7d3b52` | source-inspected · `packages/toolkit/src/query/core/buildMiddleware/queryLifecycle.ts`:431-465,508-522 |
| [electric-sql/electric-pglite](https://github.com/electric-sql/electric-pglite/blob/5ece6ad149d33607b2d72c8819af72a30baffff3/packages/pglite/tests/targets/runtimes/node-fs.test.js#L16) · `5ece6ad1` | source-inspected · `packages/pglite/tests/targets/runtimes/node-fs.test.js`:16-35 |
| [automerge/automerge](https://github.com/automerge/automerge/blob/09b19d5080a86548c72721a82747bebe272c6c31/rust/automerge/src/transaction/manual_transaction.rs#L15) · `09b19d50` | source-inspected · `rust/automerge/src/transaction/manual_transaction.rs`:15-19,73-110,140-149 |
| [sqlite/sqlite](https://github.com/sqlite/sqlite/blob/2439a84bbd1304c4b93184da04370f5ce32801c0/src/pager.c#L26) · `2439a84b` | source-inspected · `src/pager.c`:26-35,49-85,101-107 |
| [dexie/Dexie.js](https://github.com/dexie/Dexie.js/blob/95666bf5370a222a21d7f53130d87b42e9b7bac7/src/classes/transaction/transaction.ts#L115) · `95666bf5` | source-inspected · `src/classes/transaction/transaction.ts`:115-155,167-173,213-243 |
| [vercel/swr](https://github.com/vercel/swr/blob/8148ef012fd5b317d1e8ec2da4b2ca0673f63c0f/src/_internal/utils/mutate.ts#L128) · `8148ef01` | source-inspected · `src/_internal/utils/mutate.ts`:128-151,168-196,211-219 |
### Inference and memory

| Repositorio / fuente fijada | Alcance leído |
|---|---|
| [ollama/ollama](https://github.com/ollama/ollama/blob/db5266a71d6413c4568208a768757b16ffd7a021/server/sched.go#L123) · `db5266a7` | source-inspected · `server/sched.go`:123-131,240-253,280-283,426-509 |
| [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp/blob/e8fbcad855c5d8c315aa1dde231836ae472f5779/tools/server/server-context.cpp#L660) · `e8fbcad8` | source-inspected · `tools/server/server-context.cpp`:660-684,1600-1618,4634-4665 |
| [ml-explore/mlx-lm](https://github.com/ml-explore/mlx-lm/blob/56230fa02b8ff8330daf26dc95c28480423ed5fe/mlx_lm/generate.py#L286) · `56230fa0` | source-inspected · `mlx_lm/generate.py`:286-313,342-363,728-781 |
| [vllm-project/vllm](https://github.com/vllm-project/vllm/blob/bf39457294ccd246e92aa7243d46db79aa054a06/vllm/v1/core/sched/scheduler.py#L448) · `bf394572` | source-inspected · `vllm/v1/core/sched/scheduler.py`:448-458,769-828,894-957 |
| [sgl-project/sglang](https://github.com/sgl-project/sglang/blob/f6de13a0c26697382a1bb7969e24ea59f089365e/python/sglang/srt/managers/schedule_policy.py#L80) · `f6de13a0` | source-inspected · `python/sglang/srt/managers/schedule_policy.py`:80-85,903-955,1049-1057,1874-1936 |
| [huggingface/transformers](https://github.com/huggingface/transformers/blob/36e937ae761dea806a5b9fbb382e880378ad5435/src/transformers/cache_utils.py#L104) · `36e937ae` | source-inspected · `src/transformers/cache_utils.py`:104-157,1460-1517 |
| [intel/ipex-llm](https://github.com/intel/ipex-llm/blob/de6bce27133ab250f13fd5d549c197519ce16d30/python/llm/src/ipex_llm/transformers/convert.py#L1092) · `de6bce27` | source-inspected · `python/llm/src/ipex_llm/transformers/convert.py`:1092-1174 |
| [janhq/jan](https://github.com/janhq/jan/blob/da44e320f2132b6fa91879f3b723200fe281c1cb/src-tauri/src/lib.rs#L259) · `da44e320` | source-inspected · `src-tauri/src/lib.rs`:259-344,355-402,568-597,678-689,743-762 |
### Evaluation and telemetry

| Repositorio / fuente fijada | Alcance leído |
|---|---|
| [promptfoo/promptfoo](https://github.com/promptfoo/promptfoo/blob/ccafd6daf4c760e25a7e688c6a8b57ebedb3c5fd/test/evaluator/repeatCache.test.ts#L25) · `ccafd6da` | source-inspected · `test/evaluator/repeatCache.test.ts`:25-74,76-117,119-183 |
| [confident-ai/deepeval](https://github.com/confident-ai/deepeval/blob/c0bd9c89f33853b2dedc7db8415b3036894fb204/deepeval/metrics/g_eval/g_eval.py#L73) · `c0bd9c89` | source-inspected · `deepeval/metrics/g_eval/g_eval.py`:73-98,110-151,332-362 |
| [vibrantlabsai/ragas](https://github.com/vibrantlabsai/ragas/blob/8c63f10d500c44efbf24fdb9e2920de2104c321c/src/ragas/metrics/collections/faithfulness/metric.py#L102) · `8c63f10d` | source-inspected · `src/ragas/metrics/collections/faithfulness/metric.py`:102-161 |
| [langfuse/langfuse](https://github.com/langfuse/langfuse/blob/01e7f5f746b15493d18fe06b24ae06ac08d5ae74/worker/src/features/evaluation/deterministicSampling.ts#L4) · `01e7f5f7` | source-inspected · `worker/src/features/evaluation/deterministicSampling.ts`:4-30 |
| [Arize-ai/phoenix](https://github.com/Arize-ai/phoenix/blob/a111c1d4bfdf82829587f86c9911d41b2369a284/js/packages/phoenix-client/test/experiments/runExperimentProviderLifecycle.test.ts#L165) · `a111c1d4` | source-inspected · `js/packages/phoenix-client/test/experiments/runExperimentProviderLifecycle.test.ts`:165-223 |
| [open-telemetry/opentelemetry-python](https://github.com/open-telemetry/opentelemetry-python/blob/b4dff8c663110a866a5f263016679da25bd02f33/opentelemetry-sdk/src/opentelemetry/sdk/_shared_internal/__init__.py#L100) · `b4dff8c6` | source-inspected · `opentelemetry-sdk/src/opentelemetry/sdk/_shared_internal/__init__.py`:100-104,197-244 |
| [microsoft/playwright](https://github.com/microsoft/playwright/blob/826ce42b8664ea940424e77ce51f1cdf96dcd37f/packages/playwright/src/matchers/toMatchSnapshot.ts#L341) · `826ce42b` | source-inspected · `packages/playwright/src/matchers/toMatchSnapshot.ts`:341-359,382-447 |
| [vitest-dev/vitest](https://github.com/vitest-dev/vitest/blob/efba8cbfe94b1402a7ccab8a73994cb389cffa4d/test/unit/test/fixture-retry.test.ts#L1) · `efba8cbf` | source-inspected · `test/unit/test/fixture-retry.test.ts`:1-18 |
### Security tooling

| Repositorio / fuente fijada | Alcance leído |
|---|---|
| [astral-sh/ruff](https://github.com/astral-sh/ruff/blob/0222c19dd8e0c9a927f2e47bf3774a108431da25/crates/ruff_linter/src/rules/flake8_bandit/rules/shell_injection.rs#L68) · `0222c19d` | source-inspected · `crates/ruff_linter/src/rules/flake8_bandit/rules/shell_injection.rs`:68-78,310-365,402-408 |
| [pypa/pip-audit](https://github.com/pypa/pip-audit/blob/9bd0eff568298f4fbdecfd4477d9463dba8e6393/pip_audit/_audit.py#L17) · `9bd0eff5` | source-inspected · `pip_audit/_audit.py`:17-32,67-105 |
| [google/osv-scanner](https://github.com/google/osv-scanner/blob/1264316e4ccfc2e11b3e5971d3ae88c98cab9528/cmd/osv-scanner/scan/source/command.go#L97) · `1264316e` | source-inspected · `cmd/osv-scanner/scan/source/command.go`:97-100,124-138,152-184 |
| [gitleaks/gitleaks](https://github.com/gitleaks/gitleaks/blob/5f6ec56cfa6f8c67648d863582c7ae2f206d5c1c/detect/detect.go#L293) · `5f6ec56c` | source-inspected · `detect/detect.go`:293-305,367,503-514,542-567,710-748 |
| [ossf/scorecard](https://github.com/ossf/scorecard/blob/6eb56f6a7e62d8f5d55800f54cd92ea305107d1d/checks/raw/dangerous_workflow.go#L28) · `6eb56f6a` | source-inspected · `checks/raw/dangerous_workflow.go`:28-64,115-137,228-298 |
| [pyca/cryptography](https://github.com/pyca/cryptography/blob/3602bbd16ae731a4ce4dab9d43db334dbedad082/src/rust/src/fernet.rs#L56) · `3602bbd1` | source-inspected · `src/rust/src/fernet.rs`:56-65,79-98,182-228,331-335 |
| [PyCQA/bandit](https://github.com/PyCQA/bandit/blob/2d5467c45c3189f4d7d07e8022276bc73a478abd/bandit/plugins/injection_shell.py#L17) · `2d5467c4` | source-inspected · `bandit/plugins/injection_shell.py`:17-25,110-132,209-230,308-316 |
| [OWASP/CheatSheetSeries](https://github.com/OWASP/CheatSheetSeries/blob/31f5b8f5ad2995371f3a645349dd3f9e5af3a558/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.md#L243) · `31f5b8f5` | docs-inspected · `cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.md`:243-245,286-335,361-363,421-428 |
### Agent interfaces

| Repositorio / fuente fijada | Alcance leído |
|---|---|
| [assistant-ui/assistant-ui](https://github.com/assistant-ui/assistant-ui/blob/b33fbf124896e5c8343890036775dc8458ae8cb7/packages/core/src/runtime/base/base-composer-runtime-core.ts#L357) · `b33fbf12` | source-inspected · `packages/core/src/runtime/base/base-composer-runtime-core.ts`:357-395; 431-458; 520-536 |
| [CopilotKit/CopilotKit](https://github.com/CopilotKit/CopilotKit/blob/1d4be7b96e03f4eb59f9e5548060653f7a8e1d4b/packages/react-core/src/v2/components/chat/__tests__/CopilotChat.runActivityReconnect.test.tsx#L380) · `1d4be7b9` | test-source-inspected-not-executed · `packages/react-core/src/v2/components/chat/__tests__/CopilotChat.runActivityReconnect.test.tsx`:380-504; 587-640 |
| [ag-ui-protocol/ag-ui](https://github.com/ag-ui-protocol/ag-ui/blob/79530a25f3476d0abb93cb00761906fda757a2d5/docs/spec/1.0/basic/patterns/interrupt-resume.mdx#L13) · `79530a25` | contract-inspected · `docs/spec/1.0/basic/patterns/interrupt-resume.mdx`:13-42; 46-115 |
| [vercel/ai](https://github.com/vercel/ai/blob/3bea041f28e65f371e640d2c70c302776a46387f/packages/ai/src/ui/chat.ts#L1040) · `3bea041f` | source-inspected · `packages/ai/src/ui/chat.ts`:1040-1082; 1084-1142 |
| [langchain-ai/open-canvas](https://github.com/langchain-ai/open-canvas/blob/0310cecd51f31b3d37a52d6d1060137da3405280/apps/web/src/components/chat-interface/composer.tsx#L75) · `0310cecd` | source-inspected · `apps/web/src/components/chat-interface/composer.tsx`:75-117 |
| [lobehub/lobehub](https://github.com/lobehub/lobehub/blob/7157b954fd0f9eab60691b14757b35474c951148/src/features/ChatInput/hooks/useChatInputDraft.ts#L13) · `7157b954` | source-inspected · `src/features/ChatInput/hooks/useChatInputDraft.ts`:13-43; 48-68; 87-107 |
| [open-webui/open-webui](https://github.com/open-webui/open-webui/blob/b0e6098e940942281d9c83f3529ea117287a3a22/backend/open_webui/utils/tool_approval.py#L44) · `b0e6098e` | source-inspected · `backend/open_webui/utils/tool_approval.py`:44-64; 74-136; 138-213 |
| [CherryHQ/cherry-studio](https://github.com/CherryHQ/cherry-studio/blob/b5da36f92909850c54c85c04caa478e9baacc209/src/renderer/components/composer/__tests__/ComposerSurface.coldInput.test.tsx#L9) · `b5da36f9` | test-source-inspected-not-executed · `src/renderer/components/composer/__tests__/ComposerSurface.coldInput.test.tsx`:9-20; 85-129; 140-171 |
### Local applications

| Repositorio / fuente fijada | Alcance leído |
|---|---|
| [toeverything/AFFiNE](https://github.com/toeverything/AFFiNE/blob/0d594345a31dbacdc2f200d5edf7852fb5d8d751/packages/backend/native/src/runtime/storage_runtime/workspace_cleanup_checkpoint.rs#L5) · `0d594345` | source-inspected · `packages/backend/native/src/runtime/storage_runtime/workspace_cleanup_checkpoint.rs`:5-49; 136-190; 194-221 |
| [laurent22/joplin](https://github.com/laurent22/joplin/blob/68b1f922791e14d3e8fa7b4d6765ad3eaedebdd0/packages/app-mobile/components/NoteEditor/ImageEditor/promptRestoreAutosave.ts#L8) · `68b1f922` | source-inspected · `packages/app-mobile/components/NoteEditor/ImageEditor/promptRestoreAutosave.ts`:8-34 |
| [logseq/logseq](https://github.com/logseq/logseq/blob/d6082682125a4d528afc377927a1cf18f14e7d18/docs/adr/0011-undo-redo-semantic-inverse-op-persistence.md#L3) · `d6082682` | proposed-contract-inspected · `docs/adr/0011-undo-redo-semantic-inverse-op-persistence.md`:3-38; 62-71 |
| [AppFlowy-IO/AppFlowy](https://github.com/AppFlowy-IO/AppFlowy/blob/8fcee27d9bd93aad4ee0191d5d8d915d6a9a4e93/frontend/appflowy_flutter/lib/plugins/database/application/cell/cell_controller.dart#L155) · `8fcee27d` | source-inspected · `frontend/appflowy_flutter/lib/plugins/database/application/cell/cell_controller.dart`:155-163; 172-232 |
| [excalidraw/excalidraw](https://github.com/excalidraw/excalidraw/blob/c0a0ca348faa273c768de839a22df113f997c095/excalidraw-app/data/LocalData.ts#L73) · `c0a0ca34` | source-inspected · `excalidraw-app/data/LocalData.ts`:73-119; 124-172; 211-232 |
| [tldraw/tldraw](https://github.com/tldraw/tldraw/blob/3c4639ec8bce853ef19cbea0361e524f630dccfa/packages/editor/src/lib/utils/sync/TLLocalSyncClient.ts#L16) · `3c4639ec` | source-inspected · `packages/editor/src/lib/utils/sync/TLLocalSyncClient.ts`:16-19; 228-311; 320-361; 376-388 |
| [actualbudget/actual](https://github.com/actualbudget/actual/blob/9cb9b72c4ce19a5cfa0ca53e952ea600c2987cd2/packages/loot-core/src/server/sync/sync.property.test.ts#L242) · `9cb9b72c` | test-source-inspected-skipped-not-executed · `packages/loot-core/src/server/sync/sync.property.test.ts`:242-310; 315-385 |
| [outline/outline](https://github.com/outline/outline/blob/8893cb26e6b12b341deaf53c322550d2f6c322a5/app/scenes/Document/hooks/useDocumentSave.ts#L55) · `8893cb26` | source-inspected · `app/scenes/Document/hooks/useDocumentSave.ts`:55-82; 110-128; 343-386 |

## Veinte instituciones: materiales, no avales

[Registro completo](research/V5_5_UNIVERSITIES.json): contenido observado, localizador, aplicación, comprobación pendiente y límites. Se diferencia material docente de descripción curricular y lectura directa de contenido indexado.

| Institución | Fuente oficial consultada |
|---|---|
| Massachusetts Institute of Technology (MIT) | [Reading 1: Usability](https://web.mit.edu/6.813/www/sp18/classes/01-usability/) |
| Stanford University | [Assignment 7: Heuristic Evaluation (Individual)](https://hci.stanford.edu/courses/cs147/2025/au/assignments/Assignment_07_Heuristic_Evaluation_Individual.pdf) |
| Carnegie Mellon University | [Lecture 13: Evaluation of APIs and UI Tools, API Usability, Cognitive Dimensions](https://www.cs.cmu.edu/~bam/uicourse/05631fall2022/SSUI-13-eval.pdf) |
| University of California, Berkeley | [CS160 Pilot Usability Study Assignment — Grading Guidelines](https://people.eecs.berkeley.edu/~jfc/mattkam/cs160/pilotguidelines.pdf) |
| Harvard University | [Design Arguments](https://pl-hci-seminar.seas.harvard.edu/design_arguments.pdf) |
| University of Oxford | [Computer-Aided Formal Verification 2026–2027](https://www.cs.ox.ac.uk/teaching/courses/2026-2027/computeraidedverification/) |
| University of Cambridge | [Lecture 8: Usability evaluation methods](https://www.cl.cam.ac.uk/teaching/1011/HCI/HCI2010-lecture8.pdf) |
| ETH Zürich | [Quantitative User Experience Research: Surveys and Logs Analysis](https://www.vvz.ethz.ch/Vorlesungsverzeichnis/lerneinheit.view?ansicht=KATALOGDATEN&lang=en&lerneinheitId=195819&semkez=2025W) |
| École polytechnique fédérale de Lausanne (EPFL) | [Human-computer interaction — CS-213](https://edu.epfl.ch/studyplan/fr/bachelor/systemes-de-communication/coursebook/human-computer-interaction-CS-213) |
| University of Toronto | [CSC318 Tutorial: Usefulness and Usability Evaluation](https://www.dgp.toronto.edu/~tcohene/Usability.pdf) |
| Princeton University | [COS 436 / ELE 469 — P6: Pilot Usability Test (Spring 2013)](https://www.cs.princeton.edu/courses/archive/spring13/cos436/project/P6.pdf) |
| Yale University | [Yale College Programs of Study 2022–2023 — CPSC 484b](https://bulletin.yale.edu/sites/default/files/ycps-2022-2023.pdf) |
| Columbia University | [COMS W4170 User Interface Design — Assignment 1: The Beginning (Fall 2018)](https://www.cs.columbia.edu/~feiner/courses/csw4170/assn1-18f.pdf) |
| Cornell University | [Class Roster, Fall 2025 — INFO 3450 Human-Computer Interaction Design](https://classes.cornell.edu/browse/roster/FA25/class/INFO/3450) |
| University of Chicago | [Usable Security and Privacy — CMSC 23210 / CMSC 33210 (Spring 2019)](https://super.cs.uchicago.edu/usable19/) |
| California Institute of Technology (Caltech) | [2014–15 Caltech Catalog — CS 118 Logic Model Checking for Formal Software Verification](https://catalog.caltech.edu/archive/2014-15/department/CS/) |
| University College London (UCL) | [Interaction Design (COMP0021) — UCL Module Catalogue, 2026/27](https://www.ucl.ac.uk/module-catalogue/modules/interaction-design-COMP0021) |
| Imperial College London | [70101 — Human-Robot Interaction](https://www.imperial.ac.uk/computing/current-students/courses/70101/) |
| National University of Singapore (NUS) | [Exploring Activity-based Instructional Approaches to Develop Students’ Understanding of the Ethical Implications of ICT](https://blog.nus.edu.sg/teachingconnections/2024/04/29/exploring-activity-based-instructional-approaches-to-develop-students-understanding-of-the-ethical-implications-of-ict/) |
| Tsinghua University | [Qin Gao — Teaching, Department of Industrial Engineering](https://www.ie.tsinghua.edu.cn/eng/info/1051/1025.htm) |

## Feedback público y sus límites

[Registro completo](research/V5_5_FEEDBACK.json): relatos y propuestas, no incidentes reproducidos de nuestros competidores. No se comprobó que quienes publican sean clientes de pago. Se incluyó desacuerdo para no seleccionar sólo opiniones favorables a nuestra estética.

| ID | Fuente | Acceso / alcance |
|---|---|
| F01 | [Preferencias enfrentadas sobre la nueva interfaz de Claude Code](https://www.reddit.com/r/ClaudeCode/comments/1x74gg2/anyone_else_hate_the_new_ui/) | read_post_and_conflicting_comments |
| F02 | [Aprobaciones modales ocultan el contexto de la decisión](https://www.reddit.com/r/ClaudeCode/comments/1w1j8uj/ccs_modal_dialog_decision_boxes_to_exit_plan_mode/) | read_post_and_comments |
| F03 | [Codex: cancelación accidental con una sola pulsación de Escape](https://github.com/openai/codex/issues/14509) | read_full_issue_via_github_connector |
| F04 | [Codex: dificultad para interpretar consumo de cuota frente a tokens](https://github.com/openai/codex/issues/28879) | read_full_issue_via_github_connector |
| F05 | [OpenCode: navegación esperada en un compositor multilínea](https://github.com/anomalyco/opencode/issues/2649) | read_full_issue_via_github_connector |
| F06 | [T3 Code: avisos al finalizar o requerir aprobación](https://github.com/pingdotgg/t3code/issues/780) | read_full_issue_via_github_connector |
| F07 | [T3 Code: capacidad habilitada sin flujo visible de permisos](https://github.com/pingdotgg/t3code/issues/2156) | read_full_issue_via_github_connector |
| F08 | [Claude Code: solicitud de instrucciones de proyecto interoperables](https://github.com/anthropics/claude-code/issues/6235) | read_full_issue_via_github_connector |
| F09 | [OpenClaw: una salida multimedia representada dos veces](https://github.com/openclaw/openclaw/issues/78885) | read_full_issue_via_github_connector |
| F10 | [Cursor: Stop, trabajo en segundo plano y notificaciones reencoladas](https://forum.cursor.com/t/agent-chat-stop-unpredictable-and-broken/171659) | read_thread_and_support_correction |
| F11 | [Cursor: recuperación poco visible y límites de las reglas escritas](https://forum.cursor.com/t/very-ineffcient-constant-crashing-taking-forever/169219) | read_thread_including_later_counterevidence |
| F12 | [Anthropic: Building effective agents](https://www.anthropic.com/research/building-effective-agents) | read_primary_article |
| F13 | [Simon Willison: Agentic manual testing](https://simonwillison.net/guides/agentic-engineering-patterns/agentic-manual-testing/) | read_primary_guide |
| F14 | [Simon Willison: Anti-patterns, unreviewed code](https://simonwillison.net/guides/agentic-engineering-patterns/anti-patterns/) | read_primary_guide |
| F15 | [X: intento de lectura de publicación 2061567246342738242](https://x.com/pa1ar/status/2061567246342738242) | blocked_http_403_excluded_from_evidence |
| F16 | [X: intento de lectura de publicación 1990221860018204721](https://x.com/ibuildthecloud/status/1990221860018204721) | blocked_http_403_excluded_from_evidence |

## Autocrítica y siguiente discriminante

**VERIFICADO en nuestra investigación:** hay fuentes contradictorias, material propuesto, tests omitidos y restricciones de licencia. No se transformaron en evidencia de funcionamiento ni de libre copia. **DESCONOCIDO:** preferencia de usuarios de Neural Office, ganancia semántica de varios roles, consumo de larga duración y tolerancia al arranque intermitente.

Siguiente acción: observar cinco personas realizando el mismo encargo, interpretar su estado, cancelar y recuperar. Es un estudio formativo para encontrar problemas, no una estimación estadística de todo el mercado. Registrar cada ayuda, error crítico y tiempo; conservar tareas fallidas y los dos diseños comparados. No sustituir participantes por agentes ni anunciar G-UI cerrado por este informe.
