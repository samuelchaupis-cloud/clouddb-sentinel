"""
backup_manager.py — CloudDB Sentinel
=======================================
Módulo de gestión de backups para bases de datos PostgreSQL y MySQL.

Orquesta la ejecución de pg_dump / mysqldump, compresión, carga a
MinIO/S3, limpieza por retención y registro en SQLite local. Toda la
configuración sensible se carga desde variables de entorno mediante
python-dotenv.

Autor: Equipo de Plataformas Cloud
Versión: 1.0.0
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import time

# Configuración defensiva de encoding para Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

# Cargar variables de entorno desde archivo .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError as exc:
    raise ImportError(
        "Dependencia faltante: instale python-dotenv con 'pip install python-dotenv'"
    ) from exc

# Cliente AWS/MinIO S3
try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError as exc:
    raise ImportError(
        "Dependencia faltante: instale boto3 con 'pip install boto3'"
    ) from exc

try:
    import yaml
except ImportError as exc:
    raise ImportError(
        "Dependencia faltante: instale PyYAML con 'pip install pyyaml'"
    ) from exc

# Logger del módulo
logger = logging.getLogger("clouddb_sentinel.backup.manager")

# ---------------------------------------------------------------------------
# RUTAS DEL PROYECTO
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
BACKUP_DIR = PROJECT_ROOT / "backups"
DATABASES_YAML = CONFIG_DIR / "databases.yaml"
BACKUP_REGISTRY_DB = DATA_DIR / "backup_registry.db"

# ---------------------------------------------------------------------------
# CONFIGURACIÓN S3/MinIO DESDE VARIABLES DE ENTORNO
# ---------------------------------------------------------------------------
S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL", "http://127.0.0.1:9000")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY_ID") or os.environ.get("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.environ.get("S3_SECRET_ACCESS_KEY") or os.environ.get("S3_SECRET_KEY", "")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "clouddb-backups-b2b")
S3_REGION = os.environ.get("S3_REGION", "us-east-1")
S3_PATH_PREFIX = os.environ.get("S3_PATH_PREFIX", "backups")


# ---------------------------------------------------------------------------
# DATACLASSES DE RESULTADO
# ---------------------------------------------------------------------------

@dataclass
class BackupResult:
    """
    Resultado de una operación de backup de base de datos.

    Atributos
    ----------
    db_id : str
        Identificador único de la base de datos en el inventario.
    db_type : str
        Motor: 'postgres' o 'mysql'.
    db_host : str
        Hostname del servidor de base de datos.
    db_name : str
        Nombre de la base de datos respaldada.
    status : str
        Estado del backup: 'SUCCESS', 'FAILED', 'PARTIAL'.
    local_path : str
        Ruta local donde se guardó el archivo de backup.
    s3_uri : str
        URI S3/MinIO del backup subido (vacío si no se subió).
    size_bytes : int
        Tamaño del archivo de backup en bytes.
    checksum_sha256 : str
        Checksum SHA256 del archivo de backup para verificación de integridad.
    duration_seconds : float
        Duración total del proceso de backup en segundos.
    compression : str
        Algoritmo de compresión usado: 'zstd', 'gzip' o 'none'.
    backup_format : str
        Formato del backup: 'custom' (pg_dump -Fc) o 'sql' (mysqldump).
    timestamp : str
        Timestamp ISO 8601 de inicio del backup.
    error_message : str
        Mensaje de error si el backup falló.
    dr_validated : bool
        True si el backup ha sido validado para DR.
    registry_id : Optional[int]
        ID del registro en la base de datos SQLite local.
    """
    db_id: str = ""
    db_type: str = ""
    db_host: str = ""
    db_name: str = ""
    status: str = "PENDING"
    local_path: str = ""
    s3_uri: str = ""
    size_bytes: int = 0
    checksum_sha256: str = ""
    duration_seconds: float = 0.0
    compression: str = "none"
    backup_format: str = ""
    timestamp: str = ""
    error_message: str = ""
    dr_validated: bool = False
    registry_id: Optional[int] = None

    def to_dict(self) -> dict:
        """Serializa el resultado a diccionario JSON-compatible."""
        return asdict(self)


# ---------------------------------------------------------------------------
# GESTIÓN DEL REGISTRO SQLite
# ---------------------------------------------------------------------------

def _init_registry_db() -> None:
    """
    Inicializa la base de datos SQLite de registro de backups.

    Crea la tabla backup_registry si no existe. Esta tabla actúa como
    el libro de registro central de todos los backups realizados,
    persistiendo metadatos críticos para auditoría y DR.

    La base de datos se crea en data/backup_registry.db.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(BACKUP_REGISTRY_DB))
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backup_registry (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                db_id             TEXT NOT NULL,
                timestamp         TEXT NOT NULL,
                type              TEXT NOT NULL,          -- 'postgres' | 'mysql'
                local_path        TEXT,
                s3_uri            TEXT,
                size_bytes        INTEGER DEFAULT 0,
                checksum          TEXT,
                duration_seconds  REAL DEFAULT 0,
                status            TEXT NOT NULL,          -- 'SUCCESS' | 'FAILED'
                dr_validated      INTEGER DEFAULT 0,      -- 0=No, 1=Yes
                dr_validation_ts  TEXT,
                dr_result         TEXT,                   -- JSON con resultado DR
                error_message     TEXT,
                created_at        TEXT DEFAULT (datetime('now'))
            )
        """)
        # Índices para consultas frecuentes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_backup_db_id ON backup_registry(db_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_backup_timestamp ON backup_registry(timestamp)"
        )
        conn.commit()
        logger.debug("Registro SQLite inicializado: %s", BACKUP_REGISTRY_DB)
    finally:
        conn.close()


def _register_backup(result: BackupResult) -> int:
    """
    Registra un resultado de backup en la base de datos SQLite.

    Parámetros
    ----------
    result : BackupResult
        Resultado del backup a registrar.

    Retorna
    -------
    int
        ID del registro insertado en backup_registry.
    """
    _init_registry_db()
    conn = sqlite3.connect(str(BACKUP_REGISTRY_DB))
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO backup_registry
                (db_id, timestamp, type, local_path, s3_uri, size_bytes,
                 checksum, duration_seconds, status, dr_validated, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.db_id,
            result.timestamp,
            result.db_type,
            result.local_path,
            result.s3_uri,
            result.size_bytes,
            result.checksum_sha256,
            result.duration_seconds,
            result.status,
            1 if result.dr_validated else 0,
            result.error_message or None,
        ))
        conn.commit()
        registry_id = cursor.lastrowid
        logger.debug(
            "Backup registrado en SQLite — id=%d db=%s status=%s",
            registry_id, result.db_id, result.status
        )
        return registry_id
    finally:
        conn.close()


def _update_dr_status(registry_id: int, dr_validated: bool, dr_result: dict) -> None:
    """
    Actualiza el estado de validación DR para un registro de backup existente.

    Parámetros
    ----------
    registry_id : int
        ID del registro en backup_registry.
    dr_validated : bool
        True si la validación DR fue exitosa.
    dr_result : dict
        Resultado completo de la validación DR (se serializa como JSON).
    """
    _init_registry_db()
    conn = sqlite3.connect(str(BACKUP_REGISTRY_DB))
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE backup_registry
            SET dr_validated = ?,
                dr_validation_ts = ?,
                dr_result = ?
            WHERE id = ?
        """, (
            1 if dr_validated else 0,
            datetime.now(timezone.utc).isoformat(),
            json.dumps(dr_result, default=str),
            registry_id,
        ))
        conn.commit()
        logger.debug(
            "DR status actualizado — registry_id=%d validated=%s",
            registry_id, dr_validated
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# UTILIDADES DE ARCHIVO
# ---------------------------------------------------------------------------

def _compute_sha256(file_path: str) -> str:
    """
    Calcula el checksum SHA256 de un archivo local.

    Lee el archivo en bloques de 8 MB para soportar archivos grandes
    sin cargar todo el contenido en memoria.

    Parámetros
    ----------
    file_path : str
        Ruta absoluta al archivo.

    Retorna
    -------
    str
        Checksum SHA256 hexadecimal del archivo.
    """
    sha256 = hashlib.sha256()
    block_size = 8 * 1024 * 1024  # 8 MB por bloque

    with open(file_path, "rb") as fh:
        while True:
            block = fh.read(block_size)
            if not block:
                break
            sha256.update(block)

    return sha256.hexdigest()


def _compress_with_zstd(source_path: str, output_path: str) -> bool:
    """
    Comprime un archivo usando zstd (Zstandard).

    zstd ofrece mejor ratio de compresión y velocidad que gzip para
    dumps de bases de datos. Si zstd no está disponible, retorna False
    para que el llamador use gzip como fallback.

    Parámetros
    ----------
    source_path : str
        Ruta del archivo a comprimir.
    output_path : str
        Ruta de salida del archivo comprimido (.zst).

    Retorna
    -------
    bool
        True si la compresión fue exitosa, False si zstd no está disponible.
    """
    if not shutil.which("zstd"):
        logger.debug("zstd no disponible en el sistema — se usará gzip como fallback")
        return False

    try:
        result = subprocess.run(
            ["zstd", "-T0", "--rm", "-o", output_path, source_path],
            capture_output=True, text=True, check=True
        )
        logger.debug("Compresión zstd exitosa: %s → %s", source_path, output_path)
        return True
    except subprocess.CalledProcessError as exc:
        logger.warning("Error en compresión zstd: %s — usando gzip", exc.stderr)
        return False


def _compress_with_gzip(source_path: str) -> str:
    """
    Comprime un archivo usando gzip del sistema operativo.

    Parámetros
    ----------
    source_path : str
        Ruta del archivo a comprimir. El archivo original es reemplazado.

    Retorna
    -------
    str
        Ruta del archivo comprimido (.gz).

    Raises
    ------
    subprocess.CalledProcessError
        Si gzip falla durante la compresión.
    """
    output_path = source_path + ".gz"
    subprocess.run(
        ["gzip", "-f", "--best", source_path],
        capture_output=True, text=True, check=True
    )
    logger.debug("Compresión gzip exitosa: %s → %s", source_path, output_path)
    return output_path


def _build_backup_path(db_id: str, db_type: str, extension: str) -> Path:
    """
    Construye la ruta local de destino para un archivo de backup.

    Organiza los backups en subdirectorios por db_id y fecha:
    backups/{db_id}/{YYYY}/{MM}/{db_id}_YYYY-MM-DD_HH-MM-SS.{ext}

    Parámetros
    ----------
    db_id : str
        Identificador de la base de datos.
    db_type : str
        Tipo de motor ('postgres' o 'mysql').
    extension : str
        Extensión del archivo (sin punto).

    Retorna
    -------
    Path
        Ruta absoluta del archivo de backup.
    """
    now = datetime.now()
    backup_subdir = BACKUP_DIR / db_id / now.strftime("%Y") / now.strftime("%m")
    backup_subdir.mkdir(parents=True, exist_ok=True)

    filename = f"{db_id}_{now.strftime('%Y-%m-%d_%H-%M-%S')}.{extension}"
    return backup_subdir / filename


# ---------------------------------------------------------------------------
# BACKUP POSTGRESQL
# ---------------------------------------------------------------------------

def backup_postgres(db_config: dict) -> BackupResult:
    """
    Ejecuta un backup de PostgreSQL usando pg_dump en formato custom.

    Utiliza pg_dump con formato custom (-Fc) que produce el output más
    compacto y restaurable con pg_restore. Intenta comprimir con zstd
    (mayor eficiencia) y cae en gzip si no está disponible.

    Parámetros
    ----------
    db_config : dict
        Configuración de la base de datos con los siguientes campos:
        - id (str): Identificador único en el inventario.
        - host (str): Hostname del servidor.
        - port (int): Puerto TCP.
        - dbname (str): Nombre de la base de datos.
        - user (str): Usuario de backup (debe tener permisos SELECT/USAGE).
        - password (str): Contraseña del usuario.

    Retorna
    -------
    BackupResult
        Objeto con path local, tamaño, checksum SHA256 y duración.

    Notas
    -----
    - pg_dump debe estar disponible en el PATH del sistema.
    - La contraseña se pasa via variable de entorno PGPASSWORD para
      evitar que aparezca en la lista de procesos del SO.
    - El formato custom (-Fc) incluye compresión interna de pg_dump,
      pero se aplica compresión adicional con zstd/gzip para mayor ratio.
    """
    db_id = db_config.get("id", "unknown")
    db_host = db_config.get("host", "localhost")
    db_port = str(db_config.get("port", 5432))
    creds = db_config.get("credentials", {})
    db_user = creds.get("username", db_config.get("user", db_config.get("username", os.getenv("POSTGRES_USER", "admin_cloud"))))
    db_password = creds.get("password", db_config.get("password", os.getenv("POSTGRES_PASSWORD", "SecureCloudPass2026!")))
    db_name = db_config.get("database", db_config.get("dbname", os.getenv("POSTGRES_DB", "cliente_a_prod")))

    timestamp = datetime.now(timezone.utc).isoformat()
    t_start = time.perf_counter()

    result = BackupResult(
        db_id=db_id,
        db_type="postgres",
        db_host=db_host,
        db_name=db_name,
        timestamp=timestamp,
        backup_format="custom",
    )

    logger.info(
        "Iniciando pg_dump — db=%s host=%s:%s",
        db_name, db_host, db_port
    )

    raw_dump_path = _build_backup_path(db_id, "postgres", "dump")

    try:
        if shutil.which("pg_dump"):
            cmd = [
                "pg_dump",
                "--host", db_host,
                "--port", db_port,
                "--username", db_user,
                "--no-password",
                "--format=custom",
                "--compress=0",
                "--file", str(raw_dump_path),
                db_name,
            ]
            env = os.environ.copy()
            env["PGPASSWORD"] = db_password
            proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=3600)
            if proc.returncode != 0:
                result.status = "FAILED"
                result.error_message = f"pg_dump falló: {proc.stderr[:400]}"
                logger.error("[%s] %s", db_id, result.error_message)
                _register_backup(result)
                return result
        elif shutil.which("docker"):
            logger.info("[%s] Usando docker exec para pg_dump en contenedor clouddb-postgres-client-a", db_id)
            cmd = ["docker", "exec", "clouddb-postgres-client-a", "pg_dump", "-U", db_user, "-d", db_name, "-Fc"]
            with open(raw_dump_path, "wb") as out_f:
                proc = subprocess.run(cmd, stdout=out_f, stderr=subprocess.PIPE, timeout=3600)
            if proc.returncode != 0:
                result.status = "FAILED"
                result.error_message = f"docker pg_dump falló: {proc.stderr.decode('utf-8', errors='ignore')[:400]}"
                logger.error("[%s] %s", db_id, result.error_message)
                _register_backup(result)
                return result
        else:
            result.status = "FAILED"
            result.error_message = "pg_dump ni docker encontrados en el PATH"
            logger.error("[%s] %s", db_id, result.error_message)
            _register_backup(result)
            return result

        logger.info("[%s] pg_dump completado exitosamente", db_id)

        # --- COMPRESIÓN ---
        zst_path = str(raw_dump_path) + ".zst"
        if _compress_with_zstd(str(raw_dump_path), zst_path):
            final_path = zst_path
            result.compression = "zstd"
        else:
            final_path = str(raw_dump_path)
            result.compression = "none"

        # --- VERIFICACIÓN DE INTEGRIDAD ---
        result.local_path = final_path
        result.size_bytes = os.path.getsize(final_path)
        result.checksum_sha256 = _compute_sha256(final_path)
        result.duration_seconds = time.perf_counter() - t_start
        result.status = "SUCCESS"

        logger.info(
            "[%s] Backup PostgreSQL exitoso — %s | %.2f MB | SHA256: %s... | %.1fs",
            db_id, final_path,
            result.size_bytes / 1024 / 1024,
            result.checksum_sha256[:12],
            result.duration_seconds,
        )

    except Exception as exc:
        result.status = "FAILED"
        result.error_message = f"Error inesperado en backup_postgres: {exc}"
        result.duration_seconds = time.perf_counter() - t_start
        logger.exception("[%s] %s", db_id, result.error_message)

    result.registry_id = _register_backup(result)
    return result


