[CmdletBinding()]
param([Parameter(Mandatory)][ValidateSet("Start", "Stop", "Preview")][string]$Action)
$ErrorActionPreference = "Stop"
try {
    $root = Split-Path -Parent $PSScriptRoot
    switch ($Action) {
        "Start" { & (Join-Path $root "launch.ps1") }
        "Stop" { & (Join-Path $PSScriptRoot "stop.ps1") }
        "Preview" { & (Join-Path $root "launch.ps1") -Demo }
    }
} catch {
    $message = "$Action failed: $($_.Exception.Message)"
    try {
        $shell = New-Object -ComObject WScript.Shell
        $null = $shell.Popup($message, 15, "fxxk u tibo", 16)
    } catch { [Console]::Error.WriteLine($message) }
    exit 1
}
