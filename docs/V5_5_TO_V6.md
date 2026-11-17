# De V5.5 a V6: una oficina que termina un encargo

Fecha: 17 de noviembre de 2026. Este documento actualiza el tramo corto de [ROADMAP](../ROADMAP.md). Las capacidades futuras son propuestas, no funciones presentes. La evidencia de ejecución se mantiene en [la entrega V5.5](V5_5_VERIFICATION.md); la [investigación](V5_5_RESEARCH.md) conserva fuentes y contraejemplos.

## Qué aprendimos y qué hicimos mal

**OBSERVADO:** pasamos por varias escenas visuales sin cerrar antes el recorrido nativo. Una vista convincente podía convivir con un motor desconectado. Al conectarlos aparecieron diferencias reales: cancelar no siempre conciliaba el historial, paginar borraba el contexto de presupuesto y el contrato nuevo rechazaba nombres históricos válidos. Compilar tampoco aseguró que el ejecutable incorporase el frontend. [Reconstrucción y regresiones](V5_5_VERIFICATION.md).

**INFERIDO:** demasiadas entregas se describieron por componentes existentes y cantidad de pruebas, cuando la unidad útil es el trabajo terminado por una persona. Mantener prototipos rotulados como ejemplos fue necesario, pero no convirtió esas escenas en una oficina funcional. La siguiente fase necesita menos promesas simultáneas y una aceptación más exigente de cada recorrido.

**OBSERVADO en fuentes, no consenso universal:** usuarios discrepan sobre densidad y paneles; coinciden sólo parcialmente en sus dificultades. Las quejas concretas sobre contexto de aprobación, cancelación, historial y consumo son mejores candidatos a prueba que «hazlo como Claude». Los materiales universitarios refuerzan tareas y criterios previos, no un estilo visual. [Feedback F01–F16](research/V5_5_FEEDBACK.json), [materiales](research/V5_5_UNIVERSITIES.json).

**DESCONOCIDO:** que nuestra propuesta sea preferida, que varios roles mejoren calidad o que el modelo pequeño usado para integración resuelva encargos complejos. No se declara superioridad de mercado, ausencia de errores ni cinco vulnerabilidades graves por cumplir una cifra.

## Identidad propuesta y reglas de producto

**HIPÓTESIS de identidad:** «Tu encargo, una entrega que puedes comprobar». Neural Office conserva la metáfora de oficina mediante un Director, responsabilidades y traspasos comprensibles. Su diferencia debe sentirse al saber qué se va a usar, qué está ocurriendo, qué queda por decidir y cómo recuperar una entrega.

1. **Un lugar para encargar, otro para revisar.** La conversación orienta el trabajo; el resultado ocupa una superficie estable con fuentes y versiones. No se oculta el resultado dentro de un registro interminable.
2. **La autoridad se ve antes del efecto.** Aprobación específica con fuente capturada, modelo, alcance y consumo. Cerrar el diálogo no autoriza. El núcleo vuelve a comprobar la reserva.
3. **Estados verdaderos.** Preparando, trabajando, detención pendiente, detenido, fallo, recuperable y entrega disponible deben tener consecuencias distintas. Una solicitud de parada no se presenta como terminación.
4. **Detalle a demanda.** Estado y presupuesto siempre comprensibles; hashes, eventos y perfiles avanzados inspeccionables. No exigir entender IPC o SQLite para elegir un archivo.
5. **El sistema se adapta a la tarea y la ventana.** Tema oscuro cuidado, contraste y tipografía legible; modo claro; divisores ajustables y una columna cuando corresponda. La densidad se valida, no se impone como identidad.
6. **La oficina recuerda sin ejecutar de nuevo.** Reabrir conserva identidad, informe y consumo. Reintentar requiere una decisión nueva y explícita cuando proceda; un ACK perdido exige conciliación, no otro gasto silencioso.
7. **Una llamada debe justificar su coste.** Un rol por defecto, modelo compartido en serie, fuentes explícitas y contexto acotado. Roles adicionales sólo si mejoran la entrega en un corpus independiente.