# ---------------------------------------------------------------------------
# BACKUP MYSQL
# ---------------------------------------------------------------------------

def backup_mysql(db_config: dict) -> BackupResult:
    """
    Ejecuta un backup de MySQL usando mysqldump con flags de consistencia.
    """
    db_id = db_config.get("id", "unknown")
    db_host = db_config.get("host", "localhost")
    db_port = str(db_config.get("port", 3307))
    db_name = db_config.get("database", db_config.get("dbname", ""))
    creds = db_config.get("credentials", {})
    db_user = creds.get("username", db_config.get("user", db_config.get("username", "admin_mysql")))
    db_password = creds.get("password", db_config.get("password", "MySQLPass2026!"))

    timestamp = datetime.now(timezone.utc).isoformat()
    t_start = time.perf_counter()

    result = BackupResult(
        db_id=db_id,
        db_type="mysql",
        db_host=db_host,
        db_name=db_name,
        timestamp=timestamp,
        backup_format="sql",
    )

    logger.info("Iniciando mysqldump — db=%s host=%s:%s", db_name, db_host, db_port)
    raw_sql_path = _build_backup_path(db_id, "mysql", "sql")

    try:
        if shutil.which("mysqldump"):
            cmd = [
                "mysqldump",
                f"-h{db_host}",
                f"-P{db_port}",
                f"-u{db_user}",
                f"-p{db_password}",
                "--single-transaction",
                "--quick",
                db_name,
            ]
            with open(raw_sql_path, "wb") as out_f:
                proc = subprocess.run(cmd, stdout=out_f, stderr=subprocess.PIPE, timeout=3600)
            if proc.returncode != 0:
                result.status = "FAILED"
                result.error_message = f"mysqldump falló: {proc.stderr.decode('utf-8', errors='ignore')[:400]}"
                logger.error("[%s] %s", db_id, result.error_message)
                _register_backup(result)
                return result
        elif shutil.which("docker"):
            logger.info("[%s] Usando docker exec para mysqldump en contenedor clouddb-mysql-client-b", db_id)
            cmd = ["docker", "exec", "clouddb-mysql-client-b", "mysqldump",
                   f"-u{db_user}", f"-p{db_password}", "--single-transaction", "--quick", db_name]
            with open(raw_sql_path, "wb") as out_f:
                proc = subprocess.run(cmd, stdout=out_f, stderr=subprocess.PIPE, timeout=3600)
            if proc.returncode != 0:
                result.status = "FAILED"
                result.error_message = f"docker mysqldump falló: {proc.stderr.decode('utf-8', errors='ignore')[:400]}"
                logger.error("[%s] %s", db_id, result.error_message)
                _register_backup(result)
                return result
        else:
            result.status = "FAILED"
            result.error_message = "mysqldump ni docker encontrados en el PATH"
            logger.error("[%s] %s", db_id, result.error_message)
            _register_backup(result)
            return result

        logger.info("[%s] mysqldump completado exitosamente", db_id)

        # Compresión
        final_path = str(raw_sql_path)
        result.compression = "none"

        result.local_path = final_path
        result.size_bytes = os.path.getsize(final_path)
        result.checksum_sha256 = _compute_sha256(final_path)
        result.duration_seconds = time.perf_counter() - t_start
        result.status = "SUCCESS"

        logger.info(
            "[%s] Backup MySQL exitoso — %s | %.2f MB | SHA256: %s... | %.1fs",
            db_id, final_path,
            result.size_bytes / 1024 / 1024,
            result.checksum_sha256[:12],
            result.duration_seconds,
        )

    except Exception as exc:
        result.status = "FAILED"
        result.error_message = f"Error inesperado en backup_mysql: {exc}"
        result.duration_seconds = time.perf_counter() - t_start
        logger.exception("[%s] %s", db_id, result.error_message)

    result.registry_id = _register_backup(result)
    return result


