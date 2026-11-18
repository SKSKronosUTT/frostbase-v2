"""Utilidades compartidas para respaldo, restauración y verificación de la BD.

Todos los comandos se ejecutan por medio de la CLI de Docker, de modo que los
scripts funcionan desde el host sin necesidad de tener un cliente de PostgreSQL
instalado localmente.

Variables de entorno opcionales:
    FROSTBASE_DB_CONTAINER   Nombre del contenedor PostgreSQL (frostbase-db)
    FROSTBASE_APP_IMAGE      Imagen de la aplicación (frostbase-v2-app:latest)
    FROSTBASE_NETWORK        Red de Docker Compose (frostbase-v2_default)
    FROSTBASE_BACKUP_DIR     Carpeta destino de respaldos (db-backups)
    POSTGRES_DB              Base de datos de trabajo (frostbase)
    POSTGRES_USER            Usuario de PostgreSQL (frostbase)
    POSTGRES_PASSWORD        Contraseña de PostgreSQL (frostbase)
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BACKUP_DIR = Path(
    os.getenv("FROSTBASE_BACKUP_DIR", str(REPO_ROOT / "db-backups"))
)

DB_CONTAINER = os.getenv("FROSTBASE_DB_CONTAINER", "frostbase-db")
DB_USER = os.getenv("POSTGRES_USER", "frostbase")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "frostbase")
DB_NAME = os.getenv("POSTGRES_DB", "frostbase")
APP_IMAGE = os.getenv("FROSTBASE_APP_IMAGE", "frostbase-v2-app:latest")
NETWORK = os.getenv("FROSTBASE_NETWORK", "frostbase-v2_default")

BACKUP_MAGIC = b"FROSTBK1"
KDF_ITERATIONS = 600_000
PASSPHRASE_ENV = "FROSTBASE_BACKUP_PASSPHRASE"


class CommandError(RuntimeError):
    """Error al ejecutar un comando externo."""

    def __init__(self, command: list[str], returncode: int, stdout: str, stderr: str):
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        detail = (stderr or stdout or "").strip()
        super().__init__(
            f"El comando {' '.join(command)} terminó con código {returncode}: {detail}"
        )


def run(
    command: list[str],
    *,
    input_text: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Ejecuta un comando capturando su salida en UTF-8."""

    process = subprocess.run(
        command,
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and process.returncode != 0:
        raise CommandError(command, process.returncode, process.stdout, process.stderr)
    return process


def docker(*args: str, check: bool = True, input_text: str | None = None):
    return run(["docker", *args], check=check, input_text=input_text)


def exec_in(
    container: str,
    *args: str,
    check: bool = True,
    input_text: str | None = None,
):
    return docker("exec", "-i", container, *args, check=check, input_text=input_text)


def psql(
    database: str,
    sql: str,
    *,
    check: bool = True,
    container: str = DB_CONTAINER,
    user: str = DB_USER,
):
    """Ejecuta SQL con psql dentro del contenedor y formato sin tablas."""

    return exec_in(
        container,
        "psql",
        "-U",
        user,
        "-d",
        database,
        "-v",
        "ON_ERROR_STOP=1",
        "-tA",
        "-c",
        sql,
        check=check,
    )


def psql_scalar(database: str, sql: str, **kwargs) -> str:
    return psql(database, sql, **kwargs).stdout.strip()


def quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def database_exists(database: str, *, container: str = DB_CONTAINER) -> bool:
    result = psql_scalar(
        "postgres",
        f"SELECT 1 FROM pg_database WHERE datname = '{database.replace(chr(39), chr(39) * 2)}'",
        container=container,
    )
    return result == "1"


def ensure_database(
    database: str,
    *,
    drop: bool = False,
    container: str = DB_CONTAINER,
    user: str = DB_USER,
) -> None:
    """Crea la base de datos destino, opcionalmente eliminándola antes."""

    identifier = quote_ident(database)
    if drop:
        psql(
            "postgres",
            f"DROP DATABASE IF EXISTS {identifier} WITH (FORCE)",
            container=container,
            user=user,
        )
    if not database_exists(database, container=container):
        psql(
            "postgres",
            f"CREATE DATABASE {identifier}",
            container=container,
            user=user,
        )


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def database_checksums(
    database: str,
    *,
    container: str = DB_CONTAINER,
    user: str = DB_USER,
) -> dict:
    """Calcula filas y checksum MD5 determinista para cada tabla pública.

    La huella global (digest) permite comparar dos bases de datos de forma
    inequívoca sin necesidad de copiar los datos.
    """

    tables_output = psql_scalar(
        database,
        "SELECT tablename FROM pg_tables "
        "WHERE schemaname = 'public' ORDER BY tablename",
        container=container,
        user=user,
    )
    table_names = [line.strip() for line in tables_output.splitlines() if line.strip()]
    tables: dict[str, dict] = {}
    for table in table_names:
        query = (
            "SELECT count(*), "
            "md5(coalesce(string_agg(md5(x::text), '' ORDER BY md5(x::text)), '')) "
            f"FROM {quote_ident(table)} x"
        )
        row_count, checksum = psql_scalar(
            database, query, container=container, user=user
        ).split("|", 1)
        tables[table] = {"rows": int(row_count), "checksum": checksum}
    serialized = "".join(
        f"{name}:{tables[name]['rows']}:{tables[name]['checksum']}"
        for name in sorted(tables)
    )
    return {
        "database": database,
        "generated_at": utc_now(),
        "digest": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        "tables": tables,
    }


def backup_database(
    database: str = DB_NAME,
    *,
    label: str = "",
    out_dir: str | Path = DEFAULT_BACKUP_DIR,
    container: str = DB_CONTAINER,
    user: str = DB_USER,
    passphrase: str | None = None,
    remove_plaintext: bool = True,
    include_checksums: bool = True,
    mirror_dir: str | Path | None = None,
) -> dict:
    """Genera un respaldo lógico, opcionalmente cifrado y espejado.

    El respaldo se crea con ``pg_dump -Fc`` dentro del contenedor, se valida con
    ``pg_restore --list`` y se copia al host. Si se entrega ``passphrase``, el
    archivo se cifra con AES-256-GCM y, por defecto, el ``.dump`` en claro se
    elimina. Los metadatos incluyen checksums del origen para poder verificar
    la restauración más adelante.
    """

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    stem = f"{database}_{label + '_' if label else ''}{utc_stamp()}"
    file_name = f"{stem}.dump"
    remote = f"/tmp/{file_name}"

    checksums_before = (
        database_checksums(database, container=container, user=user)
        if include_checksums
        else None
    )

    exec_in(
        container,
        "pg_dump",
        "-U",
        user,
        "-Fc",
        "-f",
        remote,
        database,
    )
    local = out_path / file_name
    docker("cp", f"{container}:{remote}", str(local))

    listing = exec_in(container, "pg_restore", "--list", remote)
    objects = [
        line
        for line in listing.stdout.splitlines()
        if line.strip() and not line.startswith(";")
    ]
    exec_in(container, "rm", "-f", remote, check=False)

    checksums_after = (
        database_checksums(database, container=container, user=user)
        if include_checksums
        else None
    )
    checksums_stable = (
        checksums_before is not None
        and checksums_after is not None
        and checksums_before["digest"] == checksums_after["digest"]
    )
    plain_sha256 = sha256_file(local)
    plain_size = local.stat().st_size

    final_path = local
    encryption: dict | None = None
    if passphrase:
        encrypted_path = local.with_suffix(local.suffix + ".enc")
        encryption = encrypt_backup(local, encrypted_path, passphrase)
        final_path = encrypted_path
        if remove_plaintext:
            local.unlink()

    metadata = {
        "database": database,
        "label": label,
        "created_at": utc_now(),
        "file": str(final_path),
        "size_bytes": final_path.stat().st_size,
        "sha256": sha256_file(final_path),
        "plain_size_bytes": plain_size,
        "plain_sha256": plain_sha256,
        "format": "pg_dump custom (-Fc)",
        "objects": len(objects),
        "verified_with_pg_restore_list": True,
        "encrypted": bool(encryption),
        "encryption": encryption,
        "plaintext_removed": bool(encryption and remove_plaintext),
        "source_checksums": checksums_after,
        "source_checksums_before": checksums_before,
        "source_checksums_stable": checksums_stable if include_checksums else None,
    }
    metadata_path = metadata_path_for(final_path)
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if mirror_dir:
        metadata["mirror"] = mirror_backup(metadata, mirror_dir)
        metadata_path.write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        shutil.copy2(metadata_path, Path(mirror_dir) / metadata_path.name)

    return metadata


def restore_database(
    dump_path: str | Path,
    target_database: str,
    *,
    drop: bool = True,
    container: str = DB_CONTAINER,
    user: str = DB_USER,
    passphrase: str | None = None,
) -> dict:
    """Restaura un respaldo custom en una base de datos destino.

    Si el respaldo está cifrado, se descifra en un archivo temporal que se
    elimina automáticamente al terminar. La restauración se ejecuta en una sola
    transacción para no dejar una base parcialmente restaurada.
    """

    source = Path(dump_path)
    if not source.exists():
        raise FileNotFoundError(f"No existe el respaldo: {source}")

    workdir = Path(tempfile.mkdtemp(prefix="frostbase-restore-"))
    encrypted = is_encrypted_backup(source)
    plain_source = source
    decrypted = False
    try:
        if encrypted:
            if not passphrase:
                raise RuntimeError(
                    "El respaldo está cifrado y no se proporcionó passphrase "
                    f"(use --passphrase-file o la variable {PASSPHRASE_ENV})"
                )
            plain_source = workdir / "restore.dump"
            decrypt_backup(source, plain_source, passphrase)
            decrypted = True

        remote = f"/tmp/restore_{target_database}_{utc_stamp()}.dump"
        docker("cp", str(plain_source), f"{container}:{remote}")
        ensure_database(target_database, drop=drop, container=container, user=user)

        started = time.perf_counter()
        process = exec_in(
            container,
            "pg_restore",
            "-U",
            user,
            "-d",
            target_database,
            "--no-owner",
            "--no-acl",
            "--single-transaction",
            remote,
            check=False,
        )
        elapsed = time.perf_counter() - started
        exec_in(container, "rm", "-f", remote, check=False)

        if process.returncode != 0:
            raise CommandError(
                process.args if isinstance(process.args, list) else ["pg_restore"],
                process.returncode,
                process.stdout,
                process.stderr,
            )
        return {
            "target_database": target_database,
            "source_dump": str(source),
            "restored_at": utc_now(),
            "seconds": round(elapsed, 2),
            "warnings": process.stderr.strip(),
            "encrypted": encrypted,
            "decrypted": decrypted,
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _crypto():
    """Importa cryptography de forma diferida con un mensaje claro si falta."""

    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

        return hashes, AESGCM, PBKDF2HMAC
    except ImportError as error:  # pragma: no cover - depende del entorno
        raise RuntimeError(
            "El cifrado de respaldos requiere el paquete 'cryptography'. "
            "Instálelo con: pip install -r backend/scripts/requirements-backup.txt"
        ) from error


def resolve_passphrase(
    passphrase_file: str | Path | None = None,
    *,
    env_var: str = PASSPHRASE_ENV,
    allow_prompt: bool = True,
) -> str:
    """Obtiene la passphrase desde archivo, variable de entorno o prompt.

    Nunca se acepta la passphrase por argumento de línea de comandos para evitar
    que quede registrada en el historial del shell o en la lista de procesos.
    """

    if passphrase_file:
        path = Path(passphrase_file)
        if not path.exists():
            raise FileNotFoundError(f"No existe el archivo de passphrase: {path}")
        value = path.read_text(encoding="utf-8").strip()
    elif os.getenv(env_var):
        value = os.environ[env_var]
    elif allow_prompt:
        import getpass

        value = getpass.getpass("Passphrase del respaldo: ")
    else:
        raise RuntimeError(
            "No se proporcionó passphrase. Use --passphrase-file o defina "
            f"{env_var}."
        )
    if len(value) < 12:
        raise ValueError("La passphrase debe tener al menos 12 caracteres")
    return value


def encrypt_backup(
    source: str | Path, destination: str | Path, passphrase: str
) -> dict:
    """Cifra un respaldo con AES-256-GCM y deriva la clave con PBKDF2."""

    hashes, AESGCM, PBKDF2HMAC = _crypto()
    source_path = Path(source)
    destination_path = Path(destination)
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    key = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=KDF_ITERATIONS,
    ).derive(passphrase.encode("utf-8"))
    plaintext = source_path.read_bytes()
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, BACKUP_MAGIC)
    with open(destination_path, "wb") as handle:
        handle.write(BACKUP_MAGIC)
        handle.write(salt)
        handle.write(nonce)
        handle.write(ciphertext)
    return {
        "cipher": "AES-256-GCM",
        "kdf": "PBKDF2-HMAC-SHA256",
        "kdf_iterations": KDF_ITERATIONS,
        "salt_b64": base64.b64encode(salt).decode("ascii"),
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "plaintext_sha256": sha256_file(source_path),
        "size_bytes": destination_path.stat().st_size,
        "sha256": sha256_file(destination_path),
    }


