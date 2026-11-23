# Respaldo y restauración

> **Regla:** los respaldos viven **fuera del repositorio** y cifrados. Nunca en
> `db-backups/` ni en el árbol de trabajo versionado.

## 1. Ubicación

| Entorno | Ruta |
|---|---|
| Windows (desarrollo local) | `%USERPROFILE%\backups\frostbase\` |
| Linux/macOS | `~/backups/frostbase/` |

Los dumps antiguos que estaban en `db-backups/` se movieron a
`%USERPROFILE%\backups\frostbase\db-backups\` durante la Fase 1 del plan.

## 2. Respaldo (RPO objetivo: 24 h)

### Script automatizado (recomendado, G8)

`scripts/backup_db.py` automatiza el volcado completo: dump `-Fc` dentro del
contenedor, copia al host, retención configurable y cifrado opcional con
`age`. Verificado el 2026-11-22 (dump de 0.4 MB generado en segundos).

```powershell
# Uso directo
.\backend\.venv\Scripts\python.exe -m scripts.backup_db --keep 14

# Con la tarea del repositorio
.\tasks.ps1 backup                 # retención por defecto: 14
.\tasks.ps1 backup -Keep 30       # conservar 30 dumps

# Cifrado con age (si está instalado)
.\backend\.venv\Scripts\python.exe -m scripts.backup_db --age-recipient age1xxxxxxx
```

### Windows PowerShell (manual)

```powershell
$target = Join-Path $env:USERPROFILE "backups\frostbase"
New-Item -ItemType Directory -Force -Path $target | Out-Null
$stamp = Get-Date -Format "yyyyMMdd'T'HHmmss'Z'"

# Genera el dump dentro del contenedor y lo copia al host (evita corromper binarios)
docker compose exec -T db pg_dump -U frostbase -Fc -f /tmp/frostbase.dump frostbase
docker compose cp db:/tmp/frostbase.dump "$target\frostbase_$stamp.dump"
docker compose exec -T db rm -f /tmp/frostbase.dump

# Cifrado (si `age` está disponible)
age -r <clave-publica-o-recipient> -o "$target\frostbase_$stamp.dump.age" "$target\frostbase_$stamp.dump"
Remove-Item "$target\frostbase_$stamp.dump"
```

### Linux/macOS

```bash
target="$HOME/backups/frostbase"
mkdir -p "$target"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"

docker compose exec -T db pg_dump -U frostbase -Fc frostbase > "$target/frostbase_$stamp.dump"
age -r <recipient> -o "$target/frostbase_$stamp.dump.age" "$target/frostbase_$stamp.dump"
rm "$target/frostbase_$stamp.dump"
```

Alternativa con GPG simétrico:

```bash
gpg --symmetric --cipher-algo AES256 "$target/frostbase_$stamp.dump"
```

No guarde la passphrase ni la clave privada junto a los dumps.

### Programación automática (RPO 24 h)

**Windows · Programador de tareas** (diario a las 03:00):

```powershell
$task = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-NoProfile -Command cd 'C:\ruta\a\frostbase-v2'; .\tasks.ps1 backup"
$trigger = New-ScheduledTaskTrigger -Daily -At 03:00
Register-ScheduledTask -TaskName "FrostBase Backup" -Action $task -Trigger $trigger
```

**Linux · cron** (`crontab -e`):

```cron
0 3 * * * cd /opt/frostbase && make backup KEEP=14 >> /var/log/frostbase-backup.log 2>&1
```

Verifique semanalmente que el dump del día existe y que la restauración
sigue funcionando (drill de la sección 3).

## 3. Restauración (RTO objetivo: < 30 min)

Restauración **probada** el 2026-11-19 sobre PostgreSQL 16:

| Paso | Comando | Resultado medido |
|---|---|---|
| Dump (`pg_dump -Fc`) | `docker compose exec -T db pg_dump ...` | 104 KB, 3 116 lecturas, 29 alertas |
| Crear BD de prueba | `CREATE DATABASE frostbase_restore_drill` | < 1 s |
| Restaurar (`pg_restore`) | `pg_restore -d frostbase_restore_drill` | **0.79 s** |
| Verificación | conteos `admins/trucks/devices/readings/alerts` | 1 / 3 / 2 / 3116 / 29 |
| Limpieza | `DROP DATABASE frostbase_restore_drill` | OK |

### Procedimiento

```powershell
# 1. Detener escrituras (opcional para un drill; obligatorio en producción)
docker compose stop app

# 2. Crear una base de prueba (nunca restaure sobre la base viva)
docker compose exec -T db psql -U frostbase -d postgres -c "CREATE DATABASE frostbase_restore_drill"

# 3. Copiar el dump al contenedor y restaurar
docker compose cp "C:\ruta\al\frostbase.dump" db:/tmp/restore.dump
docker compose exec -T db pg_restore -U frostbase -d frostbase_restore_drill --no-owner --no-privileges /tmp/restore.dump

# 4. Verificar
docker compose exec -T db psql -U frostbase -d frostbase_restore_drill -c "SELECT count(*) FROM readings;"

# 5. Limpiar
docker compose exec -T db psql -U frostbase -d postgres -c "DROP DATABASE frostbase_restore_drill"
docker compose exec -T db rm -f /tmp/restore.dump
docker compose start app
```

Para reemplazar la base viva (ventana de mantenimiento):

1. `docker compose stop app`.
2. Renombrar la base actual: `ALTER DATABASE frostbase RENAME TO frostbase_old_YYYYMMDD;`
3. `CREATE DATABASE frostbase;`
4. Restaurar el dump sobre `frostbase`.
5. Arrancar `app` y verificar `alembic current == head` y `/health`.
6. Conservar `frostbase_old_YYYYMMDD` hasta validar; luego eliminarla.

## 4. RPO y RTO

| Métrica | Objetivo | Cómo se cumple |
|---|---|---|
| **RPO** | ≤ 24 h | Respaldo diario programado (cron / Programador de tareas) fuera del repo |
| **RTO** | ≤ 30 min | Restauración medida en segundos + verificación manual acotada |

## 5. Rotación y retención

- Diarios: 7 copias.
- Semanales: 4 copias.
- Mensuales: 3 copias.
- Pruebe una restauración **mensual** y registre fecha, tamaño y tiempo medido.

## 6. Verificación de higiene

```powershell
git status --ignored
```

No debe aparecer ningún `*.dump`, `*.sql`, `*.tar.gz` ni `db-backups/` dentro del
repositorio. `.gitignore` los excluye además de forma explícita.
