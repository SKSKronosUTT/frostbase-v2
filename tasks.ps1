# Tareas de desarrollo de FrostBase (Windows / PowerShell).
# Uso: .\tasks.ps1 dev | test | lint | build | seed | e2e | help

param(
    [Parameter(Position = 0)]
    [ValidateSet("dev", "up", "down", "test", "lint", "build", "seed", "e2e", "backup", "ai-probe", "ai-prompt", "net-check", "clean-alerts", "help")]
    [string]$Task = "help",
    [switch]$Reset,
    [switch]$PrintKeys,
    [int]$Trucks = 3,
    [int]$Devices = 2,
    [string]$Keep = "14",
    [string]$HostIp = "",
    [switch]$NoPrompt,
    [switch]$NoToken,
    [switch]$Apply,
    [switch]$KeepDevices,
    [int]$OlderThanDays = -1,
    [string]$Prefix = ""
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
    $previousEncoding = [Console]::OutputEncoding
    $previousUtf8 = $env:PYTHONUTF8
    try {
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        $env:PYTHONUTF8 = "1"
        & $Python @Arguments
    } finally {
        $env:PYTHONUTF8 = $previousUtf8
        [Console]::OutputEncoding = $previousEncoding
        Pop-Location
    }
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
        $arguments = @("-m", "scripts.agent_prompt")
        if ($NoToken) { $arguments += "--no-token" }
        Invoke-BackendPython $arguments
    }
    "net-check" {
        $arguments = @("-m", "scripts.network_check")
        if ($HostIp) { $arguments += @("--host-ip", $HostIp) }
        if ($NoPrompt) { $arguments += "--no-prompt" }
        if ($NoToken) { $arguments += "--no-token" }
        Invoke-BackendPython $arguments
    }
    "clean-alerts" {
        $arguments = @(
            "compose", "exec", "-T", "app", "python", "-m",
            "scripts.resolve_stale_alerts"
        )
        if ($Apply) { $arguments += "--apply" }
        if ($KeepDevices) { $arguments += "--keep-devices" }
        if ($OlderThanDays -ge 0) {
            $arguments += @("--older-than-days", "$OlderThanDays")
        }
        if ($Prefix) {
            foreach ($item in $Prefix.Split(",")) {
                if ($item.Trim()) {
                    $arguments += @("--device-prefix", $item.Trim())
                }
            }
        }
        & docker @arguments
    }
    default {
        Write-Host "Tareas disponibles:"
        Write-Host "  .\tasks.ps1 dev            Levanta el stack con build"
        Write-Host "  .\tasks.ps1 test           Ejecuta pytest con PostgreSQL real"
        Write-Host "  .\tasks.ps1 lint           ruff + mypy + ESLint + Prettier + checks"
        Write-Host "  .\tasks.ps1 build          Genera frontend/build con assets hasheados"
        Write-Host "  .\tasks.ps1 seed -Reset -PrintKeys -Trucks 20 -Devices 10"
        Write-Host "  .\tasks.ps1 e2e            Playwright (requiere navegadores instalados)"
        Write-Host "  .\tasks.ps1 net-check      Diagnostico de red y prompt tras cambiar de red"
        Write-Host "                           .\tasks.ps1 net-check -HostIp 192.168.1.45 -NoToken"
        Write-Host "  .\tasks.ps1 clean-alerts   Simula la limpieza de alertas LOAD-/E2E-"
        Write-Host "                           .\tasks.ps1 clean-alerts -Apply [-OlderThanDays 2]"
        Write-Host "  .\tasks.ps1 backup         Respaldo pg_dump (-Fc) con retención (default 14)"
        Write-Host "                           .\tasks.ps1 backup -Keep 30"
        Write-Host "  .\tasks.ps1 ai-probe       Sondeo A0 del agente ESP-Claw (HTTP + WebSocket)"
        Write-Host "  .\tasks.ps1 ai-prompt      Prompt de operación con URL y token (contiene secreto)"
    }
}
