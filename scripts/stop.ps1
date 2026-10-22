[CmdletBinding()]
param([string]$DataDir)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")
$dataPath = Get-RetryDataDir $DataDir
$null = New-Item -ItemType Directory -Path $dataPath -Force
[IO.File]::WriteAllText((Join-Path $dataPath "stop.request"), "Manual stop requested at " + [DateTimeOffset]::Now.ToString("o"), (New-Object Text.UTF8Encoding($false)))
Write-Host "Stop requested for $dataPath. An in-flight send may finish before the worker exits. Autostart/Ensure will respect this request."
