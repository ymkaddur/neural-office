# Frontera de seguridad del piloto

Esta política describe el núcleo Windows publicado, no la oficina generalista futura. La interfaz React V5.4.1 sigue desconectada; sus escenas no conceden autoridad. Las correcciones de esta auditoría se identifican como **núcleo 5.3.1** y por su commit. La etiqueta histórica `v5.3-preview.1` no las contiene.

| Actor o entrada | Confianza y control actual |
| --- | --- |
| HTML seleccionado | No confiable. Se captura con límite, no se ejecutan scripts y el modelo recibe códigos/posiciones de hallazgos, no el HTML bruto |
| Texto del objetivo y comentarios del modelo | Datos. No conceden permisos, no activan herramientas y no certifican la verdad del informe |
| Controlador del piloto | Autoridad operativa: ledger durable, cuotas, propietario de ejecución y comprobación del Job antes de recuperación |
| SQLite y testigo retenido | Evidencia de continuidad frente a errores y restauraciones parciales; no una caja fuerte frente al administrador que sustituye todos los archivos |
| Ollama y pesos instalados | Componentes del host que el usuario debe confiar. El Job permite poseer y terminar procesos; no es un sandbox de red/disco ni una cuota de RAM |
| Otros clientes locales | Fuera del control de admisión de este ledger. Loopback no autentica a todos los clientes de la máquina |
| Otros usuarios/administradores del host | No se promete aislamiento entre adversarios que comparten cuenta, archivos o privilegios. No es un servicio multiusuario expuesto a Internet |

Los datos del piloto se guardan localmente sin cifrado. No publicar SQLite, testigos, prompts, rutas privadas, logs completos, credenciales o pesos. La reproducción de un fallo debe usar datos sintéticos.

Las fuentes UNC y namespaces de dispositivo explícitos se rechazan antes de resolverlos. Eso no certifica unidades mapeadas, junctions ni la navegación realizada por el selector nativo. La política de red de toda la máquina y de los modelos no se deduce de ese rechazo.

Antes de incorporar skills con escritura, navegación o proveedores remotos hay que definir sus capacidades, aislamiento y pruebas de efectos. Los avisos de un prompt y los permisos de la UI no sustituyen esa frontera. Un reporte aceptado comprueba integridad y heurísticas limitadas; los comentarios permanecen `UNVERIFIED_ASSISTANCE`.

La [auditoría V5.4.1](docs/FORENSIC_AUDIT_V5_4_1.md) distingue fallos corregidos, hipótesis descartadas y riesgos abiertos. No es una certificación de seguridad ni garantiza ausencia de vulnerabilidades. No se ha verificado un canal privado de recepción de vulnerabilidades; no adjuntes datos sensibles a una incidencia pública.
