---
name: neural-office-accessible-workspace
description: Implementar o revisar teclado, foco, composición de texto y anuncios de estado en el escritorio de Neural Office. Úsala al modificar compositor, diálogos, paneles o navegación; no equivale a una certificación de accesibilidad.
---

# Interacción accesible del escritorio

Parte del control real y su estado, no de una captura. Conserva elementos nativos cuando expresen la operación. Personalizar una primitiva no exige heredar su aspecto ni permite eliminar nombre, semántica o salida accesible.

Lee [la evidencia pertinente](references/evidence.md) al tocar foco, anuncios o compositor. Selecciona las pruebas del componente afectado:

| Cambio | Frontera que hay que comprobar |
|---|---|
| Aprobación o diálogo | Foco inicial útil, Tab/Shift+Tab, Escape sin aprobar, retorno cuando el disparador desaparece; apertura y cierre repetidos sin listeners residuales. |
| Capas y navegación | Una sola capa modal efectiva; cerrar menú no cancela la ejecución. Abrir drawer estrecho y ensanchar deja el área principal operable, sin overlay o foco atrapado. |
| Compositor | Home/End por línea según plataforma, selección, saltos reales y líneas envueltas, pegado e IME. Enter durante composición no envía. El rechazo tardío de un envío conserva el texto nuevo. |
| Panel ajustable | Nombre y orientación del separador, ajuste por teclado, límites de tamaño, cancelación de captura y foco visible. Diferencia anchura deseada de anchura efectiva. |
| Avisos | Anunciar decisiones, fallos accionables y finales; no cada token. Deduplicar por identidad de evento. No anunciar «terminado» al recibir una simple solicitud de parada. |

No uses `relatedTarget === null` como prueba suficiente de que el usuario intentó salir del diálogo. Comprueba cambio de ventana y eliminación del elemento enfocado. Un gesto de selección iniciado dentro y terminado fuera tampoco debe convertirse por accidente en consentimiento o descarte.

Verifica contraste, foco y movimiento reducido en estados reales, incluidos error y deshabilitado. Si ejecutas un escáner, conserva sus resultados indeterminados y revísalos: ausencia de `violations` no implica cobertura completa. Distingue análisis JSX, DOM simulado, navegador, WebView nativo y lector de pantalla; informa cuál se utilizó.

La salida útil es una tabla breve de recorridos ejecutados, resultado y bloqueo pendiente, junto al cambio mínimo. No agregues un framework o una dependencia únicamente para poder afirmar accesibilidad. Si el cambio afecta anuncios o navegación asistiva, deja explícita la prueba con tecnología de asistencia que aún falte.
