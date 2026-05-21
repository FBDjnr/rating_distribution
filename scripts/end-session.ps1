$ErrorActionPreference = "Stop"
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Runner = Join-Path $ScriptDir "end-session.py"
$ForwardArgs = $args

function Test-WindowsStoreAlias {
    param(
        $CommandInfo
    )

    $paths = @($CommandInfo.Source, $CommandInfo.Path, $CommandInfo.Definition) | Where-Object { $_ }
    foreach ($path in $paths) {
        if ($path -like "*\Microsoft\WindowsApps\*") {
            return $true
        }
    }
    return $false
}

function Invoke-PythonRunner {
    param(
        [string] $Command,
        [string[]] $PrefixArgs
    )

    $found = Get-Command $Command -ErrorAction SilentlyContinue
    if (-not $found) {
        return
    }
    if (Test-WindowsStoreAlias $found) {
        return
    }

    try {
        & $Command @PrefixArgs --version *> $null
        if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
            return
        }

        & $Command @PrefixArgs $Runner @ForwardArgs
        if ($null -eq $LASTEXITCODE) {
            exit 0
        }
        exit $LASTEXITCODE
    }
    catch {
        Write-Host "$Command was found but could not be started. Trying another Python launcher."
        return
    }
}

Invoke-PythonRunner "python" @()
Invoke-PythonRunner "python3" @()
Invoke-PythonRunner "py" @("-3")

function Invoke-CondaPython {
    param(
        [string] $Command
    )

    $found = Get-Command $Command -ErrorAction SilentlyContinue
    if (-not $found) {
        return
    }

    try {
        $BasePath = & $Command info --base 2>$null | Where-Object { $_ } | Select-Object -First 1
        if (-not $BasePath) {
            return
        }

        $PythonCandidates = @(
            (Join-Path $BasePath "python.exe"),
            (Join-Path $BasePath "bin/python3"),
            (Join-Path $BasePath "bin/python")
        )
        $Python = $PythonCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
        if (-not $Python) {
            return
        }

        Write-Host "Using $Command base Python: $Python"
        & $Python $Runner @ForwardArgs
        if ($null -eq $LASTEXITCODE) {
            exit 0
        }
        exit $LASTEXITCODE
    }
    catch {
        Write-Host "$Command was found but could not launch base Python. Trying another option."
        return
    }
}

Invoke-CondaPython "conda"
Invoke-CondaPython "mamba"
Invoke-CondaPython "micromamba"

Write-Host "No Python launcher was found. Install Python 3 or make sure Conda's Python is on PATH."
exit 1