Estas reglas son una dirección propia, no autorización para copiar marcas, tipografía propietaria, código o activos de otros productos. Los colores y divisores son secundarios a los contratos anteriores.

## Secuencia de entrega

| Hito | Qué obtiene la persona | Cambio acotado | Puerta de salida y evidencia |
|---|---|---|---|
| **V5.5 — recorrido conectado** | Elegir HTML/modelo, aprobar, ejecutar, detener y recuperar desde el escritorio | Tauri con comando restringido, sidecar Python, fuente congelada, identidad durable, informe por fragmentos verificados; un rol inicial | UI nativa → selector → aprobación → modelo real → informe → cierre/reapertura; pruebas de duplicación y respuesta perdida; recursos por componente. Windows local puede bloquear el binario no firmado; no se cierra aceptación visual ni distribución por compilar en CI |
| **V5.6 — una entrega que merece el coste** | Primer resultado útil y revisión breve, sin vueltas vacías | Rúbrica y corpus HTML; comparar comprobación sin LLM, un rol y revisión limitada. Nombres de proyecto/fuente comprensibles; edición de encargo sin pérdida de borrador | Conjunto de evaluación separado de los ejemplos usados para desarrollar. Exactitud de hallazgos, utilidad de prioridades y errores contra oráculo independiente. Hasta tres iteraciones como máximo configurable, salida antes por presupuesto o falta de progreso; no confundir iteraciones con intentos |
| **V5.7 — una skill y memoria inspeccionables** | Reutilizar un procedimiento y contexto de un proyecto sin configuración oculta | Skill declarativa de solo lectura; memoria mínima con fuente, versión, ámbito, vigencia y eliminación | Mostrar qué se incorporará al contexto; ensayos de instrucciones hostiles, fuente revocada, aislamiento entre proyectos, actualización interrumpida y rollback. Nada generado se promociona automáticamente |
| **V5.8 — coste menor demostrado** | Perfil adecuado al equipo, menos espera y consumo para la misma calidad | Medir carga, consulta de ownership, prefill, generación, render y cierre; optimizar una frontera por experimento; GPU como perfil separado | Comparación pareada con misma tarea, modelo/digest, estado de caché y contexto. No regresión de calidad ni autoridad. RAM residente, compromiso, CPU acumulada, VRAM, latencia y errores separados. No eliminar verificaciones para mejorar una gráfica |
| **V5.9 — beta recuperable y distribuible** | Usar y actualizar una versión de prueba con un camino claro ante fallos | Pruebas humanas, teclado/lector, sesiones largas, cierres, copia/restauración y actualización. Probar firma/distribución en equipos limpios | Ningún defecto crítico abierto en tareas declaradas; resultados de ciclos y restauraciones, incluidos fallos; binario y dependencias identificados. R13 resuelto causalmente o contenido operacionalmente con limitación visible. La firma se adelanta por el bloqueo real observado; no se difiere a V10 |
| **V6 — dos encargos completos** | Revisar HTML y sintetizar TXT/Markdown seleccionados con citas verificables | Director con plan breve, pasos acotados, fuentes, versiones y entrega; skill/memoria mínima ya evaluadas | Ambos recorridos en escritorio real, sin inferencia simulada; verificador independiente adecuado a cada tarea, presupuestos y recuperación; aceptación humana y perfil de recursos declarado. No se anuncia una agencia universal ni autonomía sin límites |

No se fijan fechas sin una capacidad de ejecución y una línea base estables. V7–V10 siguen siendo coordinación evaluada, memoria más amplia, resiliencia y distribución sencilla; se actualizan al cerrar estas puertas.

## Plan concreto de aceptación de UI

**PROPUESTO para G-UI, aún no ejecutado con personas externas:** cinco participantes iniciales de perfiles distintos, incluyendo alguien sin experiencia en agentes y alguien que trabaje a diario con un asistente de código. Es un estudio formativo; no calcula representatividad ni cuota de mercado. Obtener consentimiento y usar archivos sintéticos, sin capturar cuentas o contenido privado.

