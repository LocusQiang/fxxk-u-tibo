[CmdletBinding()]
param(
    [string]$CodexHome,
    [string]$Python,
    [ValidateSet("auto", "en", "zh")][string]$Language = "auto"
)
$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "scripts/setup.ps1") @PSBoundParameters
& (Join-Path $PSScriptRoot "scripts/doctor.ps1")
