# Licencias de Neural Office · estado V5.5

El 16 de noviembre de 2026 el promotor eligió expresamente **MIT** para las aportaciones propias que pueda licenciar. El texto se encuentra en [LICENSE](LICENSE). Se aplica al código y documentación propios de esta entrega en la medida de los derechos que correspondan al otorgante. No pretende conceder derechos sobre material ajeno ni afirmar que todo output de IA tenga protección autoral.

Las referencias históricas a una licencia pendiente describen V5.1 antes de esa decisión. Las secciones históricas siguientes describen el material de cada entrega; la ampliación V5.5 se delimita al final.

La revisión V5.2.1 contiene el núcleo del piloto, pruebas sintéticas, documentación, diffs mínimos del legado y una captura de su interfaz con un ejemplo público. El estudio de 91 README publica referencias y observaciones propias, sin copiar sus medios ni bases de código. No incluye CrewAI, PyMuPDF, intérpretes, instaladores, ejecutables de Ollama, pesos de modelos, vídeos ni bases privadas. CrewAI es una referencia histórica, no una dependencia de este piloto; sus avisos MIT deberán preservarse si se incorpora código suyo posteriormente.

La licencia propia no resuelve por sí sola la titularidad de aportaciones históricas, derechos derivados de empleo o encargo, procedencia de entradas de terceros ni condiciones del modelo seleccionado por cada usuario. La licencia del modelo personalizado utilizado en los ensayos no está acreditada y sus pesos no se distribuyen.

El [expediente V5.2](docs/V5_2_PROVENANCE.md) recoge fuentes, declaración de creación con IA, límites y cuestiones que siguen abiertas. No se promete inmunidad jurídica ni se atribuye a la licencia de CrewAI cobertura sobre todo el entorno de desarrollo.

El [registro V5.2.1](docs/V5_2_1_FORENSIC_REVIEW.md) y sus [componentes](docs/evidence/V5_2_1_COMPONENTS.json) actualizan el alcance técnico. Esta revisión no acredita la disponibilidad del nombre como marca ni añade una garantía sobre derechos de terceros.

V5.3 incorpora un prototipo React/TypeScript, colectores propios y una captura con datos sintéticos. No copia medios ni código de los vídeos de referencia; su [revisión dirigida](docs/V5_3_VIDEO_RESEARCH.md) publica observaciones propias. En V5.3 Tauri aún no formaba parte de las dependencias integradas.

El [inventario V5.3](docs/evidence/V5_3_COMPONENTS.json) registra 74 entradas de dependencias del lockfile, incluidas variantes opcionales para otros sistemas; 23 estaban instaladas en el entorno Windows de comprobación. No equivale a 74 componentes distribuidos ni a un SBOM completo de un instalador. El runtime web usa React, React DOM y Scheduler bajo sus avisos MIT, recogidos en [THIRD_PARTY_NOTICES.md](desktop/THIRD_PARTY_NOTICES.md).

Las herramientas de compilación conservan sus licencias independientes: el lockfile incluye MIT, Apache-2.0, MPL-2.0, ISC, BSD-3-Clause y 0BSD. La publicación V5.3 contenía fuentes y referencias de paquetes; no incluía `node_modules`, binarios de herramientas ni el bundle compilado. Antes de redistribuir cualquiera de esos artefactos hay que verificar sus componentes y avisos efectivos; la elección de MIT propio no cambia las licencias de terceros.

## Alcance añadido en V5.5

El host Tauri/Rust compila un artefacto de desarrollo Windows. Su distribución debe ir acompañada de LICENSE y `native-notices`, generados desde Cargo.lock y el runtime npm instalado. [Avisos y procedimiento](desktop/THIRD_PARTY_NOTICES.md). El colector comprueba archivos contra las fuentes fijadas y conserva avisos originales; cinco paquetes requieren avisos obtenidos de su commit publicado o del texto oficial MPL. El conjunto Windows incluye dependencias de build que pueden no acabar en el ejecutable: no se anuncia un SBOM exhaustivo del binario.

Las dependencias MPL conservan sus términos y enlaces a la forma fuente exacta no modificada; MIT propio no cambia esas obligaciones. Python, Ollama, WebView2 y pesos se instalan por separado y no forman parte de ese artefacto. El ensayo V5.5 usa Qwen2.5 0.5B identificado por digest; sus pesos no se publican.

La investigación V5.5 publica observaciones propias y referencias a 80 repositorios, materiales de 20 instituciones y feedback público. La selección no autoriza copiar implementaciones con licencia comercial, Noncommercial o restricciones de marca. Las siete skills nuevas son instrucciones propias para desarrollo, no código incorporado de esos productos. No acredita titularidad histórica, disponibilidad del nombre ni inmunidad jurídica.
