$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.12 -B -m neural_office gui
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -B -m neural_office gui
} else {
    throw 'Instala Python 3.12 y Ollama. Esta versión es un piloto técnico, no un instalador autónomo.'
}
if ($LASTEXITCODE -ne 0) { throw 'Neural Office terminó con un error; consulta el mensaje anterior.' }
