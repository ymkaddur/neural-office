# De V5.7 a V6

**Dirección del producto: un encargo claro, una ejecución controlada y una entrega que puedas comprobar.** El Director coordina; las fuentes, el coste y la decisión siguen siendo visibles para la persona.

El objetivo de una oficina local generalista permanece. Los hitos se aceptan por capacidades demostradas, no por una cantidad de pantallas, agentes o documentación. No hay fechas comprometidas ni una carrera por imitar un IDE.

**V5.8 en Windows.** El ejecutable recuperó el mismo intento tras dos cortes. La comparación de CPU, RAM y tiempo en seis documentos respalda la comprobación estática por defecto. Los comentarios del modelo siguen disponibles bajo autorización. [Reconexión](docs/V5_8_REVIEW.md) · [Coste y utilidad](docs/V5_8_RESOURCES.md).

| Hito | Qué gana la persona | Puerta de aceptación |
|---|---|---|
| **V5.6 · claridad y revisión útil** | Una entrada pública, borrador conservado al navegar, informe accionable y comprobación sin modelo. | Regresiones de navegación/arranque, corpus manual con omisiones explícitas, ejecutable probado y publicación revisada. [Entrega](docs/V5_6_REVIEW.md). |
| **V5.7 · utilidad medida** | Comprobar el archivo en el escritorio antes de decidir si consultar al Director. | 18 entregas en seis tareas. Un rol y tres roles no añadieron acciones según la rúbrica. Vista estática por defecto. [Método, costes y límites](docs/V5_7_REVIEW.md). |
| **V5.8 · contexto y recursos bajo control** | Conocer el coste de comprobar un archivo y de pedir una segunda lectura. | Comparación en Windows completada con Ollama en CPU. Un perfil GPU requiere su propio ensayo. La incorporación de memoria y de una skill declarativa de lectura depende de demostrar su utilidad, procedencia, inspección y revocación. |
| **V5.9 · experiencia y distribución** | Completar el trabajo sin conocer el entorno de desarrollo. | Sesiones con personas, teclado/lector de pantalla, recuperación tras fallos y sesiones largas. Instalación firmada en equipo limpio, requisitos medidos y diagnóstico del arranque intermitente. |
| **V6 · beta coherente** | Un recorrido local útil de principio a fin. | Fuente → alcance → autorización → trabajo → entrega → reapertura. Sin duplicar efectos, con parada comprobada, evidencia comprensible y aceptación humana. El segundo flujo sólo entra si supera su propia prueba de utilidad y límites. |

## Lo que cambia en la estrategia

1. **La referencia barata va primero.** El análisis determinista no requiere un modelo. Más roles sólo serán recomendados si mejoran una rúbrica publicada sin empeorar de forma injustificada errores o consumo.
2. **La interfaz explica el trabajo real.** Mantener separadas fuente, ejecución, hallazgo, recomendación y aceptación. Mostrar eventos y tiempos medidos; no rellenar silencios con tokens, porcentajes o razonamiento inventados.
3. **Idempotencia antes de autonomía adicional.** Conservar identidades, presupuestos y recibos al reintentar o recuperar. Un borrador local no es autoridad ni una orden pendiente.
4. **Reducir superficie antes de ampliarla.** Terminal, escritura Git, exploración de directorios y herramientas arbitrarias necesitan un caso de uso, permisos y recuperación propios. No son requisitos visuales de esta revisión de lectura.
5. **Una presentación, documentación por necesidad.** README para entender y empezar; manual para operar; evidencia fechada para revisar ingeniería. Los prototipos históricos permanecen fuera de producción.

## El siguiente experimento

Entregar a cinco personas un archivo sintético. Observar si seleccionan la fuente, explican qué cuesta un intento, distinguen un hallazgo de una sugerencia, detienen un encargo y recuperan el resultado correcto. Registrar la primera equivocación, el tiempo y la ayuda. El umbral formativo es cuatro de cinco completando el recorrido sin ayuda. La validación con personas está pendiente.

V5.8 midió CPU, RAM y tiempo en la primera revisión, al repetirla y con los pesos precargados para el ensayo. Antes de añadir memoria, se debe identificar una decisión concreta que la persona necesite repetir. Un nuevo perfil o modelo deberá superar la prueba en casos reservados y en español. Los tres intentos de proyecto son un presupuesto de ejecución independiente del número de roles.

## Abierto antes de V6

Persisten dos sondas sobre el nombre accesible, el arranque intermitente de Ollama, las sesiones largas, GPU, lector de pantalla y distribución firmada. Para el candidato de texto con citas, la coincidencia literal y el respaldo de la afirmación requieren evidencias distintas. La publicación del segundo flujo depende de una prueba funcional propia.

Después de V6, la dirección hacia V10 es ampliar tareas, skills, memoria y distribución entre sistemas sobre estas mismas puertas. Esa visión no se presenta como funciones disponibles ni como fechas de lanzamiento.
