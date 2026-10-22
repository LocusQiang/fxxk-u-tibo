[CmdletBinding()]
param(
    [switch]$Demo,
    [switch]$Ensure,
    # Explicit path captured by install-autostart.ps1; otherwise use the environment/default.
    [string]$DataDir
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "scripts/common.ps1")
$dataPath = Get-RetryDataDir $DataDir
$stop = Join-Path $dataPath "stop.request"
if ($Ensure -and (Test-RetryCurrentBootStop $stop)) {
    Write-Verbose "Manual stop is active; Ensure will not start a process."
    return
}
$settings = Read-RetrySettings $dataPath
$entry = if ($Demo) { "retry_kitchen.py" } else { "supervisor.py" }
$script = Join-Path $PSScriptRoot $entry
if (-not (Test-Path -LiteralPath $script -PathType Leaf)) { throw "Missing application file: $script" }
if (-not $Demo -and -not $Ensure -and (Test-Path -LiteralPath $stop)) { Remove-Item -LiteralPath $stop -Force }
$arguments = '-X utf8 ' + (ConvertTo-RetryArgument $script)
if ($Demo) { $arguments += ' --demo --node ' + (ConvertTo-RetryArgument $settings.node) }
$saved = @{}
foreach ($name in @("CODEX_HOME", "CODEX_RETRY_DATA_DIR", "CODEX_RETRY_LANGUAGE")) {
    $saved[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}
try {
    $env:CODEX_HOME = $settings.codex_home
    $env:CODEX_RETRY_DATA_DIR = $dataPath
    $env:CODEX_RETRY_LANGUAGE = $settings.language
    # ArgumentList needs explicit Windows quoting in Windows PowerShell 5.1.
    $process = Start-Process -FilePath $settings.pythonw -ArgumentList $arguments -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
    if ($process.WaitForExit(500) -and $process.ExitCode -ne 0) {
        throw "The background process exited with code $($process.ExitCode). Run scripts/doctor.ps1 and inspect logs in $dataPath."
    }
    Write-Host "Launch requested: $entry (PID $($process.Id)). Data directory: $dataPath"
} finally {
    foreach ($name in $saved.Keys) { [Environment]::SetEnvironmentVariable($name, $saved[$name], "Process") }
}
