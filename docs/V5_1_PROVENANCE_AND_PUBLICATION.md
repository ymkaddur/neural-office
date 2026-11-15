# Expediente de procedencia y publicación de Neural Office V5.1

Este expediente delimita el contenido publicable de V5.1 y la evidencia necesaria antes de distribuir código o una aplicación. La revisión de referencia es del 15 de noviembre de 2026. La publicación actual contiene documentación nueva y referencias; el software histórico permanece fuera del paquete.

El objetivo es facilitar una futura distribución de Neural Office con modelo local y una instalación sencilla. Una auditoría técnica y una licencia no garantizan ausencia de reclamaciones. Las decisiones de titularidad, licencia y producto comercial deben revisarse sobre los archivos y usos concretos que se vayan a distribuir.

**Etiquetas:** los inventarios y antecedentes son OBSERVADO; las identidades de bytes comprobadas son VERIFICADO dentro de su alcance; los requisitos para futuras distribuciones son ESCENARIO; titularidad, compatibilidad y obligaciones todavía no resueltas son DESCONOCIDO. La investigación documental no equivale a un dictamen jurídico ni a pruebas nuevas del software.

## 1 Perímetros de publicación

| Perímetro | Contenido | Estado |
| --- | --- | --- |
| P1 Documentación V5.1 | README, tres especificaciones, índice de fuentes, registro de revisión, hoja de ruta, estado de licencias, lista de selección y manifiesto de integridad. | Publicación documental; el recibo remoto se verifica contra este paquete. |
| P2 Código del núcleo | Fuentes seleccionadas, tests y configuración portable. | Pendiente de autorización de cambios, revisión de procedencia y licencia. |
| P3 Aplicación instalable | Runtime, dependencias, interfaz, actualizador y herramientas incluidas. | Pendiente de funcionamiento, seguridad de distribución y licencias del artefacto real. |
| P4 Modelos y extensiones | Pesos, adaptadores, skills descargables y material adicional. | No incluidos; cada elemento necesita su propia ficha y condiciones de uso. |

La publicación de P1 no certifica P2, P3 o P4. GitHub permite ver y bifurcar repositorios públicos conforme a sus condiciones; cambiar después a privado no elimina copias existentes. Por ello el paquete se prepara para exposición pública desde su primer commit. [GitHub sobre licencias](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository).

## 2 Procedencia técnica reconstruida

| Familia | Procedencia contrastada | Relación y evidencia |
| --- | --- | --- |
| Autolab | Código con imports de CrewAI y eventos históricos del metaplanificador. | Origen efectivo; no demuestra que todos los módulos posteriores utilicen el framework. |
| V2 y recuperación | Paquete de reparación y recibo estructural. | Conserva antecedentes; la identidad del original no está completamente acreditada por ese recibo. |
| Plus y V3 | Fuentes coincidentes con paquetes R3 y OpenCode nativo. | Sesiones y workspace que siguen siendo referencia para capas posteriores. |
| V4 | R4 de estabilización y motor Polished coexistentes. | Dos entradas distintas; el diagnóstico Polished tiene una corrección localizada posterior. |
| V4.1 y V4.2 | STABILITY y FIXED. | Conciliación y grafos con contratos de evidencia. |
| V4.3 | Payload compartido entre tres paquetes históricos. | Los archivos instalados no distinguen cuál de sus instaladores se utilizó. |
| V4.4 y V4.4.5 | Mutex de V4.4.2 y payload de control plane coincidente. | El paquete CORRECTED corrige un pin del instalador sin reemplazar todo el código instalado. |
| V4.5 y V5 | V5 reutiliza módulos de V4.5 y contiene correcciones de director y memoria. | La corrección R1 de memoria coincide con la fuente instalada. |

La comparación de hashes verifica identidad de bytes dentro de su alcance. No prueba quién escribió el contenido, que una licencia permita distribuirlo o que las afirmaciones de un informe sean correctas.

**OBSERVADO, alcance de la auditoría anterior.** Se registró inspección de 24 ZIP históricos como archivos, sin ejecutar sus instaladores: 19 manifiestos completos, 490 entradas coincidentes y 76 entradas del staging V5 corregido. Esos agregados no se recomputan en esta revisión documental y sus paquetes no se publican; un lector público no puede verificarlos con el índice de 36 fuentes por sí solo. No se utilizan como certificación del runtime ni como prueba de derechos de distribución.

