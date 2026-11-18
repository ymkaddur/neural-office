# V5.8 · cuánto cuesta una revisión en Windows

**Decisión.** Mantener «Comprobar HTML» como entrada y la consulta al Director como opción explícita. En seis documentos, el análisis estático repitió la revisión en una mediana de 12,6 ms. Un rol tardó 11,24 s y tres roles, 18,96 s. Los comentarios añadidos coincidieron con los ya calificados para esas mismas tareas. Ninguno añadió una acción que superase la rúbrica. [Protocolo previo](V5_8_RESOURCE_PROTOCOL.md) · [Datos por documento](evidence/V5_8_RESOURCES.json).

## Coste medido en el núcleo del escritorio

El cronómetro empieza al capturar el archivo y termina cuando la entrega está disponible en el servicio del escritorio. En un encargo asistido incluye vista previa, autorización, reserva, arranque de Ollama, generación, terminación del servidor y lectura del informe. Cada celda resume seis documentos. CPU es tiempo de procesador acumulado en todos los hilos. RAM es la mediana de los picos de suma de working sets muestreados para el árbol de procesos. La memoria privada comprometida incluye páginas que pueden estar fuera de RAM.

| Perfil | Estado al empezar | Pared, mediana (mín.–máx.) | CPU, mediana | Pico de RAM, mediana | Pico privado comprometido, mediana |
|---|---|---:|---:|---:|---:|
| Estático | Primera consulta | 18,9 ms (17,6–29,1 ms) | 15,6 ms | 25,3 MiB | 15,6 MiB |
| Estático | Repetición ordinaria | 12,6 ms (11,6–16,9 ms) | 7,8 ms | 25,2 MiB | 15,7 MiB |
| Director | Primera consulta | 13,28 s (11,12–36,58 s) | 18,52 s | 655,1 MiB | 1030,0 MiB |
| Director | Repetición ordinaria | 11,24 s (10,13–15,95 s) | 17,74 s | 671,9 MiB | 1079,4 MiB |
| Director, revisor e integrador | Primera consulta | 17,76 s (16,06–20,10 s) | 45,16 s | 803,2 MiB | 1022,0 MiB |
| Director, revisor e integrador | Repetición ordinaria | 18,96 s (18,33–22,15 s) | 46,07 s | 802,6 MiB | 1086,5 MiB |

La primera consulta usa un proceso y una oficina nuevos. Si se incluye la apertura del intérprete y de la oficina, las medianas de frío son 0,138 s, 13,393 s y 17,877 s, respectivamente. En la repetición ordinaria se conserva la sesión Python y se vuelve a autorizar el encargo. La medición de CPU de Windows avanza en saltos observables de 15,625 ms en estas pruebas cortas, por lo que la cifra estática es aproximada. Los ensayos conservaron la caché de archivos y la frecuencia dinámica del portátil.

Sobre los 20 procesadores lógicos, el Director utilizó de media el 6,6 % de la capacidad total durante la primera consulta y el 8,3 % durante la repetición. Con tres roles fueron el 12,9 % y el 12,6 %. Cada cifra es la mediana de seis promedios por encargo. El tiempo de CPU suma los hilos que trabajan en paralelo y puede superar el tiempo transcurrido.

## Cuánto consume la ventana que abre el usuario

Se abrió el ejecutable Tauri V5.8.0 por separado para cada perfil. En cada sesión se eligió el mismo [HTML con cuatro hallazgos](../examples/audit-sample.html) dos veces. Se cronometró desde «Comprobar HTML» o «Autorizar y ejecutar» hasta que el nuevo resultado apareció en el árbol de accesibilidad de Windows. El tiempo de elegir el archivo y rellenar el formulario queda fuera del intervalo. La búsqueda del resultado mediante UI Automation añade latencia de observación. Cada celda es una observación de escritorio sobre ese único archivo.

