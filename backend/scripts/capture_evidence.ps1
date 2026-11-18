<#
.SYNOPSIS
    Ejecuta la suite DLP/DRP y prepara la evidencia para capturas de pantalla.

.DESCRIPTION
    El script hace cuatro cosas:

    1. Ejecuta backend/scripts/run_dlp_drp_tests.py y guarda la salida en run.log.
    2. Filtra los bloques DLP-01, DLP-02, DR-01 y DR-02 en captures\<prueba>.txt.
    3. Genera manifest.json y hashes.txt con SHA-256 de toda la evidencia.
    4. Opcionalmente captura la ventana en primer plano para cada bloque.

    Cada bloque incluye cabecera con fecha UTC, commit, comando, hash de
    results.json y el resultado PASS/FAIL/INFO. Así la captura de pantalla
    muestra el comando, el resultado y la huella verificable en una sola imagen.

.PARAMETER RepoRoot
    Raíz del repositorio Frostbase. Por defecto se deduce desde la ubicación
    de este script (backend\scripts\..\..).

.PARAMETER EvidenceDir
    Carpeta donde se guardan el log, los JSON y las capturas. Por defecto:
    docs\security\evidence\<yyyy-MM-dd>-demo. Si ya existe run.log y no se
    indica -Force, se agrega un sufijo HHmmss para no sobrescribir.

.PARAMETER RunLog
    Ruta del log de la suite. Por defecto <EvidenceDir>\run.log.

.PARAMETER Python
    Ejecutable de Python. Por defecto "python".

.PARAMETER SkipRun
    No ejecuta la suite; reutiliza un run.log existente para regenerar bloques,
    manifiesto y guía. Útil después de tomar las capturas manuales.

.PARAMETER Force
    Permite usar una carpeta existente o la carpeta oficial 2026-11-15.

.PARAMETER AutoScreenshot
    Captura automáticamente la ventana en primer plano para cada bloque y
    guarda captures\<prueba>.png. La ventana debe estar visible y en primer
    plano durante la cuenta atrás.

.PARAMETER ScreenshotDelay
    Segundos de espera antes de cada captura automática. Por defecto 3.

.PARAMETER OpenFolder
    Abre la carpeta captures al finalizar.

.EXAMPLE
    .\capture_evidence.ps1

.EXAMPLE
    .\capture_evidence.ps1 -EvidenceDir docs\security\evidence\2026-11-16-demo

.EXAMPLE
    .\capture_evidence.ps1 -AutoScreenshot -ScreenshotDelay 5

.EXAMPLE
    # Después de tomar las capturas manualmente, regenerar el manifiesto
    .\capture_evidence.ps1 -EvidenceDir docs\security\evidence\2026-11-16-demo -SkipRun

.NOTES
    La suite devuelve código 1 cuando encuentra FAIL. Eso es esperado: los FAIL
    son hallazgos de seguridad, no errores del procedimiento. El script no
    considera ese código como fallo propio.
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$EvidenceDir = "",
    [string]$RunLog = "",
    [string]$Python = "python",
    [switch]$SkipRun,
    [switch]$Force,
    [switch]$AutoScreenshot,
    [int]$ScreenshotDelay = 3,
    [switch]$OpenFolder
)

$ErrorActionPreference = "Stop"

function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Content
    )
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