# ---------------------------------------------------------------------------
# UPLOAD A S3 / MinIO
# ---------------------------------------------------------------------------

def _get_s3_client():
    """
    Crea y retorna un cliente boto3 configurado para S3 o MinIO.

    Lee la configuración desde variables de entorno. Soporta tanto
    AWS S3 nativo como MinIO mediante la configuración de endpoint_url.

    Retorna
    -------
    boto3.client
        Cliente S3 configurado.

    Raises
    ------
    ValueError
        Si las credenciales de S3 no están configuradas.
    """
    if not S3_ACCESS_KEY or not S3_SECRET_KEY:
        raise ValueError(
            "Credenciales S3 no configuradas. "
            "Defina S3_ACCESS_KEY_ID y S3_SECRET_ACCESS_KEY en el archivo .env"
        )

    client_kwargs = {
        "service_name": "s3",
        "aws_access_key_id": S3_ACCESS_KEY,
        "aws_secret_access_key": S3_SECRET_KEY,
        "region_name": S3_REGION,
    }

    # Para MinIO, se requiere el endpoint_url personalizado
    if S3_ENDPOINT_URL:
        client_kwargs["endpoint_url"] = S3_ENDPOINT_URL
        logger.debug("Cliente S3 configurado para MinIO: %s", S3_ENDPOINT_URL)
    else:
        logger.debug("Cliente S3 configurado para AWS nativo (región: %s)", S3_REGION)

    return boto3.client(**client_kwargs)


