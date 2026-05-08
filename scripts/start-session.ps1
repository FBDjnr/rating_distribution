$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Runner = Join-Path $ScriptDir "start-session.py"
$ForwardArgs = $args

function Invoke-PythonRunner {
    param(
        [string] $Command,
        [string[]] $PrefixArgs
    )

    $found = Get-Command $Command -ErrorAction SilentlyContinue
    if (-not $found) {
        return $false
    }

    try {
        & $Command @PrefixArgs $Runner @ForwardArgs
        if ($null -eq $LASTEXITCODE) {
            exit 0
        }
        exit $LASTEXITCODE
    }
    catch {
        Write-Host "$Command was found but could not be started. Trying another Python launcher."
        return $false
    }
}

if (Invoke-PythonRunner "python" @()) {
    exit $LASTEXITCODE
}

if (Invoke-PythonRunner "python3" @()) {
    exit $LASTEXITCODE
}

if (Invoke-PythonRunner "py" @("-3")) {
    exit $LASTEXITCODE
}

function Invoke-CondaPython {
    param(
        [string] $Command
    )

    $found = Get-Command $Command -ErrorAction SilentlyContinue
    if (-not $found) {
        return $false
    }

    try {
        & $Command run -n base python $Runner @ForwardArgs
        if ($null -eq $LASTEXITCODE) {
            exit 0
        }
        exit $LASTEXITCODE
    }
    catch {
        Write-Host "$Command was found but could not launch base Python. Trying another option."
        return $false
    }
}

if (Invoke-CondaPython "conda") {
    exit $LASTEXITCODE
}

if (Invoke-CondaPython "mamba") {
    exit $LASTEXITCODE
}

if (Invoke-CondaPython "micromamba") {
    exit $LASTEXITCODE
}

Write-Host "No Python launcher was found. Install Python 3 or make sure Conda's Python is on PATH."
exit 1
