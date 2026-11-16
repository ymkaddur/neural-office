# V5.3 — contrato de escritorio y núcleo

Fecha: 2026-11-16. Versión de protocolo propuesta: `1`. Estado: **especificación + validador de forma probado; transporte y controlador pendientes de V5.5**.

## Autoridad y alcance

**VERIFICADO:** el piloto Python conserva su ledger, límites, verificador, control de procesos y recuperación. El prototipo React es una simulación en memoria. No llama a Python ni a Ollama. [Adaptador de demo](../desktop/src/state.ts#L1).

**VERIFICADO:** [decode_command](../neural_office/desktop_contract.py#L44) solo valida mensajes. Un mensaje válido no demuestra identidad, autorización, existencia de un proyecto, idempotencia ni disponibilidad de presupuesto. El módulo no ofrece servidor, dispatcher ni conexión con la GUI actual.

**ESCENARIO de integración adoptado:** React/TypeScript → comandos restringidos del host Tauri 2 → proceso Python propio. El canal será privado al proceso anfitrión, con framing, identidad de sesión y mensajes tipados. No se necesita abrir un servidor HTTP local para este diseño. La [documentación de sidecars](https://v2.tauri.app/develop/sidecar/) describe el mecanismo de empaquetado; las [fronteras de seguridad de Tauri](https://v2.tauri.app/security/) no reemplazan las comprobaciones del núcleo. Implementación y prueba del transporte: pendientes.

El host futuro será dueño de sus procesos y del acceso al sistema de archivos. La webview renderizará texto no confiable sin ejecutar HTML o instrucciones del modelo. Selección de archivos, exportación y arranque tendrán capacidades concretas; no habrá un comando genérico de shell ni acceso libre al disco. La capacidad de cancelar no dependerá de que la vista esté al día.

## Peticiones: parte implementada

UTF-8 estricto, JSON sin claves duplicadas, objeto raíz con exactamente `version`, `id`, `method`, `params`; máximo 16.384 bytes. `version` es el entero 1, nunca un booleano. IDs opacos: 1–64 caracteres ASCII alfanuméricos, guion o guion bajo. Revisiones/cursor: enteros entre 0 y 2^53−1, para evitar pérdida al cruzar JavaScript. Los parámetros desconocidos se rechazan, sin ignorarlos silenciosamente.

| Método | Parámetros exactos | Comprobación futura además de la forma |
| --- | --- | --- |
| `describe` | `{}` | Capacidades realmente implementadas, versión y sesión |
| `models.list` | `{}` | Solo metadatos locales; no descarga, carga ni inferencia |
| `projects.list` | `{}` | Proyectos que la sesión puede consultar; snapshot y revisión |
| `source.pick` | `project_id` | Selector nativo; lectura acotada; token opaco unido a una captura inmutable |
| `attempt.preview` | `project_id`, `entry_token`, `model_digest`, `roles`, `objective` | Huella de entrada, modelo, perfil, autoridad, presupuesto y revisión vigentes |
| `attempt.start` | `approval_token`, `idempotency_key`, `expected_revision` | Validar concesión y reservar una sola vez en transacción |
| `attempt.cancel` | `attempt_id` | Identidad y propiedad del intento; solicitud idempotente aunque la UI esté atrasada |
| `attempt.recover` | `attempt_id`, `expected_revision` | Confirmar ausencia de procesos propios y preservar consumo |
| `attempt.get` | `attempt_id` | Snapshot autorizado y revisión consistente |
| `report.get` | `attempt_id` | Informe guardado, hash y veredicto; no recalcular mediante una inferencia |
| `events.read` | `after`, `limit` | Canal de eventos de la sesión; límite 1–200; paginación y detección de huecos |

`roles` acepta 1, 3 o 7. `model_digest` son 64 caracteres hexadecimales minúsculos. `objective` contiene 1–2.000 caracteres, contando espacios, debe tener contenido, no admite NUL ni sustitutos Unicode inválidos. El límite de bytes del sobre también se aplica. [Validación de tipos y fronteras](../neural_office/desktop_contract.py#L27), [pruebas](../tests/test_v53_contract.py#L1).

Ejemplo sintético; **no es una concesión ejecutable**:

```json
{"version":1,"id":"request-1","method":"attempt.preview","params":{"project_id":"example","entry_token":"opaque-entry","model_digest":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","roles":3,"objective":"Revisar el ejemplo incluido"}}
```

## Concesión y reserva: requisitos de V5.5

1. El host crea un identificador de sesión no elegible por el frontend. Seleccionar una fuente devuelve un token opaco, no una ruta autorizada por el navegador. La captura incluye contenido acotado y hash; un cambio posterior en disco no cambia retroactivamente lo autorizado.
2. La previsualización no consume un intento. El núcleo calcula el perfil y muestra qué se va a ejecutar. La confirmación vincula proyecto, captura, objetivo, digest, roles, perfil, cuota, revisión, sesión y caducidad.
3. Un `approval_token` copiado, caducado, de otra sesión o con datos distintos se deniega. Tener un token con forma válida nunca equivale a poseer la concesión.
4. `attempt.start` verifica revisión, autorización y cuota dentro de la misma reserva transaccional. La clave idempotente se vincula al hash de la petición. Repetición idéntica devuelve el mismo intento; repetición con otro contenido se rechaza. Un clic doble no produce otro cargo.
5. Si se pierde la respuesta después del commit, la UI consulta por la misma clave; no inventa otra clave ni reenvía trabajo como nuevo. El registro durable de idempotencia debe existir antes de lanzar procesos.
6. Cancelar preserva el cargo. La UI muestra parada pendiente hasta la prueba de terminación. Una petición atrasada de cancelar un intento ya terminal devuelve su snapshot sin reabrirlo ni cancelar otro intento.
7. Recuperar conserva la autoridad y presupuesto históricos. Ni cerrar la ventana, reconectar, seleccionar otro modelo o recargar una página concede nuevos intentos reales.

Estos requisitos no quedan demostrados por los siete tests del reducer. La integración debe probarlos contra el ledger real y sus fallos parciales antes de activarse.

## Respuestas, eventos y desconexión: diseño pendiente

Respuesta propuesta: `{version,id,ok,result,error}`; exactamente uno de `result`/`error` contiene datos. Errores: código estable y detalle público acotado; los logs privados no viajan automáticamente a la webview ni a GitHub. El framing futuro limitará también respuestas y fragmentos; un informe grande se paginará sin truncar su hash.

Cada evento futuro incluirá versión, sesión, intento, ordinal durable, revisión y tipo. El cursor del canal es global dentro de esa sesión; el ordinal del intento solo ordena ese intento. No se comparan relojes de pared para decidir autoridad. Un duplicado se ignora; un hueco obliga a pedir snapshot y reanudar desde un cursor confirmado. No se procesa una finalización de una generación anterior como parte del trabajo actual.

El reducer de V5.3 usa generación/ordinal **en memoria** para ensayar los estados. No implementa replay durable ni recuperación de un transporte. Un evento consecutivo fuera de fase avanza el cursor, pero no cambia el estado; así un progreso tardío durante `STOPPING` no impide recibir después la terminación. Un hueco se ignora en la demo; el controlador real deberá resolverlo mediante resincronización.

`BOOTING` y `STOPPING` son proyecciones visuales. No añaden estados a la base actual. `ACCEPTED` solo se muestra al finalizar la verificación; no significa que el texto del modelo sea correcto. `RECOVERY_REQUIRED` bloquea una admisión nueva hasta confirmación del núcleo. El botón de confirmación de la demo **simula** esa prueba; no puede convertirse en la implementación real.

## Recursos y experiencia

La interfaz mostrará duración, CPU acumulada, memoria residente/comprometida con su unidad, modelo/contexto y calidad de la observación. Un dato ausente es “sin medir”, nunca cero. Se separan mediciones reales de fixtures y se explicita si la UI está incluida. El usuario podrá ver entrada, presupuesto, progreso, resultado y motivos de bloqueo sin leer el log interno.

Una oficina de siete roles no requiere siete copias de pesos. La implementación actual serializa llamadas a un modelo por intento. Mantenerlo entre intentos, reducir contexto o usar GPU son decisiones de V5.4 que necesitan medición y una revisión del aislamiento; no se activan mediante un checkbox del prototipo.

## Puerta de integración

Antes de sustituir Tkinter: ida/vuelta de mensajes reales; origen y capacidades de la webview; framing y tamaños; concesiones caducadas/ajenas; reserva concurrente; pérdida de respuesta después de commit; cancelación durante carga/generación/verificación; desconexión; muerte de host/sidecar; evento duplicado/fuera de orden; lectura de informes tras reinicio; accesibilidad con teclado y lector de pantalla; recursos de host, webview y Python por separado. Estos ensayos pertenecen a V5.5 y no se contabilizan como ejecutados en V5.3.
