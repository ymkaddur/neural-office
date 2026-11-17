# Evidencia y límites de transferencia

Investigación consultada el 16–17 de noviembre de 2026. Los mecanismos externos se inspeccionaron en los archivos enlazados; no se ejecutaron sus repositorios. Las aplicaciones propuestas a Neural Office requieren prueba propia. Las licencias se indican para evitar confundir observación con permiso de copia.

## Lección aplicada al proyecto

Estos mecanismos orientan pruebas, no certifican la interfaz de Neural Office. Una prueba DOM con React real todavía no prueba WebView2 ni lector de pantalla. Para paneles, conserva también el ensayo de drawer abierto al cambiar a viewport ancho y el de compositor a poca altura, descritos en la skill existente de revisión de evidencia.


## Mecanismos externos

### radix-ui/primitives

[Archivo en el commit inspeccionado](https://github.com/radix-ui/primitives/blob/eb3a2b7091293e27df8f9ba906632d8daa3d81a3/packages/react/focus-scope/src/focus-scope.tsx#L69). Líneas 69-85,113-160,165-205,207-237; nivel: `source-inspected`.

OBSERVADO: el scope mantiene ramas según el commit, ignora focusout con relatedTarget nulo, limpia listeners/observer y respeta composición IME antes de procesar Tab. PROPUESTA V5.5/V6: probar cierre de aprobación, eliminación del elemento enfocado, cambio de ventana y teclado IME sin saltos de foco ni listeners vivos; restaurar un destino válido al cerrar.

**Límite:** Inspección estática, sin ejecutar estos tests ni reproducir el comentario histórico sobre CPU. FocusScope es una pieza; no demuestra que todos los diálogos de una aplicación tengan nombre, orden correcto o anuncios útiles.

**Licencia observada:** MIT; LICENSE:1-21 leído en el commit indicado.

### adobe/react-spectrum

[Archivo en el commit inspeccionado](https://github.com/adobe/react-spectrum/blob/360e35170568dfc99a2baaa78e6b7bdd36458d91/packages/react-aria/src/live-announcer/LiveAnnouncer.tsx#L13). Líneas 13-55,58-75,121-162; nivel: `source-inspected`.

OBSERVADO: regiones separadas polite/assertive, anuncios como textContent, eliminación por timeout y destrucción explícita del anunciador; contempla el montaje previo del live region. PROPUESTA V5.5/V6: anunciar transiciones relevantes del encargo, no cada token; diferenciar progreso de error accionable y comprobar lector de pantalla tras reapertura y duplicados.

**Límite:** No se ejecutó con NVDA/JAWS/VoiceOver ni WebView2. El retraso Safari descrito en comentarios y el timeout por defecto no son cifras transferibles sin pruebas. La fuente no demuestra deduplicación de eventos: esa responsabilidad sigue en nuestro contrato.

**Licencia observada:** Apache-2.0; LICENSE:1-25 e identificación del encabezado del fichero.

### reach/reach-ui

[Archivo en el commit inspeccionado](https://github.com/reach/reach-ui/blob/b3d94d22811db6b5c0f272b9a7e2e3c1bb4699ae/packages/dialog/src/reach-dialog.tsx#L142). Líneas 142-190; nivel: `source-inspected`.

OBSERVADO: combina foco inicial/restauración, Escape y bloqueo de scroll; el dismissal por clic compara el objetivo de mousedown con el del clic. PROPUESTA V5.5/V6: seleccionar texto dentro del diálogo y terminar el gesto fuera no debe descartar accidentalmente la aprobación; comprobar Escape, foco de retorno y conservación del borrador.

**Límite:** Inspección del componente delegador, sin ejecutar sus dependencias FocusLock/RemoveScroll. HEAD del branch dev es de 2025; no usar como prueba de mantenimiento reciente ni copiar todos sus bypasses. No demuestra por sí solo accesibilidad de la aplicación.

**Licencia observada:** MIT; LICENSE:1-20 leído.

### tailwindlabs/headlessui

[Archivo en el commit inspeccionado](https://github.com/tailwindlabs/headlessui/blob/eea57cf46fd6767ed1059012f7073b88eb159fba/packages/@headlessui-react/src/components/focus-trap/focus-trap.tsx#L51). Líneas 51-72,91-121,147-199; nivel: `source-inspected`.

OBSERVADO: separa initial focus, Tab lock, focus lock y restore; usa useIsTopLayer para guardas de Tab y diferencia blur por teclado de otras salidas de foco. PROPUESTA V5.5/V6: una sola capa modal efectiva; probar dos capas, cambio de tamaño/drawer, último elemento y restitución al cerrar sin capturar el teclado del compositor.

**Límite:** No se inspeccionó todo useIsTopLayer ni se ejecutó el navegador. Las cuatro propiedades son distintas: un test de Tab no prueba restauración o interacción con capas. La librería resuelve mecanismos, no la jerarquía del producto.

**Licencia observada:** MIT; LICENSE:1-21 leído.

### dequelabs/axe-core

[Archivo en el commit inspeccionado](https://github.com/dequelabs/axe-core/blob/e80f6b797b32b5f9d60ddaa0a7afad6ed864f121/lib/checks/color/color-contrast-evaluate.js#L20). Líneas 20-80,130-187; nivel: `source-inspected`.

OBSERVADO: el evaluador distingue resultados indeterminados para pseudocontenido, colores incompletos y ciertos textos cortos/vacíos; adjunta datos del contraste. PROPUESTA V5.5/V6: registrar violations e incomplete por tema/estado, revisar los indeterminados y hacer pruebas visuales y de teclado con errores, parada, controles deshabilitados y foco.

**Límite:** Se inspeccionó un evaluador, no se ejecutó axe ni se certificó WCAG. Ausencia de violations puede coexistir con resultados que requieren revisión y con problemas fuera de sus reglas. MPL-2.0 es distinta de MIT; esta investigación no incorpora código de axe.

**Licencia observada:** MPL-2.0; LICENSE:1-25 leído; LICENSE-3RD-PARTY.txt presente, no auditado completo.


## Feedback público

### F03: Codex: cancelación accidental con una sola pulsación de Escape

[Fuente pública](https://github.com/openai/codex/issues/14509). Publicación: 2026-03-12T20:19:32Z. Consulta: 2026-11-17. Localizador: GitHub issue body; Summary, Requested behavior, Environment.

OBSERVADO: el autor de la solicitud informa interrupciones accidentales con Escape en CLI 0.114.0 y pide doble pulsación, con comportamiento dependiente de si el compositor contiene texto.

HIPÓTESIS: Escape para cerrar overlays y cancelación de ejecución deben tener ámbitos inequívocos; preservar borradores reduce daños por errores de teclado.

PENDIENTE: probar Escape con diálogo abierto/cerrado, borrador vacío/no vacío y trabajo activo; comprobar que cerrar un menú no cancela y que cancelar no borra el borrador.

**Límite:** Preferencia de una persona, no prueba de que doble Escape sea universalmente mejor. Issue abierto al consultar; comportamiento actual no reproducido.

### F05: OpenCode: navegación esperada en un compositor multilínea

[Fuente pública](https://github.com/anomalyco/opencode/issues/2649). Publicación: 2025-09-17T16:31:05Z. Consulta: 2026-11-17. Localizador: GitHub issue body, receta de tres pasos y párrafos siguientes.

OBSERVADO: el autor reporta que Home/End saltaban al inicio/final de todo el prompt en vez de la línea, lo que dificultaba editar textos largos; tampoco encontraba alternativa documentada.

HIPÓTESIS: un compositor con edición nativa y atajos documentados aporta más utilidad que añadir controles decorativos.

PENDIENTE: teclado con líneas envueltas y saltos reales, Home/End, Ctrl+flechas, selección, IME y pegado; enviar solo con el gesto configurado y sin perder texto.

**Límite:** Reporte histórico cerrado; no se verificó el estado actual de OpenCode ni la convención de todas las plataformas. No imponer un mapa de teclas de terminal a un editor web sin validación.


## Método docente

### Stanford University

[Assignment 7: Heuristic Evaluation (Individual)](https://hci.stanford.edu/courses/cs147/2025/au/assignments/Assignment_07_Heuristic_Evaluation_Individual.pdf). CS147, Autumn 2025. Nivel: Material docente: instrucciones y rúbrica de evaluación. Localizador: PDF, páginas 1–4; tareas implementadas, severidad, justificación y recomendaciones. Consulta: 2026-11-16.

OBSERVADO: exige recorrer las tareas implementadas y documentar violación, heurística, severidad, explicación y remedio. Distingue evaluar el prototipo de enumerar funcionalidades ausentes.

PROPUESTA: auditar las cinco pantallas mediante tareas y fallos observables; eliminar duplicados. No adoptar la cuota de incidencias de la rúbrica académica como obligación de inventar defectos.

**Comprobación propuesta:** Para iniciar, detener y reabrir un resultado, adjuntar interacción reproducible, captura, severidad y corrección localizada; comprobar la misma tarea después.

**Límite:** Evaluación heurística, no ensayo con clientes. Una rúbrica académica no demuestra superioridad de producto.
