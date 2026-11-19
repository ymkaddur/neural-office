# Local integration host for the production renderer and Python stdio on Windows.
# The signed WebView2 runtime renders the page. This small test adapter replaces Tauri.
# The driver supplies a fresh ledger, an offline bundle and the Microsoft WebView2 SDK.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Security/Microsoft.PowerShell.Security.psd1') -ErrorAction Stop
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$package = (Get-Item -LiteralPath $env:NEURAL_OFFICE_TEST_WEBVIEW_SDK).FullName
$bundle = (Get-Item -LiteralPath (Join-Path $env:NEURAL_OFFICE_ROOT 'desktop/dist/index.html')).Directory.FullName
foreach ($name in @('Microsoft.Web.WebView2.Core.dll','Microsoft.Web.WebView2.WinForms.dll','WebView2Loader.dll')) {
    $dll = Join-Path $package $name
    if ((Get-AuthenticodeSignature -LiteralPath $dll).Status -ne 'Valid') { throw "Invalid SDK signature for $name" }
}
$env:PATH = $package + [IO.Path]::PathSeparator + $env:PATH
[void][Reflection.Assembly]::LoadFrom((Join-Path $package 'Microsoft.Web.WebView2.Core.dll'))
[void][Reflection.Assembly]::LoadFrom((Join-Path $package 'Microsoft.Web.WebView2.WinForms.dll'))
$form = New-Object Windows.Forms.Form
$form.Text = 'Neural Office · WebView2 integration test'
$form.ClientSize = New-Object Drawing.Size(1240,760)
$web = New-Object Microsoft.Web.WebView2.WinForms.WebView2
$web.Dock = [Windows.Forms.DockStyle]::Fill
$form.Controls.Add($web)
$form.Show()
function Wait-UiTask($task) {
    $watch = [Diagnostics.Stopwatch]::StartNew()
    while (-not $task.IsCompleted) {
        if ($watch.Elapsed.TotalSeconds -gt 30) { throw 'WebView2 initialization timed out' }
        [Windows.Forms.Application]::DoEvents()
        Start-Sleep -Milliseconds 10
    }
    $task.GetAwaiter().GetResult()
}
[Console]::InputEncoding = [Text.UTF8Encoding]::new($false)
$script:peer = $null
function New-TestPeer {
    $setup = New-Object Diagnostics.ProcessStartInfo
    $setup.FileName = $env:NEURAL_OFFICE_PYTHON
    $setup.WorkingDirectory = $env:NEURAL_OFFICE_ROOT
    $setup.Arguments = '-B -m neural_office.desktop_stdio --state "' + $env:NEURAL_OFFICE_STATE + '"'
    $setup.UseShellExecute = $false
    $setup.CreateNoWindow = $true
    $setup.RedirectStandardInput = $true
    $setup.RedirectStandardOutput = $true
    $setup.StandardOutputEncoding = [Text.UTF8Encoding]::new($false)
    $setup.EnvironmentVariables['PYTHONUTF8'] = '1'
    [void]$setup.EnvironmentVariables.Remove('PYTHONPATH')
    [void]$setup.EnvironmentVariables.Remove('PYTHONHOME')
    [Diagnostics.Process]::Start($setup)
}
$scriptText = @'
window.isTauri=true;
const pending=new Map();
window.chrome.webview.addEventListener('message',event=>{
  const answer=event.data, p=pending.get(answer.id);
  if(!p)return;
  pending.delete(answer.id);
  if(answer.fault)p.reject(answer.fault);else p.resolve(JSON.parse(answer.wire));
});
window.__TAURI_INTERNALS__={invoke:(cmd,{message})=>new Promise((resolve,reject)=>{
  if(cmd!=='desktop_request')return reject('HOST_ORIGIN_DENIED');
  pending.set(message.id,{resolve,reject});
  window.chrome.webview.postMessage(message);
})};
'@
try {
    [void](Wait-UiTask ($web.EnsureCoreWebView2Async($null)))
    $core = $web.CoreWebView2
    $core.SetVirtualHostNameToFolderMapping('tauri.localhost',$bundle,[Microsoft.Web.WebView2.Core.CoreWebView2HostResourceAccessKind]::DenyCors)
    [void](Wait-UiTask ($core.AddScriptToExecuteOnDocumentCreatedAsync($scriptText)))
    $allowed = @('describe','snapshot.get','project.history','attempt.get','attempt.lookup','attempt.events','attempt.cancel','report.get','report.read','attachments.threads','attachments.list','attachments.history')
    $core.add_WebMessageReceived({
        param($sender,$eventArgs)
        if ($eventArgs.Source -ne 'https://tauri.localhost/index.html') {return}
        $wire = $eventArgs.WebMessageAsJson
        $message = $wire | ConvertFrom-Json
        $id = $message.id
        [Console]::WriteLine(('Method {0}' -f $message.method))
        $answer = @{id=$id}
        try {
            if ($allowed -notcontains $message.method) {throw 'TEST_METHOD_OUT_OF_SCOPE'}
            if ($null -eq $script:peer -or $script:peer.HasExited) {
                if ($message.method -ne 'describe') { throw 'HOST_DISCONNECTED' }
                if ($null -ne $script:peer) {$script:peer.Dispose()}
                $script:peer = New-TestPeer
            }
            $script:peer.StandardInput.WriteLine($wire)
            $script:peer.StandardInput.Flush()
            $response = $script:peer.StandardOutput.ReadLine()
            if (-not $response) {throw 'HOST_DISCONNECTED'}
            $envelope = $response | ConvertFrom-Json
            [Console]::WriteLine(('Envelope v{0} matches={1} ok={2}' -f $envelope.version,($envelope.id -eq $id),$envelope.ok))
            if (-not $envelope.ok) {[Console]::WriteLine(('Service code {0}' -f $envelope.error.code))}
            $answer.wire = $response
        } catch {
            $answer.fault = if ($_.Exception.Message -eq 'TEST_METHOD_OUT_OF_SCOPE') {'TEST_METHOD_OUT_OF_SCOPE'} else {'HOST_DISCONNECTED'}
        }
        $sender.PostWebMessageAsJson(($answer | ConvertTo-Json -Depth 32 -Compress))
    })
    $core.add_NavigationCompleted({param($sender,$evt) [Console]::WriteLine(('Navigation {0} ({1})' -f $evt.IsSuccess,$evt.WebErrorStatus))})
    $core.Navigate('https://tauri.localhost/index.html')
    [Windows.Forms.Application]::Run($form)
} finally {
    if ($null -ne $script:peer) {
        if (-not $script:peer.HasExited) {
            $script:peer.StandardInput.Close()
            if (-not $script:peer.WaitForExit(12000)) {$script:peer.Kill();$script:peer.WaitForExit()}
        }
        $script:peer.Dispose()
    }
    $web.Dispose()
    $form.Dispose()
}
