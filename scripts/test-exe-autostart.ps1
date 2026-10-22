# Synthetic scheduler state only. This script never invokes the real task cmdlets.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$global:ExeTaskFixture = $null
$global:ExeTaskWrites = 0
$global:ExeTaskDeletes = 0
function Get-ScheduledTask { param($TaskPath, $ErrorAction) if ($global:ExeTaskFixture) { $global:ExeTaskFixture } }
function New-ScheduledTaskAction { param($Execute,$Argument,$WorkingDirectory) [pscustomobject]@{Execute=$Execute;Arguments=$Argument;WorkingDirectory=$WorkingDirectory} }
function New-ScheduledTaskTrigger { param([switch]$AtLogOn,$User,[switch]$Once,$At,$RepetitionInterval) @{} }
function New-ScheduledTaskSettingsSet { param($ExecutionTimeLimit,[switch]$AllowStartIfOnBatteries,[switch]$DontStopIfGoingOnBatteries,[switch]$StartWhenAvailable,$MultipleInstances) @{} }
function New-ScheduledTaskPrincipal { param($UserId,$LogonType,$RunLevel) @{} }
function Register-ScheduledTask {
    param($TaskName,$TaskPath,$Action,$Trigger,$Settings,$Principal,$Description,[switch]$Force)
    $global:ExeTaskWrites++
    $global:ExeTaskFixture = [pscustomobject]@{ TaskName=$TaskName; Actions=@($Action); State='Ready' }
}
function Unregister-ScheduledTask { param($TaskName,$TaskPath,$Confirm) $global:ExeTaskDeletes++; $global:ExeTaskFixture=$null }
$script = Join-Path $PSScriptRoot 'exe-autostart.ps1'
$fakeExe = Join-Path $root 'app.py'
$data = Join-Path $root 'verification/space directory'
function Check($Condition,$Message) { if (-not $Condition) { throw $Message } }
Check ((& $script -Exe $fakeExe -DataDir $data -Action Status) -eq 'absent') 'Initial status'
$null = & $script -Exe $fakeExe -DataDir $data -Action Install
Check ($global:ExeTaskWrites -eq 1) 'Install count'
Check ((& $script -Exe $fakeExe -DataDir $data -Action Status) -eq 'installed') 'Installed status'
Check ($global:ExeTaskFixture.Actions[0].Arguments -like '*space directory" --ensure') 'Quoted path'
$null = & $script -Exe $fakeExe -DataDir $data -Action Install
Check ($global:ExeTaskWrites -eq 2) 'Idempotent reinstall'
$global:ExeTaskFixture.Actions[0].Arguments += ' --preview'
$rejected = $false
try { & $script -Exe $fakeExe -DataDir $data -Action Remove } catch { $rejected=$true }
Check $rejected 'Foreign arguments must be rejected'
Check ($global:ExeTaskDeletes -eq 0) 'No foreign deletion'
$global:ExeTaskFixture.Actions[0].Arguments = $global:ExeTaskFixture.Actions[0].Arguments.Replace(' --preview','')
$global:ExeTaskFixture.Actions[0].Execute = Join-Path $root 'other.exe'
$rejected=$false
try { & $script -Exe $fakeExe -DataDir $data -Action Install } catch { $rejected=$true }
Check $rejected 'Foreign executable must be rejected'
Check ($global:ExeTaskWrites -eq 2) 'No foreign overwrite'
$global:ExeTaskFixture.Actions[0].Execute=$fakeExe
$null = & $script -Exe $fakeExe -DataDir $data -Action Remove
Check ($global:ExeTaskDeletes -eq 1) 'Owned removal'
Check ((& $script -Exe $fakeExe -DataDir $data -Action Status) -eq 'absent') 'Removed status'
'PASS: 11 EXE task ownership checks; scheduler was mocked.'