| Perfil | Tiempo frío / repetición | CPU frío / repetición | Pico de RAM frío / repetición | Pico privado comprometido frío / repetición |
|---|---:|---:|---:|---:|
| Estático | 2,20 / 2,15 s | 0,23 / 0,16 s | 536,5 / 546,1 MiB | 261,3 / 270,6 MiB |
| Director | 15,25 / 11,15 s | 22,16 / 19,50 s | 1244,7 / 1267,7 MiB | 1427,8 / 1273,6 MiB |
| Director, revisor e integrador | 19,62 / 19,03 s | 47,28 / 47,16 s | 1361,4 / 1372,0 MiB | 1305,2 / 1384,0 MiB |

Las tres ventanas estuvieron listas en 1,65–1,67 s. En los tres segundos de reposo inicial, el pico del conjunto de procesos fue de 455,8–460,1 MiB. Desde que la ventana estuvo lista hasta el primer botón de ejecución, incluido el uso del selector y del formulario, las medianas de WebView2 fueron 401,0–420,4 MiB. Para reducir la RAM de quien abre la aplicación, merece la pena medir qué aporta cada proceso de WebView2 en esa primera pantalla. La comprobación estática del núcleo, por sí sola, alcanzó unos 25 MiB.

Las seis entregas mostraron los cuatro hallazgos esperados. SQLite registró cuatro intentos asistidos y ocho llamadas reales en total. El árbol de procesos de cada ventana quedó vacío al cerrarla. El hash del ejecutable es `89bbcb48778df2ab82ab81d392a6152558b9c5a2a1fdfee8c288bac3393aaee3`. [Sonda de escritorio](../tools/measure_v58_desktop.py) · [Identidad del binario](evidence/V5_8_RECONNECTION.json).

## Qué cambia con los pesos ya cargados

