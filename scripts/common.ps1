# Shared path and prerequisite checks. Importing does not launch the application.
Set-StrictMode -Version Latest

function Get-RetryRoot {
    [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
}

function ConvertTo-RetryAbsolutePath {
    param([Parameter(Mandatory)][string]$Path, [string]$Label = "Path")
    $drivePath = $Path -match '^[A-Za-z]:[\\/]'
    $uncPath = $Path -match '^\\\\[^\\/]+[\\/][^\\/]+'
    if ((-not $drivePath -and -not $uncPath) -or $Path.IndexOfAny([IO.Path]::GetInvalidPathChars()) -ge 0) {
        throw "$Label must be an absolute Windows path: $Path"
    }
    [IO.Path]::GetFullPath($Path)
}

function Test-RetrySamePath {
    param([string]$Left, [string]$Right)
    try {
        $a = (ConvertTo-RetryAbsolutePath $Left).TrimEnd([char[]]"\/")
        $b = (ConvertTo-RetryAbsolutePath $Right).TrimEnd([char[]]"\/")
        return [string]::Equals($a, $b, [StringComparison]::OrdinalIgnoreCase)
    } catch { return $false }
}

function Get-RetryDataDir {
    param([string]$DataDir)
    if ([string]::IsNullOrWhiteSpace($DataDir)) { $DataDir = $env:CODEX_RETRY_DATA_DIR }
    if ([string]::IsNullOrWhiteSpace($DataDir)) { $DataDir = Join-Path (Get-RetryRoot) ".runtime" }
    ConvertTo-RetryAbsolutePath $DataDir "CODEX_RETRY_DATA_DIR"
}

function ConvertTo-RetryArgument {
    param([Parameter(Mandatory)][AllowEmptyString()][string]$Value)
    if ($Value.IndexOf('"') -ge 0 -or $Value.Contains([string][char]10) -or $Value.Contains([string][char]13)) {
        throw "Command arguments cannot contain quotes or line breaks."
    }
    # Windows command-line rules require doubling backslashes before a closing quote.
    $suffix = ""
    for ($i = $Value.Length - 1; $i -ge 0 -and $Value[$i] -eq [char]92; $i--) { $suffix += [char]92 }
    '"' + $Value + $suffix + '"'
}

function Read-RetrySettings {
    param([Parameter(Mandatory)][string]$DataDir)
    $path = Join-Path $DataDir "runtime.json"
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Runtime settings not found: $path. Run install.ps1 with the same CODEX_RETRY_DATA_DIR."
    }
    $settings = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json -ErrorAction Stop
    foreach ($name in @("pythonw", "node", "codex_home", "language")) {
        if ($null -eq $settings -or $null -eq $settings.PSObject.Properties[$name] -or
            $settings.$name -isnot [string] -or [string]::IsNullOrWhiteSpace($settings.$name)) {
            throw "Runtime settings require a nonempty string: $name. Run install.ps1 again."
        }
    }
    foreach ($name in @("pythonw", "node", "codex_home")) {
        $settings.$name = ConvertTo-RetryAbsolutePath $settings.$name "runtime.$name"
    }
    if ($settings.language -cnotin @("auto", "en", "zh")) { throw "runtime.language must be auto, en, or zh." }
    $expected = Join-Path (Get-RetryRoot) ".venv/Scripts/pythonw.exe"
    if (-not (Test-RetrySamePath $settings.pythonw $expected)) {
        throw "runtime.pythonw must belong to this repository: $expected. Reinstall after moving the repository."
    }
    foreach ($name in @("pythonw", "node")) {
        if (-not (Test-Path -LiteralPath $settings.$name -PathType Leaf)) { throw "Configured $name is missing: $($settings.$name). Run install.ps1 again." }
    }
    $settings
}

function Get-RetryPythonInfo {
    param([Parameter(Mandatory)][string]$Executable, [string[]]$Prefix = @())
    $output = & $Executable @Prefix -I -B -c 'import sys; print(sys.version_info.major); print(sys.version_info.minor); print(sys.executable)' 2>$null
    if ($LASTEXITCODE -ne 0 -or @($output).Count -ne 3) { throw "Cannot identify Python: $Executable" }
    $info = [pscustomobject]@{ major = [int]$output[0]; minor = [int]$output[1]; executable = [string]$output[2] }
    if ($info.major -ne 3 -or $info.minor -lt 11 -or $info.minor -gt 14) {
        throw "Python 3.11-3.14 is required; found $($info.major).$($info.minor) at $Executable."
    }
    $info
}

