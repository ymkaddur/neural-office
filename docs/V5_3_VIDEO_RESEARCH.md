# V5.3 — revisión dirigida de los vídeos de referencia

Fecha: 2026-11-16. **OBSERVADO:** seis MP4 facilitados por el promotor, duración agregada aproximada 8 h 18 min 45 s. Se inspeccionaron visualmente **24 fotogramas**, cuatro por vídeo: 15 s, 25%, 50% y 75% de su duración. No se escuchó/transcribió todo el audio ni se vieron íntegramente los vídeos. Los MP3 no se contabilizan como fuentes revisadas adicionales.

Los timestamps son posiciones de vídeo solicitadas al decodificador, redondeadas; no garantizan exactitud a nivel de frame sin PTS original. Los hashes identifican los archivos, no acreditan autoría, derechos de distribución o vigencia de sus demostraciones. No se redistribuyen medios, frames, código ajeno ni transcripciones. Se publican únicamente observaciones y decisiones propias.

## Índice comprobable

| ID | Descripción visible o nombre del material | Duración | Posiciones inspeccionadas (segundos) |
| --- | --- | --- | --- |
| VIDEO-01 | Getting more out of the Claude Platform | 1.695,10 s | 15; 423,77; 847,55; 1.271,32 |
| VIDEO-02 | Archivo de charla/demo con escenarios de evaluación y rutinas | 13.772,99 s | 15; 3.443,25; 6.886,50; 10.329,74 |
| VIDEO-03 | Charla con diapositivas de memoria de agentes | 1.887,37 s | 15; 471,84; 943,68; 1.415,52 |
| VIDEO-04 | Sesión con marca Stanford y demo de prompts | 6.011,47 s | 15; 1.502,87; 3.005,74; 4.508,60 |
| VIDEO-05 | Sesión AI Engineer Europe con evaluación y demo de audio | 4.539,60 s | 15; 1.134,90; 2.269,80; 3.404,70 |
| VIDEO-06 | Mastering LLM Inference Optimization, diapositiva NVIDIA | 2.018,68 s | 15; 504,67; 1.009,34; 1.514,01 |

SHA-256 del archivo completo:

```text
VIDEO-01 d26bc27265b05b0f3848c7d32c8bb391c1fa190d731ebf8d7af3542cba073183
VIDEO-02 8c8096c1c7e3b548ff38e4810dbde2fcfda1015b14d6067b210ec106208a41d7
VIDEO-03 50692bf0434c7c6f91fceafdaa6edd9f2fd18b6b7a555d3d6ea13cd85a882f16
VIDEO-04 50494ee7d693be936f9dc46635b89b19becbb4a0e9a4096fbe21df5e73544696
VIDEO-05 b2e36c54584e945c75e3a44fc3090e55f2e9016ae498a3af4a732c845b9a8cfa
VIDEO-06 ff8ad00e6b29b0aaefed6f5974549fd54de36cc961c5b78568b04f6b073de8a1
```

## De la observación a una decisión comprobable

| Fuente precisa | OBSERVADO en el frame | INFERIDO / decisión propia | Estado en Neural Office |
| --- | --- | --- | --- |
| VIDEO-01, 423,77 s | Demo con objetivos, fuentes y acciones de un equipo | Una interfaz puede mostrar trabajo, evidencia y presupuesto juntos | Prototipo V5.3 implementado con diseño propio; no reproduce la aplicación del vídeo |
| VIDEO-01, 847,55 s | Diapositiva sobre ejecutar herramientas sin incorporar todo resultado intermedio al contexto | Conviene medir selección/resumen de resultados antes de ampliar loops | Experimento futuro; no se ha incorporado tool calling programático |
| VIDEO-02, 3.443,25 s | Distintos evaluadores y tareas, incluyendo exactitud y eficiencia | Separar utilidad y coste, con criterio externo al agente | V5.3 mantiene verificador estático; corpus de calidad comparada pendiente |
| VIDEO-02, 6.886,50 s | Panel de verificación y comprobaciones múltiples | Mostrar estado de validación y sus límites | Separación actividad/informe/evidencia presente en la demo |
| VIDEO-02, 10.329,74 s | Ejemplos de rutinas para verificación e investigación | Una rutina necesita disparador, alcance y resultado esperado | Diseño de skills V6; no se han activado rutinas autónomas |
| VIDEO-03, 471,84 y 943,68 s | Evolución de memoria y problemas de obsolescencia/relevancia | Memoria con fuente, ámbito, vigencia y borrado | Hoja de ruta V6–V8, sin aprendizaje activo en V5.3 |
| VIDEO-03, 1.415,52 s | Memoria compartida y consolidación periódica entre sesiones | Consolidar debe ser una operación evaluada, con presupuesto y rollback | Diseño futuro; el vídeo no demuestra seguridad de nuestra implementación |
| VIDEO-04, 1.502,87 s | Demo en un playground con una versión antigua de modelo | Reproducir prompts y entradas vale más que copiar una configuración antigua | Se fija fixture y digest en las mediciones; no se incorpora ese proveedor |
| VIDEO-05, 1.134,90 s | Separación de quien construye y quien evalúa | Evitar que una autoevaluación sea la única prueba de calidad | Verificador estático independiente existente; juez semántico aún pendiente |
| VIDEO-06, 1.009,34 y 1.514,01 s | Opciones de despliegue, caché KV, cuantización y paralelismo | Comparar memoria/contexto/caché y capacidad antes de aumentar concurrencia | V5.4 medirá opciones soportadas por el runtime elegido; TensorRT-LLM no se incorpora |

Los frames de presentación, ponentes o transiciones que no aportan detalle técnico no justifican conclusiones adicionales. No se deduce identidad de personas por su cara, ni se toma una cifra de una diapositiva como benchmark propio.

## Próxima revisión de mayor utilidad

Prioridad 1: revisar con audio y continuidad temporal el bloque de optimización de VIDEO-06 alrededor de 1.009–1.514 s; contrastar cada opción con [Ollama](https://docs.ollama.com/faq), porque una función de TensorRT-LLM no implica soporte equivalente allí. Prioridad 2: VIDEO-03, 943–1.416 s, antes del contrato de memoria. Prioridad 3: bloques de evaluación de VIDEO-02/05 antes de comparar calidad de roles.

Esta agenda deja explícito qué falta examinar. La revisión parcial aporta hipótesis y decisiones de diseño; no cierra esas investigaciones ni sustituye las pruebas locales.
