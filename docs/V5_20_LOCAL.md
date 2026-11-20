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
| Primera base V5.20 (`89baf2e`) | 12,61 · 11,49 · 10,38 · 8,75 · 8,48 · 8,40 · 8,33 | **8,75 ms** | 0 | 0 |

Una primera serie de V5.20 dio 9,93 ms de mediana. La mejora medida en esa serie corresponde a recordar una elección ya guardada. En la base `89baf2e`, una pregunta compuesta aún abría cinco lectores. La siguiente medición compara esa base con la revisión del núcleo sobre encargos completos.

### Coste de siete encargos después de limitar los lectores

Se compararon `89baf2e` y `5656bc9` en el mismo Windows. Cada una de las siete tareas se ejecutó diez veces por revisión, alternando el orden de las revisiones y rotando las tareas. Cada muestra abrió un proceso nuevo del servicio de escritorio. La captura inicial y la decisión de partida se prepararon fuera del intervalo. La sonda comprobó respuestas, citas, procedencia y saldo. Las 140 ejecuciones terminaron con la respuesta esperada, cero llamadas al modelo y cero intentos. El conjunto pasó de 210 aperturas de lectores a 50. [Resultados de las 140 ejecuciones](evidence/V5_20_INSPECTION.json) · [Instrumento y criterios de aceptación](../tools/measure_v520_inspection.py).

Cada celda muestra la mediana de la base y la mediana de la revisión, en ese orden. Los lectores cuentan procesos abiertos por encargo. WS suma los conjuntos de trabajo del proceso del servicio y sus descendientes. La última columna recoge el pico de compromiso privado del grupo que registró Windows durante toda la vida de ese proceso.

| Encargo y archivos seleccionados | Lectores | Tiempo de respuesta (ms) | CPU acumulada (s) | Pico WS (MiB) | Pico comprometido (MiB) |
|---|---:|---:|---:|---:|---:|
| Contrastar plazo de PDF y JSON entre cinco archivos | 5 → 2 | 961 → 655 | 0,859 → 0,586 | 87,4 → 85,9 | 43,0 → 42,5 |
| Recuperar la decisión y contar páginas entre cinco archivos | 5 → 1 | 1040 → 479 | 0,875 → 0,430 | 86,2 → 86,4 | 42,8 → 42,7 |
| Inventariar el ZIP entre cinco archivos | 5 → 1 | 981 → 153 | 0,875 → 0,117 | 87,3 → 72,8 | 43,0 → 42,5 |
| Preguntar por un plazo de devolución ausente | 5 → 0 | 944 → 11 | 0,859 → <0,016 | 87,1 → 40,8 | 42,9 → 20,2 |
| Recordar la decisión con los cinco archivos | 0 → 0 | 13,3 → 11,4 | <0,016 en ambas | 40,8 → 40,9 | 20,2 → 20,1 |
| Medir un JPEG de 3000 × 2000 con giro EXIF | 1 → 1 | 175,6 → 173,4 | 0,156 → 0,156 | 76,8 → 76,6 | 83,6 → 60,5 |
| Comprobar la identidad de un adjunto de 8 MiB sin decisión asociada | 0 → 0 | 23,6 → 19,6 | 0,023 → 0,016 | 40,8 → 40,8 | 35,7 → 20,2 |

El proceso del lector PDF sigue dominando buena parte del coste de contar las páginas. En ese encargo el pico WS incluso subió 0,2 MiB. Para el JPEG, validar los píxeles y aplicar la orientación al cálculo de dimensiones redujo el compromiso de memoria. El tiempo y la CPU fueron similares. Las 1204 muestras de 50 ms tuvieron contadores completos. El muestreo puede perder picos entre observaciones. El menor incremento positivo de CPU observado fue de 15,625 ms. Una mediana por debajo de esa resolución deja abierta la cantidad de CPU utilizada.

**Qué protege la mejora.** Los archivos ajenos a la pregunta siguen pasando por una comprobación de identidad, longitud, tipo y SHA-256. Los datos grandes se verifican en bloques de 256 KiB. Los lectores que se necesitan conservan sus procesos aislados. Contar páginas solo abre el índice del PDF. Pedir además la comparación usa una sola lectura completa del PDF. Las pruebas cubren ocho orientaciones de imagen, un JPEG truncado, una modificación en el último byte de una captura y una cancelación entre bloques.

**Continuidad de una decisión real.** Sobre una copia de una base creada por `89baf2e`, el núcleo recuperó los cuatro informes históricos. Al repetir la comparación, conservó su identificador y la decisión de 48 h. Al repetir la pregunta compuesta, guardó un informe con el nuevo método de conteo y el mismo origen de la decisión. Cambiar la elección a 24 h, cerrar y reabrir devolvió 24 h con la cita del PDF y un saldo intacto. En otra base temporal se probó también el protocolo de escritorio mediante dos procesos reales de `desktop_stdio`, desde la captura del portal hasta la recuperación tras reiniciar.

## Un agente real en la terminal de PowerShell

Windows 11, compilación 26200, Intel Core Ultra 7 255HX con 20 procesadores lógicos. PowerShell 7.6.9 ejecutó `ollama run qwen2.5:0.5b` sobre Ollama 0.40.16. El modelo local tenía contexto de 4096 y Ollama declaró 461,2 MiB de modelo en VRAM. Se consultó un servicio propio, se verificó el proceso que poseía el puerto y se cerró únicamente ese grupo. El grupo incluyó PowerShell, CLI, servidor y runner. [Instrumento](../tools/measure_ollama_terminal.py) · [Identidad, preguntas, respuestas y medidas brutas](evidence/V5_20_TERMINAL.json).

