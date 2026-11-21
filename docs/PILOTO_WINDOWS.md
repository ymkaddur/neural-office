# Neural Office · piloto técnico para Windows x64

Extrae el ZIP completo a una carpeta local. El lanzador usa el núcleo Python de esa misma carpeta. El equipo necesita PowerShell 7, Python 3.12 x64 y Microsoft Edge WebView2. Para consultar al Director con inferencia, prepara también Ollama y un modelo local.

Desde PowerShell 7, en la carpeta extraída, ejecuta:

```powershell
.\Start-NeuralOffice-Desktop.ps1 -Check
.\Start-NeuralOffice-Desktop.ps1
```

El primer comando comprueba la configuración y el formato del ejecutable x64. El segundo abre el escritorio. Puedes comenzar escribiendo un encargo sin adjuntos. Para leer el texto de PDF o inspeccionar imágenes, prepara antes los lectores con `.\Start-NeuralOffice-Desktop.ps1 -PrepareReaders`. Ese comando descarga las dependencias fijadas por huella a un entorno local.

La aplicación conserva los proyectos en el estado local de Neural Office. Para una prueba aislada puedes pasar `-State` con una ruta nueva a un archivo SQLite local.

Este paquete se usa para validar la entrega antes de publicarla. En equipos que requieren una firma de confianza, Windows puede bloquear el ejecutable con el error 4551. Mantén activa esa protección. La distribución pública del binario espera a una firma aceptada por Windows.

`SOURCE_COMMIT` identifica el código de origen y `SHA256SUMS` recoge las huellas del contenido. Los avisos de las dependencias nativas están en `native-notices`.
