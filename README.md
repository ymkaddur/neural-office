# Neural Office

**V5.13-Polished · escritorio de revisión multiformato para Windows, en rama de pruebas.** Adjunta la entrega de un proyecto y escribe qué quieres comprobar. El hilo conserva los resultados de la inspección local y enlaza cada hallazgo con su fuente. Puedes pedir al Director que comente los extractos autorizados con un modelo de Ollama.

[![Pruebas de V5.13-Polished en Windows](https://github.com/ymkaddur/neural-office/actions/workflows/windows-tests.yml/badge.svg?branch=feat%2Fv5.13-polished)](https://github.com/ymkaddur/neural-office/actions/workflows/windows-tests.yml?query=branch%3Afeat%2Fv5.13-polished)
[![Licencia MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

## Probar una entrega

El ejemplo contiene la especificación PDF de un portal, su manifiesto JSON, dos imágenes y un ZIP. Pulsa **Adjuntar archivos**, selecciona los cinco y elige **Inspeccionar · 0 intentos**. Abre el hallazgo para comparar la página del PDF que exige una respuesta en 24 horas con la línea del manifiesto que declara 48. Los archivos, el informe y los recibos se pueden volver a abrir por proyecto e hilo. [Ejemplo, puesta en marcha y verificación](docs/V5_13_POLISHED.md)

La consulta al modelo consume **un intento al autorizar la reserva**. Cada proyecto dispone de tres. El permiso identifica los fragmentos, el modelo y el saldo. Un fallo después de la reserva y una cancelación también consumen ese intento. Abre **Actividad del encargo** para seguir los hechos registrados.

En **Apariencia** puedes cambiar entre Arena, Azul noche y el tema del sistema. Los ajustes de densidad, tamaño de texto y contraste se aplican al hilo y al inspector.

![Hilo del portal con la discrepancia entre su manifiesto y la página citada del PDF, capturado en Edge con el núcleo local](docs/images/v5.13-evidencia.png)

[Vista del paquete en Azul noche](docs/images/v5.13-paquete.png) · [Mediciones de tipografía, contraste y recursos](docs/evidence/V5_13_RENDERER.json)

## Revisión de HTML

Desde el inspector, **Abrir revisión de HTML con roles** conserva el flujo de revisión estática y la consulta opcional con 1, 3 o 7 roles secuenciales. También puedes comprobar la muestra desde Python 3.12. [Alcance de las reglas](docs/HTML_REVIEW.md)

```powershell
py -3.12 -B -m neural_office check --root examples --file examples/audit-sample.html
```

Para ejecutar la aplicación necesitas Windows x64, WebView2, Python 3.12 y el código del mismo commit que el ejecutable de prueba. El lanzador prepara los lectores PDF e imagen. Ollama se utiliza al pedir comentarios del modelo. [Instalación y compilación](desktop/README.md) · [Coste, datos y recuperación](docs/README.md)

## Hacia V6.5

La beta V6 exige instalación probada y un recorrido completo con personas nuevas. Hasta V6.5 se incorporan borradores recuperables, skills que el usuario puede inspeccionar y revocar, y revisiones con un presupuesto explícito. [Hoja de ruta y criterios de aceptación](ROADMAP.md).

En seis tareas con un modelo local pequeño, el Director y la revisión de tres roles dieron las mismas ubicaciones que las reglas. Sus comentarios no añadieron acciones útiles según la rúbrica fijada. [Comparación y costes](docs/V5_7_REVIEW.md).

## Contribuir

Prueba un caso pequeño, describe qué esperabas y qué ocurrió. [Cómo contribuir](CONTRIBUTING.md) · [Pruebas y documentación técnica](docs/README.md) · [Comunicar un problema de seguridad](SECURITY.md).

Los archivos, respuestas y registros se guardan localmente sin cifrar. No adjuntes tu carpeta de estado a un issue. [Frontera de confianza](SECURITY.md) · [Licencias y procedencia](LICENSING.md).

## Apoyo voluntario

[Patreon](https://www.patreon.com/Neural_office): 1 €, 3 €, 5 € o 10 €/mes, sin funciones exclusivas. GitHub Sponsors sigue pendiente de activación. [Detalles del apoyo](docs/SUPPORT.md). Usar Neural Office es gratis.