El [índice de evidencias](evidence/SOURCE_INDEX.md) conserva identificadores, rutas relativas, rangos de líneas y hashes de fuentes relevantes. Las rutas absolutas y las copias operativas se mantienen en el expediente local privado.

## 3 Inventario preliminar de componentes

Este inventario no es un SBOM exhaustivo del entorno instalado. El SBOM de una aplicación futura deberá generarse desde su resolución exacta de dependencias y comprobarse contra los archivos realmente distribuidos.

| Componente | Situación observada | Tratamiento antes de incluirlo |
| --- | --- | --- |
| CrewAI 1.15.40 | Entorno histórico y uso en el orquestador raíz; licencia MIT en la copia fuente consultada. | Fijar versión y origen, conservar avisos aplicables y evaluar si el núcleo futuro realmente lo necesita. |
| crewai-tools 1.15.40 | Instalado en el entorno histórico; declara dependencia de PyMuPDF. | No copiar el entorno completo. Seleccionar herramientas necesarias y auditar sus dependencias transitivas. |
| PyMuPDF 1.26.7 | Metadata local: AGPL-3.0 o licencia comercial. | Determinar integración y distribución concretas; elegir cumplimiento aplicable, alternativa o licencia comercial. |
| OpenCode 2.2.6 | Integración histórica y versión exigida por el plugin V4.3. | Revisar la versión que se distribuya o requiera, su licencia, plugins y protocolo; la compatibilidad no se presume al actualizar. |
| Ollama | Backend local observado; no se redistribuye en P1. | Fijar política de versiones y verificar obligaciones del binario que se empaquete o gestione. |
| Python y librerías de sistema | Base de los módulos propios instalados; los analizadores estáticos no encontraron imports de CrewAI en Plus a V5. | Construir un entorno mínimo y reproducible a partir de dependencias reales, sin reutilizar un venv de Downloads como instalador. |
| Modelos locales | Alias históricos y metadatos que apuntan a una familia qwen35 de aproximadamente 9B y cuantización Q4_K_M. | Ficha por digest, procedencia, licencia y capacidades. El nombre del alias no prueba identidad o autorización de redistribución. |
| Skills, prompts y corpus | Material de procedencias distintas en el legado. | Registrar origen y derechos por unidad; separar ejemplos sintéticos de datos reales o de terceros. |
| Vídeos y otros documentos | Material de referencia del diseño. | Mantener enlaces y notas propias; no redistribuir grabaciones o documentos ajenos sin base suficiente. |

