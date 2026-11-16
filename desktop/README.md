# Vista previa de escritorio · V5.3

Interfaz React/TypeScript navegable con diseño propio, tema claro/oscuro, actividad, informe, evidencia, presupuesto, modelos, skills planificadas y mediciones de referencia.

**Es una demo sin motor:** no llama a Python/Ollama, no abre archivos del usuario y no crea proyectos reales. Los trabajos e historial viven en memoria y se reinician al recargar. El único archivo que puede generar es un JSON sintético al pulsar exportar; contiene `mode: SIMULATION`. El piloto Python/Tkinter de la raíz sigue siendo la aplicación operativa.

## Abrir y comprobar

Node.js 24 (verificado con 24.21.0), npm y conexión para instalar las dependencias declaradas. No requiere Rust, Tauri, un modelo ni credenciales.

```powershell
cd desktop
npm ci --ignore-scripts
npm test
npm run build
npm run preview -- --port 5313 --strictPort
```

Abre `http://127.0.0.1:5313/`. El servidor escucha solo en loopback. Para editar con recarga de desarrollo: `npm run dev`. La instalación y el servidor de desarrollo son herramientas separadas de la inferencia local; no se promete que la descarga de paquetes sea offline.

Recorrido: simular auditoría → esperar verificación → abrir informe/evidencias → exportar demo. Prueba también detener durante ejecución, agotar tres intentos y el escenario de recuperación. Cada cancelación/fallo consume un intento simulado; no se libera la interfaz antes de la terminación simulada. Las flechas y Home/End cambian pestañas con teclado.

## Alcance técnico

- Siete pruebas de estado: doble inicio, eventos tardíos/duplicados/huecos, cuota, recuperación, verificación y configuración del siguiente equipo.
- Build con tipos comprobados; dependencias exactas y lockfile. No se incluye `node_modules` ni `dist` en Git.
- CSS y SVG propios. Fuentes del sistema; no descarga de fuentes o medios de terceros desde la aplicación.
- `baseline.json` contiene resultados observados, separados de la simulación; [método y límites](../docs/V5_3_MEASUREMENT_PROTOCOL.md).
- Contrato futuro Tauri↔Python: [especificación](../docs/V5_3_DESKTOP_CONTRACT.md). V5.3 no implementa permisos, transporte ni ledger en el navegador.

La captura publicada es del prototipo. El tamaño del bundle web no es el tamaño de un instalador, ni mide RAM de Tauri/webview/Python. Todavía no existe un paquete de escritorio autónomo.

## Licencias

MIT para el código propio. [Avisos de runtime frontend](THIRD_PARTY_NOTICES.md); [inventario declarado, incluidas herramientas y variantes opcionales](../docs/evidence/V5_3_COMPONENTS.json). Los paquetes de desarrollo conservan sus licencias propias. No se redistribuyen sus binarios en esta entrega de fuentes.