En cada uno de los 36 intentos asistidos del estudio de núcleo se observó un servidor privado inicialmente vacío. En los encargos de tres roles, el segundo y el tercero sí encontraron el modelo residente. Para aislar la carga inicial, 12 intentos de control precargaron los pesos en su servidor ya autorizado mediante una petición vacía. Ollama confirmó la finalización por carga y el digest residente antes de la primera generación. [Precarga de Ollama](https://docs.ollama.com/faq#how-can-i-preload-a-model-into-ollama-to-get-faster-response-times) · [API de modelos residentes](https://docs.ollama.com/api/ps).

| Control con pesos residentes antes del Director | Pared total | CPU total | Pico de RAM | Tiempo de carga declarado en la primera generación | Efecto pareado sobre el total |
|---|---:|---:|---:|---:|---:|
| Un rol | 14,02 s | 19,59 s | 780,0 MiB | 4 ms | +2,28 s |
| Tres roles | 24,53 s | 47,24 s | 803,5 MiB | 5 ms | +4,43 s |

Los efectos son medianas de diferencias por documento frente a su repetición ordinaria. Desde la entrada al primer rol hasta la última respuesta, la precarga ahorró 0,98 s con un rol y 0,90 s con tres. En el recorrido completo tardó más en los seis pares de cada perfil. El coste incluye verificar el propietario de la operación adicional y realizar la precarga dentro del encargo. Un servidor compartido entre encargos tendría otro ciclo de vida y seguiría consumiendo memoria durante la espera. El experimento respalda conservar la política actual de cierre. [Instrumento](../tools/measure_v58.py).

## Calidad y cuota

Cada combinación de perfil y condición produjo **5 hallazgos correctos, 1 omisión y 0 falsos positivos** sobre las seis tareas. Las reglas aceptan un atributo `aria-labelledby` no vacío sin comprobar si existe el elemento al que apunta. Todos los perfiles omitieron esa referencia rota. El resultado muestra por qué conservar la ubicación de cada hallazgo importa al comparar recursos.

| Por una pasada de los seis documentos | Estático | Un rol | Tres roles |
|---|---:|---:|---:|
| Intentos / llamadas | 0 / 0 | 6 / 6 | 6 / 18 |
| Tokens de entrada / salida | 0 / 0 | 847 / 258 | 4602 / 814 |
| Orientación útil según la rúbrica, sobre 6 | 3,5 | 3,5 | 3,5 |
| Tareas con acción adicional fundada | 0 | 0 | 0 |
| Entregas con afirmaciones sin sustento | 0 | 2 | 2 |

Se cotejaron los hallazgos con las expectativas manuales. Para cada tarea y perfil coincidieron los párrafos completos y la orientación fija con las entregas calificadas en V5.7. Se aplicó aquella rúbrica a contenidos idénticos. Cada resultado del modelo procede de una nueva llamada a Ollama con su propio registro durable. Los 36 intentos asistidos completaron 72 generaciones y sus 36 servidores privados cerraron. Las 12 precargas se contabilizaron aparte. [Rúbrica y textos evaluados](evidence/V5_7_COMPARISON.json) · [Recalcular desde SQLite y las muestras de Windows](../tools/summarize_v58.py).

## Entorno y alcance

Windows 11 Home, compilación 26200, Intel Core Ultra 7 255HX, 20 núcleos y 20 procesadores lógicos, 32 GiB de RAM instalada, plan equilibrado y alimentación externa observada antes del estudio. Python 3.12.10, Ollama 0.40.16 y `qwen2.5:0.5b`, con digest fijado en el protocolo. Cada llamada acreditó contexto 8192 y cero bytes de pesos en VRAM. Los tiempos y los picos corresponden a este portátil y a estos seis HTML.

El equipo siguió disponible para sus otras aplicaciones. Una lectura posterior del catálogo compartido encontró otro modelo con un digest distinto al del estudio. El muestreo por árbol de procesos atribuye CPU y RAM a Neural Office. El cronómetro de pared también puede reflejar la competencia por recursos del equipo. El inicio de esa otra carga es desconocido.

El observador leyó los contadores del Job de Windows cada 100 ms y en los límites de cada intervalo. En los 48 recorridos se conservaron 6374 lecturas, incluida una con RAM ilegible por la salida de un proceso. Esa lectura se excluyó del pico de memoria. El mayor hueco entre lecturas fue 103,4 ms. Los picos de working set pueden contar páginas compartidas y omitir transitorios. La CPU del Job incluye el núcleo, Ollama y los procesos auxiliares de verificación. El perfil estático incluye la memoria de Python. Se conservó el caso más lento, 36,58 s para la primera consulta al Director, en las estadísticas.

## Repetir el estudio

Desde la raíz del repositorio, en Windows, se necesita Python 3.12, Ollama accesible en el puerto local de catálogo y el modelo identificado en el protocolo. La sonda del escritorio necesita además el ejecutable con el hash indicado, una sesión gráfica y un entorno de Python con las [dependencias de UI Automation](../tests/requirements-native-ci.txt). Los directorios de salida nuevos contienen las oficinas y las muestras brutas de esa repetición.

```powershell
$medicion = Join-Path $env:TEMP ('neural-office-v58-' + [guid]::NewGuid())
$serie = Join-Path $medicion 'serie'
$ventanas = Join-Path $medicion 'ventanas'
$exe = 'desktop/src-tauri/target/release/neural-office-desktop.exe'
py -3.12 -B -m tools.measure_v58 --output $serie
if ($LASTEXITCODE -ne 0) { throw 'Falló la medición del núcleo' }
foreach ($roles in 0, 1, 3) {
    python -B -m tools.measure_v58_desktop --executable $exe --arm $roles --output $ventanas
    if ($LASTEXITCODE -ne 0) { throw "Falló la medición del perfil $roles" }
}
py -3.12 -B -m tools.summarize_v58 --series $serie --output (Join-Path $medicion 'resumen.json') --native (Join-Path $ventanas 'native-0') --native (Join-Path $ventanas 'native-1') --native (Join-Path $ventanas 'native-3')
if ($LASTEXITCODE -ne 0) { throw 'Falló la verificación del resumen' }
```
