# V5.5 — recorrido conectado, investigación y límites

Fecha: 17 de noviembre de 2026. Base anterior: `37133e8774668064f7787f538c6ec9a27ed9b294`. Progreso público: [PR 7](https://github.com/ymkaddur/neural-office/pull/7). **Vista previa de desarrollo; no instalador autónomo ni aceptación visual certificada.** Este registro distingue las pruebas con datos controlados del modelo real y del escritorio nativo.

## Fase 0: propiedad que debe sostener la entrega

«Bajo respuesta perdida, cancelación concurrente, cierre/reapertura o historial paginado, la oficina debe conservar una única identidad y su consumo, mostrar el estado autoritativo y permitir revisar la entrega, en vez de duplicar trabajo o representar un presupuesto/resultado incorrecto».

La unidad de prueba es un encargo sobre `examples/audit-sample.html`, con estado sintético nuevo. El oráculo manual espera título ausente/vacío en 1:1, idioma ausente en 2:1, imagen sin alt en 6:3 y control candidato sin etiqueta en 7:3. No se usan documentos privados, historiales operativos ni modelos cloud. [Prueba real reproducible](../tools/smoke_v55_real.py#L22).

## Qué conecta V5.5

```mermaid
sequenceDiagram
    participant U as Persona
    participant R as Interfaz React
    participant H as Host nativo
    participant S as Servicio Python
    participant L as Ledger y testigo
    participant M as Modelo propio
    U->>R: Objetivo, modelo y elegir fuente
    R->>H: source.pick (sin ruta arbitraria)
    H->>S: Captura privada desde selector nativo
    S-->>R: Token, identidad de fuente y tamaño
    R->>S: Vista previa de alcance
    S-->>R: Aprobación ligada a revisión y sesión
    U->>R: Autorizar y ejecutar
    R->>R: Conservar clave antes de enviar
    R->>S: Iniciar con la misma identidad
    S->>L: Reservar antes de lanzar worker
    S->>M: Trabajo acotado en proceso propio
    M-->>L: Respuesta y recibo
    L-->>R: Estado e informe comprobables
    Note over R,L: ACK perdido: consultar reserva; no crear otra clave automáticamente
```

**OBSERVADO en código:** [host](../desktop/src-tauri/src/main.rs), [frontera de métodos](../desktop/src-tauri/src/protocol.rs), [puente acotado](../desktop/src-tauri/src/bridge.rs), [servicio](../neural_office/desktop_service.py), [stdio](../neural_office/desktop_stdio.py), [cliente](../desktop/src/connected/client.ts) y [representación](../desktop/src/connected/ConnectedWorkspace.tsx). El servidor no expone HTTP ni una consola genérica. El modelo no concede permisos al renderer. Un comando nativo restringido lleva mensajes de hasta 16 KiB; respuestas hasta 2 MiB, ocho solicitudes pendientes y lectura de informe en fragmentos de hasta 64 KiB.

Fuente y aprobación caducan a los 120 s; aprobación ligada a sesión, proyecto, contenido, modelo, roles y revisión. Reutilizar una identidad con contenido incompatible produce conflicto. La UI conserva la petición pendiente por oficina antes del envío y consulta su reserva si falta respuesta. [Contrato](../neural_office/desktop_contract.py#L13), [reserva](../neural_office/desktop_service.py#L233), [regresión de duplicación](../tests/test_v55_service.py#L112) y [conflicto de contenido](../tests/test_v55_service.py#L130).

Los contadores y límites históricos siguen en el núcleo: tres intentos por proyecto, dos proyectos activos y una inferencia administrada. Fallo o cancelación no devuelve intentos. La CLI y el escritorio deben usar el mismo estado y conservar su testigo. El launcher usa el estado previo por defecto; no crea una oficina nueva para simular presupuesto renovado. [Launcher](../Start-NeuralOffice-Desktop.ps1), [continuidad](V5_2_1_OPERATIONS.md).

## Registro de laboratorio y correcciones

| Incidente / hipótesis falsable | Experimento antes del cambio | Intervención localizada y comprobación |
|---|---|---|
| **VERIFICADO: stop era un efecto sobre los procesos presentes, sin cerrar admisión futura** | Barrera anterior al spawn: request_stop retornaba con Job vacío y después nacían procesos; el ledger denegaba inferencia adicional. Contrafactual spawn antes de stop terminaba los hijos | Latch y exclusión en admisión; reutilizar terminación del bootstrap y Job. Dos regresiones fallaban antes, tres pasan después. [Cambio](../neural_office/ollama.py#L81), [tests](../tests/test_v55_cancellation.py#L81). Fiabilidad, no ejecución extra demostrada |
| **VERIFICADO: estado terminal cancelaba su propia conciliación React** | Mismo estado terminal: eventos inmediatos actualizaban historial; diferidos provocaban cleanup y dejaban «Trabajando» junto a detenido | Conciliar snapshot antes de publicar transición que desmonta sondeo. [Cambio](../desktop/src/connected/ConnectedWorkspace.tsx#L161), [regresión de componente](../desktop/src/connected/adversarial.test.ts#L44) |
| **VERIFICADO: dos cursores tratados como una página** | 34 proyectos y 102 intentos: avanzar intentos agotaba proyectos y reemplazaba el conjunto por vacío; fallback mostraba cero aunque consumo persistido era tres | Paginación por colección, misma oficina/sesión/revisión para combinar; presupuesto ausente se presenta por confirmar. [Cambio](../desktop/src/connected/ConnectedWorkspace.tsx#L261), [regresión](../desktop/src/connected/adversarial.test.ts#L66) |
| **VERIFICADO: proyecto textual confundido con token opaco** | Siete nombres legales del ledger, incluidos ASCII 65/80 y Unicode, eran rechazados por desktop antes de reservar | Tipo proyecto de 1–80 puntos de código UTF-8; tokens siguen restringidos. [Python](../neural_office/desktop_contract.py#L30), [Rust](../desktop/src-tauri/src/protocol.rs#L33), [TS](../desktop/src/connected/model.ts#L16), [regresión](../tests/test_v55_adversarial.py#L12) |
| **OBSERVADO: build Cargo sin feature de assets de producción** | Los dos primeros artefactos CI se construían sin custom-protocol. El código resuelto de Tauri selecciona contexto dev y assets vacíos con devUrl; compilar no ejercitaba su carga | Feature explícita, test de assets y prueba del ejecutable sin Vite. [Configuración](../desktop/src-tauri/Cargo.toml#L8), [test](../desktop/src-tauri/src/main.rs#L122), [workflow](../.github/workflows/windows-tests.yml). Resultado nativo se registra abajo; artefactos anteriores no sirven como prueba de UI |

**Contraevidencia:** en los defectos visuales no se reinició el presupuesto persistido; en la carrera de parada no se acreditó inferencia extra. La cuota solicitada de cinco vulnerabilidades graves no sustituye una reproducción. No se etiquetan estas correcciones como críticas por cantidad. El catálogo excesivo también se limita antes del doble recorrido y una sesión trabajando usa catálogo almacenado para no bloquear su cancelación con una nueva consulta; un peer lento en reposo sigue siendo una limitación distinta.

**Error propio de verificación:** el primer test Rust nuevo no especificaba `Context<Wry>` y falló con E0283 en [run 44043166728](https://github.com/ymkaddur/neural-office/actions/runs/44043166728). La corrección añade el tipo al test, sin alterar autoridad ni ejecución. No se contó ese run como prueba nativa superada.

No se reescribieron ledger, continuidad, verificador estático o runner. La corrección del backend modifica sólo la admisión/cancelación. Los módulos nuevos son el adaptador y host pedidos por V5.5, no una sustitución general del motor histórico. Los diffs completos, incluidos tests, están en la PR.

## Ejecución real y recursos

**VERIFICADO** con Windows, Python 3.12.10, Ollama 0.40.16 y `qwen2.5:0.5b`, digest `a8b0c51577010a279d933d14c2a8ab4b268079d44c5c8830c0a93900f1827c67`. El peso fue descargado por separado; no se redistribuye. Un rol, CPU, contexto 8192, salida máxima 128 tokens. Se usó `MeasuredBackend`, subclase observadora del backend real, dentro de DesktopService. Esto prueba servicio/núcleo/modelo; no por sí solo Tauri ni el selector.

| Ensayo | Resultado | Tiempo total | Residente máximo muestreado del backend | CPU acumulada |
|---|---|---:|---:|---:|
| Primer arranque | FAILED, OWNED_BACKEND_START_TIMEOUT; cero llamadas; cierre confirmado | 31,484 s | 346,66 MiB | 5,328 s |
| Segundo ensayo, entrega | ACCEPTED, una llamada, cuatro hallazgos contra oráculo manual | 11,375 s | 624,69 MiB | 15,188 s |
| Segundo ensayo, otra ejecución cancelada | CANCELLED desde RUNNING; consumo total dos; cierre confirmado | 9,063 s | 604,28 MiB | 4,281 s |

Fuentes: [fallo conservado](evidence/V5_5_REAL_FAILURE.json), [éxito y cancelación](evidence/V5_5_REAL_SUCCESS.json). Muestreo cada 0,5 s del Job propio; puede perder picos y contar páginas compartidas varias veces. Excluye interfaz y controlador, y memoria comprometida no es RAM física. La entrega observó VRAM del modelo cero; uso GPU del sistema desconocido. La cancelación se pidió 0,25 s después de entrar en el método real de inferencia, antes de su terminación: no se afirma que interrumpiese generación de tokens ya iniciada. El worker terminó 2,516 s después de pedir cancelación.

La reapertura conservó oficina, identidad de intento y consumo uno antes del segundo intento; no creó otro backend. Hash por fragmento y del informe, identidad de fuente y oráculo manual pasaron. El comentario del modelo sigue marcado `UNVERIFIED_ASSISTANCE`: consistencia del artefacto no equivale a calidad semántica. El modelo pequeño fue elegido para limitar coste de integración; no es comparación de calidad o rendimiento contra los modelos mayores de V5.3.

### R13 sigue abierto

**OBSERVADO:** seis timeouts de metadata, ningún paso de ownership/model_identity y cero inferencias en el ensayo fallido. Esto reduce la alternativa «falló después de validar el modelo» para esta ejecución, sin resolver toda la historia de R13.

Un sondeo posterior conservando tiempos y controles instrumentó connect, petición y cabeceras: conexión a ~0,555 s, cabeceras HTTP 200 a ~4,805 s; después validó propiedad e identidad y cerró. [Traza](evidence/V5_5_STARTUP_TRACE.json). **DESCONOCIDO:** origen de la demora del primer servidor. Calentamiento, contención o comprobaciones del sistema son escenarios no aislados; no se atribuyen al antivirus ni se amplía el timeout como remedio.

Siguiente experimento concreto: registrar fases connect/request/headers junto al arranque y primer log del servidor propio en un fallo frío, sin cambiar su deadline, para separar demora anterior a escucha de petición aceptada sin cabeceras. Repetir después con igual entrada y estado térmico documentado. La evidencia existente justifica la fase fallida, no la causa raíz externa.

## Verificación integrada y publicación

**VERIFICADO local:** 175 tests Python antes de incorporar cuatro tests del colector; esos cuatro pasan por separado. 33 tests Node, TypeScript/Vite y formato Rust con el toolchain disponible. Los tests frontend incluyen componente React real en Happy DOM con IPC simulado; no son pruebas visuales o de lector de pantalla. El colector real reúne 241 paquetes Cargo del superset Windows y cuatro npm runtime, con archivos y hashes comprobados; no es un SBOM binario exhaustivo.

**VERIFICADO en CI:** seis tests Rust, incluido assets de producción, y compilación release con custom-protocol en [run 44043619151](https://github.com/ymkaddur/neural-office/actions/runs/44043619151). **OBSERVADO:** el intento WebDriver falló antes del primer check en [run 44045617217](https://github.com/ymkaddur/neural-office/actions/runs/44045617217), con `session not created: DevToolsActivePort file doesn’t exist`, WebView2/driver 156.0.4314.58. El endurecimiento documentado para procesos elevados es un mecanismo compatible, todavía INFERIDO para este fallo: [explicación del proveedor](https://github.com/MicrosoftEdge/WebView2Feedback/issues/5645#issuecomment-4934355430). No se alteran flags ni protecciones de producción. **EN CURSO:** contraprueba del mismo host mediante controles Windows UI Automation, sin DevTools ni JavaScript/IPC directo. El resultado y capturas del run final se incorporarán antes de cerrar la entrega. El harness usa exclusivamente un runner Windows aislado, modelo público fijado y HTML sintético; no añade comandos de prueba al host de producción. [Harness UIA](../tests/e2e_v55_native_uia.py), [harness WebDriver con diagnóstico conservado](../tests/e2e_v55_native.py), [preparación](../tests/Prepare-V55NativeCI.ps1).

**OBSERVADO local:** Windows App Control bloqueó el ejecutable de prueba. No se desactivó ni eludió la política. CI no equivale a certificación de instalación en ese equipo. El SDK local no estaba completo y su instalación fue rechazada por revisión automática; la compilación se trasladó al runner. El paquete sigue siendo de desarrollo, requiere Python/Ollama/WebView2 y no lleva firma de distribución.

**VERIFICADO para avisos de terceros:** un checkout con core.autocrlf=true cambió la licencia MPL de SHA `fab3dd6bdab226f1c08630b1dd917e11fcb4ec5e1e020e2c16f83a0a13863e85` a `cde215e5b42363eb28ca2462c4558ff4807b38f383c537624c31e44657ac58f4`, añadiendo 373 CRLF. La regla específica [gitattributes](../.gitattributes#L2) conserva los bytes upstream: repetir el mismo checkout mantiene el SHA original. No se normaliza ni reescribe el texto de licencia.

**VERIFICADO en consulta de avisos conocidos:** 443 entradas Cargo consultadas; cero coincidencias en las 241 del grafo Windows. glib y proc-macro-error, excluidos de Windows, conservan un aviso de unsoundness y otro de mantenimiento. npm runtime y completo devolvieron cero avisos. No es prueba de seguridad total ni cubre runtimes externos. [Informe y cobertura](V5_5_DEPENDENCIES.md), [respuestas](evidence/V5_5_DEPENDENCIES.json).

**VERIFICADO para el paquete de skills:** siete nuevas skills, dos anteriores conservadas; catorce validaciones estructurales de las copias nuevas pasan. Una revisión independiente asistida por agente aplicó cinco casos a las siete skills y detectó una ambigüedad sobre clave operacional, corregida en ambas copias. No fue una prueba ciega ni estudio con personas; formato válido no garantiza comportamiento futuro. [Catálogo](../skills/README.md), [hashes y casos](evidence/V5_5_SKILLS.json).

## Duda residual, próxima acción y confianza

La duda más fuerte es la fiabilidad del recorrido empaquetado en un equipo nuevo y el arranque intermitente, seguida de utilidad real del comentario y aceptación de UI. También quedan lector de pantalla, sesiones largas, GPU, macOS/Linux, deadline total de ciertos peers lentos y efectos de una historia grande en latencia de cancelación. No se cubren por pasar la suite actual.

Siguiente acción: completar prueba nativa y revisión de capturas; mantener R13 visible; fijar tareas/rúbrica y estudio formativo de V5.6. [Hoja de ruta con puertas](V5_5_TO_V6.md). Confianza de ingeniería **94% en los cuatro mecanismos de fiabilidad reproducidos**, no una probabilidad estadística de ausencia de vulnerabilidades. La hipótesis crítica es que las fronteras del host real cumplen las mismas identidades y revisiones probadas; CI nativa debe contrastarla, no asumirse.
