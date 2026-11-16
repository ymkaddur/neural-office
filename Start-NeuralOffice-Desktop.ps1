param(
    [string]$Python = '',
    [string]$State = '',
    [string]$Executable = '',
    [switch]$Check
)
$ErrorActionPreference = 'Stop'

function Get-LocalAbsolutePath([string]$Value) {
    if ($Value.StartsWith('\\') -or $Value.StartsWith('//') -or $Value.StartsWith('\??\')) {
        throw 'This Windows test host requires local paths.'
    }
    return [IO.Path]::GetFullPath($Value)
}

if ($env:OS -ne 'Windows_NT') { throw 'The V5.5 process controller requires Windows.' }
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
if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) { throw 'Build or download the verified Windows test host first; see desktop/README.md.' }
$version = & $Python -B -c 'import sys; print(str(sys.version_info.major)+"."+str(sys.version_info.minor))'
if ($LASTEXITCODE -ne 0 -or $version.Trim() -ne '3.12') { throw 'This test package is verified with Python 3.12.' }
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