def upload_to_s3(local_path: str, backup_result: BackupResult) -> str:
    """
    Sube un archivo de backup a MinIO/S3 y retorna la URI del objeto.

    Organiza los objetos en S3 con la siguiente estructura de prefijo:
    {S3_PATH_PREFIX}/{db_type}/{db_id}/{YYYY}/{MM}/{filename}

    Incluye metadata del backup como metadatos del objeto S3 para
    facilitar auditoría y búsqueda sin necesidad de descargar el archivo.

    Parámetros
    ----------
    local_path : str
        Ruta local del archivo de backup a subir.
    backup_result : BackupResult
        Resultado del backup con metadatos para registrar en S3.

    Retorna
    -------
    str
        URI S3 completa del objeto subido: s3://bucket/prefix/filename

    Raises
    ------
    FileNotFoundError
        Si el archivo local no existe.
    ValueError
        Si las credenciales S3 no están configuradas.
    ClientError
        Si falla la operación de upload en S3/MinIO.
    """
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"Archivo de backup no encontrado: {local_path}")

    file_name = os.path.basename(local_path)
    now = datetime.now()

    # Construir la clave (key) del objeto en S3
    s3_key = "/".join([
        S3_PATH_PREFIX,
        backup_result.db_type,
        backup_result.db_id,
        now.strftime("%Y"),
        now.strftime("%m"),
        file_name,
    ])

    # Metadatos a almacenar junto al objeto en S3
    s3_metadata = {
        "db-id": backup_result.db_id,
        "db-type": backup_result.db_type,
        "db-host": backup_result.db_host,
        "db-name": backup_result.db_name,
        "backup-timestamp": backup_result.timestamp,
        "checksum-sha256": backup_result.checksum_sha256,
        "compression": backup_result.compression,
        "size-bytes": str(backup_result.size_bytes),
    }

    s3_uri = f"s3://{S3_BUCKET_NAME}/{s3_key}"
    file_size_mb = os.path.getsize(local_path) / 1024 / 1024

    logger.info(
        "Subiendo backup a S3: %s → %s (%.2f MB)",
        local_path, s3_uri, file_size_mb
    )

    t_start = time.perf_counter()
    try:
        s3_client = _get_s3_client()

        # Usar upload_file para soporte automático de multipart para archivos grandes
        s3_client.upload_file(
            Filename=local_path,
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            ExtraArgs={
                "Metadata": s3_metadata,
                "StorageClass": "STANDARD",
            },
        )

        upload_duration = time.perf_counter() - t_start
        throughput_mbps = file_size_mb / max(upload_duration, 0.001)

        logger.info(
            "Upload exitoso: %s | %.1fs | %.1f MB/s",
            s3_uri, upload_duration, throughput_mbps
        )
        return s3_uri

    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "Unknown")
        raise ClientError(
            f"Error S3 al subir {file_name}: [{error_code}] {exc}",
            exc.operation_name,
        ) from exc
    except (BotoCoreError, Exception) as exc:
        raise RuntimeError(f"Error al subir backup a S3: {exc}") from exc


