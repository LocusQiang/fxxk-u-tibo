[CmdletBinding(SupportsShouldProcess)]
param(
    [switch]$Remove,
    [ValidatePattern('^[^\\/\*?\[\]"\x00-\x1f]+$')][string]$TaskName = "CodexAutoRetryKitchen"
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "scripts/common.ps1")
try {
    Import-Module ScheduledTasks -ErrorAction Stop
    $existing = Get-RetryScheduledTask $TaskName
    if ($existing) { Assert-RetryTaskOwnership $existing }
    if ($Remove) {
        if (-not $existing) { Write-Host "Autostart task is already absent: $TaskName"; return }
        if ($PSCmdlet.ShouldProcess($TaskName, "Remove this repository's autostart task")) {
            # Re-read ownership immediately before mutation. Never stop or kill a process here.
            $current = Get-RetryScheduledTask $TaskName
            if (-not $current) { return }
            Assert-RetryTaskOwnership $current
            Unregister-ScheduledTask -TaskName $TaskName -TaskPath "\" -Confirm:$false -ErrorAction Stop
            if (Get-RetryScheduledTask $TaskName) { throw "Task still exists after removal: $TaskName" }
            Write-Host "Autostart removed: $TaskName. To stop a running worker, use Stop.vbs or scripts/stop.ps1."
        }
        return
    }
    $dataPath = Get-RetryDataDir
    $null = Read-RetrySettings $dataPath
    if (-not $PSCmdlet.ShouldProcess($TaskName, "Register logon and one-minute recovery autostart")) { return }
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $action = New-ScheduledTaskAction -Execute (Get-RetryPowerShell) -Argument (Get-RetryTaskArguments $dataPath) -WorkingDirectory $PSScriptRoot
    $logon = New-ScheduledTaskTrigger -AtLogOn -User $identity
    $recovery = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
    $registration = @{
        TaskName = $TaskName; TaskPath = "\"; Action = $action; Trigger = @($logon, $recovery)
        Settings = $settings; Principal = $principal; ErrorAction = "Stop"
        Description = "Codex Auto Retry Kitchen: logon and one-minute recovery; respects stop.request."
    }
    $current = Get-RetryScheduledTask $TaskName
    if ($current) { Assert-RetryTaskOwnership $current; $registration.Force = $true }
    $null = Register-ScheduledTask @registration
    $installed = Get-RetryScheduledTask $TaskName
    if (-not $installed) { throw "Task registration could not be verified: $TaskName" }
    Assert-RetryTaskOwnership $installed
    Write-Host "Autostart registered: $TaskName. It can start sending at the next logon or recovery tick unless stop.request exists."
} catch {
    throw "Autostart operation failed: $($_.Exception.Message) No registry fallback was attempted. If access was denied, use an account permitted to manage this scheduled task."
}
