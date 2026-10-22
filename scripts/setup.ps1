[CmdletBinding()]
param(
    [string]$CodexHome,
    [string]$Python,
    [ValidateSet("auto", "en", "zh")][string]$Language = "auto"
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")
$root = Get-RetryRoot
$dataDir = Get-RetryDataDir
$requirements = Join-Path $root "requirements.txt"
if (-not (Test-Path -LiteralPath $requirements -PathType Leaf)) { throw "Missing requirements.txt in $root." }

# Validate prerequisites before creating or changing the environment.
$nodeCommand = Get-Command node.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $nodeCommand) { throw "Node.js 22 or newer must already be installed and available on PATH." }
$node = ConvertTo-RetryAbsolutePath $nodeCommand.Source "Node executable"
$null = Get-RetryNodeVersion $node
$venvPython = Join-Path $root ".venv/Scripts/python.exe"
if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
    $info = Get-RetryPythonInfo $venvPython
    if ($Python) {
        $requested = Find-RetryPython $Python
        if ($requested.major -ne $info.major -or $requested.minor -ne $info.minor) {
            throw "Existing .venv uses Python $($info.major).$($info.minor). Move .venv aside before selecting a different Python version."
        }
    }
} else {
    if (Test-Path -LiteralPath (Join-Path $root ".venv")) { throw "An incomplete .venv already exists. Move it aside and rerun install.ps1." }
    $info = Find-RetryPython $Python
}

$configPath = Join-Path $dataDir "runtime.json"
if (-not $CodexHome -and (Test-Path -LiteralPath $configPath -PathType Leaf)) {
    $existing = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($existing.PSObject.Properties["codex_home"]) { $CodexHome = $existing.codex_home }
}
if (-not $CodexHome) { $CodexHome = $env:CODEX_HOME }
if (-not $CodexHome) { $CodexHome = Join-Path ([Environment]::GetFolderPath("UserProfile")) ".codex" }
$CodexHome = ConvertTo-RetryAbsolutePath $CodexHome "CodexHome"

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    & $info.executable -I -m venv (Join-Path $root ".venv")
    if ($LASTEXITCODE -ne 0) { throw "Python could not create .venv. Install Python with venv/ensurepip, then retry." }
}
$null = Get-RetryPythonInfo $venvPython
& $venvPython -I -m pip --require-virtualenv install --disable-pip-version-check --no-cache-dir -r $requirements
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed. Existing runtime settings were not replaced. Check the pip error and rerun install.ps1." }
& $venvPython -I -B -c 'import tkinter, PIL; print(PIL.__version__)'
if ($LASTEXITCODE -ne 0) { throw "Python must provide tkinter and the required Pillow package." }
$pythonw = Join-Path $root ".venv/Scripts/pythonw.exe"
if (-not (Test-Path -LiteralPath $pythonw -PathType Leaf)) { throw "Missing .venv/Scripts/pythonw.exe; use a standard Windows Python installation." }

$null = New-Item -ItemType Directory -Path $dataDir -Force
$settings = [ordered]@{ pythonw = $pythonw; node = $node; codex_home = $CodexHome; language = $Language.ToLowerInvariant() }
$temporary = Join-Path $dataDir ("runtime." + [guid]::NewGuid().ToString("N") + ".tmp")
try {
    [IO.File]::WriteAllText($temporary, ($settings | ConvertTo-Json), (New-Object Text.UTF8Encoding($false)))
    Move-Item -LiteralPath $temporary -Destination $configPath -Force
} finally {
    if (Test-Path -LiteralPath $temporary -PathType Leaf) { Remove-Item -LiteralPath $temporary -Force }
}
Write-Host "Installed. Runtime settings: $configPath"
Write-Host "No sender was started and no autostart task was registered."
