# Functional suite: fresh database, server with the fake language model, black-box tests,
# traceability matrix.
# Usage: powershell -File scripts/functional.ps1 [-Serve]
#   -Serve  prepares the database and keeps the server running in the foreground
#           (for the frontend functional suite); no tests are run.
param(
    [switch]$Serve
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
New-Item -ItemType Directory -Force -Path "docs/evidence" | Out-Null

$Port = 8001
$BaseUrl = "http://127.0.0.1:$Port"
$Professors = @("ft_prof", "ft_prof2")

function Invoke-Step([string]$Name, [scriptblock]$Command) {
    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED: $Name (exit code $LASTEXITCODE)" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

function Import-DotEnv {
    # Values already set in the environment win over .env.
    if (-not (Test-Path ".env")) { return }
    foreach ($line in Get-Content ".env") {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            $name = $Matches[1]
            $value = $Matches[2].Trim().Trim('"')
            if (-not [Environment]::GetEnvironmentVariable($name)) {
                [Environment]::SetEnvironmentVariable($name, $value)
            }
        }
    }
}

function Reset-FunctionalDatabase {
    if (-not $env:FUNCTIONAL_DATABASE_URL) {
        Write-Host "FUNCTIONAL_DATABASE_URL is not set (see .env.example)." -ForegroundColor Red
        exit 1
    }
    $uri = [System.Uri]($env:FUNCTIONAL_DATABASE_URL -replace '^[^:]+://', 'postgres://')
    $database = $uri.AbsolutePath.TrimStart("/")
    $user = $uri.UserInfo.Split(":")[0]
    if ($database -notmatch '^[a-z0-9_]*functional[a-z0-9_]*$') {
        Write-Host "Refusing to drop '$database': the name must contain 'functional'." -ForegroundColor Red
        exit 1
    }
    Invoke-Step "recreate database $database" {
        docker compose exec -T db psql -U $user -d postgres -v ON_ERROR_STOP=1 `
            -c "DROP DATABASE IF EXISTS $database WITH (FORCE);" `
            -c "CREATE DATABASE $database;"
    }
}

function Test-PortBusy {
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $listener
}

function Wait-Server($Process) {
    $deadline = (Get-Date).AddSeconds(60)
    while ((Get-Date) -lt $deadline) {
        if ($Process -and $Process.HasExited) { return $false }
        try {
            $response = Invoke-WebRequest "$BaseUrl/health" -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) { return $true }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    return $false
}

Import-DotEnv
if (-not $env:CODEQUEST_PROFESSOR_PASSWORD) {
    if ($Serve) {
        # Other processes (the frontend suite) must log in as ft_prof, so the password must be known.
        Write-Host "Set CODEQUEST_PROFESSOR_PASSWORD (environment or .env) to use -Serve." -ForegroundColor Red
        exit 1
    }
    # A full run only needs the password inside this process tree.
    $env:CODEQUEST_PROFESSOR_PASSWORD = "ft-" + [guid]::NewGuid().ToString("N")
}
if (Test-PortBusy) {
    Write-Host "Port $Port is already in use; stop the process listening on it first." -ForegroundColor Red
    exit 1
}

# 1. Fresh database with the current schema.
Reset-FunctionalDatabase
$env:DATABASE_URL = $env:FUNCTIONAL_DATABASE_URL
Invoke-Step "alembic upgrade head" { uv run alembic upgrade head }

# 2. Accounts and content. The base game is loaded twice: the second load must add nothing.
foreach ($professor in $Professors) {
    Invoke-Step "create-professor $professor" { uv run python -m app.cli create-professor $professor }
}
Invoke-Step "seed-demo" { uv run python -m app.cli seed-demo }
Invoke-Step "load-base (first load)" { uv run python -m app.cli load-base content/base }
Invoke-Step "load-base (second load)" { uv run python -m app.cli load-base content/base }

# 3. Server settings for the functional run.
$env:LLM_PROVIDER = "fake"
$env:FAKE_LLM_LOG = Join-Path $Root "docs/evidence/fake-llm.jsonl"
$env:HINT_COOLDOWN_SECONDS = "2"
# Tests type wrong passwords on purpose; the login limit would block the later ones.
$env:LOGIN_MAX_ATTEMPTS = "1000"
$env:FUNCTIONAL_BASE_URL = $BaseUrl
Remove-Item $env:FAKE_LLM_LOG -ErrorAction SilentlyContinue

if ($Serve) {
    Write-Host ""
    Write-Host "Serving $BaseUrl (Ctrl+C to stop)" -ForegroundColor Green
    uv run uvicorn app.main:app --port $Port
    exit $LASTEXITCODE
}

$uv = (Get-Command uv).Source
$server = Start-Process -FilePath $uv -ArgumentList @("run", "uvicorn", "app.main:app", "--port", "$Port") `
    -NoNewWindow -PassThru `
    -RedirectStandardOutput "docs/evidence/functional-server.log" `
    -RedirectStandardError "docs/evidence/functional-server-error.log"

$testsExit = 1
try {
    Write-Host ""
    Write-Host "==> waiting for $BaseUrl/health" -ForegroundColor Cyan
    if (-not (Wait-Server $server)) {
        Write-Host "FAILED: the server did not start (see docs/evidence/functional-server-error.log)" -ForegroundColor Red
        exit 1
    }

    # 4. Functional suite.
    Write-Host ""
    Write-Host "==> functional tests" -ForegroundColor Cyan
    uv run pytest tests/functional -m functional -q `
        --junitxml=docs/evidence/functional-junit.xml
    $testsExit = $LASTEXITCODE
} finally {
    # 5. Stop the server (uv starts uvicorn as a child process, so kill the whole tree).
    $ErrorActionPreference = "Continue"
    if ($server -and -not $server.HasExited) {
        taskkill /PID $server.Id /T /F | Out-Null
    }
    $ErrorActionPreference = "Stop"
}

Write-Host ""
Write-Host "==> traceability matrix" -ForegroundColor Cyan
uv run python tools/traceability.py
$traceExit = $LASTEXITCODE

# 6. Fail when a test failed or a requirement has no passing functional test.
if ($testsExit -ne 0 -or $traceExit -ne 0) {
    Write-Host ""
    Write-Host "Functional suite FAILED (tests: $testsExit, traceability: $traceExit)." -ForegroundColor Red
    exit 1
}
Write-Host ""
Write-Host "Functional suite passed." -ForegroundColor Green
