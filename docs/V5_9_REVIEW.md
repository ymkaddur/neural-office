# V5.9 · revisar, seguir y recuperar un encargo

Base de comparación: `8b1219c` (V5.8). Las observaciones describen el flujo conectado de revisión HTML para Windows. Las pruebas visuales usan el cliente de producción compilado y respuestas locales sintéticas. El trabajo nativo con el ejecutable tiene una prueba propia en GitHub Actions. [Recorrido nativo](../tests/e2e_v55_native_uia.py) · [Mediciones y muestras públicas](evidence/V5_9_CHECKS.json).

## Qué cambió después de las auditorías

| Observación contrastada | Decisión de producto | Evidencia o límite |
|---|---|---|
| El escritorio ya tenía eventos del encargo y recibos por llamada. Costaba ver el alcance autorizado junto a lo ocurrido. El número usado en la lista era una secuencia global. | Mostrar el modelo, el máximo autorizado, el orden dentro del encargo y el estado registrado de cada llamada. Mantener los eventos detallados bajo demanda. | Una llamada con secuencia global 27 se presenta como primera del encargo. Una lectura desconectada conserva el calificativo de última lectura. [Presentación de llamadas](../desktop/src/connected/ConnectedWorkspace.tsx#L500) · [Pruebas de la vista](../desktop/src/connected/adversarial.test.ts). |
| Al comenzar la ejecución desaparecía el lugar para escribir el siguiente encargo. | Se puede abrir un borrador por proyecto durante la ejecución y recuperarlo al terminar. Es texto en memoria de esta ventana. El usuario vuelve a elegir fuente, revisar y autorizar el nuevo trabajo. | Se escribe durante una llamada, se pulsa Ctrl+Intro, se alcanza el estado terminal y se recupera el texto. El transporte registra cero órdenes de inicio, recuperación, cancelación o aprobación durante esa prueba. [Borrador](../desktop/src/connected/ConnectedWorkspace.tsx#L362). |
| Filtrar una página global de cien intentos podía ocultar parte o todo el historial del proyecto seleccionado. | Cuando la instantánea global es incompleta, pedir únicamente los intentos del proyecto y ordenarlos por su ordinal. Cargar, error y vacío confirmado tienen estados distintos. | Cincuenta proyectos y 150 intentos. Comprobados el proyecto en el límite y el último, las tres identidades en orden descendente, una respuesta tardía de otro proyecto y una revisión y cuota intactas. [Consulta](../neural_office/desktop_service.py#L117) · [Consumidor](../desktop/src/connected/ProjectHistory.tsx#L12). |
| Una referencia inexistente y una etiqueta vacía podían ocultar un control sin nombre. | La regla v3 comprueba destinos, texto, asociación y alternativas. Devuelve la ubicación del control que requiere revisión. | Las dos omisiones de V5.8 ahora dan hallazgo. Los 18 contratos históricos coinciden. En 15 documentos adicionales se contrastaron la presencia de nombre calculada por la regla y el nombre completo del árbol de accesibilidad de Edge. El lector abre los informes históricos v1 y v2. [Regla](../neural_office/audit.py#L91) · [Expectativas de los 15 casos](../tests/test_v59_names.py). |
| El selector, las posiciones y los controles competían visualmente. Había información operativa en cuerpos de 9–11 px. | Reunir archivo, acción y coste, usar tipografía del sistema y cifras monoespaciadas en las posiciones y contadores. Separar la decisión de consultar al modelo. Colores de tinta, papel y verde mineral en ambos temas. | Diez pares de texto y fondo por tema en la vista de resultados. Contraste mínimo de 8,18:1 en oscuro y 6,28:1 en claro. Cuatro tamaños comprobados, incluyendo navegación por teclado hasta el último hallazgo. [Captura](images/v5.9-review.png) · [Valores por selector](evidence/V5_9_CHECKS.json). |

Las recomendaciones de tres paneles fijos, herramientas en vivo y tres iteraciones por defecto presuponen capacidades distintas de las actuales. La decisión para V5.9 es mostrar la identidad, las llamadas y la entrega que existen. La comprensión en diez segundos, la preferencia tipográfica y las comparaciones con otros productos siguen siendo hipótesis de diseño.

## Coste de abrir un intento

Una lectura del escritorio abría dos veces la misma frontera de continuidad y volvía a consultar los resultados. La verificación de los bytes de la fuente y de las respuestas ahora se hace con la conexión que ya adquirió el bloqueo de la oficina. El control de integridad detectó una respuesta alterada en el común de lectura del escritorio. [Lectura del escritorio](../neural_office/desktop_service.py#L276) · [Verificación de los bytes](../neural_office/ledger.py#L420).

| Medida en Windows x64 | V5.8 | V5.9 |
|---|---:|---:|
| Verificaciones de continuidad al abrir un intento | 2 | 1 |
| Mediana de las medianas de lectura | 4,26 ms | 2,10 ms |
| Mediana de los p95 de cada lote | 5,79 ms | 2,87 ms |
| Mediana de CPU del proceso por 60 lecturas | 265,6 ms | 132,8 ms |
| Mediana del pico de memoria de trabajo del proceso, incluido arranque | 31,5 MiB | 31,4 MiB |

Cuatro procesos independientes por versión, en orden alternado y contrabalanceado, con una oficina temporal de un intento terminado. Cada proceso hizo tres lecturas de calentamiento y sesenta medidas. La dispersión figura en los datos brutos. La memoria es prácticamente igual en esta muestra. El resultado de lectura no estima el rendimiento de Ollama, el consumo de WebView2 ni el coste de una oficina grande. El cálculo de la firma todavía recorre las tablas. [Instrumento](../tools/measure_v59_read.py#L32) · [Resultados por lote](evidence/V5_9_CHECKS.json).

Resolver las referencias de etiquetas también tiene un coste. En 40 lecturas por versión del mismo HTML, alternando el orden dentro del mismo proceso, la mediana del ejemplo pasó de 0,030 a 0,036 ms. Un formulario de 40 campos pasó de 0,367 a 0,425 ms. Con 800 campos y 50 131 bytes pasó de 6,676 a 8,289 ms. Las tres entradas compartidas dieron los mismos hallazgos en ambas versiones. Esta medición cubre el analizador, desde bytes en memoria hasta la lista de hallazgos. [Comparador reproducible](../tools/compare_v59_html.py) · [Medianas, p95 y huellas](evidence/V5_9_CHECKS.json).

Para repetir el ensayo desde la raíz de V5.9 con Python 3.12, el parámetro `--checkout` permite seleccionar una copia de V5.8 o de V5.9. El instrumento crea su propia oficina temporal. El corpus de HTML y las pruebas del cliente se ejecutan por separado.

```powershell
py -3.12 -B tools/measure_v59_read.py --checkout . --reads 60
py -3.12 -B tools/evaluate_v56_html.py
py -3.12 -B -m unittest discover -s tests -q
Set-Location desktop
npm ci --ignore-scripts
npm test
npm run build -- --mode native
```

En una estación de pruebas con Microsoft Edge, Python 3.12 y el módulo de desarrollo Playwright disponible para Node, `node tools/verify_v59_names.cjs` reproduce los quince nombres desde la raíz del repositorio. [Oráculo de navegador](../tools/verify_v59_names.cjs).

## Qué queda abierto

En 1440 × 900 y 1024 × 697 las cuatro filas del ejemplo caben en la vista. En 390 × 720 y 768 × 540 la última se alcanza con desplazamiento y teclado. Las cuatro vistas mantuvieron el presupuesto dentro de pantalla. Comprobar una muestra de colores y el árbol de accesibilidad de ejemplos no sustituye a recorrer la aplicación con Narrador o NVDA. La puntuación competitiva de las auditorías no predice la experiencia de una persona. La siguiente puerta incluye sesiones largas, primer resultado pintado, usuarios nuevos y distribución firmada. [Criterios hasta V6.5](../ROADMAP.md).