def decrypt_backup(
    source: str | Path, destination: str | Path, passphrase: str
) -> dict:
    """Descifra un respaldo creado por ``encrypt_backup``."""

    hashes, AESGCM, PBKDF2HMAC = _crypto()
    source_path = Path(source)
    destination_path = Path(destination)
    raw = source_path.read_bytes()
    if not raw.startswith(BACKUP_MAGIC):
        raise ValueError("El archivo no tiene el formato cifrado de Frostbase")
    offset = len(BACKUP_MAGIC)
    salt = raw[offset : offset + 16]
    nonce = raw[offset + 16 : offset + 28]
    ciphertext = raw[offset + 28 :]
    key = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=KDF_ITERATIONS,
    ).derive(passphrase.encode("utf-8"))
    try:
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, BACKUP_MAGIC)
    except Exception as error:  # InvalidTag
        raise ValueError(
            "No se pudo descifrar el respaldo: passphrase incorrecta o archivo corrupto"
        ) from error
    destination_path.write_bytes(plaintext)
    return {
        "file": str(destination_path),
        "size_bytes": destination_path.stat().st_size,
        "sha256": sha256_file(destination_path),
    }


def is_encrypted_backup(path: str | Path) -> bool:
    try:
        with open(path, "rb") as handle:
            return handle.read(len(BACKUP_MAGIC)) == BACKUP_MAGIC
    except OSError:
        return False