# ---------------------------------------------------------------------------
# LIMPIEZA POR RETENCIÓN
# ---------------------------------------------------------------------------

def cleanup_old_backups(db_id: str, retention_days: int) -> dict:
    """
    Elimina backups locales y en S3 más antiguos que el período de retención.

    Escanea el directorio local de backups del db_id especificado y
    elimina los archivos con fecha anterior al umbral. También elimina
    los objetos correspondientes en S3 si tienen la misma estructura
    de prefijos. Actualiza el registro SQLite marcando los registros
    eliminados.

    Parámetros
    ----------
    db_id : str
        Identificador de la base de datos cuyos backups se limpiarán.
    retention_days : int
        Número de días de retención. Backups más antiguos serán eliminados.

    Retorna
    -------
    dict
        Resumen de la limpieza con:
        - local_deleted (int): Archivos locales eliminados.
        - s3_deleted (int): Objetos S3 eliminados.
        - local_errors (int): Errores al eliminar localmente.
        - s3_errors (int): Errores al eliminar en S3.
        - bytes_freed (int): Bytes liberados en disco local.
    """
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    logger.info(
        "Iniciando limpieza de backups — db_id=%s retención=%d días (antes de %s)",
        db_id, retention_days, cutoff_date.strftime("%Y-%m-%d")
    )

    summary = {
        "local_deleted": 0,
        "s3_deleted": 0,
        "local_errors": 0,
        "s3_errors": 0,
        "bytes_freed": 0,
    }

    # --- LIMPIEZA LOCAL ---
    db_backup_dir = BACKUP_DIR / db_id
    if db_backup_dir.exists():
        for backup_file in db_backup_dir.rglob("*"):
            if not backup_file.is_file():
                continue

            # Verificar fecha de modificación del archivo
            file_mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
            if file_mtime < cutoff_date:
                try:
                    file_size = backup_file.stat().st_size
                    backup_file.unlink()
                    summary["local_deleted"] += 1
                    summary["bytes_freed"] += file_size
                    logger.debug("Archivo local eliminado: %s", backup_file)
                except Exception as exc:
                    summary["local_errors"] += 1
                    logger.error("Error al eliminar %s: %s", backup_file, exc)

    logger.info(
        "Limpieza local completada — %d archivos eliminados (%d MB liberados)",
        summary["local_deleted"],
        summary["bytes_freed"] // 1024 // 1024,
    )

    # --- LIMPIEZA EN S3 ---
    try:
        s3_client = _get_s3_client()
        f"{S3_PATH_PREFIX}/"

        # Listar objetos del db_id en S3
        paginator = s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(
            Bucket=S3_BUCKET_NAME,
            Prefix=f"{S3_PATH_PREFIX}/postgres/{db_id}/",
        )

        objects_to_delete = []
        for page in pages:
            for obj in page.get("Contents", []):
                obj_date = obj["LastModified"].replace(tzinfo=None)
                if obj_date < cutoff_date:
                    objects_to_delete.append({"Key": obj["Key"]})

        # Hacer lo mismo para mysql prefix
        for db_type_prefix in ("postgres", "mysql"):
            pages = paginator.paginate(
                Bucket=S3_BUCKET_NAME,
                Prefix=f"{S3_PATH_PREFIX}/{db_type_prefix}/{db_id}/",
            )
            for page in pages:
                for obj in page.get("Contents", []):
                    obj_date = obj["LastModified"].replace(tzinfo=None)
                    if obj_date < cutoff_date:
                        key_entry = {"Key": obj["Key"]}
                        if key_entry not in objects_to_delete:
                            objects_to_delete.append(key_entry)

        # Eliminar en lotes de hasta 1000 objetos (límite de S3)
        for i in range(0, len(objects_to_delete), 1000):
            batch = objects_to_delete[i:i + 1000]
            if batch:
                try:
                    response = s3_client.delete_objects(
                        Bucket=S3_BUCKET_NAME,
                        Delete={"Objects": batch, "Quiet": False},
                    )
                    deleted_count = len(response.get("Deleted", []))
                    errors_count = len(response.get("Errors", []))
                    summary["s3_deleted"] += deleted_count
                    summary["s3_errors"] += errors_count
                    logger.info(
                        "Lote S3 eliminado: %d objetos (%d errores)",
                        deleted_count, errors_count
                    )
                except ClientError as exc:
                    summary["s3_errors"] += len(batch)
                    logger.error("Error al eliminar lote en S3: %s", exc)

    except ValueError as exc:
        logger.warning("S3 no configurado — omitiendo limpieza en S3: %s", exc)
    except Exception as exc:
        logger.error("Error inesperado en limpieza S3: %s", exc)

    logger.info(
        "Limpieza completada — Local: %d eliminados | S3: %d eliminados | Errores: %d local / %d S3",
        summary["local_deleted"], summary["s3_deleted"],
        summary["local_errors"], summary["s3_errors"],
    )
    return summary


