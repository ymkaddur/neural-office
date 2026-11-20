# V5.20 · núcleo local y referencia de recursos en Windows

La rama de ingeniería parte de V5.14 `e10a8b6`. Se comprobaron el núcleo Python, la lectura real de cinco formatos del ejemplo y una consulta individual de Ollama lanzada por PowerShell. La topología de tres rondas tiene aquí una entrada de planificación. La ejecución por rondas, la medición del equipo completo y la prueba del ejecutable instalado tienen sus propios hitos en la [hoja de ruta](../ROADMAP.md).

## Qué cambió en un encargo real

El ejemplo del portal exige 24 h en la especificación y declara 48 h en el manifiesto. Se eligieron 48 h, se abrió de nuevo el almacén y se consultó con los cinco archivos seleccionados. El núcleo siguió devolviendo la misma decisión junto al identificador del informe original. También se repitió por el servicio que utiliza el escritorio, cerrando y abriendo dos instancias sobre la misma base. El servicio devolvió «Se eligieron 48 h» y «2 páginas». La instantánea final del proyecto confirmó cero intentos consumidos.

| Encargo o fallo inyectado | Conducta verificada |
|---|---|
| «¿Con cuál nos quedamos?» | Recupera la elección del hilo. Comprueba propietario, longitud, tipo y huella de los archivos. |
| «¿Qué decidimos y cuántas páginas tiene el PDF?» | Entrega la decisión de 48 h y las dos páginas del PDF. Cada resultado conserva su procedencia. |
| «¿Qué hay dentro del ZIP?» | Responde con los cuatro archivos del paquete en el propio informe y conserva la fuente ZIP. En paquetes más grandes muestra hasta seis nombres con vista previa. |
| «¿Cuál es el plazo de devolución?» o «¿Qué decidimos sobre el precio?» | Devuelve que falta concretar esa comprobación. El plazo de primera respuesta pertenece a otro concepto. |
| Cambiar una captura, seleccionar cuatro de los cinco archivos o consultar desde otro proyecto | La alteración de bytes se rechaza. Una selección distinta carece de esa decisión. El proyecto ajeno carece de acceso a los adjuntos. |
| Reabrir un hallazgo V5.14 con las mismas fuentes y hechos | Conserva el identificador y la decisión humana. Una consulta distinta puede generar un informe nuevo. |

El lector local responde a un conjunto delimitado de operaciones. El reconocimiento de frases sigue siendo determinista y admite abstenciones. Las pruebas de paráfrasis cubren los ejemplos concretos, sin pretender resolver lenguaje abierto.

### Coste de recordar una decisión

Mismo equipo, mismo intérprete privado Python 3.12.10, mismo generador de archivos, una ronda de calentamiento y siete consultas medidas por versión. En cada muestra se abrió un almacén nuevo sobre la misma base del ensayo, se comprobó el origen y contenido de la respuesta y se contó cada invocación del decodificador real. Las capturas proceden del ejemplo sintético público. [Instrumento](../tools/measure_decision_recall.py).

| Versión | Milisegundos por muestra | Mediana | Decodificadores por consulta | Llamadas e intentos |
|---|---|---:|---:|---:|
| V5.14 publicada | 791,21 · 931,06 · 876,03 · 906,81 · 924,54 · 903,67 · 1098,73 | **906,81 ms** | 5 | 0 |
| V5.20 | 12,61 · 11,49 · 10,38 · 8,75 · 8,48 · 8,40 · 8,33 | **8,75 ms** | 0 | 0 |

Una primera serie de V5.20 dio 9,93 ms de mediana. La mejora medida corresponde a recordar una elección ya guardada. Generar un informe por primera vez sigue requiriendo los lectores pertinentes, y las operaciones mixtas aún pueden abrir lectores innecesarios.

## Un agente real en la terminal de PowerShell

