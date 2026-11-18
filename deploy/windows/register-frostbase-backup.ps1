<#
.SYNOPSIS
    Registra el respaldo diario de Frostbase en el Programador de tareas.

.DESCRIPTION
    Crea o reemplaza la tarea "Frostbase Backup", que ejecuta
    deploy\windows\frostbase-backup.ps1 con la ruta real de este repositorio.

    Antes de registrar valida el script de respaldo, Python y la passphrase.
    Con -CreatePassphrase genera la passphrase si no existe y restringe sus ACL.
    Nunca sobrescribe una passphrase existente, porque eso invalidaría los
    respaldos anteriores.

.PARAMETER RepoRoot
    Raíz del repositorio. Si se omite, se deduce desde la ubicación del script.

.PARAMETER BackupDir
    Carpeta local de respaldos. Si se omite, se usa
    %USERPROFILE%\FrostbaseBackups.

.PARAMETER MirrorDir
    Carpeta externa para la copia espejo. Vacío para deshabilitar.

.PARAMETER PassphraseFile
    Archivo con la passphrase del respaldo.

.PARAMETER Database
    Base de datos a respaldar.

.PARAMETER RetentionDays
    Días de retención para --prune.

.PARAMETER KeepLast
    Cantidad mínima de respaldos recientes que siempre se conservan.

.PARAMETER LogDir
    Carpeta de logs del respaldo.

.PARAMETER Python
    Ejecutable de Python. Use la ruta completa si no está en PATH.

.PARAMETER TaskName
    Nombre de la tarea en el Programador de tareas.

.PARAMETER At
    Hora diaria en formato 24 h. Por defecto 02:15.

.PARAMETER CreatePassphrase
    Crea la passphrase si no existe. No sobrescribe una existente.

.PARAMETER RunNow
    Inicia la tarea inmediatamente después de registrarla.

.PARAMETER Force
    Reemplaza la tarea si ya existe.

.EXAMPLE
    .\deploy\windows\register-frostbase-backup.ps1 -CreatePassphrase -RunNow

