# Read-only dependency/configuration check. Does not import or start the application.
[CmdletBinding()]
param([string]$DataDir)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")
$dataPath = Get-RetryDataDir $DataDir
$settings = Read-RetrySettings $dataPath
$python = Join-Path (Split-Path -Parent $settings.pythonw) "python.exe"
$info = Get-RetryPythonInfo $python
$nodeVersion = Get-RetryNodeVersion $settings.node
& $python -I -B -c 'import tkinter, PIL, ssl, sqlite3; print(PIL.__version__)'
if ($LASTEXITCODE -ne 0) { throw "Dependency check failed. Run install.ps1 again." }
foreach ($entry in @("supervisor.py", "retry_kitchen.py", "desktop_bridge.cjs")) {
    if (-not (Test-Path -LiteralPath (Join-Path (Get-RetryRoot) $entry) -PathType Leaf)) { throw "Missing application file: $entry" }
}
if (-not (Test-Path -LiteralPath $settings.codex_home -PathType Container)) {
    Write-Warning "Configured CodexHome does not exist yet: $($settings.codex_home). Open Codex or reinstall with -CodexHome before sending."
}
[pscustomobject]@{
    Status = "OK"; Python = "$($info.major).$($info.minor)"; Node = $nodeVersion
    DataDir = $dataPath; CodexHome = $settings.codex_home; Language = $settings.language
    StopRequested = (Test-Path -LiteralPath (Join-Path $dataPath "stop.request"))
    Scope = "Read-only dependencies and paths; no sending, UI, or scheduled task check."
}
