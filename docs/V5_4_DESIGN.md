# V5.4 · Decisiones de interfaz

Estado: dirección propuesta, pendiente de revisión. [Galería](V5_4_UI_REVIEW.md).

## Objetivo y composición

El usuario debe reconocer el encargo, el estado y la entrega. El Director es el interlocutor principal; los roles se revelan dentro del trabajo cuando aportan información. Una sesión y su documento comparten espacio. Los controles de autoridad, fuentes, skills y medición se abren bajo demanda.

Navegación → sesión → conversación / entrega → inspector. La barra superior de cinco escenas es instrumental de revisión y no pertenece al producto final. La barra inferior conserva estado e intentos, distinguiendo ambos de las iteraciones internas.

| Decisión | Aplicación | Motivo y reserva |
| --- | --- | --- |
| Fuentes del sistema | Segoe UI / sistema; monoespaciada para referencias y código | Sin peticiones de fuentes ni cambio de layout por descarga; aspecto variable entre sistemas |
| Jerarquía tipográfica | Lectura principal 14–15 px; metadatos principalmente 12–13 px | Densidad sin convertir todo en texto pequeño; revisar escalado y preferencias |
| Fondo y superficies | Navegación grafito, lienzo neutro, documento blanco; variante oscura equivalente | Separar zonas por función, no por cuadrículas de tarjetas |
| Acento contenido | Terracota para identidad/foco; verde/error para estado con texto | Color acompañado por palabras e iconos; no depender solo de puntos |
| Iconos | SVG propios, decorativos ocultos a tecnologías de asistencia | Sin paquete adicional; botones iconográficos con nombre accesible |
| Movimiento | Sin animaciones, shimmer, barra falsa de progreso ni bucle permanente | Atención en el contenido y trabajo acotado en reposo |
| Detalle progresivo | Diálogos nativos, actividad desplegable y pestañas | Menos controles permanentes; preservar foco y cierre predecible |
| Historial | Ventana de 50 filas en el ensayo de paginación | No añadir miles de nodos; pendiente almacenamiento y transporte real |

Tokens y reglas en [workspace.css](../desktop/src/workspace/workspace.css). Composición en [Workspace.tsx](../desktop/src/workspace/Workspace.tsx). Fixtures originales en [fixtures.ts](../desktop/src/workspace/fixtures.ts); no contienen archivos de usuarios, transcripciones, recursos de competidores ni testimonios.

## Estados y límites

`ready → running → result | error | stopping`. `stopping` necesita confirmación antes de admitir otro trabajo. Las acciones terminales llevan una revisión; una respuesta atrasada no completa otro recorrido. Vacío, doble inicio y cuota agotada no admiten trabajo. [Transiciones de la fixture](../desktop/src/workspace/model.ts#L14-L24).

Esto **no es el contrato del motor**. La fixture no implementa persistencia autoritativa, secuencias IPC, resincronización o recuperación tras caída. La galería carga estados preparados y reinicia su contador; «Nuevo encargo» durante el recorrido no devuelve intentos. Solo el borrador y el tema se conservan en `sessionStorage`; no hay historial persistente. El contenido escrito permanece en el navegador local, sin cifrado ni garantía de persistencia fuera de esa pestaña.

La futura integración debe conservar generación, secuencia, idempotencia, reserva de presupuesto, parada confirmada y `RECOVERY_REQUIRED` del [contrato de escritorio](V5_3_DESKTOP_CONTRACT.md). No sustituir ese contrato por el reductor de demostración.

## Recursos y procedencia

React/ReactDOM, TypeScript y Vite ya estaban declarados. Esta fase no añade bibliotecas, fuentes ni medios al runtime. Las capturas viven en documentación y no se cargan en la aplicación. No hay servidor de API, shell, lectura de archivos, telemetría ni peticiones al modelo desde la UI. La política CSP del build restringe conexiones; el servidor de desarrollo tiene HMR y un régimen distinto. [Configuración](../desktop/vite.config.ts).

No se copiaron código, logos o ilustraciones de Claude, OpenCode, T3 o de la auditoría recibida. Las referencias orientan la composición; no demuestran preferencia de usuarios. La crítica previa y la revisión dirigida de vídeos se traducen aquí en artefacto visible, contexto inspeccionable y separación de memoria/UI/modelo. No se distribuyen los vídeos ni se presenta su muestreo como reproducción audiovisual completa. [Investigación anterior delimitada](V5_3_VIDEO_RESEARCH.md).

## Puerta G-UI

Debe quedar aceptada la dirección visual y cerrada una lista de ajustes, con los cinco estados reconocibles. Pendientes: paneles redimensionables, casos largos, lector de pantalla, escalado y sesiones formativas. Una suite verde no concede aceptación visual. No se anuncian memoria aprendida, skills ejecutables, tres iteraciones reales, múltiples proyectos o un instalador como capacidades de esta UI.
