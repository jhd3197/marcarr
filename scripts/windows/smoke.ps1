<#
.SYNOPSIS
  Check a built portable bundle: it runs, imports its dependencies, finds ffmpeg and serves the UI.
#>
param([Parameter(Mandatory)][string]$Root, [int]$Port = 7471)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path $Root).Path
$py = Join-Path $Root "python\python.exe"
$env:PATH = "$Root\ffmpeg;$env:PATH"
$env:MARCARR_CONFIG = Join-Path $env:TEMP "marcarr-smoke\config.yaml"
$env:MARCARR_DATA_DIR = Join-Path $env:TEMP "marcarr-smoke\data"
Remove-Item -Recurse -Force (Split-Path $env:MARCARR_CONFIG) -ErrorAction SilentlyContinue

& $py -m marcarr --version
if ($LASTEXITCODE) { throw "marcarr --version failed" }
& $py -c "import marcarr.server, cv2, numpy, PIL, prompture; print('imports ok')"
if ($LASTEXITCODE) { throw "an import failed" }
& "$Root\ffmpeg\ffmpeg.exe" -version | Select-Object -First 1
if ($LASTEXITCODE) { throw "ffmpeg does not run" }
& "$Root\ffmpeg\ffprobe.exe" -version | Select-Object -First 1
if ($LASTEXITCODE) { throw "ffprobe does not run" }

$log = Join-Path $env:TEMP "marcarr-smoke.log"
$proc = Start-Process $py -ArgumentList "-m", "marcarr", "serve", "--port", $Port -PassThru `
    -RedirectStandardOutput $log -RedirectStandardError "$log.err"
try {
    $status = $null
    for ($i = 0; $i -lt 60 -and -not $status; $i++) {
        Start-Sleep -Seconds 1
        if ($proc.HasExited) { throw "marcarr exited early (code $($proc.ExitCode))" }
        try { $status = Invoke-RestMethod "http://127.0.0.1:$Port/api/v1/status" -TimeoutSec 3 } catch { }
    }
    if (-not $status) { throw "the API did not come up" }
    Write-Host "status: version $($status.version)"
    $page = Invoke-WebRequest "http://127.0.0.1:$Port/" -UseBasicParsing
    if ($page.Content -notmatch 'id="root"') { throw "the web UI is not served" }
    if (-not (Test-Path $env:MARCARR_CONFIG)) { throw "config.yaml was not created" }
    Write-Host "smoke ok"
} finally {
    if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force }
    if (Test-Path "$log.err") { Get-Content "$log.err" -Tail 15 }
}
