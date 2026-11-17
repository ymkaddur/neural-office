$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_OS -ne 'Windows') {
    throw 'This harness operates only on an isolated GitHub Windows runner.'
}
$testTools = Join-Path $env:RUNNER_TEMP 'neural-office-native-tools'
New-Item -ItemType Directory -Path $testTools -ErrorAction Stop | Out-Null
python -m pip install --only-binary=:all: --require-hashes -r tests/requirements-native-ci.txt
if ($LASTEXITCODE -ne 0) { throw 'Pinned test dependency installation failed.' }
cargo install tauri-driver --version 2.1.0 --locked
if ($LASTEXITCODE -ne 0) { throw 'tauri-driver installation failed.' }
$runtimeBase = Join-Path ${env:ProgramFiles(x86)} 'Microsoft/EdgeWebView/Application'
$runtime = Get-ChildItem -LiteralPath $runtimeBase -Directory |
    Where-Object { $_.Name -match '^\d+\.\d+\.\d+\.\d+$' } |
    Sort-Object { [version]$_.Name } -Descending | Select-Object -First 1
if (-not $runtime) { throw 'A WebView2 runtime is required; none is installed on this runner.' }
$runtimeVersion = $runtime.Name
$driverArchive = Join-Path $testTools 'edge.zip'
Invoke-WebRequest -Uri "https://msedgedriver.microsoft.com/$runtimeVersion/edgedriver_win64.zip" -OutFile $driverArchive
Expand-Archive -LiteralPath $driverArchive -DestinationPath (Join-Path $testTools 'edge')
$edgeDriver = Join-Path $testTools 'edge/msedgedriver.exe'
$signature = Get-AuthenticodeSignature -LiteralPath $edgeDriver
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') {
    throw 'Microsoft EdgeDriver signature was not verified.'
}
$driverVersion = & $edgeDriver --version
if ($LASTEXITCODE -ne 0 -or $driverVersion -notmatch [regex]::Escape($runtimeVersion)) {
    throw 'The EdgeDriver version does not exactly match WebView2.'
}
@{
    webview2_version = $runtimeVersion
    edge_driver_version = $driverVersion
    edge_driver_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $edgeDriver).Hash.ToLowerInvariant()
    edge_driver_signature = 'Valid Microsoft Corporation'
    tauri_driver_version = '2.1.0'
} | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $testTools 'tools.json')
"NO_E2E_TOOLS=$testTools" | Out-File -Append -Encoding utf8 $env:GITHUB_ENV