function Write-Utf8Bom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Content
    )
    $encoding = New-Object System.Text.UTF8Encoding($true)
    [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

function Get-RelativePath {
    param(
        [Parameter(Mandatory = $true)][string]$Base,
        [Parameter(Mandatory = $true)][string]$Path
    )
    $baseFull = [System.IO.Path]::GetFullPath($Base).TrimEnd('\', '/')
    $pathFull = [System.IO.Path]::GetFullPath($Path)
    if ($pathFull.StartsWith($baseFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $pathFull.Substring($baseFull.Length).TrimStart('\', '/')
    }
    return $pathFull
}

function Get-Sha256 {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Test-CommandAvailable {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

try {
    # ------------------------------------------------------------------
    # 1. Rutas y validaciones
    # ------------------------------------------------------------------
    if (-not $RepoRoot) {
        if ($PSScriptRoot) {
            $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
        } else {
            $RepoRoot = (Get-Location).Path
        }
    } else {
        $RepoRoot = (Resolve-Path $RepoRoot).Path
    }

    $suiteScript = Join-Path $RepoRoot "backend\scripts\run_dlp_drp_tests.py"
    if (-not (Test-Path -LiteralPath $suiteScript)) {
        throw "No se encontró $suiteScript. Use -RepoRoot para indicar la raíz del repositorio."
    }

    if (-not $EvidenceDir) {
        $EvidenceDir = Join-Path $RepoRoot ("docs\security\evidence\{0}-demo" -f (Get-Date -Format "yyyy-MM-dd"))
    } elseif (-not [System.IO.Path]::IsPathRooted($EvidenceDir)) {
        $EvidenceDir = Join-Path $RepoRoot $EvidenceDir
    }
    $EvidenceDir = [System.IO.Path]::GetFullPath($EvidenceDir).TrimEnd('\', '/')

    $officialDir = [System.IO.Path]::GetFullPath(
        (Join-Path $RepoRoot "docs\security\evidence\2026-11-15")
    ).TrimEnd('\', '/')
    if ($EvidenceDir -eq $officialDir -and -not $Force) {
        throw "Negado: $EvidenceDir es la evidencia oficial. Use otra carpeta o -Force para sobrescribir."
    }

    if (-not $SkipRun -and (Test-Path -LiteralPath (Join-Path $EvidenceDir "run.log")) -and -not $Force) {
        $suffix = Get-Date -Format "HHmmss"
        $EvidenceDir = "$EvidenceDir-$suffix"
        Write-Host "La carpeta ya contenía run.log; se usará $EvidenceDir" -ForegroundColor Yellow
    }

    $capturesDir = Join-Path $EvidenceDir "captures"
    New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
    New-Item -ItemType Directory -Force -Path $capturesDir | Out-Null

    if (-not $RunLog) {
        $RunLog = Join-Path $EvidenceDir "run.log"
    } elseif (-not [System.IO.Path]::IsPathRooted($RunLog)) {
        $RunLog = Join-Path $RepoRoot $RunLog
    }
    $RunLog = [System.IO.Path]::GetFullPath($RunLog)

    if (-not (Test-CommandAvailable $Python)) {
        throw "No se encontró el ejecutable '$Python'. Use -Python para indicar la ruta."
    }

    if (-not $SkipRun) {
        if (-not (Test-CommandAvailable "docker")) {
            throw "Docker no está disponible en PATH."
        }
        docker info *> $null
        if ($LASTEXITCODE -ne 0) {
            throw "Docker no está en ejecución. Inicie Docker Desktop y reintente."
        }
        $running = @(docker ps --format "{{.Names}}")
        if ($running -notcontains "frostbase-db") {
            throw "El contenedor frostbase-db no está en ejecución. Ejecute: docker compose up -d db"
        }
        docker image inspect frostbase-v2-app:latest *> $null
        if ($LASTEXITCODE -ne 0) {
            throw "No existe la imagen frostbase-v2-app:latest. Ejecute: docker compose build app"
        }
    } elseif (-not (Test-Path -LiteralPath $RunLog)) {
        throw "No existe el log indicado: $RunLog. Ejecute el script sin -SkipRun primero."
    }

    # ------------------------------------------------------------------
    # 2. Contexto
    # ------------------------------------------------------------------
    $generatedAt = (Get-Date).ToUniversalTime().ToString("o")
    $commit = "unknown"
    $branch = "unknown"
    if (Test-CommandAvailable "git") {
        try { $commit = ((& git -C $RepoRoot rev-parse --short HEAD 2>$null) | Out-String).Trim() } catch { }
        try { $branch = ((& git -C $RepoRoot rev-parse --abbrev-ref HEAD 2>$null) | Out-String).Trim() } catch { }
    }
    $pythonVersion = ((& $Python --version 2>&1) | Out-String).Trim()
    $osCaption = "unknown"
    try { $osCaption = (Get-CimInstance Win32_OperatingSystem).Caption } catch { }

    $suiteCommand = "$Python backend/scripts/run_dlp_drp_tests.py --evidence-dir `"$EvidenceDir`""
    $context = [ordered]@{
        generated_at     = $generatedAt
        commit           = $commit
        branch           = $branch
        host             = $env:COMPUTERNAME
        user             = $env:USERNAME
        os               = $osCaption
        powershell       = $PSVersionTable.PSVersion.ToString()
        python           = $pythonVersion
        evidence_dir     = $EvidenceDir
        suite_command    = $suiteCommand
        suite_exit_code  = $null
    }

    # ------------------------------------------------------------------
    # 3. Ejecutar la suite
    # ------------------------------------------------------------------
    $suiteExit = $null
    if (-not $SkipRun) {
        Write-Host ""
        Write-Host "== Ejecutando suite DLP/DRP ==" -ForegroundColor Cyan
        Write-Host "Evidencia: $EvidenceDir"
        Write-Host "Log:       $RunLog"
        Write-Host "Nota: la suite devuelve código 1 cuando hay FAIL; es el resultado esperado."
        Write-Host ""

        & $Python $suiteScript --evidence-dir $EvidenceDir 2>&1 |
            Tee-Object -FilePath $RunLog
        $suiteExit = $LASTEXITCODE

        Write-Host ""
        Write-Host "Suite finalizada con código: $suiteExit" -ForegroundColor Yellow
    } else {
        Write-Host "Modo -SkipRun: se reutiliza $RunLog" -ForegroundColor Cyan
    }

    $resultsPath = Join-Path $EvidenceDir "results.json"
    $resultsHash = Get-Sha256 $resultsPath
    $resultsGeneratedAt = $null
    $summaryCounts = $null
    if ($resultsHash) {
        try {
            $resultsData = Get-Content -LiteralPath $resultsPath -Raw | ConvertFrom-Json
            $summaryCounts = $resultsData.summary
            $resultsGeneratedAt = $resultsData.generated_at
        } catch {
            Write-Warning "No se pudo leer results.json: $($_.Exception.Message)"
        }
    } else {
        $resultsHash = "N/A"
        Write-Warning "No se encontró results.json; los bloques se generarán solo desde el log."
    }

    # En -SkipRun no hay código de salida de la suite. Se deduce del resumen:
    # FAIL o ERROR implican código 1; si no, 0. Si no hay results.json, "not-run".
    if ($null -eq $suiteExit) {
        if ($summaryCounts) {
            $failCount = [int]$summaryCounts.FAIL
            $errorCount = [int]$summaryCounts.ERROR
            $suiteExit = if (($failCount + $errorCount) -gt 0) { 1 } else { 0 }
        } else {
            $suiteExit = "not-run"
        }
    }

    $context.suite_exit_code = $suiteExit
    $context.suite_results_generated_at = $resultsGeneratedAt
    Write-Utf8NoBom -Path (Join-Path $EvidenceDir "context.json") `
        -Content (($context | ConvertTo-Json -Depth 5) + "`r`n")

    # La cabecera de los bloques debe mostrar el instante de la suite, no el
    # instante en que se regeneran los bloques con -SkipRun.
    $suiteTimestamp = if ($resultsGeneratedAt) { $resultsGeneratedAt } else { $generatedAt }

    # ------------------------------------------------------------------
    # 4. Bloques listos para captura
    # ------------------------------------------------------------------
    $tests = @(
        [pscustomobject]@{ Id = "DLP-01"; Title = "Control de acceso y exfiltración" },
        [pscustomobject]@{ Id = "DLP-02"; Title = "Borrado lógico, integridad y trazabilidad" },
        [pscustomobject]@{ Id = "DR-01"; Title = "Respaldo lógico y restauración completa" },
        [pscustomobject]@{ Id = "DR-02"; Title = "Pérdida total de la base y recuperación" }
    )

    $logLines = @(Get-Content -LiteralPath $RunLog)
    $generated = @()

    foreach ($test in $tests) {
        $pattern = '^\[(OK|FALLO|INFO)\]\s+' + [regex]::Escape($test.Id) + '\.'
        $lines = @($logLines | Where-Object { $_ -match $pattern })
        $pass = @($lines | Where-Object { $_ -match '^\[OK\]' }).Count
        $fail = @($lines | Where-Object { $_ -match '^\[FALLO\]' }).Count
        $info = @($lines | Where-Object { $_ -match '^\[INFO\]' }).Count

        $header = @(
            ("=" * 78),
            "PRUEBA:     $($test.Id) - $($test.Title)",
            "EJECUCIÓN:  $suiteTimestamp",
            "COMMIT:     $commit",
            "EVIDENCIA:  results.json SHA-256 $resultsHash",
            "COMANDO:    $suiteCommand",
            "RESULTADO:  $pass PASS / $fail FAIL / $info INFO",
            "CAPTURA:    incluya esta cabecera y las líneas de resultado",
            ("=" * 78),
            ""
        ) -join "`r`n"

        if ($lines.Count -eq 0) {
            $body = "No se encontraron líneas para $($test.Id) en $RunLog."
            Write-Warning $body
        } else {
            $body = $lines -join "`r`n"
        }

        $footer = @(
            "",
            ("-" * 78),
            "Leyenda: [OK]=PASS, [FALLO]=hallazgo, [INFO]=informativo.",
            "Los FAIL son hallazgos de seguridad, no errores del procedimiento.",
            "Evidencia estructurada: results.json / summary.md"
        ) -join "`r`n"

        $blockText = $header + $body + "`r`n" + $footer + "`r`n"
        $blockPath = Join-Path $capturesDir ("$($test.Id).txt")
        Write-Utf8Bom -Path $blockPath -Content $blockText

        $generated += [pscustomobject]@{
            Id    = $test.Id
            Title = $test.Title
            Path  = $blockPath
            Pass  = $pass
            Fail  = $fail
            Info  = $info
            Text  = $blockText
        }
    }

    # ------------------------------------------------------------------
    # 5. Captura automática opcional
    # ------------------------------------------------------------------
    $capturedPngs = 0
    if ($AutoScreenshot) {
        if (-not [Environment]::UserInteractive) {
            Write-Warning "Sesión no interactiva: se omite -AutoScreenshot."
        } else {
            try {
                Add-Type -AssemblyName System.Drawing
                Add-Type -AssemblyName System.Windows.Forms

                if (-not ("FrostbaseCapture" -as [type])) {
                    Add-Type @"
using System;
using System.Runtime.InteropServices;

[StructLayout(LayoutKind.Sequential)]
public struct FrostbaseRect
{
    public int Left;
    public int Top;
    public int Right;
    public int Bottom;
}

public class FrostbaseCapture
{
    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out FrostbaseRect lpRect);

    [DllImport("user32.dll")]
    public static extern bool SetProcessDPIAware();
}
"@
                }

                [FrostbaseCapture]::SetProcessDPIAware() | Out-Null

                try {
                    $raw = $Host.UI.RawUI
                    $max = $raw.MaxWindowSize
                    $width = [Math]::Min(200, $max.Width)
                    $height = [Math]::Min(60, $max.Height)
                    $raw.WindowSize = New-Object System.Management.Automation.Host.Size($width, $height)
                } catch { }

                foreach ($capture in $generated) {
                    try { Clear-Host } catch { }
                    Write-Host $capture.Text
                    Write-Host ""
                    Write-Host "Captura automática de $($capture.Id) en $ScreenshotDelay segundos..." -ForegroundColor Yellow
                    Write-Host "Mantenga esta ventana en primer plano." -ForegroundColor Yellow
                    Start-Sleep -Seconds $ScreenshotDelay

                    $pngPath = Join-Path $capturesDir ("$($capture.Id).png")
                    try {
                        $hWnd = [FrostbaseCapture]::GetForegroundWindow()
                        $rect = New-Object FrostbaseRect
                        if (-not [FrostbaseCapture]::GetWindowRect($hWnd, [ref]$rect)) {
                            throw "GetWindowRect falló"
                        }
                        $width = $rect.Right - $rect.Left
                        $height = $rect.Bottom - $rect.Top
                        if ($width -le 0 -or $height -le 0) {
                            throw "La ventana no tiene un tamaño válido"
                        }

                        $bitmap = New-Object System.Drawing.Bitmap($width, $height)
                        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
                        try {
                            $graphics.CopyFromScreen(
                                $rect.Left, $rect.Top, 0, 0,
                                (New-Object System.Drawing.Size($width, $height))
                            )
                            $bitmap.Save($pngPath, [System.Drawing.Imaging.ImageFormat]::Png)
                        } finally {
                            $graphics.Dispose()
                            $bitmap.Dispose()
                        }
                        $capturedPngs++
                        Write-Host "Captura guardada: $pngPath" -ForegroundColor Green
                    } catch {
                        Write-Warning "No se pudo capturar $($capture.Id): $($_.Exception.Message)"
                    }
                    Start-Sleep -Seconds 1
                }
            } catch {
                Write-Warning "No se pudo inicializar la captura automática: $($_.Exception.Message)"
            }
        }
    }

    # ------------------------------------------------------------------
    # 6. Guía de capturas
    # ------------------------------------------------------------------
    $guideHeader = @"
# Guía de capturas DLP/DRP

- Ejecución: $suiteTimestamp
- Commit: $commit
- Suite exit code: $($context.suite_exit_code) (1 = hay FAIL, esperado)
- results.json SHA-256: $resultsHash
- Carpeta: $EvidenceDir

"@

    $guideBody = @'
## Capturas principales

| Prueba | Bloque listo | Captura PNG | Qué debe verse |
| --- | --- | --- | --- |
| DLP-01 | `captures\DLP-01.txt` | `captures\DLP-01.png` | 401 anónimo, 403 RBAC, 401 token, PII redactada |
| DLP-02 | `captures\DLP-02.txt` | `captures\DLP-02.png` | estado CO, active=false, FK, recovered=true |
| DR-01 | `captures\DR-01.txt` | `captures\DR-01.png` | expected_digest == actual_digest, differences=[] |
| DR-02 | `captures\DR-02.txt` | `captures\DR-02.png` | exists_after_drop=false, checksums_match=true, rto_seconds |

## Cómo capturar manualmente

1. Abra `captures\<PRUEBA>.txt` en un editor o terminal.
2. Maximice la ventana y use una fuente legible (14-16 pt).
3. Verifique que se vean la cabecera, el comando y todas las líneas de resultado.
4. Capture con `Win + Shift + S` y guarde como `captures\<PRUEBA>.png`.
5. Ejecute de nuevo este script con `-SkipRun` para incluir los PNG en `manifest.json`.

## Reglas de evidencia

- No oculte los `[FALLO]`: son hallazgos de seguridad, no errores del procedimiento.
- No muestre PII real. La suite ya entrega una muestra redactada.
- No recorte el comando ni la cabecera: son parte de la evidencia.
- Use el mismo `results.json` para las cuatro capturas y muestre su SHA-256.
'@

    $guide = $guideHeader + $guideBody + "`r`n"
    Write-Utf8Bom -Path (Join-Path $EvidenceDir "capture-guide.md") -Content $guide

    # ------------------------------------------------------------------
    # 7. Manifiesto SHA-256
    # ------------------------------------------------------------------
    $manifestPath = Join-Path $EvidenceDir "manifest.json"
    $hashesPath = Join-Path $EvidenceDir "hashes.txt"
    $excluded = @(
        [System.IO.Path]::GetFullPath($manifestPath),
        [System.IO.Path]::GetFullPath($hashesPath)
    )

    $files = @(
        Get-ChildItem -LiteralPath $EvidenceDir -Recurse -File |
            Where-Object { $excluded -notcontains $_.FullName } |
            Sort-Object FullName
    )

    $entries = foreach ($file in $files) {
        [pscustomobject]@{
            path   = Get-RelativePath -Base $EvidenceDir -Path $file.FullName
            bytes  = $file.Length
            sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
        }
    }

    $scriptPath = $MyInvocation.MyCommand.Path
    $scriptHash = Get-Sha256 $scriptPath

    $manifest = [ordered]@{
        generated_at    = (Get-Date).ToUniversalTime().ToString("o")
        commit          = $commit
        branch          = $branch
        host            = $env:COMPUTERNAME
        user            = $env:USERNAME
        os              = $osCaption
        powershell      = $PSVersionTable.PSVersion.ToString()
        python          = $pythonVersion
        evidence_dir    = $EvidenceDir
        suite_exit_code = $context.suite_exit_code
        results_sha256  = $resultsHash
        script          = $scriptPath
        script_sha256   = $scriptHash
        files           = @($entries)
    }

    Write-Utf8NoBom -Path $manifestPath `
        -Content (($manifest | ConvertTo-Json -Depth 6) + "`r`n")

    $hashLines = $entries | ForEach-Object { "$($_.sha256)  $($_.path)" }
    Write-Utf8NoBom -Path $hashesPath `
        -Content (($hashLines -join "`r`n") + "`r`n")

    # ------------------------------------------------------------------
    # 8. Resumen
    # ------------------------------------------------------------------
    Write-Host ""
    Write-Host "== Evidencia generada ==" -ForegroundColor Green
    Write-Host "Carpeta:             $EvidenceDir"
    Write-Host "results.json SHA-256: $resultsHash"
    foreach ($item in $generated) {
        Write-Host ("  {0}: {1} PASS / {2} FAIL / {3} INFO -> {4}" -f `
            $item.Id, $item.Pass, $item.Fail, $item.Info, $item.Path)
    }
    Write-Host "Manifiesto:          $manifestPath"
    Write-Host "Hashes:              $hashesPath"
    Write-Host "Guía:                $(Join-Path $EvidenceDir 'capture-guide.md')"
    if ($AutoScreenshot) {
        Write-Host "Capturas automáticas: $capturedPngs de $($generated.Count)"
    }
    if ($suiteExit -eq 1) {
        if ($SkipRun) {
            Write-Host "Nota: results.json contiene FAIL; el código equivalente es 1." -ForegroundColor Yellow
        } else {
            Write-Host "Nota: la suite devolvió 1 porque hay FAIL; es el resultado esperado del análisis." -ForegroundColor Yellow
        }
    }

    if ($OpenFolder) {
        Invoke-Item $capturesDir
    }

    if ($generated.Count -eq 0 -or -not (Test-Path -LiteralPath $resultsPath)) {
        exit 1
    }
    exit 0
} catch {
    Write-Host ""
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 2
}
