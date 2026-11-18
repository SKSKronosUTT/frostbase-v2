<#
.SYNOPSIS
    Respaldo diario cifrado y verificado de Frostbase en Windows.

.DESCRIPTION
    Ejecuta db_backup.py con cifrado AES-256-GCM, retención, copia externa y
    verificación por restauración. Escribe un log por ejecución y un evento en
    el registro de Windows si falla.

.PARAMETER RepoRoot
    Ruta del repositorio Frostbase. Si se omite, se deduce desde la ubicación
    de este script (deploy\windows\..\..).

.PARAMETER BackupDir
    Carpeta local de respaldos (fuera del repositorio). Si se omite, se usa
    %USERPROFILE%\FrostbaseBackups.

.PARAMETER MirrorDir
    Carpeta externa para la copia espejo. Vacío para deshabilitar.

.PARAMETER PassphraseFile
    Archivo con la passphrase. Debe estar protegido con ACL (solo el usuario
    que ejecuta la tarea y Administradores).

.PARAMETER Database
    Base de datos a respaldar.

.EXAMPLE
    .\frostbase-backup.ps1 -BackupDir D:\Backups\frostbase `
        -MirrorDir E:\Offsite\frostbase `
        -PassphraseFile C:\ProgramData\Frostbase\backup.pass

.NOTES
    Este script ejecuta el respaldo. Para registrar la tarea diaria use
    register-frostbase-backup.ps1, que pasa automáticamente las rutas:

    .\deploy\windows\register-frostbase-backup.ps1 -CreatePassphrase -RunNow

    El usuario de la tarea debe poder ejecutar Docker y leer el archivo de
    passphrase. No use SYSTEM si Docker Desktop está instalado en el perfil de
    un usuario interactivo.
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
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

if (-not $RepoRoot) {
    if ($PSScriptRoot) {
        $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
    } else {
        $RepoRoot = (Get-Location).Path
    }
} else {
    $RepoRoot = (Resolve-Path $RepoRoot).Path
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

try {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
} catch {
    throw "No se pudo crear la carpeta de logs '$LogDir': $($_.Exception.Message). Use -LogDir con una ruta escribible."
}

$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$log = Join-Path $LogDir "frostbase-backup-$stamp.log"

$backupScript = Join-Path $RepoRoot "backend\scripts\db_backup.py"
if (-not (Test-Path $backupScript)) {
    throw "No se encontró $backupScript"
}
if (-not (Test-Path $PassphraseFile)) {
    throw "No se encontró el archivo de passphrase $PassphraseFile"
}

$arguments = @(
    $backupScript,
    "--db", $Database,
    "--label", "nightly",
    "--out-dir", $BackupDir,
    "--encrypt",
    "--passphrase-file", $PassphraseFile,
    "--prune",
    "--retention-days", "$RetentionDays",
    "--keep-last", "$KeepLast",
    "--verify"
)

if ($MirrorDir) {
    $arguments += @("--mirror-dir", $MirrorDir)
}

"[$(Get-Date -Format o)] Inicio del respaldo de $Database" | Tee-Object -FilePath $log
& $Python @arguments 2>&1 | Tee-Object -FilePath $log -Append
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    $message = "El respaldo de Frostbase falló con código $exitCode. Ver $log"
    Write-EventLog -LogName Application -Source "Frostbase" -EventId 9001 `
        -EntryType Error -Message $message -ErrorAction SilentlyContinue
    Write-Error $message
    exit $exitCode
}

"[$(Get-Date -Format o)] Respaldo completado correctamente" |
    Tee-Object -FilePath $log -Append
exit 0
