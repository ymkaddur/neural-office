# Índice de evidencias de Neural Office V5.1

Este índice identifica fuentes consultadas del legado. Las rutas son relativas a raíces lógicas; no exponen carpetas personales. Los archivos de origen no están incluidos en la publicación documental. Verificar su contenido requiere una copia autorizada coincidente con el hash.

La revisión de referencia corresponde al 15 de noviembre de 2026. Las líneas empiezan en 1 y los hashes corresponden a los bytes completos del archivo, no solo al fragmento citado. Un hash acredita coincidencia de bytes; no certifica derechos o autoría.

## Raíces lógicas

| Raíz | Significado |
| --- | --- |
| LEGACY | Raíz del proyecto histórico de Neural Office. |
| CREWAI_ENV | Entorno Python histórico inspeccionado, excluido de la distribución. |
| CREWAI_SOURCE | Copia fuente de CrewAI inspeccionada. |
| V5_STAGE | Staging histórico de V5 corregido, excluido de la distribución. |
| DOWNLOADS | Archivo histórico identificado por nombre, sin publicar su ubicación personal. |

## Referencias

| ID | Raíz y ruta relativa | Líneas | Hecho contrastado |
| --- | --- | --- | --- |
| E01 | `LEGACY/studio/studio.py` | 28–30 | Catálogo V1 y límites. |
| E02 | `LEGACY/studio/office/neural_office_v4/engine/office_v4.py` | 324–343 | Avance de versiones y sincronización V1 pendiente. |
| E03 | `LEGACY/studio/office/neural_office_v41/engine/v41.py` | 234–249 | Conciliación V1/V4. |
| E04 | `LEGACY/studio/office/neural_office_v42/engine/v42.py` | 353–404 | Validación de recibos y contenido de dependencias. |
| E05 | `LEGACY/studio/office/neural_office_v5/runtime/controlplane.py` | 172–278 | Activación local, intentos y veredictos. |
| E06 | `LEGACY/studio/office/neural_office_v5/runtime/orchestration.py` | 54–160 | Traspaso por hashes y director serial. |
| E07 | `LEGACY/studio/office/neural_office_v5/runtime/v5.py` | 24–79 | Dependencias fijadas y CLI de simulación. |
| E08 | `LEGACY/studio/office/neural_office_plus/office_plus/runtime.py` | 301–328 | Director y piloto histórico. |
| E09 | `LEGACY/studio/office/neural_office_v3/v3.py` | 112–153 | Configuración nativa y workspace heredado. |
| E10 | `LEGACY/studio/office/neural_office_v4/v4.ps1` | 9–19 | Lanzador de la rama V4 R4. |
| E11 | `LEGACY/studio/office/neural_office_v44/engine/mutex.py` | 37–49 | Nombre y alcance del mutex. |
| E12 | `LEGACY/studio/office/neural_office_v5/runtime/gateway45.py` | 60–130 | Admisión, sesión, lease y transporte. |
| E13 | `LEGACY/studio/office/neural_office_v5/runtime/protocol.py` | 9–66 | Subconjuntos nativo y compatible. |
| E14 | `LEGACY/studio/office/neural_office_v5/runtime/routepatch.py` | 22–57 | Parche de URL con control de hash. |
| E15 | `LEGACY/studio/office/neural_office_v5/operations/COMPAT_GATE_B_CPU64K_OPERATOR.ps1` | 7–14 | Ruta esperada del Modelfile. |
| E16 | `LEGACY/studio/office/neural_office_v5/operations/COMPAT_GATE_C_ROUTE_OPERATOR.ps1` | 7–19 | Ruta esperada del operador de parche. |
| E17 | `LEGACY/studio/office/neural_office_v5/runtime/knowledge.py` | 51–151 | Bloqueo por ruta y biblioteca de contexto. |
| E18 | `LEGACY/studio/office/neural_office_v5/runtime/skills.py` | 1–23 | Cuarentena y promoción pendiente. |
| E19 | `LEGACY/studio/office/neural_office_v5/runtime/context.py` | 1–47 | Empaquetado de contexto y presupuesto. |
| E20 | `LEGACY/studio/office/neural_office_v5/runtime/prompting.py` | 1–24 | Mandatos y preparación de prompts. |
| E21 | `LEGACY/studio/office/neural_office_v45/engine/contracts.py` | 6–15 | Cinco productos y perfil CPU64k. |
| E22 | `LEGACY/studio/office/neural_office_v5/profiles/CPU_ONLY_OPERATING_PROFILE.json` | 1–14 | Perfil CPU y límites declarados. |
| E23 | `LEGACY/studio/office/neural_office_v43/plugin/index.js` | 5–29 | Adaptador de OpenCode y pin de versión. |
| E24 | `LEGACY/studio/office/neural_office_v5/runtime/readiness.py` | 7–59 | Diagnóstico y límites de certificación. |
| E25 | `LEGACY/studio/office/neural_office_v45/engine/director.py` | 108–128 | Aparcado no persistido en el director anterior. |
| E26 | `LEGACY/studio/office/neural_office_v5/runtime/director.py` | 108–136 | Corrección durable del director de compatibilidad. |
| E27 | `LEGACY/studio/office/neural_office_v445/engine/policy445.py` | 115–175 | Inspección de rutas y cobertura no demostrada. |
| E28 | `LEGACY/studio/office/neural_office_v5/profiles/Modelfile_CPU64K_FOR_OPERATOR.txt` | 1–5 | Definición de modelo candidato. |
| E29 | `LEGACY/orchestrator.py` | 226–274 | Uso efectivo de clases CrewAI en el origen. |
| E30 | `CREWAI_ENV/Lib/site-packages/crewai_tools-1.15.40.dist-info/METADATA` | 2–17 | Versión y dependencia PyMuPDF. |
| E31 | `CREWAI_ENV/Lib/site-packages/pymupdf-1.26.7.dist-info/METADATA` | 2–8 | Versión y declaración de licencia dual. |
| E32 | `CREWAI_SOURCE/LICENSE` | 1–19 | Licencia MIT del código fuente consultado. |
| E33 | `V5_STAGE/VALIDATION_REPORT.json` | 16–64 | Resultados declarados y repetición Windows pendiente. |
| E34 | `DOWNLOADS/NEURAL_GATE_A_VERIFIED_20261115_174056_149db6a3.json` | 17–93 | Recibo histórico de Gate A y hashes. |
| E35 | `LEGACY/studio/office/neural_office_plus/workspaces/web-auditor/opencode.json` | 1001–1011 | Modelo, límites y ruta de la configuración del workspace. |
| E36 | `LEGACY/studio/office/recovery_backups/recovery_20261114T083640504710/RECOVERY_RECEIPT.json` | 2–10 | Recuperación estructural y límites de evidencia. |