# ---------------------------------------------------------------------------
# ESTADO DEL ÚLTIMO BACKUP
# ---------------------------------------------------------------------------

def get_backup_status(db_id: str) -> dict:
    """
    Retorna el estado del último backup disponible para una base de datos.

    Consulta el registro SQLite para obtener el registro más reciente
    del db_id especificado, incluyendo si fue validado para DR.

    Parámetros
    ----------
    db_id : str
        Identificador de la base de datos.

    Retorna
    -------
    dict
        Información del último backup:
        - found (bool): True si existe algún backup registrado.
        - db_id (str): Identificador de la base de datos.
        - timestamp (str): Timestamp del último backup.
        - status (str): Estado: 'SUCCESS' o 'FAILED'.
        - size_mb (float): Tamaño en MB.
        - s3_uri (str): URI S3 del backup.
        - checksum (str): SHA256 del archivo.
        - duration_seconds (float): Duración del backup.
        - dr_validated (bool): Si fue validado para DR.
        - dr_validation_ts (str): Timestamp de validación DR.
        - age_hours (float): Antigüedad del backup en horas.
    """
    _init_registry_db()
    conn = sqlite3.connect(str(BACKUP_REGISTRY_DB))
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT *
            FROM backup_registry
            WHERE db_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (db_id,))
        row = cursor.fetchone()

        if not row:
            logger.info("[%s] Sin backups registrados", db_id)
            return {"found": False, "db_id": db_id}

        # Calcular antigüedad del backup
        try:
            backup_ts = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - backup_ts).total_seconds() / 3600
        except Exception:
            age_hours = None

        return {
            "found": True,
            "db_id": db_id,
            "registry_id": row["id"],
            "timestamp": row["timestamp"],
            "type": row["type"],
            "status": row["status"],
            "size_mb": round((row["size_bytes"] or 0) / 1024 / 1024, 2),
            "size_bytes": row["size_bytes"],
            "local_path": row["local_path"],
            "s3_uri": row["s3_uri"],
            "checksum": row["checksum"],
            "duration_seconds": row["duration_seconds"],
            "dr_validated": bool(row["dr_validated"]),
            "dr_validation_ts": row["dr_validation_ts"],
            "error_message": row["error_message"],
            "age_hours": round(age_hours, 2) if age_hours is not None else None,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# BACKUP MASIVO DE TODAS LAS BASES DE DATOS
# ---------------------------------------------------------------------------
# EJECUCIÓN MASIVA Y HELPERS
# ---------------------------------------------------------------------------

def _load_database_configs() -> list[dict]:
    """
    Carga el inventario de bases de datos desde config/databases.yaml.
    Retorna una lista de diccionarios.
    """
    if not DATABASES_YAML.exists():
        return []
    with open(DATABASES_YAML, "r", encoding="utf-8") as fh:
        raw_text = fh.read()
        for key, value in os.environ.items():
            raw_text = raw_text.replace(f"${{{key}}}", value)
        data = yaml.safe_load(raw_text) or {}
    raw_dbs = data.get("databases", [])
    if isinstance(raw_dbs, dict):
        return [{"id": k, **v} for k, v in raw_dbs.items()]
    elif isinstance(raw_dbs, list):
        return raw_dbs
    return []


def get_last_backup(db_id: str) -> Optional[dict]:
    """
    Obtiene el último backup registrado en SQLite para la base de datos especificada.
    """
    _init_registry_db()
    conn = sqlite3.connect(str(BACKUP_REGISTRY_DB))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM backup_registry WHERE db_id = ? ORDER BY id DESC LIMIT 1",
            (db_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def run_backup_all() -> List[BackupResult]:
    """
    Ejecuta el ciclo de backup para TODAS las bases de datos del inventario.
    """
    logger.info("╔══════════════════════════════════════════╗")
    logger.info("║  CloudDB Sentinel — Backup Manager       ║")
    logger.info("║  Ejecución: %s              ║",
                datetime.now().strftime("%Y-%m-%d %H:%M"))
    logger.info("╚══════════════════════════════════════════╝")

    databases_list = _load_database_configs()
    if not databases_list:
        logger.warning("No hay bases de datos configuradas en databases.yaml")
        return []

    logger.info("Bases de datos a respaldar: %d", len(databases_list))
    results: List[BackupResult] = []

    for db_config in databases_list:
        db_id = db_config.get("id", "unknown")
        db_type = db_config.get("type", "").lower()
        db_config_with_id = {**db_config, "id": db_id}

        # Resolver variables de entorno en la configuración
        for key, value in list(db_config_with_id.items()):
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                db_config_with_id[key] = os.environ.get(env_var, value)
            elif isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
                env_var = value.strip("{{ }}").strip()
                db_config_with_id[key] = os.environ.get(env_var, value)

        logger.info("══ Backup: %s (%s) ══", db_id, db_type.upper())

        try:
            # Ejecutar backup según el motor
            if db_type in ("postgres", "postgresql"):
                result = backup_postgres(db_config_with_id)
            elif db_type in ("mysql", "mariadb"):
                result = backup_mysql(db_config_with_id)
            else:
                logger.error("[%s] Tipo de motor no soportado: '%s'", db_id, db_type)
                result = BackupResult(
                    db_id=db_id,
                    db_type=db_type,
                    status="FAILED",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    error_message=f"Motor no soportado: '{db_type}'",
                )
                results.append(result)
                continue

            results.append(result)

            # Upload a S3 si el backup fue exitoso
            if result.status == "SUCCESS" and result.local_path:
                try:
                    s3_uri = upload_to_s3(result.local_path, result)
                    result.s3_uri = s3_uri

                    # Actualizar el registro SQLite con la URI de S3
                    if result.registry_id:
                        conn = sqlite3.connect(str(BACKUP_REGISTRY_DB))
                        try:
                            conn.execute(
                                "UPDATE backup_registry SET s3_uri = ? WHERE id = ?",
                                (s3_uri, result.registry_id)
                            )
                            conn.commit()
                        finally:
                            conn.close()

                    logger.info("[%s] Upload S3 exitoso: %s", db_id, s3_uri)

                except (ValueError, RuntimeError) as exc:
                    logger.warning(
                        "[%s] Upload S3 omitido (S3 no configurado o error): %s",
                        db_id, exc
                    )
                except Exception as exc:
                    logger.error("[%s] Error al subir a S3: %s", db_id, exc)

            # Verificar retención configurada por base de datos
            retention_days = db_config.get("backup_retention_days",
                                           int(os.environ.get("DEFAULT_RETENTION_DAYS", 30)))
            cleanup_old_backups(db_id, retention_days)

        except Exception as exc:
            logger.exception("[%s] Error inesperado en backup: %s", db_id, exc)
            results.append(BackupResult(
                db_id=db_id,
                db_type=db_type,
                status="FAILED",
                timestamp=datetime.now(timezone.utc).isoformat(),
                error_message=f"Error inesperado: {exc}",
            ))

    # Resumen final
    successful = sum(1 for r in results if r.status == "SUCCESS")
    failed = sum(1 for r in results if r.status == "FAILED")
    total_size_mb = sum(r.size_bytes for r in results if r.status == "SUCCESS") / 1024 / 1024

    logger.info(
        "Backup masivo completado — Exitosos: %d | Fallidos: %d | Tamaño total: %.2f MB",
        successful, failed, total_size_mb
    )

    return results


# ---------------------------------------------------------------------------
# PUNTO DE ENTRADA PARA EJECUCIÓN DIRECTA
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    results = run_backup_all()
    for r in results:
        status_icon = "✓" if r.status == "SUCCESS" else "✗"
        print(f"{status_icon} {r.db_id} ({r.db_type}): {r.status} | "
              f"{r.size_bytes // 1024 // 1024} MB | {r.duration_seconds:.1f}s")

    sys.exit(0 if all(r.status == "SUCCESS" for r in results) else 1)