Windows 11, compilación 26200, Intel Core Ultra 7 255HX con 20 procesadores lógicos. PowerShell 7.6.9 ejecutó `ollama run qwen2.5:0.5b` sobre Ollama 0.40.16. El modelo local tenía contexto de 4096 y Ollama declaró 461,2 MiB de modelo en VRAM. Se consultó un servicio propio, se verificó el proceso que poseía el puerto y se cerró únicamente ese grupo. El grupo incluyó PowerShell, CLI, servidor y runner. [Instrumento](../tools/measure_ollama_terminal.py) · [Identidad, preguntas, respuestas y medidas brutas](evidence/V5_20_TERMINAL.json).

| Estado inicial | Pared | CPU total | Pico CPU en 1 s, núcleos equivalentes | Pico de RAM muestreado, suma WS | Pico de memoria privada comprometida |
|---|---:|---:|---:|---:|---:|
| Modelo sin cargar, servidor ya listo · 1 ejecución | 2,471 s | 2,562 s | 1,119 | 771,9 MiB | 1543,3 MiB |
| Modelo residente · mediana de 3 ejecuciones | 0,790 s | 0,922 s | 0,847 | 771,8 MiB | 1543,0 MiB |

El cronómetro de entrega y la CPU acumulada terminaron cuando salió la terminal. Las consultas cortas siguieron bajo observación hasta completar una ventana real de al menos un segundo para calcular el pico. Muestras aproximadas cada 100 ms. Los cuatro registros contienen contadores completos. La caché del sistema operativo se mantuvo. Las páginas compartidas pueden contarse varias veces en la suma de conjuntos de trabajo. La cifra que Ollama atribuye al modelo mide residencia declarada y deja abierta la medición de utilización de GPU de todo el proceso. [Consulta de modelos residentes en Ollama](https://docs.ollama.com/api/ps).

**Utilidad.** El encargo pedía indicar que el PDF dice 24 h, el JSON dice 48 h y los valores discrepan. En una de las cuatro salidas aparecen ambas cifras, pero la formulación confunde qué representan. Las otras tres omiten al menos una cifra. Ninguna cumple los tres criterios de la tarea en esa serie. El texto exacto de las cuatro salidas acompaña las medidas. Con un modelo pequeño, repetir una consulta barata puede repetir también el error.

**Qué se puede concluir sobre 1,50×.** Existe una primera referencia instrumental para medir el denominador. Faltan un perfil individual que alcance la calidad fijada, una muestra pareada por tarea y la ejecución completa del Director con seis especialistas. La prueba histórica de V5.8 comparaba dos perfiles del escritorio configurados para CPU. Los datos nuevos corresponden a una terminal con pesos en GPU. Dividir un resultado por el otro daría un cociente sin interpretación. [Protocolo y condiciones del límite](../ROADMAP.md).

## Reproducir

Desde la raíz de esta rama en Windows, usa el intérprete con las dependencias del lector, Pillow y pypdfium2. La sonda de terminal usa un intérprete de pruebas con pywin32 y psutil. El nombre del modelo debe corresponder a pesos ya instalados. El parámetro `--output` de la sonda crea un archivo nuevo.

```powershell
python -B -m unittest discover -s tests
python -B -m neural_office office-plan --objective "Revisar la entrega del portal"
python -B tools/measure_decision_recall.py --checkout . --samples 7
python -B tools/measure_ollama_terminal.py --model qwen2.5:0.5b --warm 3
```

**Pruebas del núcleo en Windows.** 251 pruebas pasaron, incluidas recuperación, cancelación, continuidad, autoridad, comprobación de archivos y las regresiones de este corte. La CLI describe tres rondas, seis especialistas por ronda y 22 pasos ordenados por dependencias. En una carpeta temporal vacía, comprobar el plan dejó cero ficheros de estado, reservas y llamadas. El encargo de tres rondas supera el límite de doce llamadas del protocolo de ejecución heredado. [Regresiones de V5.20](../tests/test_v520_local.py) · [Límite nativo de V5.14](V5_14_LOCAL.md).
