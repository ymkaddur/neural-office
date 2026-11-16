# Vista previa de escritorio · V5.4.1

Director, versiones y fuentes en un espacio ajustable. **Cinco pantallas para revisión visual, sin conectar el motor.** [Galería y revisión crítica](../docs/V5_4_1_UI_REVIEW.md) · [Recursos](../docs/V5_4_1_RESOURCE_BASELINE.md).

## Abrir

Node.js 24 (verificado con 24.21.0), npm y conexión para instalar las dependencias fijadas. No requiere Rust, Tauri, modelo o credenciales.

```powershell
cd desktop
npm ci --ignore-scripts
npm test
npm run build
npm run preview -- --port 5316 --strictPort
```

Abre `http://127.0.0.1:5316/`. El servidor escucha en loopback. La barra superior cambia entre escenas independientes:

| Ruta | Escena |
| --- | --- |
| `/?screen=ready` | Objetivo, fuentes y compositor |
| `/?screen=running` | Borrador y actividad del equipo |
| `/?screen=result` | Entrega v3, versiones anteriores, cambios y exportación |
| `/?screen=error` | Encargo editable, sin resultado generado |
| `/?screen=stopping` | Confirmación pendiente antes de admitir otro inicio |

## Recorrido de revisión

1. En Inicio, inspecciona las fuentes y envía el objetivo con el botón o Ctrl+Enter. Se consume un intento y el compositor queda vacío.
2. Pulsa **Simular revisión**, **Simular integración** y **Mostrar entrega**. Son tres etapas manuales del mismo intento; no hay llamadas al modelo.
3. Selecciona Borrador, Revisión o Entrega en la franja superior. La pestaña Cambios compara v1 → v2 y v2 → v3. Solo v3 terminada habilita exportar el Markdown preparado.
4. Escribe un nuevo mensaje para probar un ajuste. La respuesta de Norte continúa siendo fija; se ensaya la interacción, no generación de contenido.
5. Arrastra los divisores de navegación o conversación. También admiten flechas, Shift+flechas, Home/End y Enter para restablecer. Escape cancela el arrastre en curso. La entrega puede ocultarse con su botón; en ventanas estrechas los paneles se apilan.
6. Detén un ejemplo. Hasta pulsar **Simular cierre confirmado** no se admite otro trabajo. Fallo, parada y «Nuevo encargo» no reembolsan intentos.
7. En Error, edita el encargo y usa el único botón de reintento. Con texto vacío o tres intentos consumidos queda desactivado.
8. Cambia tema y tamaño de ventana. En **Medir**, toma muestras de cinco segundos y exporta su JSON.

## Datos, límites y consumo

El material de Norte es sintético y está incluido en el código. La UI no llama a Python/Ollama, no lee archivos del usuario y no altera proyectos. La parada confirmada es manual; no prueba cierre de procesos. El piloto Python/Tkinter de la raíz conserva el motor V5.3.

Recargar o cambiar de escena carga una fixture nueva y reinicia sus contadores. No existe continuidad de ejecuciones. Borrador de **Inicio**, tema y anchos se conservan en `sessionStorage` durante la pestaña; los mensajes de ajuste y reintento no se restauran tras recargar. Si el borrador no puede guardarse, se avisa. Los tamaños mantienen funcionamiento en memoria si el almacenamiento está bloqueado.

No hay analítica, fuentes remotas, intervalos de sondeo o librerías nuevas de paneles. El build incluye CSP con `connect-src 'none'`; `npm run dev` usa HMR y no representa el reposo de producción. Las descargas son Markdown sintético y JSON de muestras.

La prueba de historial genera **50 filas de 10.000 posiciones lógicas**, no 10.000 objetos persistentes. El heap JS, cuando está disponible, no representa RAM total del navegador, Python, GPU o modelo. Cada muestra desconecta su colector al terminar y solo se conservan diez.

## Verificación y procedencia

18 pruebas Node: siete del estado anterior, ocho del recorrido y tres de tamaños. Incluyen eventos duplicados/atrasados, reenvío vacío, cuota, cierre, tres etapas, almacenamiento inválido y límites de paneles. TypeScript, build y comprobaciones manuales de navegador: [evidencia](../docs/evidence/V5_4_1_VERIFICATION.json).

`main.tsx` monta `workspace/Workspace.tsx`. Los componentes anteriores permanecen para trazabilidad. MIT para código propio; SVG, CSS y fixtures originales. No se ha copiado código o material gráfico de Dusk. [Avisos de terceros](THIRD_PARTY_NOTICES.md).

Quedan pendientes aceptación visual, pruebas con usuarios, lector de pantalla, dispositivos táctiles, transporte y escritorio empaquetado. Esta entrega no certifica G-UI ni ausencia total de errores.
