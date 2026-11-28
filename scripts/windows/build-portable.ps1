<#
.SYNOPSIS
  Build the portable Windows bundle: embedded Python + the Marcarr wheel + ffmpeg + a launcher.
.EXAMPLE
  .\scripts\windows\build-portable.ps1 -Wheel dist\marcarr-0.1.1-py3-none-any.whl -Version 0.1.1
  # -> dist-win\Marcarr-0.1.1-windows-x64\   (and the .zip next to it)
#>
param(
    [Parameter(Mandatory)][string]$Wheel,
    [Parameter(Mandatory)][string]$Version,
    [string]$Out = "dist-win",
    [string]$PythonVersion = "3.12.8"
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # Invoke-WebRequest is far faster without the progress bar
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$wheelPath = (Resolve-Path $Wheel).Path
$name = "Marcarr-$Version-windows-x64"
New-Item -ItemType Directory -Force $Out | Out-Null
$outAbs = (Resolve-Path $Out).Path
$root = Join-Path $outAbs $name
$tmp = Join-Path $outAbs "_dl"
if (Test-Path $root) { Remove-Item -Recurse -Force $root }
New-Item -ItemType Directory -Force $root, $tmp | Out-Null

# Embedded Python, with site-packages switched on so pip works.
$pyDir = Join-Path $root "python"
Invoke-WebRequest "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip" -OutFile "$tmp\python.zip"
Expand-Archive "$tmp\python.zip" -DestinationPath $pyDir
$pth = Get-ChildItem $pyDir -Filter "python*._pth" | Select-Object -First 1
(Get-Content $pth.FullName) -replace '^#\s*import site', 'import site' | Set-Content $pth.FullName
$py = Join-Path $pyDir "python.exe"
Invoke-WebRequest "https://bootstrap.pypa.io/get-pip.py" -OutFile "$tmp\get-pip.py"
& $py "$tmp\get-pip.py" --no-warn-script-location --disable-pip-version-check
if ($LASTEXITCODE) { throw "get-pip failed" }
& $py -m pip install --no-warn-script-location --disable-pip-version-check "${wheelPath}[faces,mcp]"
if ($LASTEXITCODE) { throw "installing marcarr failed" }

# ffmpeg and ffprobe.
Invoke-WebRequest "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip" -OutFile "$tmp\ffmpeg.zip"
Expand-Archive "$tmp\ffmpeg.zip" -DestinationPath "$tmp\ffmpeg"
$ff = Get-ChildItem "$tmp\ffmpeg" -Directory | Select-Object -First 1
New-Item -ItemType Directory -Force (Join-Path $root "ffmpeg") | Out-Null
Copy-Item (Join-Path $ff.FullName "bin\ffmpeg.exe"), (Join-Path $ff.FullName "bin\ffprobe.exe") (Join-Path $root "ffmpeg")
Copy-Item (Join-Path $ff.FullName "LICENSE.txt") (Join-Path $root "ffmpeg\LICENSE.txt")

Copy-Item (Join-Path $here "Marcarr.bat"), (Join-Path $here "README.txt") $root
Copy-Item (Join-Path $here "..\..\LICENSE") (Join-Path $root "LICENSE.txt")
Remove-Item -Recurse -Force $tmp

$zip = Join-Path $outAbs "$name.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path $root -DestinationPath $zip -CompressionLevel Optimal
$hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
"$hash  $name.zip" | Set-Content -Encoding ascii "$zip.sha256"
Write-Host "Built $zip ($([math]::Round((Get-Item $zip).Length / 1MB)) MB)"
