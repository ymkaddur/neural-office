# Revisar HTML

## En el escritorio

**Elegir archivo HTML → Comprobar HTML** muestra las ubicaciones en la copia seleccionada. Cada página contiene hasta 24 hallazgos. Puedes abrir la orientación con teclado o pasar a **Consultar al Director** con la misma fuente. Para analizar cambios en el original, vuelve a elegir el archivo. La vista estática se consulta en la ventana. El historial conserva los encargos autorizados con modelo.

## Una referencia sin modelo

```powershell
py -3.12 -B -m neural_office check --root examples --file examples/audit-sample.html
```

Lee una captura UTF-8 local de hasta 256 KiB, sin ejecutar sus scripts ni seguir enlaces. Imprime el informe JSON; puedes conservarlo mediante la redirección de tu terminal. Esta operación no abre un ledger, reserva intentos ni llama a Ollama. Los límites de captura son los mismos del piloto.

El ejemplo debe señalar idioma ausente, título vacío, imagen sin `alt` y control candidato sin etiqueta. Las reglas no necesitan IA. En la [comparación de V5.7](V5_7_REVIEW.md), las reglas y su orientación fija resolvieron tantas decisiones como los dos perfiles con modelo en la muestra ensayada.

## Interpretar el resultado

| Señal | Qué hacer |
|---|---|
| Idioma ausente | Declarar el idioma principal correcto en `html`. |
| Título ausente o vacío | Dar a la página un título descriptivo dentro de `head`. |
| Imagen sin `alt` | Decidir según su contexto: descripción informativa/funcional o alternativa vacía si es decorativa. |
| Control candidato | Comprobar su nombre accesible en el navegador y una etiqueta útil. |

La UI conserva las ubicaciones de la captura. Las comprobaciones globales de documento usan 1:1 como referencia, no como ubicación exacta de un nodo ausente. Si modificas el archivo después, vuelve a capturarlo antes de interpretar posiciones.

Las recomendaciones se apoyan en [idioma](https://www.w3.org/WAI/WCAG22/Understanding/language-of-page.html), [títulos](https://www.w3.org/WAI/WCAG22/Understanding/page-titled.html), [alternativas de imágenes](https://www.w3.org/WAI/tutorials/images/decision-tree/) y [etiquetas de controles](https://www.w3.org/WAI/tutorials/forms/labels/) de W3C WAI. La implementación cubre presencia y asociaciones simples, no todo lo que describen esas guías.

## Calidad comprobable y límites

El [corpus manual](../examples/html-review-corpus.json) contiene 18 casos de contrato y dos sondas semánticas separadas. Se redactaron las expectativas antes de ejecutar la comparación; el revisor conocía el código. No es un corpus ciego ni representativo de toda la web.

```powershell
py -3.12 -B tools/evaluate_v56_html.py
```

El evaluador publica cada expectativa y observación. Su código de salida refleja los 18 contratos históricos. V5.9 añade pruebas de regresión para las dos sondas que fallaban. Una referencia sin destino y una etiqueta vacía generan un candidato cuando el control carece de otra fuente de nombre reconocida. [Casos de prueba y contraste en Edge](V5_9_REVIEW.md).

Los informes nuevos llevan `static-html-checks-v3`. El escritorio puede reabrir informes v1, v2 y v3 a partir de sus bytes y recibos guardados. La asociación de una etiqueta se comprueba sobre el HTML capturado. CSS, scripts, árboles de sombra y el cálculo completo del nombre accesible requieren revisión en navegador.

No se calculan nombres accesibles completos, contraste, orden de foco, comportamiento JavaScript ni seguridad. Un resultado vacío significa que estas reglas no encontraron señales; no certifica que la página sea accesible. [Evaluación y cambios](V5_6_REVIEW.md).
