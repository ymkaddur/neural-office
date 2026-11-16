# Neural Office · V5.2

Una oficina de agentes locales, en desarrollo. **V5.2 es una vista previa técnica para Windows**: permite seleccionar un HTML, un modelo local instalado y un recorrido de uno, tres o siete roles. Produce un informe estático con evidencia persistida y comentarios del modelo claramente identificados como no certificados.

La meta sigue siendo descargar la aplicación, elegir un modelo local y comenzar. Esta versión todavía requiere Python 3.12 y Ollama instalados. No es el instalador autónomo de V10 ni una migración de las oficinas históricas.

## Probar el piloto

1. Descarga el código de este repositorio y extrae la carpeta.
2. Ten disponibles Python 3.12 con Tk y Ollama, con un modelo local ya instalado.
3. Desde la carpeta extraída, ejecuta:

```powershell
py -3.12 -B -m neural_office gui
```

También se incluye `Start-NeuralOffice.ps1`. El lanzador no instala componentes ni cambia la política de PowerShell. Si tu política no permite ejecutar el script, utiliza directamente el comando anterior.

En la ventana, elige el modelo y pulsa «Usar ejemplo» o selecciona tu HTML. «Autorizar y auditar» consume un intento. «Detener» solicita cancelar y espera la terminación comprobada. «Ver presupuesto» y «Ver último informe» consultan el estado persistido.

Se admite una inferencia administrada simultánea por ledger, como máximo dos proyectos activos y tres intentos por proyecto. Los fallos y cancelaciones cuentan. Reiniciar no devuelve presupuesto. Un informe aceptado acredita las comprobaciones estáticas descritas; los comentarios del modelo siguen requiriendo revisión humana.

La entrada es HTML local UTF-8, hasta 256 KiB. Se comprueban idioma, título, atributos `alt` y posibles controles sin etiqueta. No se ejecutan scripts del HTML, no se navega por sus enlaces y no se modifica el archivo original. Esto no certifica WCAG, seguridad ni comportamiento de una web completa.

## Estado probado

- Suite pública de 60 pruebas, con fixtures y comprobaciones nativas Windows.
- Ejecuciones locales reales de uno, tres y siete roles sobre el mismo ejemplo.
- Cancelación después de un POST real, terminación del árbol propio y recuperación tras caída del controlador.
- Lectura del informe y conservación del presupuesto después de reiniciar la interfaz.
- Cinco correcciones puntuales del V5 histórico, documentadas con diff y hashes.

El modelo de ensayo usa un alias personalizado que menciona DeepSeek/64k, pero su metadata informa `qwen35`, 9B, Q4_K_M. El perfil ejecutado y observado fue **CPU, contexto 8.192**, con salida acotada. Esto no certifica todos los modelos ni contexto de 64k. Los pesos no se distribuyen y su licencia no se presume por el alias.

Los [recibos](docs/evidence/V5_2_EXECUTION.json) y el [diario de revisión](docs/V5_2_REVIEW_REPORT.md) conservan también los fallos: un timeout de arranque sin causa demostrada y una respuesta de red intermitente en el gateway histórico. Una corrida posterior exitosa no los declara resueltos.

## Desarrollo y límites

```powershell
py -3.12 -B -m unittest discover -s tests -v
py -3.12 -B -m neural_office models
py -3.12 -B -m neural_office status
```

Los tests no requieren un modelo ni credenciales. `status` no crea una base inexistente. La aplicación guarda estado, entradas y respuestas localmente; no cifra esos archivos. No compartas su carpeta de datos como si fuera código publicable.

V5.2 no importa historiales V1/V4/V5. No uses un ledger nuevo para resetear cuotas de proyectos históricos. OpenCode y otros clientes quedan fuera del dominio de exclusión de este piloto. No se incluyen todavía memoria aprendida, promoción de skills, herramientas generales, aplicación de parches ni integración de las 69 reglas de V5.1 en su totalidad.

Los documentos actuales son el [contrato implementado](docs/V5_2_AUTHORITY_AND_COUNTERS.md), la [matriz de los 45 casos](docs/V5_2_INTEGRATION_AND_ACCEPTANCE.md) y el [expediente de procedencia](docs/V5_2_PROVENANCE.md). El [diseño V5.1](docs/V5_1_INTEGRATION_SPEC.md) y su [registro de revisión](docs/V5_1_REVIEW_REPORT.md) se conservan como historia fechada, con sus pendientes de entonces. La [hoja de ruta](ROADMAP.md) fija el avance hasta V10.

## Licencia y procedencia

[MIT](LICENSE) para las aportaciones propias que el promotor pueda licenciar. Desarrollo asistido por IA bajo supervisión; CrewAI fue una base conceptual e histórica, pero no es una dependencia del núcleo V5.2. Consulta [LICENSING.md](LICENSING.md) para el alcance y los derechos de terceros. La licencia abierta no equivale a blindaje jurídico, certificación de seguridad ni disponibilidad general del producto.
