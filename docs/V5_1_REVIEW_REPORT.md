# Registro de revisión crítica de V5.1 documental

Revisión cerrada documentalmente el 16 de noviembre de 2026, hora de Madrid. La instantánea histórica de referencia es del 15 de noviembre. Se realizaron tres pasadas sucesivas por el mismo revisor asistido; no son auditorías independientes. No se ejecutó el runtime, ningún instalador histórico, pruebas del proyecto ni inferencia de modelos.

## Fase 0: incidente y propiedad exigida

**OBSERVADO.** En el borrador documental de V5.1, algunas reglas permitían interpretaciones incompatibles sobre estados, identidad, exclusión y evidencia, en lugar de un contrato único que una implementación pudiera satisfacer y verificar. Además, la publicación remota estaba pendiente. No se dispone de una firma de fallo de producción atribuible a estas reglas propuestas; no se inventa un stack trace, código de retorno o cronología de ejecución.

**ESCENARIO, propiedad exigida.** Publicar exclusivamente documentación coherente, trazable y sin datos privados, manteniendo intacto el legado. Los requisitos futuros deben distinguirse de hechos observados y pruebas ejecutadas. La reproducción mínima del defecto documental consiste en leer las reglas citadas y construir los contraejemplos de este registro; no exige arrancar agentes.

La copia anterior y el diff exacto se conservan en el expediente privado. El diff de los seis archivos existentes modificados tiene SHA-256 `420f1ae7b89db30c359ef6d731e9f6cfbb0b56b096de4fc1cb581b55c71d9e01`. El registro presente y el manifiesto son archivos nuevos; no están incluidos en ese diff, para evitar una dependencia circular. El manifiesto identifica los bytes finales del conjunto publicable.

## Diario de reconstrucción: escenarios y orden causal

El orden T0–T7 representa dependencias observadas de esta revisión, no timestamps inventados de ejecución del producto. Los timestamps de herramientas y recibos de comprobación se conservan localmente. La firma buscada es una contradicción o un requisito insuficientemente definido en documentos, no una excepción del software.

| Orden | Escenario o experimento | Resultado y actualización |
| --- | --- | --- |
| T0 | Preservar los ocho archivos iniciales y leer los contratos completos. | OBSERVADO: existe una tabla que mezcla estados de proyecto e intento y permite salir de un terminal hacia READY. |
| T1 | H1: faltan límites semánticos entre entidades y operaciones. Predice contraejemplos aun sin cambios de archivos o de entorno. | VERIFICADO documentalmente: la lectura de la tabla y los ejemplos D01–D05 muestran ambigüedad o garantías insuficientes. H1 queda dominante. |
| T2 | H2: es solo un error de formato o de numeración. Predice que el contenido normativo ya excluye todos los contraejemplos. | DESCARTADO como explicación principal: una exclusión por recurso admite dos recursos simultáneos; corregir numeración no cambia esa relación. Sí existía un defecto menor de recuento, D06. |
| T3 | H3: el lector debe completar las garantías usando implícitamente el código histórico. | DESCARTADO como fundamento del contrato: E05 y E06 describen componentes separados y el documento se presenta como propuesta futura. E05:250–256 ya protege un estado de veredicto en su propio flujo; no se le atribuye el defecto de duplicación de la especificación incompleta. |
| T4 | Primera intervención: separar entidades, precisar reserva, idempotencia, terminación y exclusión global. | ESCENARIO corregido en AUT, CTR, STA y CON; se añaden casos límite pendientes. No se transforma esa corrección de texto en prueba del runtime. |
| T5 | Segunda pasada: intentar refutar las garantías mediante lectura intercalada, restauración completa y redacción de entradas. Contrastar E34 y licencias primarias. | VERIFICADO: los contraejemplos delimitan lo que un hash puede demostrar. E34 respalda V1/V4; se retiran inferencias sobre otras bases que ese recibo no demuestra. Se preserva la incertidumbre de derechos y dependencia transitiva. |
| T6 | Tercera pasada adversarial: suponer que el contrato corregido todavía permite trabajo tras el terminal. Revisar todos los consumidores y la integración final. | OBSERVADO: faltaba situar la aplicación del candidato antes del resultado terminal. Se añade INTEGRATING/STA-05 y se revalida autoridad por operación, AUT-09. Se comprueban también el recuento, las referencias y la privacidad de metadatos de publicación. |
| T7 | Comparar hashes protegidos, rangos de evidencia, selección pública y bytes a publicar. | VERIFICADO en el ámbito indicado abajo. La publicación remota se verifica después de este cierre local y se registra en un recibo separado; este informe no anticipa su resultado. |

H4, alternativa adversarial más fuerte: el nuevo texto todavía deja contratos de implementación sin fijar y podría permitir otra interpretación. **NO ELIMINADA globalmente.** Se reduce para los casos identificados mediante reglas explícitas y casos de aceptación, pero permanece para algoritmos de persistencia, aislamiento, recuperación y cancelación que todavía deben diseñarse y probarse. Por ello no se declara ausencia total de errores ni se autoriza modificar producción como consecuencia automática de esta revisión.

