# Frontera de seguridad del piloto

Esta política describe el núcleo Windows y su adaptador desktop V5.5, no la oficina generalista futura. La galería V5.4.1 conserva escenas desconectadas explícitas. La interfaz conectada envía un conjunto cerrado de comandos al host; una ruta arbitraria del renderer no se convierte en selección de archivo. El selector nativo captura la fuente y el núcleo valida alcance, revisión e identidad antes de reservar. [Código y pruebas de estas fronteras](docs/V5_5_VERIFICATION.md).

| Actor o entrada | Confianza y control actual |
| --- | --- |
| HTML seleccionado | No confiable. Se captura con límite, no se ejecutan scripts y el modelo recibe códigos/posiciones de hallazgos, no el HTML bruto |
| Texto del objetivo y comentarios del modelo | Datos. No conceden permisos, no activan herramientas y no certifican la verdad del informe |
| Controlador del piloto y sidecar desktop | Autoridad operativa: ledger durable, cuotas, propietario de ejecución y comprobación del Job antes de recuperación |
| SQLite y testigo retenido | Evidencia de continuidad frente a errores y restauraciones parciales; no una caja fuerte frente al administrador que sustituye todos los archivos |
| Ollama y pesos instalados | Componentes del host que el usuario debe confiar. El Job permite poseer y terminar procesos; no es un sandbox de red/disco ni una cuota de RAM |
| Otros clientes locales | Fuera del control de admisión de este ledger. Loopback no autentica a todos los clientes de la máquina |
| Otros usuarios/administradores del host | No se promete aislamiento entre adversarios que comparten cuenta, archivos o privilegios. No es un servicio multiusuario expuesto a Internet |

Los datos del piloto se guardan localmente sin cifrado. No publicar SQLite, testigos, prompts, rutas privadas, logs completos, credenciales o pesos. La reproducción de un fallo debe usar datos sintéticos.

V5.7 rechaza las rutas explícitas de flujos NTFS nombrados antes de consultar el sistema de archivos. El escritorio exige una captura vigente del proyecto para leer sus hallazgos estáticos. Une estado aceptado y veredicto positivo al publicar el informe asistido. Los intentos rechazados conservan su evidencia en el ledger local. [Investigación y alcance](docs/V5_7_REVIEW.md).

Las fuentes UNC y namespaces de dispositivo explícitos se rechazan antes de resolverlos. Eso no certifica unidades mapeadas, junctions ni la navegación realizada por el selector nativo. La política de red de toda la máquina y de los modelos no se deduce de ese rechazo.

Antes de incorporar skills con escritura, navegación o proveedores remotos hay que definir sus capacidades, aislamiento y pruebas de efectos. Los avisos de un prompt y los permisos de la UI no sustituyen esa frontera. Un reporte aceptado comprueba integridad y heurísticas limitadas; los comentarios permanecen `UNVERIFIED_ASSISTANCE`.

La [auditoría V5.4.1](docs/FORENSIC_AUDIT_V5_4_1.md) distingue fallos corregidos, hipótesis descartadas y riesgos abiertos. No es una certificación de seguridad ni garantiza ausencia de vulnerabilidades. No se ha verificado un canal privado de recepción de vulnerabilidades; no adjuntes datos sensibles a una incidencia pública.

V5.5 limita framing, solicitudes pendientes, catálogo y fragmentos de informe; la UI presenta texto escapado, no HTML del modelo. La política CSP no concede red de proveedor o shell al renderer. El host configura Python y estado desde un launcher de confianza; no es instalación para un entorno multiusuario adversarial. La configuración del host y los runtimes instalados forman parte de su frontera de confianza.

La [auditoría V5.5](docs/V5_5_VERIFICATION.md) conserva fallos y contrapruebas, incluido R13 de arranque. El binario de desarrollo no está firmado; Windows puede impedir ejecutarlo. No se recomienda desactivar controles del sistema. Publicar un artefacto CI no constituye garantía de seguridad ni prueba de instalación en todos los equipos.