def metadata_path_for(dump_path: str | Path) -> Path:
    return Path(str(dump_path) + ".json")


def load_metadata(
    dump_path: str | Path, metadata_path: str | Path | None = None
) -> dict | None:
    path = Path(metadata_path) if metadata_path else metadata_path_for(dump_path)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def mirror_backup(metadata: dict, mirror_dir: str | Path) -> dict:
    """Copia el respaldo y sus metadatos a una ubicación externa y verifica."""

    target_dir = Path(mirror_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    source = Path(metadata["file"])
    target = target_dir / source.name
    shutil.copy2(source, target)
    actual = sha256_file(target)
    if actual != metadata["sha256"]:
        raise RuntimeError(
            f"La copia espejo no coincide en SHA-256: {target} ({actual})"
        )
    source_metadata = metadata_path_for(source)
    metadata_target = target_dir / source_metadata.name
    shutil.copy2(source_metadata, metadata_target)
    return {
        "mirror_dir": str(target_dir),
        "file": str(target),
        "metadata": str(metadata_target),
        "sha256": actual,
        "verified": True,
    }


def prune_backups(
    out_dir: str | Path = DEFAULT_BACKUP_DIR,
    *,
    database: str | None = None,
    retention_days: int = 30,
    keep_last: int = 7,
    dry_run: bool = False,
) -> dict:
    """Elimina respaldos antiguos conservando siempre los más recientes.

    Solo considera archivos ``*.dump`` y ``*.dump.enc`` (y sus ``.json``). Si se
    indica ``database``, limita la poda a los respaldos de esa base.
    """

    directory = Path(out_dir)
    if not directory.exists():
        return {
            "directory": str(directory),
            "dry_run": dry_run,
            "deleted": [],
            "kept": [],
        }

    candidates = []
    for path in directory.iterdir():
        if not path.is_file():
            continue
        name = path.name
        if not (name.endswith(".dump") or name.endswith(".dump.enc")):
            continue
        if database and not name.startswith(database + "_"):
            continue
        candidates.append(path)

    candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    keep = set(candidates[:keep_last])
    now = time.time()
    deleted: list[dict] = []
    kept: list[str] = []

    for path in candidates:
        age_days = (now - path.stat().st_mtime) / 86400
        if path in keep or age_days < retention_days:
            kept.append(path.name)
            continue
        metadata = metadata_path_for(path)
        record = {
            "file": path.name,
            "metadata": metadata.name,
            "size_bytes": path.stat().st_size,
            "age_days": round(age_days, 1),
        }
        deleted.append(record)
        if not dry_run:
            path.unlink()
            if metadata.exists():
                metadata.unlink()

    return {
        "directory": str(directory),
        "database": database,
        "retention_days": retention_days,
        "keep_last": keep_last,
        "dry_run": dry_run,
        "deleted": deleted,
        "kept": kept,
    }


def verify_backup(
    dump_path: str | Path,
    *,
    metadata_path: str | Path | None = None,
    passphrase: str | None = None,
    container: str = DB_CONTAINER,
    user: str = DB_USER,
    temp_database: str = "frostbase_verify",
    keep_temp_database: bool = False,
) -> dict:
    """Restaura el respaldo en una base temporal y compara checksums.

    La comparación se hace contra ``source_checksums`` guardado en los metadatos
    al momento del respaldo. Así se verifica que el archivo restaura exactamente
    el estado del que se tomó.
    """

    source = Path(dump_path)
    metadata = load_metadata(source, metadata_path)
    if not metadata:
        raise FileNotFoundError(
            "No se encontraron metadatos para el respaldo; no es posible "
            "verificar contra la huella del origen"
        )

    workdir = Path(tempfile.mkdtemp(prefix="frostbase-verify-"))
    encrypted = is_encrypted_backup(source)
    plain_source = source
    try:
        if encrypted:
            if not passphrase:
                raise RuntimeError(
                    "El respaldo está cifrado y no se proporcionó passphrase"
                )
            plain_source = workdir / "verify.dump"
            decrypt_backup(source, plain_source, passphrase)

        restore = restore_database(
            plain_source,
            temp_database,
            drop=True,
            container=container,
            user=user,
        )
        actual = database_checksums(
            temp_database, container=container, user=user
        )
        expected = metadata.get("source_checksums")
        comparison = compare_checksums(expected, actual) if expected else None

        result = {
            "dump": str(source),
            "metadata": str(
                Path(metadata_path)
                if metadata_path
                else metadata_path_for(source)
            ),
            "encrypted": encrypted,
            "restore": restore,
            "checksums": actual,
            "comparison": comparison,
            "verified": bool(comparison and comparison["match"]),
        }
        if not keep_temp_database:
            psql(
                "postgres",
                f"DROP DATABASE IF EXISTS {quote_ident(temp_database)} "
                "WITH (FORCE)",
                container=container,
                user=user,
                check=False,
            )
        return result
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def wait_http(url: str, timeout: float = 60, interval: float = 0.5) -> bool:
    """Espera a que una URL responda 2xx."""

    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if 200 <= response.status < 300:
                    return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def container_exists(name: str) -> bool:
    return docker("inspect", name, check=False).returncode == 0


def stop_container(name: str) -> dict:
    process = docker("stop", name, check=False)
    return {"container": name, "stopped": process.returncode == 0, "stderr": process.stderr.strip()}


def start_container(name: str) -> dict:
    process = docker("start", name, check=False)
    return {"container": name, "started": process.returncode == 0, "stderr": process.stderr.strip()}


def compare_checksums(expected: dict, actual: dict) -> dict:
    """Compara dos resultados de database_checksums y devuelve el detalle."""

    differences = []
    expected_tables = expected.get("tables", {})
    actual_tables = actual.get("tables", {})
    for table in sorted(set(expected_tables) | set(actual_tables)):
        left = expected_tables.get(table)
        right = actual_tables.get(table)
        if left != right:
            differences.append({"table": table, "expected": left, "actual": right})
    return {
        "match": expected.get("digest") == actual.get("digest") and not differences,
        "expected_digest": expected.get("digest"),
        "actual_digest": actual.get("digest"),
        "differences": differences,
    }
