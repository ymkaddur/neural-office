# V5.7 · protocolo fijado antes de medir

Base del producto `42f5345a28cc53ad20ca8998b8c381525d08e81f`. Las [seis tareas](../examples/v57-tasks.json) fijan los bytes UTF-8 (sin salto añadido), el encargo, el orden, las posiciones y las decisiones esperadas. Los casos son sintéticos y dirigidos, incluido un caso sin defectos y una asociación que las reglas publicadas pueden pasar por alto. El autor conoce el alcance del analizador. Una muestra por celda y un solo modelo sirven para una decisión de producto provisional.

## Qué se compara

- **0**. Captura de archivo y comprobación estática del producto. La entrega evaluada incluye los hallazgos y la orientación fija disponible en V5.6. El JSON de `check` por sí solo sólo contiene los hallazgos.
- **1**. Mismos bytes, reglas y orientación; se añade el Director del producto.
- **3**. Misma base; Director, revisor e integrador existentes, en secuencia. Un máximo de tres llamadas, 128 tokens por respuesta, CPU, contexto 8192, temperatura 0. Un envío por rol, sin herramientas ni reintentos del experimento. Tope de 18 celdas y 24 inferencias. Nunca se alimentan las respuestas esperadas al modelo.

Se usan las seis permutaciones del orden 0/1/3. Cada intento con modelo abre un servidor propio y termina su árbol de procesos. No se controla la caché del SO. Los roles del mismo intento comparten pesos y pueden aprovechar prefijos. El protocolo evalúa el flujo actual, que pasa códigos, posiciones, objetivo y comentarios previos al modelo. El modelo no recibe el HTML. Para texto con citas se hará una prueba de admisión aparte, en papel, con citas literales y posiciones. Promover un segundo flujo requiere una implementación y evidencia propias.

## Rúbrica y decisión

1. **Detección**. Coincidencia exacta de (código, línea, columna) frente a las expectativas manuales. Publicar verdaderos positivos, falsos positivos y omisiones por brazo; coincidencia exacta también para el control negativo.
2. **Decisión útil**. Para cada tarea, puntuar 0, ½ o 1 según la orientación específica en `decision` (ausente, parcial o completa y fundada). Una acción repetida se cuenta una sola vez. La orientación estática y el texto adicional se entregan juntos al evaluador.
3. **Valor adicional**. Un punto por tarea a lo sumo por el procedimiento específico en `extra`, cuando esté sustentado y sea más concreto que la orientación fija. Repetir un código o recomendar genéricamente comprobar accesibilidad vale cero.
4. **Daño**. Contar las entregas con al menos una aseveración sobre el archivo sin sustento o una acción contraria a la evidencia. Contar aparte el idioma de la orientación añadida, las respuestas truncadas y las celdas fallidas. Una recomendación condicional es distinta de una afirmación factual. Conservar las razones de las puntuaciones.
5. **Coste**. Desde captura hasta informe disponible, tiempo de pared por celda, mediana y rango por brazo. Separar intentos, llamadas efectivas, tokens de entrada/salida y CPU/working set/commit del Job de Ollama. En 0 no existe Job. La RAM total del escritorio, energía y coste monetario quedan sin medir. Contabilizar los errores en el denominador; si no se puede confirmar la terminación, detener el ensayo.
6. **Evaluación con etiquetas ocultas**. Barajar las 18 entregas y retirar metadatos, nombres de rol y tiempos antes de puntuar. Congelar las puntuaciones antes de abrir la correspondencia. El texto puede delatar el tratamiento. Un evaluador técnico que conoce el producto no representa a usuarios externos.
7. **Umbral**. Promover 1 sobre 0 o 3 sobre 1 sólo si suma una acción adicional en al menos dos tareas frente al brazo más barato, mantiene detección y puntuación de decisión, completa las seis y no aumenta el número de entregas con afirmaciones sin sustento. Exigir también mediana de pared ≤30 s por tarea con modelo y, para 3, ≤2,5 veces la mediana de 1. En empate se prefiere el más barato. Si falla el umbral no se promueve. Publicar la incertidumbre y el coste incluso con un resultado desfavorable.

## Aceptación del escritorio

En un HTML pequeño, distinguir qué se ha comprobado, ubicación y acción, fuente de la sugerencia y coste antes de autorizar. El recorrido de lectura debe funcionar con teclado, mantener las ubicaciones visibles a la geometría nativa ya aceptada y no gastar intentos al consultar. Revisar identidad de la fuente, límite de representación y texto tratado como datos. Repetir pruebas del componente y del ejecutable, y separar sus resultados de la evaluación con personas. El ensayo formativo previsto requiere cinco participantes reales, con un objetivo de cuatro que completen sin ayuda selección, coste, parada, recuperación y explicación del resultado.