## Identidad de las fuentes

```text
E01  6aacfcefad33b92e67f53f75178447884793e6d4a85c7ac8db01d22af42ec1d4
E02  fa04a5be5662ea884803a8658218162af8f0d4079406ac91e1193985b907bbc7
E03  d34270374730815140587d73a4a2916b0bba098c0d2905513dba5383924b31c8
E04  0b28224482100f78b32cfcce037cc6ce25c6ea9e3bc598b4ebe71ca961d6713c
E05  9297a6b21fdd21241479f76278fa8a14f968407eca2ff674c2d5543e951037f2
E06  3bac808d2b938509db91adcbf7c51cad9435756125045d13240e901b032ee258
E07  1239a263e5e3a3d3adf995fa4f397d0ab3eb53b0d8762f8a2077fa5037bab823
E08  f09313402c4ae4d4f44a8f6efecd054aa5faa37e84f9cfd23acd1256de70aca9
E09  fca31a2bd587cf2aec42604a3cd567e4b6cda80c2b5eed447c60f545cc0f071f
E10  80725dadbcbc7a7e2a8897157f22921e42c80eed40fc0e341b865a5e107faaa7
E11  7cc99129a1bbdd9528744d6d92d913d7b746462693dd0fae9897b16f814dc225
E12  00e82c5fca90df136bf9526867254ffcfd89d173c9521aee4e14bf7c2d86c5af
E13  e989e21874090edb818add2d6ec185c6b1b2c0f96cb02b06258c4f55a07bf6f3
E14  509b6386e203decaa7beb62094f9f4b45abee897088668f50d02f727bfe41c57
E15  515f67a3ad77a23b62020b90c45ece021ffbbd4354a01fe4ebafdd6ba6412196
E16  dcd284c435c21fdf4bf619194cd3333345601be4e0a063a07113a132ec8f15a5
E17  1a95a86d6fcc64a1360bc716a55da9bf586d228066ec484aaf408bc56f0ac728
E18  aa87e90276cd4a57aa48eac80ae9adb560db5f05fd8d8c8d634c00b93f39da95
E19  8d3af7682a1e62e1c97d2ae4d65f650c58f564f1aa5e825817e98201b570223d
E20  9e6b9530bb4457a2f73dce4e84d829540e3a7cadd7819af0459a139f13940334
E21  1f2c1e47a13c94046002035c74a53ac927e6861c808171cc25c551a645df936a
E22  e8624a9e8fd74a5d312ec437dcdc2e0dfd685bb01e261ec323293050c32f3465
E23  e05ae489a8a017683336e34e823fadb7f765a01cbf109c82d78849cc2abccbe4
E24  e4eddf58a97e0d22ca3ce4fb1886d0d0bc3b1a52fbc945e6e92cd015c30e9515
E25  b457d75a65646e89237f2ae8574b617ebda927c8a59992e75b2a262bbd36d028
E26  c989c3afae043eb74ae0c082a2028bcf2705e4e8c4cb57b0c90520bac93fe004
E27  77ba05c6b0d9f9ddeb828cd225137f56ce5fc3a41be33d2ad6bd59bdfb915ec1
E28  72b8eb6a38bb9ac5e88efdd0a5b8be6083179ea125b968e974eb0845d15d8258
E29  eeed7114ac4d6f80bdf627f216ba19ac8bb5fea1ed5eb5aba5b4361b093f7b93
E30  dda0242706f96c561b4197d21891ceacdfe4dd81a06f00eb0dd333729141d2d4
E31  1be20696e95d6a94cf0f331464ee3932516304e253a11cc73634cd5027eed728
E32  28868731966f4aa37f02879839aabc797137e27ddde4e274ef9cf965f9a71774
E33  ef0ca9c964f3778c5b04dc29e596c54241ecc3c3f3186349eca01cae6f797cc4
E34  a3a293df161f694bdff28929d3b8250cf5b56a4afd07edcb37ac18a4d40fe0f4
E35  47f1762d01c9d8e164f4e2b4e62455e1cb83b26f11374b2d32e12f326c499fb1
E36  d0bd137d79ff72113bd160159381823634158c9a9b6de7fdceaf477e7c60aa44
```

## Lectura de los resultados

Los requisitos AUT, CTR, STA, CON, MIG, VER, MOD, NET, TOOL, ROLE y LOOP son ESCENARIO: propuestas de diseño vinculadas a estos hallazgos. Los casos A01–A22 e I01–I23 están pendientes de ejecución. La verificación documental de vínculos, rangos y hashes no cuenta como prueba del runtime. Las fuentes E01–E36 son OBSERVADO por inspección; su identidad de bytes y la validez de sus rangos se comprueban por separado. Un informe histórico sigue siendo una declaración de su emisor, incluso cuando su hash coincide.
