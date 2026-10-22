# Run with powershell.exe -NoProfile -File scripts/test-scripts.ps1.
# No real processes, sending, installation, or scheduled-task mutations.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$script:checks = 0
function Assert-Check([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
    $script:checks++
}
function Assert-Rejected([scriptblock]$Action, [string]$Message) {
    $rejected = $false
    try { & $Action } catch { $rejected = $true }
    Assert-Check $rejected $Message
}
$files = @(Get-ChildItem -LiteralPath $root -Filter '*.ps1') + @(Get-ChildItem -LiteralPath $PSScriptRoot -Filter '*.ps1')
foreach ($file in $files) {
    $tokens = $null; $parseErrors = $null
    $null = [Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$parseErrors)
    Assert-Check ($parseErrors.Count -eq 0) ("Parse failed: " + $file.Name + ': ' + $parseErrors)
}
. (Join-Path $PSScriptRoot 'common.ps1')
foreach ($relative in @('relative', 'C:relative', '\relative')) {
    Assert-Rejected { ConvertTo-RetryAbsolutePath $relative } 'Relative path was accepted.'
}
$action = [pscustomobject]@{
    Execute = Get-RetryPowerShell; WorkingDirectory = $root
    Arguments = Get-RetryTaskArguments (Join-Path $root '.runtime')
}
$task = [pscustomobject]@{ TaskName = 'FixtureOnly'; Actions = @($action) }
Assert-RetryTaskOwnership $task
$script:checks++
$action.WorkingDirectory = Split-Path -Parent $root
Assert-Rejected { Assert-RetryTaskOwnership $task } 'Foreign working directory was accepted.'
$action.WorkingDirectory = $root
$originalArgs = $action.Arguments
$action.Arguments += ' -Demo'
Assert-Rejected { Assert-RetryTaskOwnership $task } 'Extra task arguments were accepted.'
$action.Arguments = $originalArgs.Replace('launch.ps1', 'other.ps1')
Assert-Rejected { Assert-RetryTaskOwnership $task } 'Foreign script was accepted.'
$action.Arguments = $originalArgs
$task.Actions = @($action, $action)
Assert-Rejected { Assert-RetryTaskOwnership $task } 'Multiple task actions were accepted.'

$fixtureParent = Join-Path $root 'verification'
$fixture = Join-Path $fixtureParent ('scripts-test-' + [guid]::NewGuid().ToString('N') + ' space')
$null = New-Item -ItemType Directory -Path (Join-Path $fixture 'scripts'), (Join-Path $fixture '.venv/Scripts'), (Join-Path $fixture '.runtime') -Force
$saved = @{}
foreach ($name in @('CODEX_HOME','CODEX_RETRY_DATA_DIR','CODEX_RETRY_LANGUAGE')) { $saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
try {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'common.ps1'), (Join-Path $PSScriptRoot 'stop.ps1') -Destination (Join-Path $fixture 'scripts')
    Copy-Item -LiteralPath (Join-Path $root 'launch.ps1') -Destination $fixture
    $data = Join-Path $fixture '.runtime'
    $pythonw = Join-Path $fixture '.venv/Scripts/pythonw.exe'
    $node = Join-Path $fixture 'node.exe'
    foreach ($file in @($pythonw, $node, (Join-Path $fixture 'supervisor.py'), (Join-Path $fixture 'retry_kitchen.py'))) { [IO.File]::WriteAllText($file, '') }
    @{ pythonw=$pythonw; node=$node; codex_home=$fixture; language='zh' } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $data 'runtime.json') -Encoding UTF8
    $env:CODEX_RETRY_DATA_DIR = $data
    $env:CODEX_HOME = 'inherited-home-must-not-win'
    $env:CODEX_RETRY_LANGUAGE = 'en'
    $global:RetryScriptTestLaunches = @()
    function Start-Process {
        param($FilePath, $ArgumentList, $WorkingDirectory, $WindowStyle, [switch]$PassThru)
        $global:RetryScriptTestLaunches += [pscustomobject]@{ File=$FilePath; Args=$ArgumentList; Cwd=$WorkingDirectory; Style=$WindowStyle; Home=$env:CODEX_HOME; Data=$env:CODEX_RETRY_DATA_DIR; Lang=$env:CODEX_RETRY_LANGUAGE }
        $process = [pscustomobject]@{ Id=123; ExitCode=0 }
        $process | Add-Member -MemberType ScriptMethod -Name WaitForExit -Value { param($Milliseconds) return $false }
        return $process
    }
    & (Join-Path $fixture 'scripts/stop.ps1')
    & (Join-Path $fixture 'launch.ps1') -Ensure
    Assert-Check ($global:RetryScriptTestLaunches.Count -eq 0) 'Ensure ignored current-boot stop.'
    & (Join-Path $fixture 'launch.ps1') -Demo
    Assert-Check ($global:RetryScriptTestLaunches.Count -eq 1 -and $global:RetryScriptTestLaunches[0].Args -like '* --demo --node *') 'Demo launch arguments failed.'
    Assert-Check (Test-Path -LiteralPath (Join-Path $data 'stop.request')) 'Demo cleared stop marker.'
    & (Join-Path $fixture 'launch.ps1')
    Assert-Check (-not (Test-Path -LiteralPath (Join-Path $data 'stop.request'))) 'Manual launch did not clear stop.'
    $last = $global:RetryScriptTestLaunches[-1]
    Assert-Check ($last.File -eq $pythonw -and $last.Args -like '*supervisor.py*' -and $last.Cwd -eq $fixture -and $last.Style -eq 'Hidden') 'Launch command is incorrect.'
    Assert-Check ($last.Home -eq $fixture -and $last.Data -eq $data -and $last.Lang -eq 'zh') 'Child environment did not use runtime settings.'
    Assert-Check ($env:CODEX_HOME -eq 'inherited-home-must-not-win' -and $env:CODEX_RETRY_LANGUAGE -eq 'en') 'Parent environment was not restored.'
    & (Join-Path $fixture 'scripts/stop.ps1')
    (Get-Item -LiteralPath (Join-Path $data 'stop.request')).LastWriteTimeUtc = [DateTime]::SpecifyKind([DateTime]'2000-01-01', [DateTimeKind]::Utc)
    & (Join-Path $fixture 'launch.ps1') -Ensure
    Assert-Check ($global:RetryScriptTestLaunches.Count -eq 3) 'Ensure did not allow an old-boot stop marker.'
    Assert-Check (Test-Path -LiteralPath (Join-Path $data 'stop.request')) 'Ensure must leave old marker cleanup to supervisor.'
} finally {
    foreach ($name in $saved.Keys) { [Environment]::SetEnvironmentVariable($name, $saved[$name], 'Process') }
    Remove-Item Function:\Start-Process -ErrorAction SilentlyContinue
    # Only delete this run's exact generated fixture under verification.
    $resolved = [IO.Path]::GetFullPath($fixture)
    $boundary = [IO.Path]::GetFullPath($fixtureParent).TrimEnd([char]92) + [char]92
    if (-not $resolved.StartsWith($boundary, [StringComparison]::OrdinalIgnoreCase)) { throw 'Fixture cleanup boundary failed.' }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
Write-Host "PASS: $script:checks script checks; no real launch or task registration."