| Estado inicial | Pared | CPU total | Pico CPU en 1 s, núcleos equivalentes | Pico de RAM muestreado, suma WS | Pico de memoria privada comprometida |
|---|---:|---:|---:|---:|---:|
| Modelo sin cargar, servidor ya listo · 1 ejecución | 2,471 s | 2,562 s | 1,119 | 771,9 MiB | 1543,3 MiB |
| Modelo residente · mediana de 3 ejecuciones | 0,790 s | 0,922 s | 0,847 | 771,8 MiB | 1543,0 MiB |

El cronómetro de entrega y la CPU acumulada terminaron cuando salió la terminal. Las consultas cortas siguieron bajo observación hasta completar una ventana real de al menos un segundo para calcular el pico. Muestras aproximadas cada 100 ms. Los cuatro registros contienen contadores completos. La caché del sistema operativo se mantuvo. Las páginas compartidas pueden contarse varias veces en la suma de conjuntos de trabajo. La cifra que Ollama atribuye al modelo mide residencia declarada y deja abierta la medición de utilización de GPU de todo el proceso. [Consulta de modelos residentes en Ollama](https://docs.ollama.com/api/ps).

**Utilidad.** El encargo pedía indicar que el PDF dice 24 h, el JSON dice 48 h y los valores discrepan. En una de las cuatro salidas aparecen ambas cifras, pero la formulación confunde qué representan. Las otras tres omiten al menos una cifra. Ninguna cumple los tres criterios de la tarea en esa serie. El texto exacto de las cuatro salidas acompaña las medidas. Con un modelo pequeño, repetir una consulta barata puede repetir también el error.

### Referencia individual con una respuesta correcta

Se repitió exactamente la misma pregunta en la terminal con `qwen3.5:9b`, cuantización Q4_K_M, desactivando la generación de pensamiento mediante la opción de Ollama. Se usaron los pesos ya instalados. El identificador del modelo y la huella de la pregunta acompañan las respuestas íntegras. En las cuatro, el modelo atribuyó 24 h al PDF y 48 h al JSON e indicó que discrepan. Son cuatro repeticiones de un mismo encargo. [Resultados individuales y medición de procesos](evidence/V5_20_TERMINAL_9B.json).

| Estado al lanzar la terminal | Tiempo hasta terminar | CPU acumulada | Pico CPU en 1 s, núcleos equivalentes | Pico de RAM, suma WS | Pico privado comprometido |
|---|---:|---:|---:|---:|---:|
| Modelo sin cargar, servidor listo · una ejecución | 12,848 s | 30,766 s | 10,020 | 1467,3 MiB | 8441,4 MiB |
| Modelo residente · mediana de tres ejecuciones | 1,747 s | 13,000 s | 9,871 | 1565,7 MiB | 8500,4 MiB |

Los cuatro registros de procesos estuvieron completos. Ollama declaró contexto de 4096 y 5205,6 MiB de pesos residentes en VRAM. El compromiso privado y el conjunto de trabajo miden cosas distintas.

**Estado del objetivo de 1,50×.** Ya hay una referencia individual que cumple el criterio de utilidad de este encargo. Para conocer el cociente faltan la ejecución del Director y seis especialistas sobre las mismas tareas, con las mismas condiciones de cómputo y calidad, y los pares exigidos por el protocolo. La prueba de V5.8 comparaba dos perfiles de escritorio configurados para CPU. Las lecturas de la terminal de V5.20 incluyen pesos en GPU. [Protocolo y condiciones del límite](../ROADMAP.md).

## Reproducir

Desde la raíz de esta rama en Windows, usa el intérprete con las dependencias del lector, Pillow y pypdfium2. La sonda de terminal usa un intérprete de pruebas con pywin32 y psutil. El nombre del modelo debe corresponder a pesos ya instalados. El parámetro `--output` de la sonda crea un archivo nuevo.

```powershell
python -B -m unittest discover -s tests
python -B -m neural_office office-plan --objective "Revisar la entrega del portal"
python -B tools/measure_decision_recall.py --checkout . --samples 7
python -B tools/measure_ollama_terminal.py --model qwen2.5:0.5b --warm 3
python -B tools/measure_ollama_terminal.py --model qwen3.5:9b --no-thinking --warm 3
```

Para repetir la comparación de lectores, el directorio indicado por `--baseline` debe contener la revisión anterior. El intérprete que lanza la sonda necesita pywin32. `--reader` es el intérprete del núcleo que tiene instalados los lectores de escritorio.

```powershell
git worktree add --detach ../neural-office-base-v520 89baf2e
$readerPython = python -c "import sys, PIL, pypdfium2; print(sys.executable)"
py -3.12 -B tools/measure_v520_inspection.py --baseline ../neural-office-base-v520 --reader $readerPython --pairs 10 --output comparacion-v520.json
```

**Pruebas del núcleo en Windows.** Pasaron 255 pruebas, incluidas recuperación, cancelación, continuidad, autoridad, comprobación de archivos y las regresiones de este corte. La CLI describe tres rondas, seis especialistas por ronda y 22 pasos ordenados por dependencias. En una carpeta temporal vacía, comprobar el plan dejó cero ficheros de estado, reservas y llamadas. El encargo de tres rondas supera el límite de doce llamadas del protocolo de ejecución heredado. [Regresiones de V5.20](../tests/test_v520_local.py) · [Límite nativo de V5.14](V5_14_LOCAL.md).