Mismas tareas en una ventana horizontal y otra estrecha/vertical: preparar el encargo, explicar qué aprobará, encontrar su consumo, detener, reconocer la terminación, reabrir y localizar fuente/resultado. Comparar la versión compacta con detalle desplegable, no dos motores distintos. Registrar tiempo, primer clic, errores, ayudas y comprensión; preguntar preferencia al final. Un éxito con asistencia se cuenta por separado.

Puertas de aceptación propuestas: ninguna ejecución involuntaria; nadie confunde parada pendiente con terminada ni una fixture con trabajo real; ningún borrador perdido en las transiciones probadas; fuente y siguiente acción localizables sin ayuda por al menos cuatro de cinco participantes. El número pequeño sirve para detectar fallos y repetir el ciclo, no para probar estadísticamente que todo el producto es usable. Documentar excepciones, no borrar participantes incómodos.

Teclado y accesibilidad son recorridos específicos: Ctrl/Meta+Enter con IME, Escape según capa, foco visible tras modal, tabulación sin trampas, pestañas y divisores con teclado, anuncios sin saturación y lector de pantalla en el paquete real. Scanner automático, inspección de DOM y opinión del creador aportan evidencia parcial distinta.

## Seguridad, idempotencia y límites

**Contrato:** una misma identidad durable con el mismo contenido devuelve la misma reserva; cambiar contenido con la misma identidad produce conflicto. Esto no promete exactamente una vez para cualquier herramienta externa futura. La autoridad del ledger, el cierre del proceso, los testigos de continuidad y la idempotencia de futuros efectos se prueban por separado.

**Prioridad de amenazas:** renderer o contenido hostil intentando ampliar autoridad; fuente/ruta mutable; respuesta tardía después de cancelar; salida sin límites; pérdida de respuesta o corrupción de estado; restauración que reponga presupuesto; dependencia o artefacto distinto del revisado. Cada candidato requiere actor, precondición, propiedad y reproducción. El Job Object controla procesos propios, no es sandbox de disco o red. El usuario local con control de todos los archivos/testigos queda fuera de una garantía antimanipulación absoluta. [SECURITY](../SECURITY.md).

V5.5 publica controles y regresiones de esas fronteras; no transforma pruebas favorables en ausencia universal de vulnerabilidades. La UI no representa razonamiento privado del modelo: muestra acciones, entradas, estados y resultados observables.

## Optimización sin cifras decorativas

La prueba real V5.5 con Qwen2.5 0.5B sirve para integración: no demuestra calidad comparable a un modelo grande ni una mejora frente a V5.3. El primer arranque falló y el siguiente pasó; ambos cuentan. Las cifras de backend excluyen webview/controlador y no se suman a muestras tomadas en otro momento para inventar un pico total.

En cada fase conservar: hardware, versiones y hashes; tarea y rúbrica; número de llamadas reales; tokens observados frente a límites solicitados; caché fría/caliente; consumo por componente y total simultáneo cuando esté medido. Si una lectura falla, desconocido. Si el backend no transmite en streaming, no inventar TTFT. Presupuestos numéricos de producto se ratifican con esta base y el equipo objetivo, no con tamaños del bundle.

El primer candidato de ahorro es **evitar trabajo sin valor**: los cuatro hallazgos estáticos no necesitan un LLM. El modelo debe justificar prioridades, claridad o una tarea adicional; si no mejora la rúbrica, el modo sin modelo debe seguir disponible en el diseño de V5.6. Mantener un modelo cargado entre intentos requiere propiedad y cancelación verificadas, no sólo aumentar keep_alive.

## Próxima acción y confianza

Cerrar la evidencia nativa V5.5, revisar su entrega visual y aislar el arranque R13 con la siguiente traza discriminante. Después fijar el corpus y la rúbrica V5.6 antes de implementar loops. Las [skills de desarrollo](../skills/README.md) codifican los errores y métodos, sin añadir una capacidad de aprendizaje autónomo al producto.

Confianza de ingeniería **90% en la secuencia propuesta**, no probabilidad de éxito comercial o ausencia de errores. La suposición crítica es que las dos tareas acotadas resuelvan una necesidad real; el estudio de uso y la comparación con una solución sin modelo pueden invalidarla y cambiar prioridades.
