# Neural Office

**Revisa en local. Decide con evidencia.**

Un espacio de trabajo para encargar una revisión, seguir su ejecución y recuperar la entrega. Gratis y open source, con las mismas funciones para todo el mundo.

**V5.10 · escritorio Windows en pruebas.** Elige un HTML para localizar las líneas que conviene revisar. Comprobar el archivo cuesta cero intentos. Si encargas una revisión al Director, puedes abrir una entrega anterior y detener el trabajo que sigue en marcha.

[![Tests Windows de esta rama](https://github.com/ymkaddur/neural-office/actions/workflows/windows-tests.yml/badge.svg?branch=feat%2Fv5.10-windows-review)](https://github.com/ymkaddur/neural-office/actions/workflows/windows-tests.yml?query=branch%3Afeat%2Fv5.10-windows-review)
[![Licencia MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

![Variante grafito del escritorio Windows con los cuatro hallazgos del ejemplo público](docs/images/v5.10-graphite.png)

Abre **Paleta · Grafito** en el pie de la navegación para alternar con el acabado mineral de V5.9. [Comparación visual, coste y pruebas de V5.10](docs/V5_10_REVIEW.md) · [Referencia V5.9](docs/V5_9_REVIEW.md).

## Qué puedes hacer

- **Revisar un HTML:** idioma, título, alternativas de imágenes y posibles controles sin etiqueta, con ubicación y una acción sugerida.
- **Pedir comentarios al Director:** elige tu modelo instalado en Ollama y autoriza el alcance antes de empezar.
- **Controlar el trabajo:** consulta llamadas, detén la ejecución y vuelve a abrir el informe sin repetirla.
- **Conservar contexto:** consulta el historial y vuelve al borrador durante la misma apertura. La fuente original permanece intacta.

Los hallazgos estáticos y los comentarios del modelo se presentan por separado. El producto lee archivos; no edita repositorios ni ejecuta herramientas propuestas por un modelo.

## Probarlo

Para comprobar un HTML sin modelo en Windows, descarga la rama de prueba, extrae la carpeta y ejecuta el siguiente comando con Python 3.12. [Código de V5.10](https://github.com/ymkaddur/neural-office/archive/refs/heads/feat/v5.10-windows-review.zip).

```powershell
py -3.12 -B -m neural_office check --root examples --file examples/audit-sample.html
```

Devuelve cuatro hallazgos en JSON y la huella del archivo. No inicia Ollama, crea estado ni consume intentos. [Ejemplos y alcance](docs/HTML_REVIEW.md).

**En el escritorio:** sigue la [guía de compilación y uso](desktop/README.md). Necesita Windows x64, Python 3.12 y WebView2. La consulta opcional al Director requiere Ollama y un modelo instalado. Compilar requiere Node, Rust y las herramientas de Windows. Todavía se distribuye como código para desarrollo, sin instalador firmado.

1. Pulsa **Elegir archivo HTML** y **Comprobar HTML**. Puedes recorrer todas las ubicaciones sin gastar intentos.
2. Abre **Qué revisar** junto a un hallazgo para decidir cómo comprobarlo en tu documento.
3. **Consultar al Director** conserva la fuente. Revisa el número de llamadas y autoriza el encargo si te interesa guardarlo con comentarios.

La consulta asistida empieza con un rol en CPU. Cada proyecto dispone de tres intentos. Un fallo o una cancelación después de reservar también cuenta. [Uso, datos y recuperación](docs/README.md).

## Hacia V6.5

La beta V6 exige instalación probada y un recorrido completo con personas nuevas. Hasta V6.5 se incorporan borradores recuperables, skills que el usuario puede inspeccionar y revocar, y revisiones con un presupuesto explícito. [Hoja de ruta y criterios de aceptación](ROADMAP.md).

En seis tareas con un modelo local pequeño, el Director y la revisión de tres roles dieron las mismas ubicaciones que las reglas. Sus comentarios no añadieron acciones útiles según la rúbrica fijada. [Comparación y costes](docs/V5_7_REVIEW.md).

## Contribuir

Prueba un caso pequeño, describe qué esperabas y qué ocurrió. [Cómo contribuir](CONTRIBUTING.md) · [Pruebas y documentación técnica](docs/README.md) · [Comunicar un problema de seguridad](SECURITY.md).

Los archivos, respuestas y registros se guardan localmente sin cifrar. No adjuntes tu carpeta de estado a un issue. [Frontera de confianza](SECURITY.md) · [Licencias y procedencia](LICENSING.md).

## Apoyo voluntario

[Patreon](https://www.patreon.com/Neural_office): 1 €, 3 €, 5 € o 10 €/mes, sin funciones exclusivas. GitHub Sponsors sigue pendiente de activación. [Detalles del apoyo](docs/SUPPORT.md). Usar Neural Office es gratis.
