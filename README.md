# Neural Office

**Tu oficina de agentes de IA, en tu máquina.**

Software gratuito y de código abierto bajo [MIT](LICENSE), con [apoyo voluntario](#apoya-el-proyecto) y las mismas funciones para todas las personas.

Hoy puedes revisar un HTML local con un modelo instalado, conservar su informe y controlar cada intento. **V5.5 conecta el espacio de trabajo React con el núcleo Python mediante Tauri:** fuente explícita, aprobación, ejecución acotada y entrega revisable. Es una vista previa de desarrollo para Windows; aceptación visual, arranque intermitente e instalación en equipos nuevos siguen abiertos. [Qué se ha probado y qué falta](docs/V5_5_VERIFICATION.md).

[![Tests Windows](https://github.com/ymkaddur/neural-office/actions/workflows/windows-tests.yml/badge.svg?branch=main)](https://github.com/ymkaddur/neural-office/actions/workflows/windows-tests.yml)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue)](https://www.python.org/downloads/)
[![Licencia MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

[Abrir el escritorio de desarrollo](desktop/README.md) · [Hoja de ruta hasta V6](docs/V5_5_TO_V6.md) · [Investigación de 80 repositorios](docs/V5_5_RESEARCH.md) · [Skills de desarrollo](skills/README.md).

La [galería V5.4.1](docs/V5_4_1_UI_REVIEW.md) se conserva como ejemplo sintético separado. En un navegador se abre explícitamente con `?preview=1&screen=ready`: sus escenas no ejecutan modelos. El escritorio usa el servicio real y conserva el estado del piloto; no se borra una oficina para actualizarla.

## Usar el piloto HTML desde Python

Necesitas **Windows, Python 3.12 con Tk y Ollama con un modelo local ya descargado**. Esta descarga contiene el código del piloto; el instalador autónomo es un hito futuro.

1. [Descarga la revisión actual del piloto](https://github.com/ymkaddur/neural-office/archive/refs/heads/main.zip) y extrae la carpeta. Cierra los controladores anteriores antes de usarla; la etiqueta histórica `v5.3-preview.1` no contiene las correcciones de esta auditoría.
2. Abre `.\run.bat`. También puedes ejecutar `py -3.12 -B -m neural_office gui` desde esa carpeta.
3. Selecciona el modelo, pulsa **Usar ejemplo** y después **Autorizar y auditar**.
4. Consulta **Ver presupuesto** y **Ver último informe**. **Detener** solicita cancelar y espera la terminación comprobada.

El [HTML de ejemplo](examples/audit-sample.html) tiene cuatro hallazgos esperados: falta de idioma, título vacío, imagen sin `alt` y un control cuya etiqueta hay que revisar. No requiere descargar una web. Los comentarios generados pueden variar; las comprobaciones estáticas tienen un resultado contrastable.

El piloto admite HTML UTF-8 de hasta 256 KiB. Lee la entrada sin ejecutar sus scripts, seguir sus enlaces ni modificarla. El análisis cubre esas heurísticas, no una certificación de accesibilidad o seguridad.

## Lo que puedes controlar hoy

- **Roles:** uno, tres o siete, ejecutados en secuencia con un backend local propio.
- **Presupuesto:** tres intentos por proyecto; los fallos y cancelaciones cuentan. Es el límite deliberado de esta vista previa.
- **Parada y recuperación:** el árbol de procesos propio debe terminar antes de liberar el bloqueo.
- **Evidencia:** entradas capturadas, respuestas e informe guardados localmente, con verificación de las comprobaciones estáticas.
- **Continuidad:** respaldo y restauración con un testigo retenido, sin devolver intentos al cargar una copia antigua.
- **Historial:** conciliación explícita de fuentes V1/V4/Plus y ledgers compatibles; importar no activa proyectos ni concede autoridad.

Se admite una inferencia administrada por ledger y hasta dos proyectos activos. La conciliación bloquea discrepancias y esquemas no mapeados; no sustituye ni controla clientes externos como OpenCode. El [manual de continuidad y conciliación](docs/V5_2_1_OPERATIONS.md) explica el alcance, los comandos y la conservación del testigo.

**Si ya usabas V5.2:** cierra los controladores anteriores y ejecuta `.\run.bat protect` sobre tu estado existente antes de abrir la interfaz. No borres el estado para actualizar. Para un ledger explícito: `.\run.bat --state "D:\NeuralOfficeState\office.sqlite3" protect`.

## Estado de la entrega

| Capacidad | Estado |
| --- | --- |
| Piloto HTML, informes y cuotas persistentes | Pruebas actuales; ejecuciones con modelo documentadas históricamente en [V5.3](docs/V5_3_MEASUREMENT_PROTOCOL.md) y [V5.4](docs/evidence/V5_4_ENGINE.json) |
| Conciliación histórica y restauración | Verificadas para los esquemas y límites documentados |
| Respuesta 401 intermitente del gateway histórico | Reproducida y corregida; diff y regresión publicados |
| Timeout histórico al arrancar Ollama | Causa pendiente; instrumentación por etapas verificada |
| Medición CPU, memoria del backend y comparación 1/3/7 | V5.3: seis intentos reales aceptados; calidad comparada y GPU pendientes; la auditoría actual usa datos sintéticos |
| Escritorio V5.5 | Interfaz conectada mediante Tauri/Python; [recorrido real y limitaciones](docs/V5_5_VERIFICATION.md). Galería sintética aparte; aceptación visual pendiente |
| Contrato de escritorio | Transporte restringido, captura nativa, reserva durable, aprobación ligada a revisión y lectura verificada del informe |
| Memoria, skills aprendidas y tareas generales | Planificadas |
| Instalador autónomo y otros sistemas operativos | Planificados |

La [auditoría de V5.4.1](docs/FORENSIC_AUDIT_V5_4_1.md) documenta tres defectos corregidos: recuperación durante arranque, protección inicial interrumpida y rechazo tardío de rutas de red. Distingue fiabilidad y seguridad sin declarar tres vulnerabilidades críticas. Consulta la [frontera de confianza](SECURITY.md) y la [visión hasta V10](ROADMAP.md). Los informes [V5.3](docs/V5_3_FORENSIC_REVIEW.md) y [V5.2.1](docs/V5_2_1_FORENSIC_REVIEW.md) conservan su evidencia histórica.

## Optimización con una referencia real

| Roles en secuencia | Mediana total | Pico residente observado del backend¹ |
| --- | --- | --- |
| 1 | 28,80 s | 5,88 GiB |
| 3 | 57,39 s | 6,25 GiB |
| 7 | 109,46 s | 6,90 GiB |

Dos ensayos por perfil, una máquina, el HTML incluido y un modelo en CPU. ¹ Suma muestreada de memoria residente; puede contar páginas compartidas varias veces y excluye interfaz/controlador. Estas cifras no son requisitos mínimos ni una comparación de calidad. [Protocolo, entorno y recibos](docs/V5_3_MEASUREMENT_PROTOCOL.md).

V5.4 publica una [nueva línea base](docs/V5_4_RESOURCE_BASELINE.md): tres ensayos CPU del motor conservado y muestras de la UI por separado. No se anuncia una aceleración ni un consumo total del futuro escritorio. V5.5 añade integración real y conserva abierta la aceptación visual; el corpus amplio y las comparaciones controladas siguen pendientes. [Contrato de integración](docs/V5_3_DESKTOP_CONTRACT.md) · [revisión dirigida de vídeos](docs/V5_3_VIDEO_RESEARCH.md).

La entrega visual original V5.4.1 mantuvo el motor intacto y [midió solo el frontend](docs/V5_4_1_RESOURCE_BASELINE.md). Corrigió reenvío involuntario, bloqueo de navegación entre tamaños y prioridad visual de la parada. La auditoría posterior incorpora las correcciones del núcleo 5.3.1 documentadas arriba; las dependencias de ejecución siguen iguales. La [revisión visual](docs/V5_4_1_UI_REVIEW.md) conserva su alcance original.

## Apoya el proyecto

Neural Office es gratuito y de código abierto. Puedes usar todas sus funciones disponibles sin pagar ni tener una cuenta de patrocinador. El apoyo es voluntario y ayuda a sostener el desarrollo, las pruebas, la documentación y la distribución.

Los límites técnicos de esta vista previa se aplican por igual a todo el mundo. Aportar no desbloquea funciones ni aumenta cuotas; tampoco concede acceso anticipado, prioridad de soporte o trabajo personalizado. Las novedades y la documentación del proyecto son públicas.

Puedes apoyar el proyecto a través de estas plataformas:

| Plataforma | Modalidad | Estado |
| --- | --- | --- |
| GitHub Sponsors | Aportaciones puntuales o mensuales | Pendiente de habilitación del perfil de cobro |
| [Patreon](https://www.patreon.com/Neural_office) | Apoyo mensual en euros | Página publicada |

**Niveles de apoyo en Patreon:**

| Nivel | Aportación base |
| --- | --- |
| Apoyo de 1 € | 1 €/mes |
| Apoyo de 3 € | 3 €/mes |
| Apoyo de 5 € | 5 €/mes |
| Apoyo de 10 € | 10 €/mes |

Todos los niveles tienen el mismo propósito: apoyar el proyecto, sin funciones ni contenido exclusivos. Elige el importe que te resulte cómodo; usar Neural Office sin aportar también está bien. Los importes indicados son los precios base; la plataforma mostrará el total aplicable antes de confirmar la suscripción.

El botón **Sponsor** de este repositorio enlaza a Patreon. GitHub Sponsors sigue pendiente de activación y configura sus niveles en [dólares estadounidenses](https://docs.github.com/en/sponsors/receiving-sponsorships-through-github-sponsors/setting-up-github-sponsors-for-your-personal-account#creating-sponsorship-tiers); sus importes se mostrarán por separado, sin prometer una equivalencia fija con los euros de Patreon.

También puedes ayudar probando la aplicación, comunicando errores reproducibles o mejorando la documentación. La gratuidad corresponde al software; el equipo, los modelos y cualquier servicio externo conservan sus propios requisitos, licencias y posibles costes.

## Desarrollo y contribuciones

```powershell
.\run.bat --version
py -3.12 -B -m unittest discover -s tests -v
.\run.bat models
.\run.bat status
```

La suite pública Python funciona sin modelos, credenciales ni historial privado. Los resultados fechados están en la [evidencia de auditoría](docs/evidence/V5_4_1_FORENSIC.json) y los checks de cada commit; el [frontend](desktop/README.md) tiene pruebas de estado y comprobación de tipos/build. [CONTRIBUTING.md](CONTRIBUTING.md) explica cómo aportar una reproducción pequeña, una corrección localizada o documentación. Las [nueve skills de desarrollo y revisión](skills/README.md) recogen errores demostrados y fuentes inspeccionadas; son herramientas de desarrollo, no skills ya conectadas a los agentes del producto. La [comparación de 91 README](docs/README_RESEARCH_91.md) conserva sus decisiones de presentación.

## Datos y licencia

El piloto se comunica con Ollama por loopback y rechaza perfiles cloud. Guarda entradas, respuestas y estado en archivos locales **sin cifrado**; no publiques esa carpeta de datos. Descargar modelos y el comportamiento de otros clientes son flujos separados. No se promete privacidad absoluta de toda la máquina.

[MIT](LICENSE) para las aportaciones propias que el promotor pueda licenciar. Desarrollo asistido por IA bajo supervisión. CrewAI fue una base conceptual e histórica; no es una dependencia del núcleo publicado. No se incluyen runtimes, pesos, vídeos ni historiales privados. [LICENSING.md](LICENSING.md) y el [expediente de procedencia](docs/V5_2_PROVENANCE.md) delimitan los derechos de terceros y las cuestiones jurídicas abiertas.

La [entrega V5.5](docs/V5_5_VERIFICATION.md) añade el adaptador y host nativo, con avisos de las dependencias del artefacto. Los contratos [V5.1](docs/V5_1_INTEGRATION_SPEC.md) y [V5.2](docs/V5_2_INTEGRATION_AND_ACCEPTANCE.md) se conservan como documentos fechados. La auditoría posterior a V5.4.1 corrige el núcleo con alcance documentado, conserva cuotas y mantiene abierto el timeout histórico R13. [Dependencias del frontend](docs/evidence/V5_3_COMPONENTS.json) y [avisos de terceros](desktop/THIRD_PARTY_NOTICES.md).
