# Tareas de desarrollo de FrostBase (Windows / PowerShell).
# Uso: .\tasks.ps1 dev | test | lint | build | seed | e2e | help

param(
    [Parameter(Position = 0)]
    [ValidateSet("dev", "up", "down", "test", "lint", "build", "seed", "e2e", "backup", "ai-probe", "ai-prompt", "help")]
    [string]$Task = "help",
    [switch]$Reset,
    [switch]$PrintKeys,
    [int]$Trucks = 3,
    [int]$Devices = 2,
    [string]$Keep = "14"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"

function Invoke-BackendPython {
    param([string[]]$Arguments)
    if (-not (Test-Path $Python)) {
        throw "No existe $Python. Cree el entorno con: python -m venv backend\.venv && pip install -r backend\requirements-dev.txt"
    }
    Push-Location $Backend
    try { & $Python @Arguments } finally { Pop-Location }
}

switch ($Task) {
    "dev" { docker compose up -d --build }
    "up" { docker compose up -d }
    "down" { docker compose down }
    "test" {
        docker compose -f compose.test.yml up -d --wait
        try {
            Invoke-BackendPython @("-m", "pytest", "--cov=app", "--cov-report=term-missing", "--cov-fail-under=70")
        } finally {
            docker compose -f compose.test.yml down | Out-Null
        }
    }
    "lint" {
        Invoke-BackendPython @("-m", "ruff", "check", ".")
        Invoke-BackendPython @("-m", "ruff", "format", "--check", ".")
        Invoke-BackendPython @("-m", "mypy", "app")
        Push-Location $Frontend
        try {
            npx --yes eslint@8 js
            npx --yes prettier@3 --check js css
            npm run check:css
            npm run check:html
        } finally { Pop-Location }
    }
    "build" {
        Push-Location $Frontend
        try { npm run build } finally { Pop-Location }
    }
    "seed" {
        $arguments = @("-m", "scripts.seed_demo", "--trucks", $Trucks, "--devices", $Devices)
        if ($Reset) { $arguments += "--reset" }
        if ($PrintKeys) { $arguments += "--print-keys" }
        Invoke-BackendPython $arguments
    }
    "e2e" {
        Push-Location $Frontend
        try { npx playwright test } finally { Pop-Location }
    }
    "backup" {
        Invoke-BackendPython @("-m", "scripts.backup_db", "--keep", $Keep)
    }
    "ai-probe" {
        Invoke-BackendPython @("-m", "scripts.ai_probe", "--mode", "both")
    }
    "ai-prompt" {
        Invoke-BackendPython @("-m", "scripts.agent_prompt")
    }
    default {
        Write-Host "Tareas disponibles:"
        Write-Host "  .\tasks.ps1 dev            Levanta el stack con build"
        Write-Host "  .\tasks.ps1 test           Ejecuta pytest con PostgreSQL real"
        Write-Host "  .\tasks.ps1 lint           ruff + mypy + ESLint + Prettier + checks"
        Write-Host "  .\tasks.ps1 build          Genera frontend/build con assets hasheados"
        Write-Host "  .\tasks.ps1 seed -Reset -PrintKeys -Trucks 20 -Devices 10"
        Write-Host "  .\tasks.ps1 e2e            Playwright (requiere navegadores instalados)"
        Write-Host "  .\tasks.ps1 backup         Respaldo pg_dump (-Fc) con retención (default 14)"
        Write-Host "                           .\tasks.ps1 backup -Keep 30"
        Write-Host "  .\tasks.ps1 ai-probe       Sondeo A0 del agente ESP-Claw (HTTP + WebSocket)"
        Write-Host "  .\tasks.ps1 ai-prompt      Prompt de operación con URL y token (contiene secreto)"
    }
}