function Find-RetryPython {
    param([string]$Python)
    if ($Python) {
        $command = Get-Command -Name $Python -CommandType Application -ErrorAction Stop | Select-Object -First 1
        return Get-RetryPythonInfo $command.Source
    }
    foreach ($name in @("python.exe", "python3.exe")) {
        $command = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($command -and $command.Source -notlike "*\Microsoft\WindowsApps\*") {
            try { return Get-RetryPythonInfo $command.Source } catch { Write-Verbose $_.Exception.Message }
        }
    }
    $launcher = Get-Command py.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($launcher) {
        foreach ($version in @("-3.14", "-3.13", "-3.12", "-3.11")) {
            try { return Get-RetryPythonInfo $launcher.Source @($version) } catch { Write-Verbose $_.Exception.Message }
        }
    }
    throw "Install Python 3.11-3.14 with venv and tkinter, or pass -Python with its executable path."
}

function Get-RetryNodeVersion {
    param([Parameter(Mandatory)][string]$Node)
    $output = & $Node --version 2>$null
    if ($LASTEXITCODE -ne 0 -or ($output -join "") -notmatch '^v(\d+)\.\d+\.\d+' -or [int]$Matches[1] -lt 22) {
        throw "Node.js 22 or newer must already be installed. Invalid Node executable: $Node"
    }
    ($output -join "").Trim()
}

function Get-RetryPowerShell {
    Join-Path $env:SystemRoot "System32/WindowsPowerShell/v1.0/powershell.exe"
}

function Test-RetryCurrentBootStop {
    param([Parameter(Mandatory)][string]$StopPath)
    if (-not (Test-Path -LiteralPath $StopPath)) { return $false }
    # Fail closed if the boot timestamp cannot be read.
    try {
        $boot = (Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop).LastBootUpTime
        return (Get-Item -LiteralPath $StopPath).LastWriteTimeUtc -ge $boot.ToUniversalTime()
    } catch { return $true }
}

function Get-RetryTaskArguments {
    param([Parameter(Mandatory)][string]$DataDir)
    '-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy RemoteSigned -File ' +
        (ConvertTo-RetryArgument (Join-Path (Get-RetryRoot) "launch.ps1")) +
        ' -Ensure -DataDir ' + (ConvertTo-RetryArgument $DataDir)
}

function Assert-RetryTaskOwnership {
    param([Parameter(Mandatory)]$Task)
    $actions = @($Task.Actions)
    $root = Get-RetryRoot
    $prefix = '-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy RemoteSigned -File ' +
        (ConvertTo-RetryArgument (Join-Path $root "launch.ps1")) + ' -Ensure -DataDir '
    $owned = $false
    if ($actions.Count -eq 1 -and
        (Test-RetrySamePath $actions[0].Execute (Get-RetryPowerShell)) -and
        (Test-RetrySamePath $actions[0].WorkingDirectory $root)) {
        $args = [string]$actions[0].Arguments
        if ($args.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
            $tail = $args.Substring($prefix.Length)
            $owned = $tail.Length -gt 2 -and $tail[0] -eq '"' -and $tail[$tail.Length - 1] -eq '"' -and
                $tail.Substring(1, $tail.Length - 2).IndexOf('"') -lt 0
        }
    }
    if (-not $owned) {
        throw "Refusing to change task '$($Task.TaskName)': its exact action, launch script, or working directory does not belong to this repository. Choose a different -TaskName. No task was changed."
    }
}

function Get-RetryScheduledTask {
    param([Parameter(Mandatory)][string]$TaskName)
    @(Get-ScheduledTask -TaskPath "\" -ErrorAction Stop) | Where-Object {
        [string]::Equals($_.TaskName, $TaskName, [StringComparison]::OrdinalIgnoreCase)
    }
}
