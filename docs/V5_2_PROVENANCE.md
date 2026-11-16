# V5.2: procedencia, derechos y publicación

Expediente técnico de la vista previa, 16 de noviembre de 2026. Distingue hechos comprobados, declaraciones del promotor y cuestiones jurídicas que el análisis de archivos no puede resolver. No es un dictamen jurídico ni una garantía de ausencia de reclamaciones.

## Origen de las aportaciones

**OBSERVADO, declaración del promotor.** El histórico fue elaborado mediante ChatGPT bajo su supervisión constante. La implementación del piloto y esta documentación también se han desarrollado con asistencia de IA y revisión humana del encargo. No se presentan como contenido escrito íntegramente por una persona.

**DESCONOCIDO.** Esa declaración no demuestra por sí sola originalidad de cada fragmento, ausencia de material ajeno en las entradas, contribución humana protegible ni inexistencia de derechos de un empleador o cliente. Los hashes prueban identidad de bytes; no prueban titularidad. No se ha hecho una búsqueda exhaustiva de similitud contra todo el código publicado en Internet.

**OBSERVADO, fuente contractual.** Los términos europeos de OpenAI atribuyen al usuario, frente a OpenAI y con las limitaciones de la ley aplicable, los derechos que OpenAI pudiera tener sobre el output; advierten que puede no ser único y separan material de terceros. Esto no constituye un saneamiento universal de derechos. Debe conservarse la versión de los términos realmente aplicable al servicio/cuenta y fecha de cada aportación; no se presupone que todos los trabajos históricos estuvieran bajo la misma modalidad. [Términos de OpenAI, sección Content](https://openai.com/policies/eu-terms-of-use/).

**OBSERVADO, marco español.** La LPI vincula la autoría a personas naturales y exige originalidad; establece una regla específica de titularidad para software creado por un trabajador en el ejercicio de sus funciones o siguiendo instrucciones empresariales, salvo pacto contrario. La supervisión de IA no decide automáticamente cómo se aplica ese marco a un archivo concreto. [LPI, artículos 5, 10 y 97](https://www.boe.es/buscar/act.php?id=BOE-A-1996-8930).

**OBSERVADO, decisión expresa del promotor.** El 16 de noviembre de 2026 eligió MIT para las aportaciones propias que pueda licenciar. Se incorpora [LICENSE](../LICENSE); el alcance y las exclusiones se explican en [LICENSING.md](../LICENSING.md). La elección no convierte derechos de terceros o titularidad desconocida en derechos acreditados.

## Inventario del paquete real

| Componente | Presencia en el paquete | Procedencia y tratamiento |
| --- | --- | --- |
| `neural_office/*.py` | Código nuevo del piloto. | Elaborado en esta revisión con IA; biblioteca estándar, sin código fuente de CrewAI o PyMuPDF incorporado deliberadamente. Revisar cada contribución posterior. |
| `tests/*.py` | Fixtures y pruebas propias. | Entradas sintéticas; no incluyen proyectos, conversaciones ni bases de usuario. |
| `examples/audit-sample.html` | Ejemplo mínimo con cuatro hallazgos esperados. | Creado para ensayos; no descarga recursos al ser analizado. |
| `Start-NeuralOffice.ps1` | Lanzador técnico. | No instala dependencias ni cambia políticas de ejecución. |
| Documentación V5.1/V5.2 | Diseño, revisión y evidencias minimizadas. | El histórico V5.1 queda fechado; no se reescribe como si hubiese ejecutado pruebas posteriores. |
| Diff de cinco archivos históricos | Fragmentos mínimos de las reparaciones. | Vinculado a hashes antes/después; no importa el runtime completo ni sus bases. La declaración de origen no sustituye una revisión de derechos. |
| Python/Tk/Tcl, SQLite del intérprete | **No redistribuidos.** | Componentes del entorno de ejecución. Si se construye un binario/instalador deberán inventariarse sus licencias y avisos reales. |
| Ollama | **No redistribuido.** | Ejecutable local con firma válida de Ollama Inc.; versión API observada en el recibo. No se publica el instalador ni su configuración. |
| Pesos de modelo | **No redistribuidos.** | El alias ensayado tiene metadata `qwen35` y carece de campo de licencia en `/api/show`. No se le atribuye una licencia por su nombre o familia. |
| CrewAI | Referencia histórica, **no dependencia del piloto**. | Su licencia pública permite reutilización bajo condiciones MIT; una adaptación real debe conservar los avisos correspondientes. No se afirma que licencie automáticamente todo Neural Office. |
| PyMuPDF y demás entorno histórico | **No incluidos ni requeridos** por el piloto. | La metadata histórica de PyMuPDF declara AGPL/comercial; su eventual incorporación requiere analizar el componente y forma de distribución concretos. |
| Vídeos, MP3, capturas, transcripciones y paquetes descargados | **No publicados.** | Material de contextualización; no hay autorización inferida de redistribución por haber sido descargado. |

Fuentes primarias: [licencia de CrewAI](https://raw.githubusercontent.com/crewAIInc/crewAI/main/LICENSE), [licencias de PyMuPDF](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright), [licencias de Python](https://docs.python.org/3.12/license.html), [licencia de Ollama](https://raw.githubusercontent.com/ollama/ollama/main/LICENSE). Los avisos de una distribución futura deben fijarse a los bytes/versiones realmente incluidos, no a una rama remota mutable.

La ausencia de imports externos se comprueba sobre el paquete seleccionado; no certifica todas las aplicaciones instaladas en el equipo ni un árbol de dependencias que no se distribuye. El inventario es técnico y deliberadamente no se denomina una SBOM exhaustiva de un instalador inexistente.

## Modelo local: identidad separada del alias

**OBSERVADO.** El nombre personalizado contiene `deepseek` y `cpu64k`. `/api/tags` y `/api/show` describen familia `qwen35`, 9B, Q4_K_M y un contexto teórico anunciado de 262.144. En el ensayo se solicitó y observó una asignación de 8.192; no se deduce la capacidad efectiva del alias o del máximo anunciado.

El digest fijado identifica la manifestación local observada, pero no recupera por sí solo la cadena completa de entrenamiento, conversiones, modificaciones o licencias. La procedencia jurídica de esos pesos queda **DESCONOCIDA**. Se usan únicamente como modelo ya instalado para los ensayos autorizados; el paquete público no contiene ni enlaza una descarga de esos pesos personalizados.

## Datos y permisos de publicación

La selección pública es cerrada y se expresa en `.gitignore` y `PUBLICATION_MANIFEST.sha256`. No se añade el historial Git operativo, bases SQLite, prompts reales, claves, archivos `.env`, logs brutos, rutas personales ni correos privados. Los commits emplean la identidad pública `noreply` de la cuenta propietaria. Los receipts públicos contienen escenarios sintéticos y métricas minimizadas; los originales quedan en el expediente local privado.

**LÍMITE.** El piloto guarda localmente instantáneas, objetivos, respuestas y logs de backend. No cifra el ledger ni incorpora todavía borrado selectivo, retención o exportación general. El usuario debe elegir entradas que pueda tratar. Publicar el software no autoriza publicar datos de sus futuros usuarios. [RGPD](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng).

La publicación se verifica después del commit mediante lectura remota anónima: propietario, visibilidad, árbol, contenido de cada blob, manifiesto y metadatos de autor/committer. El recibo de esa operación se conserva separado para no introducir una referencia circular al commit que lo contendría. La mera presencia de este documento no acredita que un push haya terminado.

## Registro jurídico y de investigación pendiente

| Punto | Estado y cierre concreto exigido |
| --- | --- |
| Licencia propia | DECIDIDA: MIT por elección expresa del promotor, limitada a los derechos que pueda conceder. No certifica titularidad. |
| Empleo, encargo y aportaciones humanas | DESCONOCIDO. Declaración específica del promotor y, si corresponde, documentación de cesión y revisión profesional. La respuesta sobre ChatGPT no cubre estos hechos. |
| Fragmentos de terceros | No se han identificado incorporaciones deliberadas en el núcleo nuevo; no hay certificación universal de originalidad. Conservar procedencia por contribución y revisar coincidencias significativas. |
| Modelo personalizado | PENDIENTE de origen/licencia verificables antes de redistribuirlo o recomendar esa descarga. |
| Marca Neural Office | Sin búsqueda exhaustiva de disponibilidad o conflictos marcarios; publicar un repositorio no registra una marca. |
| Colaboradores futuros | Exigir procedencia, licencias compatibles y revisión antes de aceptar cambios; aún no hay acuerdos de contribución implantados. |
| Servicio comercial o usos regulados | Requieren analizar producto, roles, mercados y datos concretos. No se deduce una exención general por ser local o abierto. [Reglamento de IA](https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng). |
| Audiovisuales históricos | El visionado sigue siendo parcial: 42 frames de siete archivos, casi nueve horas en total según el expediente V5.1. No se convierte esa muestra en visionado íntegro ni en transcripción completa. |

**Conclusión limitada.** La publicación minimiza material distribuido y hace explícita la procedencia declarada. No ofrece «blindaje» jurídico absoluto. La revisión profesional debe recibir este inventario, las contribuciones humanas documentadas y los contratos aplicables; no basta con afirmar que se usó ChatGPT o CrewAI.
