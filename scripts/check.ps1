param([Parameter(Mandatory = $true)][int]$Phase)

$ErrorActionPreference = "Continue"
$results = @()

function Invoke-Step([string]$Name, [scriptblock]$Command) {
    Write-Host "`n=== $Name ===" -ForegroundColor Cyan
    & $Command
    $ok = ($LASTEXITCODE -eq 0)
    $script:results += [pscustomobject]@{ Step = $Name; Result = $(if ($ok) { "PASS" } else { "FAIL" }) }
    if (-not $ok) {
        $script:results | Format-Table -AutoSize
        Write-Host "Gate for phase $Phase FAILED at: $Name" -ForegroundColor Red
        exit 1
    }
}

New-Item -ItemType Directory -Force -Path docs/evidence | Out-Null

Invoke-Step "ruff check" { uv run ruff check . }
Invoke-Step "ruff format --check" { uv run ruff format --check . }
if ($Phase -ge 1) {
    Invoke-Step "lint-imports" { uv run lint-imports }
    Invoke-Step "alembic check" { uv run alembic check }
}
Invoke-Step "pytest + coverage" {
    uv run pytest --cov=app --cov-report=xml:docs/evidence/coverage.xml `
        --cov-report=html:docs/evidence/htmlcov --junitxml=docs/evidence/junit.xml -m "not live"
}
Invoke-Step "traceability" { uv run python tools/traceability.py --phase $Phase }

$results | Format-Table -AutoSize
Write-Host "Gate for phase $Phase PASSED" -ForegroundColor Green
exit 0
