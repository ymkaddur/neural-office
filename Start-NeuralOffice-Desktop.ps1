param(
    [string]$Python = '',
    [string]$State = '',
    [string]$Executable = '',
    [switch]$Check,
    [switch]$PrepareReaders
)
$ErrorActionPreference = 'Stop'

function Get-LocalAbsolutePath([string]$Value) {
    if ($Value.StartsWith('\\') -or $Value.StartsWith('//') -or $Value.StartsWith('\??\')) {
        throw 'This Windows test host requires local paths.'
    }
    return [IO.Path]::GetFullPath($Value)
}

if ($env:OS -ne 'Windows_NT') { throw 'The V5.5 process controller requires Windows.' }
$readerRequirements = Join-Path $PSScriptRoot 'requirements-readers-windows.txt'
$requirementsHash = (Get-FileHash -LiteralPath $readerRequirements -Algorithm SHA256).Hash.Substring(0,12)
$runtimeRoot = Join-Path $env:LOCALAPPDATA 'NeuralOffice/desktop-runtimes'
$readerEnvironment = Join-Path $runtimeRoot "py312-$requirementsHash"
$readerPython = Join-Path $readerEnvironment 'Scripts/python.exe'
if (-not $Python -and -not $PrepareReaders -and (Test-Path -LiteralPath $readerPython -PathType Leaf)) {
    $Python = $readerPython
}
if (-not $Python) {
    $Python = & py -3.12 -c 'import sys; print(sys.executable)'
    if ($LASTEXITCODE -ne 0 -or -not $Python) { throw 'Install Python 3.12 or supply -Python with its executable.' }
}
if (-not $State) { $State = Join-Path $env:LOCALAPPDATA 'NeuralOffice/v52.sqlite3' }
if (-not $Executable) { $Executable = Join-Path $PSScriptRoot 'desktop/src-tauri/target/release/neural-office-desktop.exe' }
$Python = Get-LocalAbsolutePath $Python
$State = Get-LocalAbsolutePath $State
$Executable = Get-LocalAbsolutePath $Executable
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw 'Python executable is missing.' }
$version = & $Python -B -c 'import sys; print(sys.version_info.major,sys.version_info.minor)'
if ($LASTEXITCODE -ne 0 -or $version.Trim() -ne '3 12') { throw 'This test package is verified with Python 3.12.' }
$checkReaders = Join-Path $PSScriptRoot 'neural_office/check_readers.py'
if ($PrepareReaders) {
    [IO.Directory]::CreateDirectory($runtimeRoot) | Out-Null
    $setupLock = [IO.File]::Open((Join-Path $runtimeRoot "$requirementsHash.lock"), 'OpenOrCreate', 'ReadWrite', 'None')
    try {
        if (-not (Test-Path -LiteralPath $readerPython -PathType Leaf)) {
            & $Python -m venv $readerEnvironment
            if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno de lectura.' }
        }
        & $readerPython -m pip --disable-pip-version-check install --only-binary=:all: --require-hashes -r $readerRequirements
        if ($LASTEXITCODE -ne 0) { throw 'Falló la instalación de los lectores con sus huellas fijadas.' }
        $prepared = & $readerPython -I -B $checkReaders $readerRequirements
        if ($LASTEXITCODE -ne 0 -or $prepared -ne 'available') { throw 'La comprobación de los lectores instalados falló.' }
        Write-Output 'Lectores PDF e imagen preparados para el escritorio.'
    } finally {
        $setupLock.Dispose()
    }
    exit 0
}
if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) { throw 'Build or download the verified Windows test host first; see desktop/README.md.' }
$readers = & $Python -I -B $checkReaders $readerRequirements
if ($LASTEXITCODE -ne 0 -or $readers -ne 'available') {
    Write-Warning 'Los lectores PDF e imagen requieren .\Start-NeuralOffice-Desktop.ps1 -PrepareReaders. HTML y JSON se pueden revisar con este Python.'
} elseif ($Check) {
    Write-Output 'Lectores PDF, PNG y JPEG comprobados.'
}
if ($Check) { Write-Output 'Desktop launcher configuration checked; no service or model started.'; exit 0 }

# Configure only the child. The renderer cannot set these paths or execute a shell.
# The default preserves the existing ledger and its counters; tests use -State.
$start = [Diagnostics.ProcessStartInfo]::new()
$start.FileName = $Executable
$start.UseShellExecute = $false
$start.WorkingDirectory = $PSScriptRoot
$start.Environment['NEURAL_OFFICE_PYTHON'] = $Python
$start.Environment['NEURAL_OFFICE_ROOT'] = $PSScriptRoot
$start.Environment['NEURAL_OFFICE_STATE'] = $State
$process = [Diagnostics.Process]::Start($start)
Write-Output ('Neural Office desktop started (PID {0}).' -f $process.Id)