## Registro de caza de matices

Las referencias siguientes apuntan a la versión final de los documentos. Las líneas son de esta entrega; para una revisión posterior deben usarse el commit y los hashes correspondientes.

| ID | Matiz, predicción discriminante y observación | Corrección documental y fuente exacta |
| --- | --- | --- |
| D01 | OBSERVADO: mezclar entidades permite interpretar que un intento terminal vuelve a estar listo. El detalle se descarta solo si cada estado tiene dueño y los terminales carecen de salidas. | Proyecto ACTIVE/PARKED separado del intento; terminal inmutable y un solo intento pendiente. [Autoridad:81](V5_1_AUTHORITY_AND_COUNTERS.md#L81), [STA-04:104](V5_1_AUTHORITY_AND_COUNTERS.md#L104). |
| D02 | VERIFICADO en modelo abstracto: recurso A ocupado=1 y recurso B ocupado=1 satisfacen sendos límites de 1, pero suman 2. No es un ensayo del gateway. | Un dominio estable, una admisión global, restricciones por recurso adicionales. [CON-01:110](V5_1_AUTHORITY_AND_COUNTERS.md#L110). |
| D03 | VERIFICADO en secuencia sintética: hash A → lectura B → hash A conserva ambos hashes y no prueba que se leyera A. Se refutaría si el lector consumiera una identidad inmutable. | Instantánea inmutable y recibo de los bytes consumidos. [STA-01:98](V5_1_AUTHORITY_AND_COUNTERS.md#L98). |
| D04 | VERIFICADO en datos sintéticos: dos argumentos distintos redactados como el mismo marcador producen idéntica proyección. Su digest tampoco distinguiría los originales. | Separación entre entradas privadas efectivas y proyección exportable; no deduplicar por esta última. [Integración:95](V5_1_INTEGRATION_SPEC.md#L95), [Integración:103](V5_1_INTEGRATION_SPEC.md#L103). |
| D05 | INFERIDO por indistinguibilidad: un sistema sin testigo retenido ve el mismo S0 si nunca avanzó o si todo fue revertido a S0. No puede demostrar el consumo perdido a partir de S0 solo. | Restauración gestionada con evidencia conservada fuera de la copia; ausencia de evidencia bloquea; reversión de todos los testigos fuera de garantía. [CTR-07:71](V5_1_AUTHORITY_AND_COUNTERS.md#L71). |
| D06 | VERIFICADO: el recuento anterior detectaba 58 requisitos en negrita y omitía los 8 AUT de tabla: eran 66, no 58. Una expresión demasiado amplia también confundía I1–I8, pasos de implementación, con I01–I23, casos de aceptación. | Recuento por sintaxis de definición y dos dígitos para casos. Resultado final: 69 requisitos únicos y 45 casos futuros; no se contabilizan como tests ejecutados. |
| D07 | OBSERVADO: la reserva no vinculaba explícitamente la misma clave a un contenido único ni imponía unicidad del veredicto en la especificación completa. Una clave distinta tampoco debe permitir otra aceptación del mismo intento. | Ámbito, digest canónico, conflicto y unicidad terminal. [CTR-02:61](V5_1_AUTHORITY_AND_COUNTERS.md#L61), [VER-03:150](V5_1_AUTHORITY_AND_COUNTERS.md#L150), [Integración:101](V5_1_INTEGRATION_SPEC.md#L101). |
| D08 | ESCENARIO adversarial: director, planner, calibración o curación consumen modelo antes de reservar o fuera de cuotas. Refutación exigida: toda llamada tiene una categoría y presupuesto autorizado. | Reservar antes de planificar; sondas sintéticas acotadas; curación dentro de un intento. [CTR-01:59](V5_1_AUTHORITY_AND_COUNTERS.md#L59), [MOD-06:68](V5_1_INTEGRATION_SPEC.md#L68), [Integración:208](V5_1_INTEGRATION_SPEC.md#L208). |
| D09 | ESCENARIO adversarial: cancelar un socket, vencer un lease o confirmar manualmente la recuperación libera el recurso mientras el efecto continúa. | STOPPING/RECOVERY_REQUIRED conservan exclusión; terminación y efectos requieren evidencia. No se promete exactamente una vez en sistemas externos por usar una transacción local. [Estados:83](V5_1_AUTHORITY_AND_COUNTERS.md#L83), [CON-06:120](V5_1_AUTHORITY_AND_COUNTERS.md#L120). |
| D10 | ESCENARIO adversarial: un enlace cambia entre validar la ruta y abrirla; un prefijo textual similar sale del workspace. No se ejecutó ataque sobre archivos reales. | Vincular la operación a la identidad autorizada o denegar; caso I20 pendiente. [TOOL-02:146](V5_1_INTEGRATION_SPEC.md#L146). |
| D11 | OBSERVADO en revisión del diseño: aceptar antes de integrar deja un efecto productivo fuera del intento terminado. | INTEGRATING precede al terminal, consume cuotas y requiere recibo. Si cambió la base, no se aplica ni modifica el candidato bajo el veredicto anterior. [STA-05:106](V5_1_AUTHORITY_AND_COUNTERS.md#L106), [TOOL-04:150](V5_1_INTEGRATION_SPEC.md#L150). |
| D12 | OBSERVADO: un recibo histórico, un informe de tests o una licencia declarada podían interpretarse con más alcance del acreditado. | Separar lectura, identidad de bytes, ejecución, entorno y derechos. E34 solo sustenta sus campos; agregados anteriores y visionado parcial se califican como tales. [Procedencia:35](V5_1_PROVENANCE_AND_PUBLICATION.md#L35), [Procedencia:57](V5_1_PROVENANCE_AND_PUBLICATION.md#L57), [Procedencia:125](V5_1_PROVENANCE_AND_PUBLICATION.md#L125). |

## Registro de evidencia y comprobaciones ejecutadas

**VERIFICADO, integridad acotada.** Se compararon los 201 archivos protegidos enumerados por la línea base privada: cero diferencias. Se releyeron las 36 fuentes E01–E36: hashes coincidentes y rangos de líneas válidos. Esto acredita esos archivos, no todos los archivos del equipo ni la corrección del programa. El [índice de fuentes](evidence/SOURCE_INDEX.md) conserva sus rutas lógicas, rangos y hashes sin publicar sus contenidos privados.

**VERIFICADO, revisión documental.** Los requisitos finales son 69 y los casos de aceptación 45 (A01–A22 e I01–I23). Se revisaron las referencias internas, unicidad de identificadores, coherencia de los nuevos estados, lista cerrada de archivos y patrones de datos privados. La inspección manual completa el barrido de patrones; ninguno equivale a una prueba matemática de ausencia de información sensible.

**OBSERVADO, procedencia.** La licencia de la copia de CrewAI y su referencia pública es MIT; la metadata de PyMuPDF declara AGPL o licencia comercial. La dependencia consta en E30:12. La obligación del producto final no se deduce solo de tener un paquete instalado. Las fuentes primarias y las decisiones pendientes están en el [expediente](V5_1_PROVENANCE_AND_PUBLICATION.md). No se concede una licencia propia por analogía con CrewAI.

**DESCONOCIDO, funcionamiento.** Los 45 casos futuros no se ejecutaron. No hay resultados nuevos de carreras, cancelaciones reales, recuperación de efectos, instalación limpia, selección de modelos, calidad de roles o cumplimiento jurídico de un binario futuro. El visionado audiovisual sigue siendo parcial; no se presenta como investigación exhaustiva de casi nueve horas de material.

**ESCENARIO, comprobación remota.** Tras publicar, leer anónimamente el repositorio público, fijar el SHA del commit, comprobar todos los blobs y su manifiesto, verificar que el árbol tiene solo los diez archivos previstos y revisar identidad de autor/committer. Conservar el recibo fuera de la selección pública. Un fallo de esa comprobación impide declarar la publicación verificada.

## Escenario causal dominante y duda residual

**INFERIDO, alcance documental.** El defecto dominante era una especificación insuficientemente precisa en las fronteras entre estado, autoridad, efecto y evidencia. La revisión anterior de vínculos y hashes no podía detectarlo: identificaba archivos y referencias, sin demostrar sus implicaciones semánticas. Se han corregido esas fronteras en los documentos; no se ha demostrado ni corregido un incidente de producción.

La duda residual más relevante es si una implementación concreta puede imponer estos límites en Windows cuando una operación externa queda indeterminada. Los estados y casos escritos no resuelven ese problema por sí solos. El siguiente experimento deberá ser una reproducción mínima aislada de admisión, cancelación y recuperación, con eventos correlacionados y sin modificar el legado. Requiere una fase de implementación autorizada aparte.

## Siguiente acción y confianza

Publicar y verificar este paquete documental. Después, abordar V5.1 implementación por incidentes acotados, comenzando por las rutas de empaquetado y el contrato de admisión, con diff mínimo y pruebas de borde antes de activar un piloto. No iniciar agentes como efecto secundario de esta entrega.

**Confianza: 90 %**, juicio técnico no calibrado sobre que las ambigüedades identificadas han quedado explícitamente tratadas en esta entrega documental. No es una probabilidad de ausencia de errores ni de seguridad o cumplimiento jurídico del producto. La asunción crítica es que el perímetro relevante es la oficina administrada y que los componentes futuros respetarán una única autoridad durable; si existen rutas de ejecución fuera de ella, la garantía de exclusión y presupuesto no se extiende a esas rutas.

El cierre es satisfactorio para la revisión documental de los hallazgos enumerados, sujeto a la verificación remota separada. La implementación, las pruebas dinámicas y las decisiones de derechos siguen pendientes y no se ocultan tras la palabra «verificado».
