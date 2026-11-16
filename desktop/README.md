# Vista previa de escritorio · V5.4

Un espacio de trabajo con Director, fuentes inspeccionables y entrega comparada. **Cinco pantallas para revisión visual, todavía sin motor.** [Ver la galería](../docs/V5_4_UI_REVIEW.md) · [Mediciones y límites](../docs/V5_4_RESOURCE_BASELINE.md).

## Abrir

Node.js 24 (verificado con 24.21.0), npm y conexión para instalar las dependencias fijadas. No requiere Rust, Tauri, modelo o credenciales.

```powershell
cd desktop
npm ci --ignore-scripts
npm test
npm run build
npm run preview -- --port 5315 --strictPort
```

Abre `http://127.0.0.1:5315/`. El servidor escucha en loopback. La barra superior permite recorrer las cinco escenas; también se pueden abrir directamente:

| Ruta | Escena |
| --- | --- |
| `/?screen=ready` | Objetivo, fuentes y compositor |
| `/?screen=running` | Director, revisor y borrador parcial |
| `/?screen=result` | Entrega, cambios y exportación |
| `/?screen=error` | Encargo conservado, resultado sin generar |
| `/?screen=stopping` | Parada solicitada y confirmación pendiente |

Para desarrollo con recarga: `npm run dev`. La política CSP estricta se incorpora al **build**; el desarrollo necesita inyección de estilos y HMR. Probar el modo `preview` evita confundir esa actividad con el reposo de producción. El tamaño gzip no es RAM ni tamaño de un instalador.

## Qué puedes probar

1. Abrir una fuente y leer sus líneas. Editar el objetivo y comenzar con Ctrl+Enter.
2. En curso: abrir `alcance.md:6`, inspeccionar la actividad y avanzar manualmente a la entrega.
3. Comparar v1 y v2, cambiar pestañas con flechas/Home/End y exportar Markdown.
4. Solicitar parada: hasta confirmar el cierre simulado no se admite otro trabajo; la cuota permanece consumida.
5. Cargar el error y reintentar: consume otro intento de ejemplo.
6. Cambiar tema, ocultar la entrega y probar una ventana estrecha.
7. «Medir»: tres o más muestras de reposo y de historial. Cada muestra dura cinco segundos, conserva como máximo diez resultados y desconecta el colector al terminar. Se puede exportar JSON.

El historial de medición genera **solo 50 filas de una secuencia lógica de 10.000**. Mide representación paginada, no almacenamiento de 10.000 eventos completos. `performance.memory`, cuando está disponible, es una aproximación del heap JS y puede incluir instrumentación. No representa memoria privada del navegador, WebView, Python o modelo.

## Contrato de esta demostración

Todo el contenido de «Norte» es sintético y está incluido en el código. **Cambiar el objetivo no genera una respuesta nueva**: el artefacto está preparado para revisar la interfaz. Los botones no llaman a Python/Ollama, no leen archivos ni modifican proyectos reales. El piloto Python/Tkinter de la raíz conserva el motor operativo V5.3.

La galería carga fixtures independientes: navegar a otra escena o recargar reinicia su estado y contador. «Nuevo encargo» dentro del recorrido no reembolsa intentos. Solo borrador y tema se guardan en `sessionStorage`; no se implementa continuidad de ejecuciones. Si el almacenamiento está bloqueado, el borrador funciona en memoria y se avisa.

Las dos descargas posibles son Markdown sintético y JSON de muestras de UI. No hay subida de documentos, analítica ni fuentes remotas. La parada confirmada es una **acción manual de demostración**; no prueba terminación de procesos reales.

## Verificación y límites

Doce pruebas: siete del estado anterior conservado y cinco del recorrido nuevo. Incluyen doble inicio, eventos terminales atrasados, cuota, cancelación y paginación en los bordes. Comprobación TypeScript + build y recorridos manuales de navegador registrados en [V5_4_UI.json](../docs/evidence/V5_4_UI.json).

El código anterior `App.tsx/state.ts/styles.css` se conserva para trazabilidad; `main.tsx` monta `workspace/Workspace.tsx`. No se mezclan sus reductores ni se transportan eventos del motor a la fixture. [Contrato futuro Tauri↔Python](../docs/V5_3_DESKTOP_CONTRACT.md).

Pendientes: aceptación visual, paneles redimensionables, pruebas formativas, lector de pantalla y carga real; después transporte, persistencia y recuperación. No hay instalador autónomo ni host Tauri en esta entrega.

## Licencias

MIT para el código propio. CSS, SVG y fixtures originales. [Avisos de terceros](THIRD_PARTY_NOTICES.md) e [inventario previo](../docs/evidence/V5_3_COMPONENTS.json); V5.4 no añade dependencias. No se publican `node_modules`, `dist`, vídeos, modelos, logs privados ni bases de datos.
