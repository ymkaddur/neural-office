# Evidencia y límites de transferencia

Investigación consultada el 16–17 de noviembre de 2026. Los mecanismos externos se inspeccionaron en los archivos enlazados; no se ejecutaron sus repositorios. Las aplicaciones propuestas a Neural Office requieren prueba propia. Las licencias se indican para evitar confundir observación con permiso de copia.

## Lección aplicada al proyecto

Estas son reglas para una capacidad futura, no afirmaciones de que V5.5 implemente memoria aprendida o skills del producto. Las skills de este directorio se ejecutan como instrucciones del agente de desarrollo.

Aprender un principio de un repositorio no autoriza copiar su código. En particular, el ADR de Logseq figura Proposed y el editor de tldraw tiene licencia restrictiva. Joplin muestra una interacción de recuperación localizada, no atomicidad universal del autosave.


## Mecanismos externos

### anthropics/claude-code

[Archivo en el commit inspeccionado](https://github.com/anthropics/claude-code/blob/8a17c18509e5b76f8f3029d47d2538c99f6930ed/mods/sec-default/hooks/policy/managed-tools-restored/managed-tools-restored.ts#L9). Líneas 9-30,32-86; nivel: `source-inspected`.

OBSERVADO: el módulo conserva herramientas de autoridad gestionada frente a sustituciones de hooks de usuario; valida arrays y nombres reales en runtime; ante política ilegible conserva el listado gestionado. El test asociado incluye variantes de nombre y herramientas falsificadas. APLICACIÓN PROPUESTA V5.5: skills no deben poder sustituir autoridad ni registrar una herramienta que suplante identidad de otra.

**Límite:** Se inspeccionó un módulo público de políticas y su test, no el motor completo ni la seguridad global de Claude Code. Tests leídos, no ejecutados. LICENSE.md:1 reserva derechos y remite a términos comerciales; el repositorio público no equivale a licencia libre.

**Licencia observada:** No licencia libre detectada; LICENSE.md:1: derechos reservados y uso sujeto a Commercial Terms of Service.

### crewAIInc/crewAI

[Archivo en el commit inspeccionado](https://github.com/crewAIInc/crewAI/blob/96c4d85b6423dd06b7f1c38f12dd472399c6ce43/lib/crewai/src/crewai/flow/persistence/sqlite.py#L192). Líneas 192-215,285-327; nivel: `source-inspected`.

OBSERVADO: SQLiteFlowPersistence guarda estado y marcador de feedback pendiente en una misma conexión/transacción, usando lock y closing explícito. PROPUESTA V6: publicar la pausa/aprobación sólo cuando su estado durable esté guardado; probar caída entre escrituras y reanudar con identidad y permisos originales.

**Límite:** No ejecutado. decorators.py:147-159 aclara que persist sólo marca metadata y el motor guarda después del método: ello no hace atómico el efecto externo del método y su checkpoint. No reintroducir CrewAI al piloto sólo por genealogía; evaluar coste y contrato antes.

**Licencia observada:** MIT; LICENSE:1-19 inspeccionado.

### automerge/automerge

[Archivo en el commit inspeccionado](https://github.com/automerge/automerge/blob/09b19d5080a86548c72721a82747bebe272c6c31/rust/automerge/src/transaction/manual_transaction.rs#L15). Líneas 15-19,73-110,140-149; nivel: `source-inspected`.

OBSERVADO: la transacción manual consume inner al hacer commit/rollback; Drop revierte una transacción que todavía conserva inner. APLICACIÓN V6: mantener ownership explícito y cerrar las actualizaciones de memoria/skills en una frontera verificable; si no hay commit confirmado, no publicar estado intermedio como aprendizaje válido. Prueba: error en cada etapa anterior al commit conserva la versión previa y no emite aprobación.

**Límite:** El mecanismo agrupa/revierte operaciones del documento en memoria. No convierte automáticamente su persistencia, sincronización de red o herramientas externas en una transacción durable y reversible. No se ejecutaron tests ni se recomienda incorporar un CRDT para el piloto monousuario.

**Licencia observada:** MIT; LICENSE:1-19 leído en el SHA indicado.

### tldraw/tldraw

[Archivo en el commit inspeccionado](https://github.com/tldraw/tldraw/blob/3c4639ec8bce853ef19cbea0361e524f630dccfa/packages/editor/src/lib/utils/sync/TLLocalSyncClient.ts#L16). Líneas 16-19; 228-311; 320-361; 376-388; nivel: `source-inspected`.

OBSERVADO: recibe y almacena mensajes durante carga, espera flushes anteriores de la misma clave y drena antes de declarar cargado; al cerrar espera escritura activa y vacía cambios pendientes. Poda estados de sesión sin convertir un fallo de poda en fallo de carga. PROPUESTA V6: proyecto nuevo no puede sobrescribir una persistencia saliente; prueba cerrar/reabrir mientras una escritura está retenida, con evento concurrente y sin cambios.

**Límite:** Inspección estática, sin tests ejecutados ni medición de recursos. Es IndexedDB/BroadcastChannel y no prueba durabilidad ante caída del SO. Las colas leídas no establecen un límite numérico universal; requerimos presupuesto de memoria propio. No importar el editor para resolver persistencia.

**Licencia observada:** packages/editor/LICENSE.md:1 remite a LICENSE.md. LICENSE.md:15-34 autoriza desarrollo y prohíbe producción sin licencia alternativa; incluye restricciones de distribución y mecanismo de licencia (48-50). Fuente disponible no significa MIT ni open source permisivo.

### laurent22/joplin

[Archivo en el commit inspeccionado](https://github.com/laurent22/joplin/blob/68b1f922791e14d3e8fa7b4d6765ad3eaedebdd0/packages/app-mobile/components/NoteEditor/ImageEditor/promptRestoreAutosave.ts#L8). Líneas 8-34; nivel: `source-inspected`.

OBSERVADO: al hallar un dibujo autoguardado, ofrece descartar o adjuntar; no restaura silenciosamente. PROPUESTA V5.5/V6: mostrar borrador recuperable por proyecto, con vista previa y decisión explícita; conservar la copia hasta que el destino confirme persistencia. Pruebas: cierre tras leer y antes de adjuntar, rechazo del destino, recuperación repetida y cambio de proyecto.

**Límite:** La ruta leída es del editor móvil de dibujos, no del editor general. El callback de adjuntar se invoca después de borrar el autosave (líneas 27-30); esta inspección no demuestra recuperación atómica. El archivo auxiliar usa un nombre único por directorio de recursos; no trasladarlo como diseño multisesión ni afirmar que Joplin pierde datos sin reproducción.

**Licencia observada:** LICENSE:1-10: AGPL-3.0-or-later por defecto, salvo LICENSE local; no se encontró excepción antecesora en esta ruta. LICENSE:14-23 reserva marca, logos e iconos. Solo aprendizaje de principio; sin copia de código o recursos.

### logseq/logseq

[Archivo en el commit inspeccionado](https://github.com/logseq/logseq/blob/d6082682125a4d528afc377927a1cf18f14e7d18/docs/adr/0011-undo-redo-semantic-inverse-op-persistence.md#L3). Líneas 3-38; 62-71; nivel: `proposed-contract-inspected`.

OBSERVADO: ADR 0011 propone una acción durable identificada por tx-id; el historial UI conserva selección/foco y referencia esa acción. Distingue operación semántica inversa de repetición de datos brutos. PROPUESTA V6: deshacer una edición del informe y compensar un efecto del agente deben ser operaciones distintas, enlazadas a evidencia. Pruebas: editar, recibir cambio remoto, deshacer y rehacer sin perder la identidad de la acción.

**Límite:** Status: Proposed en línea 4; no se ha demostrado implementación. El propio contrato excluye pendientes antiguos sin metadatos y operaciones sin inversa semántica. Cancelar una inferencia o un correo ya enviado no equivale a undo; mostrar Deshacer sin capacidad de compensación sería engañoso.

**Licencia observada:** LICENSE.md:1-65 inspeccionado, AGPL-3.0; no excepción antecesora para el ADR. Referencia conceptual, sin incorporar implementación.


## Feedback público

### F08: Claude Code: solicitud de instrucciones de proyecto interoperables

[Fuente pública](https://github.com/anthropics/claude-code/issues/6235). Publicación: 2025-08-21T07:22:15Z. Consulta: 2026-11-17. Localizador: GitHub issue body completo (dos párrafos).

OBSERVADO: el autor pide AGENTS.md porque el archivo específico de Claude dificulta colaborar con personas que usan otros agentes.

HIPÓTESIS: Neural Office debe mostrar qué instrucciones y skills aplica, su procedencia y alcance, sin obligar a duplicarlas silenciosamente por proveedor.

PENDIENTE: cargar instrucciones solapadas y contradictorias; inspeccionar precedencia determinista y cambios visibles; verificar que texto importado nunca amplía permisos de ejecución.

**Límite:** Solicitud histórica cerrada; no demuestra la cobertura actual de AGENTS.md en Claude ni que una convención de archivos garantice seguridad.

### F11: Cursor: recuperación poco visible y límites de las reglas escritas

[Fuente pública](https://forum.cursor.com/t/very-ineffcient-constant-crashing-taking-forever/169219). Publicación: 2026-08-23T11:57 (hora mostrada por el foro; zona no acreditada). Consulta: 2026-11-17. Localizador: Entradas 8-9, 13-14 y 20-26; lectura incluye la recaída y la rectificación sobre planes separados.

OBSERVADO: usuario no encuentra restauración y describe fallos de una refactorización larga. Soporte reconoce controles de checkpoint que no se muestran en algunos chats y distingue instrucciones de bloqueos. Una mejora inicial relatada por el usuario no se mantiene en mensajes posteriores.

HIPÓTESIS: restauración debe ser descubrible fuera del hover y funcionar sin depender de un chat sano; las pausas de revisión deben imponerse por estado, no por prosa del plan.

PENDIENTE: historial paginado/reabierto, sesión cancelada y proyecto recuperado; localizar restauración sin ayuda y validar alcance antes de aplicar. Probar que el motor no atraviesa una puerta de revisión.

**Límite:** No tomar las explicaciones de RAM/contexto como causalidad probada: soporte pide logs adicionales. Parte final contiene una autodescripción del modelo, que tampoco es una autopsia técnica verificada.


## Método docente

### California Institute of Technology (Caltech)

[2014–15 Caltech Catalog — CS 118 Logic Model Checking for Formal Software Verification](https://catalog.caltech.edu/archive/2014-15/department/CS/). Descripción de CS 118. Nivel: catalog_description. Localizador: CS 118; líneas extraídas 385–392. Consulta: 2026-11-17.

Presenta comprobación de modelos, verificación mediante autómatas y herramientas como apoyo a la corrección de programas concurrentes y diseños de sistemas.

INFERIDO: expresar transiciones e invariantes antes de modificar cancelación, presupuesto o reintentos; buscar contraejemplos pequeños.

**Comprobación propuesta:** PROPUESTO: explorar un modelo acotado de intento, reserva, cancelación y confirmación; contrastarlo después con pruebas del código real.

**Límite:** Catálogo de 2014–15, sin clases inspeccionadas ni afirmación de oferta vigente. Un modelo correcto no prueba automáticamente la implementación.
