# Evidencia — Endurecimiento de respaldos

**Fecha:** 16 de noviembre de 2026 (UTC)
**Fase:** backup-hardening
**Base de práctica:** `frostbase_drill`
**Base principal:** `frostbase` (solo lectura; no se modificó)
**Entorno:** Windows 11, Docker Desktop, PostgreSQL 16.14

Esta evidencia valida las mejoras de cifrado, retención, espejo externo,
verificación y recuperación guiada descritas en
[`../../../backup-restore-guide.md`](../../../backup-restore-guide.md).

---

## Resultado global

| Métrica | Valor |
| --- | ---: |
| Casos ejecutados | 7 |
| PASS | 7 |
| FAIL | 0 |

---

## Casos

| Caso | Resultado | Evidencia clave |
| --- | --- | --- |
| Respaldo cifrado + espejo + retención + verificación | **PASS** | `.dump.enc` de 57 973 B; `plaintext_removed: true`; `source_checksums_stable: true` |
| Verificación independiente con `db_verify.py` | **PASS** | `verified: true`; digest `5a0341b9…92e6` |
| Passphrase incorrecta | **PASS** | error limpio y código de salida `1` |
| Restauración cifrada con `db_restore.py` | **PASS** | `encrypted: true`; `match: true`; 0.54 s |
| Retención con `db_prune.py` | **PASS** | conservó 1 y eliminó 2 respaldos antiguos |
| Recuperación guiada con `db_recover.py` | **PASS** | `success: true`; `app_health: true`; `match: true`; RTO **20.62 s** |
| Respaldo físico con `db_basebackup.py` | **PASS** | `.tar.gz` de 6 283 121 B con `backup_manifest`, `base.tar.gz` y `pg_wal.tar.gz`; `pitr_ready: false` |

---

## Comandos ejecutados

```bash
# 1. Dependencia de cifrado
pip install -r backend/scripts/requirements-backup.txt

# 2. Passphrase de prueba (eliminada al finalizar)
python -c "import secrets; print(secrets.token_urlsafe(32))" > db-backups/test.pass

# 3. Respaldo cifrado + retención + espejo + verificación
python backend/scripts/db_backup.py --db frostbase_drill --label hardening \
  --out-dir db-backups/hardening \
  --encrypt --passphrase-file db-backups/test.pass \
  --mirror-dir db-backups/mirror \
  --prune --retention-days 30 --keep-last 7 --verify

# 4. Verificación independiente
python backend/scripts/db_verify.py \
  --dump db-backups/hardening/frostbase_drill_hardening_20261116T020457Z.dump.enc \
  --passphrase-file db-backups/test.pass \
  --output db-backups/hardening/verify.json

# 5. Passphrase incorrecta (debe fallar)
python backend/scripts/db_verify.py \
  --dump db-backups/hardening/frostbase_drill_hardening_20261116T020457Z.dump.enc \
  --passphrase-file db-backups/wrong.pass

# 6. Restauración en base de prueba
python backend/scripts/db_restore.py \
  --dump db-backups/hardening/frostbase_drill_hardening_20261116T020457Z.dump.enc \
  --target frostbase_restore \
  --passphrase-file db-backups/test.pass \
  --compare docs/security/evidence/2026-11-15/checksums_baseline.json \
  --output db-backups/hardening/restore.json

# 7. Retención sobre datos sintéticos
python backend/scripts/db_prune.py --dir db-backups/prune-test \
  --database frostbase_drill --retention-days 30 --keep-last 1 --yes

# 8. Recuperación guiada sobre la copia de práctica
python backend/scripts/db_recover.py \
  --dump db-backups/hardening/frostbase_drill_hardening_20261116T020457Z.dump.enc \
  --target frostbase_drill \
  --app-container frostbase-drill-app \
  --health-url http://localhost:8001/api/health \
  --passphrase-file db-backups/test.pass --yes \
  --output db-backups/hardening/recover.json

# 9. Respaldo físico
python backend/scripts/db_basebackup.py --label hardening --out-dir db-backups/base
```

---

## Hashes de referencia

| Artefacto | SHA-256 |
| --- | --- |
| Respaldo cifrado | `96cd58a73ba86f1d826464b9d04a8563660c97556985ad9f10aa54fb1aa286a9` |
| Dump plano antes de cifrar | `9f631a7d443650d754e5c315e9662b275df844fef0d6abedadcf42b44bd34fb9` |
| Espejo | `96cd58a73ba86f1d826464b9d04a8563660c97556985ad9f10aa54fb1aa286a9` |
| `pre_restore` de `db_recover.py` | `064040a97a891159a3117db98588e559558e3c2800ff902bcf2ff71e888adefc` |
| Respaldo físico | `9733bdcb9a74d5e62b78d86e22da58f9be3bab466375011f207f08fd630c35d2` |
| Digest de la base de práctica | `5a0341b93fdb8c00a623a1b509cbba3e9ec4bfe94408d641f61e44aa36ad92e6` |

---

## Detalle de seguridad

- Cifra: AES-256-GCM; KDF: PBKDF2-HMAC-SHA256 con 600 000 iteraciones.
- Salt y nonce aleatorios por archivo; el nonce nunca se reutiliza.
- La passphrase no se almacena en los metadatos ni en la línea de comandos.
- El respaldo se valida con `pg_restore --list` antes de cifrarse.
- El espejo se verifica recalculando SHA-256.
- Una passphrase incorrecta falla con código `1` sin dejar archivos temporales.

---

## Limitaciones y siguientes pasos

1. El RTO de 20.62 s corresponde al volumen de práctica (98 objetos) y a Docker
   local; no debe extrapolarse a producción.
2. `archive_mode=off`: el respaldo físico es completo pero **no** habilita PITR.
   Para activarlo, use `docker-compose.backup.yml` y respalde el volumen WAL.
3. Falta desplegar la programación real (cron/systemd/Task Scheduler) y definir
   el almacenamiento externo definitivo.
4. La passphrase de prueba fue eliminada; los `.enc` de esta evidencia no son
   descifrables, lo cual es intencional.
5. La evidencia no contiene filas ni PII: solo rutas, hashes, conteos y
   resultados.

---

## Archivos

- `results.json` — resultados completos de los 7 casos.
- `summary.md` — este resumen.
