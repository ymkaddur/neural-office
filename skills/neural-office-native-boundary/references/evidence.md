# Evidencia y límites de transferencia

Investigación consultada el 16–17 de noviembre de 2026. Los mecanismos externos se inspeccionaron en los archivos enlazados; no se ejecutaron sus repositorios. Las aplicaciones propuestas a Neural Office requieren prueba propia. Las licencias se indican para evitar confundir observación con permiso de copia.

## Lección aplicada al proyecto

Regla de entrega derivada de la investigación propia: separar compilación, assets embebidos, ejecución nativa y autorización del sistema operativo. El caso V5.5 mostró que un build CI por sí solo no verifica que el artefacto arranque en la máquina del usuario. La comprobación del paquete debe usar las features y versiones resueltas, no una analogía con otro shell.

En la prueba nativa V5.5, leer inmediatamente el textarea devolvió vacío a 16 ms y el valor exacto a 531 ms; la captura inicial mostraba el texto, por lo que no se corrigió producción por un fallo del instrumento. El selector de archivo exponía Edit 1148 y no el supuesto 1001. Además, el texto «Tu encargo» ya estaba dentro de la etiqueta anterior a reservar: una búsqueda por subcadena no probaba la transición. El [registro del ensayo](https://github.com/ymkaddur/neural-office/blob/b7e92d9d05a21d698ebe8f7ce2dbac30971c836a/docs/evidence/V5_5_NATIVE_GEOMETRY.json) conserva la observación y sus límites; el [harness revisado](https://github.com/ymkaddur/neural-office/blob/b7e92d9d05a21d698ebe8f7ce2dbac30971c836a/tests/e2e_v55_native_uia.py) exige postcondiciones e identidades de procesos. Son errores concretos de verificación; no justifican usar esos IDs para otros diálogos o asumir que todo control necesita el mismo retraso.

El canal público y la captura privada se declaran en `desktop/src-tauri/src/protocol.rs` y `neural_office/desktop_contract.py`. Son localizadores del proyecto, no una afirmación de que cualquier revisión futura conserve esas garantías. Comprueba cada ruta antes de transferirlas a una funcionalidad nueva.


## Mecanismos externos

### tauri-apps/tauri

[Archivo en el commit inspeccionado](https://github.com/tauri-apps/tauri/blob/4acdc0a2230ced11567a90962b07eedfa53dc3d2/crates/tauri-utils/src/acl/capability.rs#L77). Líneas 77-86,128-174; nivel: `source-inspected`.

OBSERVADO: Capability expresa permisos por ventana/webview y distingue contenido local de orígenes remotos; una ventana coincidente habilita todas sus webviews. APLICACIÓN V5.5: limitar la capability al host local, sin glob de ventanas ni orígenes remotos; probar una ventana secundaria y un comando no autorizado.

**Límite:** Se inspeccionaron contrato y deserialización, no toda la implementación de enforcement. La configuración no demuestra por sí sola aislamiento de disco/red. HEAD investigado no se confunde con la versión fijada en Cargo.lock. No se ejecutó Tauri ajeno.

**Licencia observada:** MIT y Apache-2.0 declaradas en LICENSE.spdx:7-8; LICENSE-MIT:1-21 y cabeceras del archivo inspeccionados.

### tauri-apps/plugins-workspace

[Archivo en el commit inspeccionado](https://github.com/tauri-apps/plugins-workspace/blob/21f01aa3d5d171f7e5deb5262480bb6ae20e3d0c/plugins/shell/src/commands.rs#L79). Líneas 79-96,103-163; nivel: `source-inspected`.

OBSERVADO: prepare_cmd comprueba que el sidecar figure en external_bin y aplica scope a programa/argumentos antes de crear el comando; env/cwd y agrupación de procesos son decisiones distintas. APLICACIÓN V5.5: conservar el proxy estrecho de operaciones de negocio; ninguna ruta, entorno o shell arbitrarios desde JS. Probar rechazo de comando privado y argumentos añadidos.

**Límite:** El plugin admite configuración más amplia y process_group es optativo; usar sidecar no equivale automáticamente a matar todo el árbol. No se ejecutaron pruebas. Neural Office no necesita adoptar este plugin ni copiar su código.

**Licencia observada:** MIT / Apache-2.0 en cabecera; LICENSE_MIT:1-21 inspeccionado.

### electron/electron

[Archivo en el commit inspeccionado](https://github.com/electron/electron/blob/ca3e18572bbfa2645a15e7c0e81f2319f1dcb7a7/docs/tutorial/security.md#L743). Líneas 743-777,780-799; nivel: `docs-inspected`.

OBSERVADO: la guía oficial pide validar el emisor/origen de cada IPC y limitar navegación, ventanas y capacidades del renderer. APLICACIÓN V5.5: probar que contenido remoto, ventanas secundarias y mensajes malformados no alcancen la autoridad; servir sólo assets locales previstos.

**Límite:** Es documentación de seguridad, no auditoría del código ni prueba de que todos los consumidores cumplan. Las reglas específicas de Electron no se trasladan literalmente a Tauri. No permite afirmar cifras de RAM o superioridad de uno.

**Licencia observada:** MIT; LICENSE:1-21 inspeccionado.

### openai/codex

[Archivo en el commit inspeccionado](https://github.com/openai/codex/blob/d5a478e31c3296e544d53424a7a6c995e7dfb0f5/codex-rs/core/src/tools/approvals.rs#L525). Líneas 525-547,594-640,687-705,807-864; nivel: `source-inspected`.

OBSERVADO: un checkpoint humano no se satisface con un allow de hook; las denegaciones prevalecen; se revisa la política tras la respuesta; cancelación puede convertir approved en abort; la ruta human_once evita la caché y usa approvalId único. APLICACIÓN PROPUESTA V5.5: separar autorización persistente de consentimiento para un efecto concreto y validar autoridad/cancelación otra vez antes del efecto.

**Límite:** Inspección de rutas seleccionadas, sin ejecutar tests ni auditar sandbox. La aprobación no prueba aislamiento OS. README app-server:11-20 además declara integración experimental y rechazo cuando no hay cliente capaz; no prometer paridad del protocolo.

**Licencia observada:** Apache-2.0; LICENSE:1-5 y metadato SPDX verificados.

### openai/openai-agents-python

[Archivo en el commit inspeccionado](https://github.com/openai/openai-agents-python/blob/25e7b2e40258cc0910159f35d463b64582ec83f6/src/agents/run_context.py#L556). Líneas 556-607,831-872,1341-1366; nivel: `source-inspected`.

OBSERVADO: vincula call_id a tipo de invocación, ámbito y fingerprint; reutilizar ID con otra invocación produce ModelBehaviorError. Distingue aprobaciones por llamada y permanentes por agente, y marca bindings restaurados incompletos. PROPUESTA V5.5/V6: aprobación ligada a contenido/ámbito; prueba mutar argumentos, agente o fuente conservando ID y restaurar una autorización sin binding.

**Límite:** No ejecutado. Esta inspección verifica controles en memoria/serialización del contexto, no atomicidad entre un efecto externo y su recibo. El permiso permanente no debe extrapolarse al permiso efímero de Neural Office; no audita todo el SDK ni el proveedor.

**Licencia observada:** MIT; LICENSE:1-21 inspeccionado.


## Feedback público

### F07: T3 Code: capacidad habilitada sin flujo visible de permisos

[Fuente pública](https://github.com/pingdotgg/t3code/issues/2156). Publicación: 2026-04-18T04:05:35Z. Consulta: 2026-11-17. Localizador: GitHub issue body; Problem or use case, Smallest useful scope, Risks or tradeoffs.

OBSERVADO: el autor no puede distinguir si Computer Use es incompatible, carece de permiso del sistema o necesita una aprobación que la UI no muestra; propone como mínimo informar explícitamente de incompatibilidad.

HIPÓTESIS: mostrar la capacidad realmente disponible, su bloqueo concreto y el próximo paso evita botones que aparentan ejecutar funciones ausentes.

PENDIENTE: probar capacidad ausente, denegada y disponible; cada estado debe dar una explicación y acción distinta; ningún evento desconocido debe quedar esperando invisible.

**Límite:** Issue cerrado; no acredita un defecto vigente ni equivalencia entre Codex Desktop y app-server. Propuesta de usuario, no diseño validado experimentalmente.


## Método docente

### Columbia University

[COMS W4170 User Interface Design — Assignment 1: The Beginning (Fall 2018)](https://www.cs.columbia.edu/~feiner/courses/csw4170/assn1-18f.pdf). Rúbrica de análisis heurístico e implementación web. Nivel: assignment_material. Localizador: Part 1: Usability Analysis, página 1, líneas 13–29; Submission Instructions, página 4, líneas 102–108. Consulta: 2026-11-17.

Cada problema requiere comportamiento observado, perjuicio al usuario, heurística, captura y severidad. La entrega debe descargarse en otra carpeta para comprobar el artefacto efectivamente publicado.

INFERIDO: toda crítica visual debe producir una incidencia reproducible; verificar el paquete distribuido, además del entorno de desarrollo.

**Comprobación propuesta:** PROPUESTO: documentar incidentes con capturas y escenarios; ejecutar la entrega pública desde un directorio limpio.

**Límite:** Ejercicio de 2018 con un evaluador; no equivale a estudio de usuarios ni a clasificación de vulnerabilidades.
