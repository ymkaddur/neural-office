# De V5.6 a V6

**Dirección del producto: un encargo claro, una ejecución controlada y una entrega que puedas comprobar.** El Director coordina; las fuentes, el coste y la decisión siguen siendo visibles para la persona.

El objetivo de una oficina local generalista permanece. Los hitos se aceptan por capacidades demostradas, no por una cantidad de pantallas, agentes o documentación. No hay fechas comprometidas ni una carrera por imitar un IDE.

| Hito | Qué gana la persona | Puerta de aceptación |
|---|---|---|
| **V5.6 · claridad y revisión útil** | Una entrada pública, borrador conservado al navegar, informe accionable y comprobación sin modelo. | Regresiones de navegación/arranque, corpus manual con omisiones explícitas, ejecutable probado y publicación revisada. [Entrega](docs/V5_6_REVIEW.md). |
| **V5.7 · utilidad antes de más agentes** | Comentarios que realmente ayuden a decidir qué corregir. | Comparar sin modelo / un rol / revisión acotada sobre tareas iguales; medir errores, acciones útiles y coste. Evaluar también un documento de texto con citas como candidato a segundo flujo. |
| **V5.8 · contexto y recursos bajo control** | Evitar repetir instrucciones útiles y trabajar dentro de los recursos del equipo. | Sólo una skill declarativa de lectura y memoria mínima si V5.7 demuestra necesidad; procedencia, inspección y revocación. Comparación CPU/RAM/tiempo con igual calidad; GPU como perfil separado. |
| **V5.9 · experiencia y distribución** | Completar el trabajo sin conocer el entorno de desarrollo. | Sesiones con personas, teclado/lector de pantalla, recuperación tras fallos y sesiones largas. Instalación firmada en equipo limpio, requisitos medidos y diagnóstico del arranque intermitente. |
| **V6 · beta coherente** | Un recorrido local útil de principio a fin. | Fuente → alcance → autorización → trabajo → entrega → reapertura. Sin duplicar efectos, con parada comprobada, evidencia comprensible y aceptación humana. El segundo flujo sólo entra si supera su propia prueba de utilidad y límites. |

## Lo que cambia en la estrategia

1. **La referencia barata va primero.** El análisis determinista no requiere un modelo. Más roles sólo serán recomendados si mejoran una rúbrica publicada sin empeorar de forma injustificada errores o consumo.
2. **La interfaz explica el trabajo real.** Mantener separadas fuente, ejecución, hallazgo, recomendación y aceptación. Mostrar eventos y tiempos medidos; no rellenar silencios con tokens, porcentajes o razonamiento inventados.
3. **Idempotencia antes de autonomía adicional.** Conservar identidades, presupuestos y recibos al reintentar o recuperar. Un borrador local no es autoridad ni una orden pendiente.
4. **Reducir superficie antes de ampliarla.** Terminal, escritura Git, exploración de directorios y herramientas arbitrarias necesitan un caso de uso, permisos y recuperación propios. No son requisitos visuales de esta revisión de lectura.
5. **Una presentación, documentación por necesidad.** README para entender y empezar; manual para operar; evidencia fechada para revisar ingeniería. Los prototipos históricos permanecen fuera de producción.

## Cómo se decidirá V5.7

- Congelar tareas y rúbrica antes de medir. Registrar modelo/digest, entrada, perfil, orden, caché, hardware y llamadas; limitar el experimento antes de comenzar.
- Valorar por separado detección determinista, corrección factual de los comentarios, acciones específicas y omisiones. No usar el verificador que genera el informe como juez de su utilidad.
- Ensayo formativo con cinco participantes externos y datos sintéticos: seleccionar fuente, entender el coste, detener, recuperar y explicar el resultado. Objetivo propuesto: cuatro de cinco completan las tareas críticas sin ayuda; no equivale a una estimación estadística de mercado.
- No imponer tres pasadas. A lo sumo tres iteraciones sólo cuando exista una regla de mejora y parada medible; **iteraciones y tres intentos de proyecto son conceptos distintos**.

## Abierto antes de V6

El timeout histórico de arranque de Ollama conserva su investigación pendiente; no se resuelve aumentando plazos sin causa. Las dos sondas de nombre accesible siguen fuera del analizador actual. Faltan evaluación humana, comparación de utilidad de roles, consumo prolongado/GPU y distribución firmada. [Estado técnico](docs/V5_6_REVIEW.md).

Después de V6, la dirección hacia V10 es ampliar tareas, skills, memoria y distribución entre sistemas sobre estas mismas puertas. Esa visión no se presenta como funciones disponibles ni como fechas de lanzamiento.
