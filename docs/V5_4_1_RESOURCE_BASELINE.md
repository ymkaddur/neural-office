# V5.4.1 · Recursos de la interfaz

**Ámbito:** build de producción del frontend, sin motor, modelos, Tauri o inferencias. Las cifras finales y el inventario de assets están en [V5_4_1_VERIFICATION.json](evidence/V5_4_1_VERIFICATION.json). La referencia anterior permanece en [V5.4](V5_4_RESOURCE_BASELINE.md).

## Resultados observados

| Medida | V5.4.1 | Alcance |
| --- | --- | --- |
| HTML + CSS + JS sin comprimir | 294.727 bytes | Build web, excluye imágenes de documentación |
| Suma gzip, nivel 6 | 87.285 bytes (85,24 KiB) | +3.041 bytes, aproximadamente +3,61 % frente a V5.4 recomprimida con el mismo runtime |
| Dependencias directas de ejecución | 2, sin cambios | React y React DOM; lock de dependencias idéntico |
| Heap JS, seis muestras finales | 8,30–19,85 MiB | Tres de reposo y tres de historial, ventanas de unos 5 s |
| Tareas largas notificadas en esas ventanas | 0 | No equivale a una medición de latencia p95 ni de fps |
| Escenas × anchuras CSS | 5 × 7 = 35 | 320, 392, 520, 768, 1024, 1280 y 2560 px; sin desbordamientos horizontales en los paneles comprobados |

El heap bajó de 19,85 a 8,30 MiB entre muestras. Es compatible con recolección de memoria y con el efecto de la instrumentación, pero no identifica su causa ni demuestra ausencia de fugas. No se calcula una mejora porcentual de RAM contra V5.4: faltan ejecuciones comparables y atribución al proceso. El incremento del bundle se declara como coste de estas funciones, no como una optimización de tamaño.

## Diseño del consumo

- React y React DOM siguen siendo las dos dependencias directas de ejecución; no se añaden bibliotecas, fuentes, imágenes remotas o animaciones continuas.
- Dos divisores ligeros. Estado de tamaño aislado en cada divisor; CSS dimensiona los paneles. Un frame pendiente como máximo por divisor durante el arrastre. Sin bucle de frames en reposo ni sondeo periódico.
- `ResizeObserver` responde a cambios de contenedor; `matchMedia` al cruce del breakpoint. Ambos desconectan sus listeners al desmontar.
- Preferencias leídas al inicializar. El ancho se escribe al terminar el gesto; el borrador se limita a 2.000 caracteres. Las ejecuciones no se guardan en almacenamiento del navegador.
- Cada medición dura aproximadamente cinco segundos y conserva hasta diez muestras. Su `PerformanceObserver` se desconecta al terminar. Se admite que el panel de medida y la automatización influyan en el heap.
- El historial sintético representa 10.000 posiciones lógicas generando solo 50 filas visibles. No prueba persistencia o memoria de 10.000 eventos completos.

## Reproducción

```powershell
cd desktop
npm ci --ignore-scripts
npm test
npm run build
npm run preview -- --port 5316 --strictPort
```

Abrir `http://127.0.0.1:5316/?screen=stopping`, pulsar **Medir** y recoger tres muestras de reposo y tres del historial. Evitar el servidor HMR para esta medida. Exportar desde la UI; los bytes sin redondear se conservan en la evidencia. Registrar escena, tamaño CSS y visibilidad de la pestaña.

El peso gzip se calcula comprimiendo por separado cada asset y `index.html` con nivel 6, usando el mismo procedimiento que la referencia V5.4. Los hashes identifican el build medido; `dist` no se distribuye en el repositorio.

## Qué no se ha medido

El heap JS no es RAM total del navegador ni del futuro escritorio. No hay una medición atribuible de CPU, RAM residente/comprometida o GPU del host por pestaña. No se ejecutó el motor: sus cifras históricas no se presentan como resultados de V5.4.1.

No se afirma «60 fps constantes», ausencia de fugas, accesibilidad certificada ni cumplimiento del presupuesto total de V6. Las muestras cortas no sustituyen los treinta ciclos y los diez minutos de reposo previstos. Quedan pendientes trazas de interacción, host empaquetado, consumo conjunto y validación en equipos con poca memoria.

## Puerta de salida

Esta versión entrega una interfaz revisable y correcciones verificadas en su dominio. El presupuesto del escritorio, la calidad del resultado de los modelos y el transporte de eventos conservan sus pruebas pendientes. Un incremento pequeño de bytes o una muestra sin tareas largas no demuestra por sí solo una experiencia mejor.