La licencia MIT de CrewAI permite uso, modificación y distribución, incluida la comercial, con sus condiciones de avisos. No impone automáticamente MIT a todas las aportaciones propias ni cubre dependencias ajenas. [Licencia oficial de CrewAI](https://github.com/crewAIInc/crewAI/blob/main/LICENSE).

Fuentes locales de las distinciones anteriores: E29 acredita el uso de clases de CrewAI, E30 la versión de crewai-tools y su dependencia de CrewAI/PyMuPDF, E31 la declaración de licencia de PyMuPDF y E32 la licencia de la copia fuente consultada. Una licencia en la rama pública `main` es una referencia móvil; la futura distribución deberá fijar la revisión y conservar el texto correspondiente al paquete concreto.

La instalación de PyMuPDF no permite concluir por sí sola que todo el proyecto deba relicenciarse. Debe analizarse su uso e integración en lo que se entrega. Artifex ofrece rutas AGPL y comercial. [Licenciamiento de PyMuPDF](https://pymupdf.io/licensing).

Las fichas públicas del modelo transformado y de su cuantización declaran Apache-2.0. Es una declaración de esas fuentes, no una auditoría completa de la cadena de derechos o de entrenamiento. [Modelo transformado](https://huggingface.co/xtools-at/DeepSeek-V4-Pro-Qwen3.5-9B-UNCENSORED-heretic), [cuantización](https://huggingface.co/mradermacher/DeepSeek-V4-Pro-Qwen3.5-9B-UNCENSORED-heretic-i1-GGUF).

## 4 Material excluido del repositorio público

Se excluyen fuentes operativas del legado, bases SQLite y ficheros WAL/SHM, credenciales, tokens, conversaciones, prompts privados, informes con rutas personales, repositorios de productos históricos, backups, ZIP, vídeos, audio, pesos de modelos, entornos virtuales, cachés y archivos descargados de terceros.

Los prompts históricos son evidencia de decisiones, no autorizaciones para copiar o publicar contenido ajeno. La eventual incorporación de código de juegos, repositorios externos o material descompilado requiere una revisión propia. No se presume que se haya incorporado ese material al núcleo por aparecer en una instrucción.

En España, las reglas de titularidad y explotación del software y la excepción limitada de descompilación para interoperabilidad requieren analizar el caso concreto. La excepción no es una autorización general para producir un programa similar copiando su expresión. [LPI, artículos 96 a 100](https://www.boe.es/buscar/act.php?id=BOE-A-1996-8930#a96).

La lista de exclusiones se aplica a la selección de archivos, al índice de Git y al historial que se vaya a publicar. Un archivo ignorado puede estar ya versionado; `.gitignore` no limpia commits anteriores.

## 5 Registro de derechos por archivo o componente

Antes de entrar en P2 o P3, cada unidad incorporada debe tener un registro con:

| Campo | Contenido requerido |
| --- | --- |
| Identidad | Ruta en el paquete, versión y SHA-256. |
| Origen | Autor o proveedor conocido, URL y revisión/commit cuando corresponda. |
| Forma de incorporación | Código propio, dependencia, copia modificada, snippet, dato o recurso audiovisual. |
| Derechos | Licencia aplicable, titular declarado, avisos, condiciones y evidencia de permiso cuando se necesite. |
| Modificaciones | Cambios realizados y responsable de revisarlos. |
| Uso y distribución | Si se ejecuta, enlaza, incluye como archivo, descarga por separado o solo se cita. |
| Decisión | Admitido, sustituido, excluido o pendiente, con motivo. |
| Verificación | Revisor, fecha y digest del conjunto revisado. |

Las aportaciones asistidas por IA necesitan revisión de procedencia y titularidad; no se les atribuye automáticamente exclusividad ni originalidad. Las contribuciones humanas deben identificar las condiciones bajo las que se reciben. La decisión de licencia propia se tomará después de delimitar los derechos que el proyecto puede conceder.

## 6 Decisiones de licencia y producto pendientes

| ID | Decisión pendiente | Evidencia necesaria |
| --- | --- | --- |
| LEG-01 | Licencia de documentación y código propio. | Titularidad y alcance de los derechos concedidos; elección expresa del responsable. |
| LEG-02 | Perfil mínimo de dependencias del núcleo. | Resolución fijada, SBOM y comprobación de licencias transitivas. |
| LEG-03 | Uso o exclusión de herramientas con obligaciones recíprocas o comerciales. | Integración concreta, modo de distribución y revisión jurídica aplicable. |
| LEG-04 | Distribución o descarga gestionada de modelos. | Ficha por digest, avisos, términos y procedencia suficiente. |
| LEG-05 | Nombre y presentación comercial del producto. | Revisión de marcas y ausencia de afirmaciones de afiliación no autorizadas. |
| LEG-06 | Condiciones para colaboradores. | Política de contribución y declaraciones de derechos adecuadas al proyecto. |
| LEG-07 | Usos profesionales, datos personales y servicio comercial. | Flujo de datos, finalidades, mercados, clasificación del sistema y obligaciones aplicables. |

Esta entrega no se anuncia como software open source. Su [estado de licencias](../LICENSING.md) deja explícita la decisión pendiente.

Si el producto procesa datos personales, deben analizarse minimización, base jurídica, conservación, seguridad y derechos de los interesados. Publicar código no autoriza publicar datos de usuarios. [RGPD](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng).

El Reglamento de IA distingue usos y actores; su tratamiento de sistemas abiertos tiene excepciones. La clasificación depende del producto que finalmente se ponga en servicio o comercialice. [Reglamento de IA, artículo 2](https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng).

## 7 Procedimiento de publicación documental

1. Construir una carpeta nueva con una lista cerrada de archivos de documentación.
2. Comprobar que el propietario de GitHub es el indicado por el usuario y que el nombre no sobrescribe un repositorio ajeno o existente.
3. Revisar contenido, vínculos, afirmaciones, datos personales, secretos, extensiones y metadatos de autoría de commits. La identidad pública de GitHub puede figurar; una dirección personal de correo no se publica por defecto. Usar la dirección `noreply` de GitHub o una identidad pública autorizada y verificar el resultado.
4. Generar un manifiesto SHA-256 de los archivos seleccionados. El propio manifiesto queda fuera de su lista para evitar autorreferencia.
5. Crear el commit únicamente con esa selección. No importar el historial del workspace operativo ni el del producto histórico.
6. Publicar con la visibilidad autorizada.
7. Leer de vuelta archivos y metadatos remotos; contrastar árbol, hashes y visibilidad con la entrega prevista.
8. Conservar en el expediente privado el recibo de publicación y la comparación de integridad del legado.

El manifiesto detecta diferencias de contenido; no es una firma de autoría ni un dictamen de derechos. Si se detecta una credencial expuesta, la respuesta incluye revocarla o rotarla y evaluar su presencia en el historial. [Guía de GitHub](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).

La selección pública comprende exactamente los diez archivos registrados por el manifiesto y su exclusión de autorreferencia: nueve entradas más `PUBLICATION_MANIFEST.sha256`. Los recibos privados, la copia anterior y el diff de revisión no se añaden al repositorio. La integridad remota se acredita después de publicar mediante lectura anónima del commit y comparación de bytes; este documento por sí solo no declara que esa operación ya haya ocurrido. El correo empleado por la interfaz web depende de la configuración de privacidad de GitHub. [Documentación de correo de commits](https://docs.github.com/en/account-and-profile/how-tos/email-preferences/setting-your-commit-email-address).

## 8 Evidencia audiovisual y adaptación

La revisión audiovisual del legado fue parcial: se inspeccionaron 42 fotogramas distribuidos por siete archivos, con casi nueve horas de duración conjunta, y se contrastaron varias ponencias con sus organizadores. No se presenta como transcripción ni visionado íntegro.

| Fuente pública | Lección adoptada como requisito | Límite |
| --- | --- | --- |
| [Brad Abrams sobre Claude Platform](https://claude.com/code-with-claude/session/sf-getting-more-out-of-the-claude-platform) | Gestionar contexto, herramientas y revisión auxiliar con mediciones. | No implica que la API local tenga las mismas funciones. |
| [AI Engineer sobre agentes de larga duración](https://ai.engineer/talks/mR-WAvEPRwE-build-agents-that-run-hours-without-losing) | Evaluar mediante uso y pruebas del producto; conservar progreso y evidencia. | Un rol de QA no demuestra calidad por su nombre. |
| [Lamis Mukta sobre memoria y curación](https://tessl.io/speaker/lamis-mukta) | Versionar, resolver concurrencia y evaluar curación de memoria. | No acredita aprendizaje continuo en el runtime actual. |
| [Isabella He sobre Managed Agents](https://claude.com/code-with-claude/session/ldn-ext-ship-your-first-managed-agent) | Separar agente, entorno, sesión y eventos. | Se adapta el concepto; no se incorpora el servicio cloud por defecto. |

La cartela del vídeo local de Managed Agents identifica a Isabella He; un documento histórico lo atribuía a otra sesión. Se conserva la corrección de procedencia sin redistribuir el vídeo.

## 9 Condiciones para publicar una aplicación

La salida de P3 exige que los documentos se correspondan con el paquete construido: versiones fijadas, fuentes y licencias revisadas, dependencias mínimas, recursos excluidos correctamente, configuración sin secretos, instalación y desinstalación probadas, actualización verificable y funcionamiento del ciclo completo.

La revisión jurídica debe recibir el inventario del paquete real y las decisiones de producto, no solo una declaración genérica de que el proyecto usa CrewAI. Ninguna denominación como V5, V10, verificado o seguro sustituye ese expediente.
