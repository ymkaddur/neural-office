# V5.5 — Dependencias: consulta de avisos conocidos

**VERIFICADO, 17 de noviembre de 2026, 08:06:55–08:09:08 UTC.** Se consultaron versiones exactas de los locks observados en el commit `b59bd6fff7afc413e3fd85cf165ecbe47026f3b2`. Los hashes de ambos locks permanecieron iguales al terminar. No se ejecutó `audit fix`, no se instaló ninguna dependencia y no se modificó producción.

## Registro de investigación

| Experimento ejecutado | Cobertura | Resultado |
|---|---:|---|
| OSV `/v1/querybatch`, lotes de 100 y manejo de paginación | 443 dependencias de terceros de Cargo.lock; el paquete propio es la entrada 444 | 443 consultas completas; dos paquetes con coincidencias, tres IDs que representan dos avisos distintos |
| Cargo metadata con `custom-protocol`, target `x86_64-pc-windows-msvc` | 241 componentes de terceros del grafo Windows, incluidas dependencias de build | Ninguno de los dos paquetes coincidentes pertenece a este grafo |
| `cargo tree --locked --features custom-protocol --target x86_64-pc-windows-msvc -i …` para ambos paquetes | Comprobación inversa independiente de selección de target | Ambas ejecuciones terminaron con código 0 y `nothing to print` |
| `npm audit --json --package-lock-only --ignore-scripts --omit=dev` | Cuatro paquetes runtime de terceros | Código 0; cero avisos devueltos |
| `npm audit --json --package-lock-only --ignore-scripts` | 123 entradas de terceros del lock, 119 marcadas dev | Código 0; cero avisos devueltos |

Las consultas npm usaron explícitamente el registro público y configuraciones vacías separadas; se enviaron nombres y versiones públicas. La primera invocación no produjo JSON válido y no se utilizó para concluir nada; las dos ejecuciones válidas posteriores están registradas por separado. Node `v24.21.0`, npm `11.19.0`. El contador `prod: 5` de npm incluye la raíz del proyecto; hay cuatro entradas de terceros runtime: `@tauri-apps/api@2.12.5`, `react@19.3.1`, `react-dom@19.3.1` y `scheduler@0.28.0`. Los contadores opcionales y dev de npm se solapan y no se suman como componentes runtime únicos.

El método de OSV garantiza correspondencia de orden entre consulta y respuesta y exige seguir tokens de paginación cuando aparecen. npm consulta avisos del registro; `audit-level` modifica el umbral de fallo, no filtra la salida. No se aplicó un umbral que ocultara hallazgos. Fuentes: [API querybatch de OSV](https://google.github.io/osv.dev/post-v1-querybatch/) y [documentación oficial de npm audit](https://docs.npmjs.com/cli/v11/commands/npm-audit/).

## Evidencia y evaluación de alcance

**OBSERVADO:** `glib@0.18.5`, en `desktop/src-tauri/Cargo.lock:1138`, coincide con **RUSTSEC-2024-0429**, alias **GHSA-wrw7-89jp-8q8g**. El aviso describe uso incorrecto de mutabilidad en `VariantStrIter`, con comportamiento indefinido y posibles fallos de acceso a puntero nulo; indica corrección desde `0.20.0`. GitHub lo clasifica MODERATE y RustSec INFO Unsound. Son dos identificadores del mismo aviso, no dos vulnerabilidades. [Aviso primario de RustSec](https://rustsec.org/advisories/RUSTSEC-2024-0429.html).

**VERIFICADO:** ese paquete no está en el grafo Windows resuelto con la feature de producción. Además, `desktop/src-tauri/src/main.rs:2` rechaza compilar el host actual fuera de Windows. No se ha demostrado una ruta explotable de este aviso en el artefacto Windows ni se ejecutó una explotación. **Pendiente para un futuro port Linux:** actualizar la cadena GTK pertinente o demostrar el alcance del método afectado en ese artefacto; no forzar ahora una versión incompatible de glib en el lock.

**OBSERVADO:** `proc-macro-error@1.0.4`, en `desktop/src-tauri/Cargo.lock:2514`, coincide con **RUSTSEC-2024-0370**. Es un aviso informativo de mantenimiento abandonado; no describe por sí solo una vulnerabilidad explotable ni una severidad alta. Tampoco pertenece al grafo Windows actual. Su cadena de macros debe reevaluarse antes de adoptar otros targets. [Aviso primario de RustSec](https://rustsec.org/advisories/RUSTSEC-2024-0370.html).

**VERIFICADO:** las 241 consultas Cargo correspondientes al grafo Windows y las dos auditorías npm no devolvieron coincidencias. Esta afirmación es sobre respuestas de bases de avisos en la fecha indicada; no equivale a «el código es seguro».

## Identidad exacta de entradas

| Entrada | SHA-256 |
|---|---|
| `desktop/src-tauri/Cargo.lock` | `7de12e25786b9ece9be599bc0faa71624495f034070c6665538e28c129c80c94` |
| `desktop/package-lock.json` | `69cc53de70505e0262fd09595d958fe28d80dd348dd438dd9e2257548dd79c6c` |
| Metadata Windows filtrada, registro privado | `e81debe07eae49663274c2da26b5afe5d1eb250f43ff05a0f64206ad41bcb4b8` |

El [JSON acompañante](evidence/V5_5_DEPENDENCIES.json) conserva nombres, versiones, checksums, respuestas, IDs, clasificación, cobertura y errores. No contiene rutas personales. La metadata bruta de Cargo y los scripts de trabajo contienen rutas locales y no forman parte de la entrega pública.

## Duda residual y siguiente acción

**DESCONOCIDO:** completitud de las bases, vulnerabilidades todavía no publicadas, reconocimiento independiente de todas las versiones, explotación de código propio y componentes fuera de estos locks. No se incluyeron el sistema operativo, WebView2 instalado, compilador Rust, runtime/stdlib Python, binario de Ollama, modelos ni la totalidad de la cadena de suministro. El grafo de build no es una lista exacta de código enlazado en el ejecutable.

No hay una causa reproducida que justifique cambiar producción a partir de estos resultados. Mantener los dos avisos de otros targets como puerta explícita antes de ampliar plataformas y repetir las consultas cuando cambien los locks o se prepare una publicación. La ausencia de avisos no sustituye las pruebas causales de autoridad, cancelación, recuperación y límites.

**Confianza:** alta en la correspondencia de versiones, respuestas y exclusión de ambos paquetes del target Windows consultado; no se asigna una probabilidad estadística de seguridad total. La asunción crítica es que el artefacto distribuido se construya con estos locks, target y features, sin dependencias externas omitidas por la auditoría.
