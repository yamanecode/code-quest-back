# Quality gate: lint, layer contracts, migrations and internal tests with coverage.
# Usage: powershell -File scripts/check.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
New-Item -ItemType Directory -Force -Path "docs/evidence" | Out-Null

function Invoke-Step([string]$Name, [scriptblock]$Command) {
    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED: $Name (exit code $LASTEXITCODE)" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Invoke-Step "ruff check" { uv run ruff check . }
Invoke-Step "ruff format --check" { uv run ruff format --check . }
Invoke-Step "lint-imports" { uv run lint-imports }

Invoke-Step "alembic check" { uv run alembic check }

$TestDirs = @(@("tests/unit", "tests/integration") | Where-Object { Test-Path $_ })
Invoke-Step "internal tests" {
    uv run pytest @TestDirs -q `
        --junitxml=docs/evidence/internal-junit.xml `
        --cov=app --cov-report=term --cov-report=xml:docs/evidence/coverage.xml
}

Invoke-Step "domain coverage 100 %" {
    uv run coverage report --include="app/domain/*" --show-missing --fail-under=100
}

Write-Host ""
Write-Host "Quality gate passed." -ForegroundColor Green
