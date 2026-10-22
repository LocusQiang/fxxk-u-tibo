[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Exe,
    [Parameter(Mandatory)][string]$DataDir,
    [ValidateSet('Install','Remove','Status')][string]$Action = 'Status'
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
$exePath = [IO.Path]::GetFullPath($Exe)
$dataPath = [IO.Path]::GetFullPath($DataDir)
foreach ($value in @($exePath, $dataPath)) {
    if ($value.Contains('"') -or $value.Contains([string][char]10) -or $value.Contains([string][char]13)) { throw 'Invalid path.' }
}
if (-not (Test-Path -LiteralPath $exePath -PathType Leaf)) { throw 'Executable is missing.' }
$folder = Split-Path -Parent $exePath
$taskName = 'FxxkUTibo'
$arguments = '--data-dir "' + $dataPath.TrimEnd([char]92) + '" --ensure'
function Read-OwnedTask {
    $task = @(Get-ScheduledTask -TaskPath '\' -ErrorAction Stop) | Where-Object { $_.TaskName -eq $taskName }
    if ($task) {
        $actions = @($task.Actions)
        if ($actions.Count -ne 1 -or $actions[0].Execute -ne $exePath -or
            $actions[0].Arguments -cne $arguments -or $actions[0].WorkingDirectory -ne $folder) {
            throw 'FxxkUTibo belongs to another path or installation. No task was changed. Remove it from its original installation first.'
        }
    }
    $task
}
$existing = Read-OwnedTask
if ($Action -eq 'Status') {
    if ($existing -and $existing.State -ne 'Disabled') { 'installed' } else { 'absent' }
    return
}
if ($Action -eq 'Remove') {
    if ($existing) {
        $null = Read-OwnedTask
        Unregister-ScheduledTask -TaskName $taskName -TaskPath '\' -Confirm:$false
        if (Read-OwnedTask) { throw 'Task still exists after removal.' }
    }
    'removed'
    return
}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$run = New-ScheduledTaskAction -Execute $exePath -Argument $arguments -WorkingDirectory $folder
$logon = New-ScheduledTaskTrigger -AtLogOn -User $identity
$recovery = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$registration = @{
    TaskName=$taskName; TaskPath='\'; Action=$run; Trigger=@($logon,$recovery)
    Settings=$settings; Principal=$principal
    Description='fxxk u tibo: logon startup and one-minute supervisor recovery; respects manual Stop.'
}
if (Read-OwnedTask) { $registration.Force = $true }
$null = Register-ScheduledTask @registration
if (-not (Read-OwnedTask)) { throw 'Task registration was not verified.' }
'installed'