.EXAMPLE
    .\deploy\windows\register-frostbase-backup.ps1 `
        -BackupDir D:\Backups\frostbase `
        -MirrorDir E:\Offsite\frostbase `
        -Force

.NOTES
    La tarea se registra con el usuario actual y LogonType Interactive: solo
    corre con la sesión iniciada, porque Docker Desktop depende del perfil del
    usuario. No use SYSTEM.
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$BackupDir = "",
    [string]$MirrorDir = "",
    [string]$PassphraseFile = "C:\ProgramData\Frostbase\backup.pass",
    [string]$Database = "frostbase",
    [int]$RetentionDays = 30,
    [int]$KeepLast = 7,
    [string]$LogDir = "C:\ProgramData\Frostbase\logs",
    [string]$Python = "python",
    [string]$TaskName = "Frostbase Backup",
    [string]$At = "02:15",
    [switch]$CreatePassphrase,
    [switch]$RunNow,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Fail {
    param([string]$Message)
    Write-Host ""
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 2
}

try {
    # ------------------------------------------------------------------
    # 1. Rutas
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

    $backupScript = Join-Path $RepoRoot "deploy\windows\frostbase-backup.ps1"
    if (-not (Test-Path -LiteralPath $backupScript)) {
        Fail "No se encontró $backupScript. Use -RepoRoot para indicar la raíz del repositorio."
    }

    if (-not $BackupDir) {
        $BackupDir = Join-Path $env:USERPROFILE "FrostbaseBackups"
    }
    $BackupDir = [System.IO.Path]::GetFullPath($BackupDir)
    $PassphraseFile = [System.IO.Path]::GetFullPath($PassphraseFile)
    $LogDir = [System.IO.Path]::GetFullPath($LogDir)

    if ($MirrorDir) {
        $MirrorDir = [System.IO.Path]::GetFullPath($MirrorDir)
    }

    if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
        Fail "No se encontró el ejecutable '$Python'. Use -Python con la ruta completa."
    }

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Warning "Docker no está en PATH. La tarea fallará hasta que Docker Desktop esté disponible."
    }

    # ------------------------------------------------------------------
    # 2. Passphrase
    # ------------------------------------------------------------------
    if (-not (Test-Path -LiteralPath $PassphraseFile)) {
        if (-not $CreatePassphrase) {
            Fail "No existe $PassphraseFile. Créelo o ejecute este script con -CreatePassphrase."
        }

        $passDir = Split-Path -Parent $PassphraseFile
        if ($passDir) {
            New-Item -ItemType Directory -Force -Path $passDir | Out-Null
        }

        $secret = (& $Python -c "import secrets; print(secrets.token_urlsafe(32))" | Out-String).Trim()
        if (-not $secret -or $secret.Length -lt 32) {
            Fail "No se pudo generar la passphrase con $Python."
        }

        $encoding = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($PassphraseFile, $secret, $encoding)
        Write-Host "Passphrase creada: $PassphraseFile" -ForegroundColor Green

        if (Get-Command icacls -ErrorAction SilentlyContinue) {
            & icacls $PassphraseFile /inheritance:r /grant:r "$($env:USERNAME):M" "*S-1-5-32-544:F" | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "No se pudieron ajustar las ACL de $PassphraseFile. Revise los permisos manualmente."
            }
        }
    } else {
        $existing = [System.IO.File]::ReadAllText($PassphraseFile).Trim()
        if ($existing.Length -lt 12) {
            Fail "La passphrase de $PassphraseFile es demasiado corta (mínimo 12 caracteres)."
        }
        Write-Host "Passphrase existente: $PassphraseFile" -ForegroundColor Green
    }

    try {
        New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    } catch {
        Write-Warning "No se pudo crear la carpeta de logs '$LogDir': $($_.Exception.Message)"
    }

    # ------------------------------------------------------------------
    # 3. Tarea existente
    # ------------------------------------------------------------------
    $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existingTask -and -not $Force) {
        Fail "La tarea '$TaskName' ya existe. Use -Force para reemplazarla."
    }

    # ------------------------------------------------------------------
    # 4. Registrar
    # ------------------------------------------------------------------
    $taskArguments = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$backupScript`"",
        "-RepoRoot", "`"$RepoRoot`"",
        "-BackupDir", "`"$BackupDir`"",
        "-PassphraseFile", "`"$PassphraseFile`"",
        "-Database", "`"$Database`"",
        "-RetentionDays", "$RetentionDays",
        "-KeepLast", "$KeepLast",
        "-LogDir", "`"$LogDir`"",
        "-Python", "`"$Python`""
    )
    if ($MirrorDir) {
        $taskArguments += @("-MirrorDir", "`"$MirrorDir`"")
    }
    $argumentLine = $taskArguments -join " "

    $currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $argumentLine
    $trigger = New-ScheduledTaskTrigger -Daily -At $At
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
        -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal -UserId $currentUser `
        -LogonType Interactive -RunLevel Limited

    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal `
        -Description "Respaldo diario cifrado y verificado de Frostbase" `
        -Force:$Force | Out-Null

    $task = Get-ScheduledTask -TaskName $TaskName
    $info = Get-ScheduledTaskInfo -TaskName $TaskName

    Write-Host ""
    Write-Host "Tarea registrada correctamente" -ForegroundColor Green
    Write-Host "  Nombre:      $($task.TaskName)"
    Write-Host "  Estado:      $($task.State)"
    Write-Host "  Usuario:     $currentUser"
    Write-Host "  Próxima:     $($info.NextRunTime)"
    Write-Host "  Repositorio: $RepoRoot"
    Write-Host "  Respaldos:   $BackupDir"
    Write-Host "  Passphrase:  $PassphraseFile"
    Write-Host "  Logs:        $LogDir"
    if ($MirrorDir) {
        Write-Host "  Espejo:      $MirrorDir"
    }
    Write-Host ""
    Write-Host "La tarea solo corre con la sesión iniciada, porque Docker Desktop depende del perfil del usuario." -ForegroundColor Yellow
    Write-Host "Si Register-ScheduledTask devuelve 'Acceso denegado', abra PowerShell como administrador." -ForegroundColor Yellow

    if ($RunNow) {
        Start-ScheduledTask -TaskName $TaskName
        Write-Host ""
        Write-Host "Ejecución iniciada. Revise el log en $LogDir" -ForegroundColor Cyan
    }

    exit 0
} catch {
    Write-Host ""
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 2
}
