# V5.4 · Medir interfaz y motor por separado

**Línea base, no anuncio de aceleración.** Mediciones locales del 16 de noviembre de 2026. La UI está desconectada del motor; la campaña del backend se ejecutó por separado durante el desarrollo del prototipo. No es un ensayo de la futura aplicación integrada ni una prueba de concurrencia UI + inferencia.

## Backend existente: tres intentos reales

VERIFICADO en [V5_4_ENGINE.json](evidence/V5_4_ENGINE.json): motor V5.3 sin cambios; Windows, Python 3.12.10, runtime 0.40.16, Intel Core Ultra 7 255HX, 20 procesadores lógicos y 33.752.997.888 bytes de memoria física. Modelo identificado por digest, sin publicar su alias local. Mismo HTML sintético empaquetado, un rol, contexto 8192, salida máxima 128, CPU (`num_gpu=0`). No se evalúa calidad semántica de sus comentarios.

| Repetición | Total | CPU acumulada | CPU media del equipo | Pico residente muestreado¹ | Pico de memoria comprometida del Job |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 49,625 s | 111,328 s | 11,23 % | 5,849 GiB | 6,892 GiB |
| 2 | 21,686 s | 101,828 s | 23,56 % | 5,875 GiB | 6,892 GiB |
| 3 | 23,394 s | 104,938 s | 22,50 % | 5,874 GiB | 6,890 GiB |

Mediana total: **23,394 s**. Tres artefactos aceptados por el verificador estático y tres cierres confirmados con cero procesos propios activos. `ACCEPTED` verifica las comprobaciones y su vinculación al artefacto; no demuestra que la redacción del modelo sea útil o correcta en general.

¹ Suma de working sets del árbol propio, muestreada cada 0,5 s; puede contar páginas compartidas varias veces y perder picos entre muestras. CPU media = CPU acumulada / tiempo observado / 20 procesadores lógicos; **no es porcentaje de un núcleo**. Se excluyen controlador Python, navegador y demás aplicaciones. Energía, temperatura y uso GPU del sistema: no medidos. La VRAM asignada al modelo fue cero en este perfil CPU.

## Diario de variación temporal

| Registro | Evidencia observada | Conclusión permitida |
| --- | --- | --- |
| R1: primera ejecución más lenta | Cinco `STARTUP_RETRY` en fase `metadata`; backend listo a 29,015 s | Parte de la diferencia está localizada antes de admitir la llamada |
| R2 / R3 | Backend listo a 6,012 / 6,490 s, sin esos reintentos | El comportamiento de arranque varía en esta muestra |
| Consulta de ownership | Pares `OWNER_QUERY_BEGIN/END` en cada intento y llamada | Existe coste observable; no se elimina el control para mejorar la cifra |
| Generación | 58 tokens en los tres ensayos; 9,43 / 9,65 / 9,52 tokens/s | El total no se explica solo por velocidad de decodificación |
| Cierre | `termination_verified=true`, muestreo completo, sin errores de observación | Se verificó el cierre del árbol administrado en estos tres casos |

**Escenario dominante limitado:** la espera de metadatos contribuye a la latencia del primer intento. **DESCONOCIDO:** por qué el servicio tardó en responder. Contención de otros procesos y caché del sistema son alternativas no aisladas. No se atribuye la diferencia al diseño de la UI: las muestras de navegador se tomaron después de la campaña del backend. No se reproduce la firma de fallo terminal de R13 ni se declara corregida.

Siguiente experimento discriminante: repetir una única entrada y perfil, con trazas temporales del servicio y contención registrada, separando arranque frío y caliente; mantener los controles de ownership. No ampliar timeouts ni activar GPU como supuesto remedio sin esa evidencia. Tres muestras no permiten afirmar una distribución estable ni comparar mejoras con la campaña V5.3, cuyo entorno no estaba controlado de la misma forma.

## Interfaz web

[V5_4_UI.json](evidence/V5_4_UI.json) conserva muestras individuales de cinco segundos y comprobaciones manuales. [V5_4_BUILD.json](evidence/V5_4_BUILD.json) identifica los assets finales, tamaños gzip, pruebas y hashes. Abrir el build de producción evita cargar HMR durante la medida.

| Modo | Ventanas | Heap JS observado | Nodos DOM | Tareas largas reportadas |
| --- | --- | ---: | ---: | ---: |
| Reposo, inspector abierto | 3 × ~5 s | 7.85–8.30 MiB | 181–203 | 0 |
| 10.000 posiciones / 50 filas | 3 × ~5 s | 8.21–8.59 MiB | 419–431 | 0 |

Build web: **282,428 bytes** sin comprimir y **84,244 bytes** sumando gzip por asset (nivel 6). Cinco escenas sin inspector: 174–260 nodos en 1707 × 960 CSS px, sin desbordamiento horizontal observado. Estas cifras incluyen React, no los JPEG de documentación.


- El colector se activa por botón, se detiene al finalizar y conserva como máximo diez muestras. No hay sondeo de backend, animaciones permanentes ni bucle de `requestAnimationFrame`.
- El escenario de historial representa una secuencia de 10.000 posiciones con 50 filas montadas. **No reserva 10.000 objetos de evento ni prueba su transporte/persistencia.** La tabla de resultados del propio colector incrementa ligeramente el DOM entre muestras.
- Heap JS es una aproximación del navegador y puede incluir instrumentación; una bajada puede deberse a recolección de basura. No acredita ausencia de fuga ni un ahorro respecto a V5.3.
- Cero tareas largas observadas en una ventana significa cero eventos reportados por esa API durante esa ventana. No demuestra CPU cero, p95 de interacción ni fluidez bajo carga del modelo.
- React, ReactDOM y las herramientas ya estaban presentes. No se añadieron dependencias. Los JPEG de documentación no forman parte del bundle de la aplicación.

Para repetir: seguir [desktop/README.md](../desktop/README.md), abrir Inicio, mantener la pestaña visible y usar «Medir». Registrar navegador, viewport, build y presencia de instrumentación; separar reposo con panel abierto de historial paginado. No sumar heap JS a working set como si fueran magnitudes equivalentes.

## Presupuestos todavía no acreditados

| Objetivo propuesto hasta V6 | Estado de esta entrega | Prueba necesaria |
| --- | --- | --- |
| UI + host + Python ≤350 MiB en reposo; ≤500 MiB con historial | DESCONOCIDO; no existe host Tauri integrado | Medir memoria privada de todos los procesos propios, separada del modelo |
| CPU en reposo ≤1 % de un núcleo durante 10 min | No medido | Medir tiempo de CPU del árbol UI/core con coste del colector declarado |
| Respuesta local p95 ≤100 ms; evento→pintado p95 ≤200 ms | No medido | Serie de interacciones y eventos reales con tamaño de muestra y reloj definidos |
| 30 ciclos tarea/parada/restauración sin crecimiento no acotado | No ejecutado en esta UI | Integración persistente y comparación de reposo tras estabilización |
| Menos coste sin pérdida de calidad | No establecido | Corpus independiente con entradas cortas/largas, resultados comprobables y variación de una condición por vez |

El HTML empaquetado constituye una referencia reproducible pequeña; **no es todavía el corpus amplio de V5.4**. El ejemplo documental Norte solo prueba presentación. La siguiente fase no debe convertir estos límites en métricas verdes por cambiarles el nombre.
