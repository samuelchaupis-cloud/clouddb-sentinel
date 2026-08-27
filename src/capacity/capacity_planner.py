"""
capacity_planner.py - Módulo de Capacity Planning para CloudDB Sentinel v1.0
=============================================================================
Recopila métricas de tamaño de bases de datos y espacio en disco, calcula
tasas de crecimiento mediante regresión lineal y proyecta el consumo futuro
para planificación proactiva de capacidad en entornos B2B de telecomunicaciones.

Autor: CloudDB Sentinel - Equipo de Ingeniería de Plataformas
Fecha: 2026
"""

import sqlite3
import json
import logging
import os
import subprocess
import sys

# Configuración defensiva de encoding para Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional

import psycopg2
import mysql.connector

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Configuración del logger estructurado
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

# ---------------------------------------------------------------------------
# Ruta de la base de datos SQLite de historial
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAPACITY_DB_PATH = os.path.join(BASE_DIR, "data", "capacity_history.db")

# Umbral crítico de disco (porcentaje). Si el uso supera este valor se emite alerta.
DISCO_UMBRAL_CRITICO_PCT = 85.0

# ---------------------------------------------------------------------------
# Dataclasses de dominio
# ---------------------------------------------------------------------------

@dataclass
class CapacitySnapshot:
    """Instantánea de capacidad de una base de datos en un momento dado."""
    db_id: str
    timestamp: str                  # ISO 8601
    db_size_mb: float               # Tamaño de la BD en MiB
    disk_used_gb: float             # Espacio usado en el host en GiB
    disk_total_gb: float            # Espacio total en el host en GiB
    disk_free_gb: float             # Espacio libre en el host en GiB
    disk_usage_percent: float       # Porcentaje de uso del disco
    largest_tables: list = field(default_factory=list)  # Lista de dicts {tabla, size_mb}


@dataclass
class GrowthRate:
    """Resultados del análisis de crecimiento de una base de datos."""
    db_id: str
    window_days: int
    samples: int                    # Número de snapshots usados
    avg_growth_mb_day: float        # Crecimiento promedio en MB/día
    projection_30d_gb: float        # Tamaño proyectado en 30 días (GiB)
    projection_60d_gb: float        # Tamaño proyectado en 60 días (GiB)
    projection_90d_gb: float        # Tamaño proyectado en 90 días (GiB)
    time_to_exhaustion_days: Optional[float]  # Días hasta alcanzar umbral crítico
    trend: str                      # 'stable' | 'growing' | 'accelerating'
    calculated_at: str              # ISO 8601


@dataclass
class Alert:
    """Alerta emitida por el sistema de monitoreo."""
    db_id: str
    level: str          # 'WARNING' | 'CRITICAL'
    category: str       # 'CAPACITY_ALERT' | 'DISK_ALERT' | etc.
    message: str
    value: float
    threshold: float
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class CapacityReport:
    """Reporte consolidado de capacidad para todas las bases de datos."""
    generated_at: str
    db_id: Optional[str]            # None = reporte de todas las BDs
    snapshots: list = field(default_factory=list)
    growth_rates: list = field(default_factory=list)
    alerts: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Inicialización del almacén SQLite de historial
# ---------------------------------------------------------------------------

def _init_capacity_db() -> None:
    """
    Crea la base de datos SQLite y la tabla de historial si no existen.
    Se invoca automáticamente en la primera operación de escritura.
    """
    os.makedirs(os.path.dirname(CAPACITY_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(CAPACITY_DB_PATH)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS capacity_snapshots (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                db_id               TEXT    NOT NULL,
                timestamp           TEXT    NOT NULL,
                db_size_mb          REAL    NOT NULL,
                disk_used_gb        REAL    NOT NULL,
                disk_total_gb       REAL    NOT NULL,
                disk_free_gb        REAL    NOT NULL,
                disk_usage_percent  REAL    NOT NULL,
                largest_tables_json TEXT    DEFAULT '[]'
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cap_db_ts ON capacity_snapshots(db_id, timestamp)"
        )
        conn.commit()
        logger.debug("Base de datos SQLite de capacidad inicializada correctamente.")
    finally:
        conn.close()


def _save_snapshot(snapshot: CapacitySnapshot) -> int:
    """
    Persiste un CapacitySnapshot en el historial SQLite.

    Args:
        snapshot: El snapshot a guardar.

    Returns:
        ID del registro insertado.
    """
    _init_capacity_db()
    conn = sqlite3.connect(CAPACITY_DB_PATH)
    try:
        cursor = conn.execute(
            """
            INSERT INTO capacity_snapshots
                (db_id, timestamp, db_size_mb, disk_used_gb, disk_total_gb,
                 disk_free_gb, disk_usage_percent, largest_tables_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.db_id,
                snapshot.timestamp,
                snapshot.db_size_mb,
                snapshot.disk_used_gb,
                snapshot.disk_total_gb,
                snapshot.disk_free_gb,
                snapshot.disk_usage_percent,
                json.dumps(snapshot.largest_tables, ensure_ascii=False),
            ),
        )
        conn.commit()
        row_id = cursor.lastrowid
        logger.info(
            "Snapshot guardado en SQLite | db_id=%s | id=%d | db_size_mb=%.2f",
            snapshot.db_id,
            row_id,
            snapshot.db_size_mb,
        )
        return row_id
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Helpers de consulta a bases de datos
# ---------------------------------------------------------------------------

def _get_postgres_metrics(db_config: dict) -> tuple[float, list]:
    """
    Consulta el tamaño de la BD y las tablas más grandes en PostgreSQL.
    """
    creds = db_config.get("credentials", {})
    user = creds.get("username", db_config.get("user", db_config.get("username", os.getenv("POSTGRES_USER", "admin_cloud"))))
    password = creds.get("password", db_config.get("password", os.getenv("POSTGRES_PASSWORD", "")))
    database = db_config.get("database", db_config.get("dbname", os.getenv("POSTGRES_DB", "cliente_a_prod")))
    host = db_config.get("host", os.getenv("POSTGRES_HOST", "127.0.0.1"))
    port = int(db_config.get("port", os.getenv("POSTGRES_PORT", 5432)))
    params = {
        "host": host,
        "port": port,
        "database": database,
        "user": user,
        "password": password,
        "connect_timeout": 10,
    }
    try:
        conn = psycopg2.connect(**params)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_database_size(current_database()) / 1048576.0 AS size_mb")
                db_size_mb = float(cur.fetchone()[0])
                cur.execute("""
                    SELECT
                        schemaname || '.' || tablename AS tabla,
                        pg_total_relation_size(schemaname || '.' || tablename) / 1048576.0 AS size_mb
                    FROM pg_tables
                    WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                    ORDER BY 2 DESC
                    LIMIT 10
                """)
                largest_tables = [
                    {"tabla": row[0], "size_mb": round(float(row[1]), 3)}
                    for row in cur.fetchall()
                ]
            return db_size_mb, largest_tables
        finally:
            conn.close()
    except Exception:
        # Fallback a docker exec
        cmd_size = ["docker", "exec", "clouddb-postgres-client-a", "psql", "-U", user, "-d", database, "-t", "-A", "-c", "SELECT pg_database_size(current_database()) / 1048576.0;"]
        proc_s = subprocess.run(cmd_size, capture_output=True, text=True, timeout=15)
        db_size_mb = float(proc_s.stdout.strip()) if proc_s.returncode == 0 and proc_s.stdout.strip() else 0.0

        cmd_tab = ["docker", "exec", "clouddb-postgres-client-a", "psql", "-U", user, "-d", database, "-t", "-A", "-F", "\t", "-c", "SELECT schemaname || '.' || tablename, pg_total_relation_size(schemaname || '.' || tablename) / 1048576.0 FROM pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema') ORDER BY 2 DESC LIMIT 10;"]
        proc_t = subprocess.run(cmd_tab, capture_output=True, text=True, timeout=15)
        largest_tables = []
        if proc_t.returncode == 0 and proc_t.stdout.strip():
            for line in proc_t.stdout.strip().splitlines():
                parts = line.split("\t")
                if len(parts) >= 2:
                    largest_tables.append({"tabla": parts[0], "size_mb": round(float(parts[1]), 3)})
        return db_size_mb, largest_tables


def _get_mysql_metrics(db_config: dict) -> tuple[float, list]:
    """
    Consulta el tamaño de la BD y las tablas más grandes en MySQL/MariaDB.
    """
    creds = db_config.get("credentials", {})
    user = creds.get("username", db_config.get("user", db_config.get("username", os.getenv("MYSQL_USER", "admin_mysql"))))
    password = creds.get("password", db_config.get("password", os.getenv("MYSQL_PASSWORD", "")))
    database = db_config.get("database", db_config.get("dbname", os.getenv("MYSQL_DB", "cliente_b_prod")))
    host = db_config.get("host", os.getenv("MYSQL_HOST", "127.0.0.1"))
    port = int(db_config.get("port", os.getenv("MYSQL_PORT", 3307)))

    conn = mysql.connector.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
        connection_timeout=10,
    )
    try:
        cursor = conn.cursor()
        # Tamaño total de la base de datos en MB
        cursor.execute("""
            SELECT COALESCE(SUM(data_length + index_length), 0) / 1048576.0 AS size_mb
            FROM information_schema.tables
            WHERE table_schema = %s
        """, (database,))
        row = cursor.fetchone()
        db_size_mb = float(row[0]) if row and row[0] else 0.0

        # Top 10 tablas más grandes
        cursor.execute("""
            SELECT
                CONCAT(table_schema, '.', table_name) AS tabla,
                (data_length + index_length) / 1048576.0 AS size_mb
            FROM information_schema.tables
            WHERE table_schema = %s
            ORDER BY size_mb DESC
            LIMIT 10
        """, (database,))
        largest_tables = [
            {"tabla": row[0], "size_mb": round(float(row[1]), 3)}
            for row in cursor.fetchall()
        ]
        cursor.close()
        return db_size_mb, largest_tables
    finally:
        conn.close()


def _get_disk_metrics(db_config: dict) -> tuple[float, float, float, float]:
    """
    Obtiene las métricas del sistema de archivos del host donde reside la BD.
    Para hosts locales usa shutil; para hosts remotos usa la configuración
    disk_total_gb / disk_free_gb si se proveen (override manual).

    Args:
        db_config: Diccionario de configuración de la BD.

    Returns:
        Tupla (disk_used_gb, disk_total_gb, disk_free_gb, disk_usage_pct).
    """
    # Si el usuario provee las métricas de disco directamente (p.ej. para BD remota)
    if "disk_total_gb" in db_config and "disk_free_gb" in db_config:
        total_gb = float(db_config["disk_total_gb"])
        free_gb = float(db_config["disk_free_gb"])
        used_gb = total_gb - free_gb
        pct = (used_gb / total_gb * 100.0) if total_gb > 0 else 0.0
        return used_gb, total_gb, free_gb, pct

    # Fallback: métricas del disco local (donde corre el agente)
    import shutil
    path = db_config.get("data_dir", "/")
    try:
        usage = shutil.disk_usage(path)
        total_gb = usage.total / (1024 ** 3)
        free_gb = usage.free / (1024 ** 3)
        used_gb = usage.used / (1024 ** 3)
        pct = (used_gb / total_gb * 100.0) if total_gb > 0 else 0.0
        return used_gb, total_gb, free_gb, pct
    except Exception as exc:
        logger.warning("No se pudo obtener métricas de disco locales: %s", exc)
        return 0.0, 0.0, 0.0, 0.0


# ---------------------------------------------------------------------------
# Función principal: collect_current_metrics
# ---------------------------------------------------------------------------

def collect_current_metrics(db_config: dict) -> CapacitySnapshot:
    """
    Recopila el tamaño actual de la BD, las tablas más grandes y el espacio en disco
    del host donde reside la base de datos. Persiste un snapshot en SQLite.

    Args:
        db_config: Diccionario de configuración con las siguientes claves obligatorias:
            - db_id (str): Identificador único de la BD (ej. 'crm-prod-pg01')
            - engine (str): 'postgresql' | 'mysql'
            - host (str): Hostname o IP del servidor
            - port (int): Puerto de escucha
            - database (str): Nombre de la base de datos
            - user (str): Usuario de conexión
            - password (str): Contraseña
            Claves opcionales:
            - disk_total_gb (float): Capacidad total del disco en GiB (override)
            - disk_free_gb (float): Espacio libre en disco en GiB (override)
            - data_dir (str): Ruta del sistema de archivos a analizar

    Returns:
        CapacitySnapshot con todos los datos recopilados.

    Raises:
        ValueError: Si 'engine' no es reconocido.
        Exception: Si la conexión a la BD falla.
    """
    db_id = db_config.get("id", db_config.get("db_id", db_config.get("database", "unknown")))
    engine = db_config.get("type", db_config.get("engine", "postgresql")).lower()
    timestamp = datetime.now().isoformat()

    logger.info("Iniciando recopilación de métricas de capacidad | db_id=%s | engine=%s", db_id, engine)

    # Obtener tamaño de la BD y tablas
    try:
        if engine in ("postgresql", "postgres", "pg"):
            db_size_mb, largest_tables = _get_postgres_metrics(db_config)
        elif engine in ("mysql", "mariadb"):
            db_size_mb, largest_tables = _get_mysql_metrics(db_config)
        else:
            raise ValueError(f"Motor de BD no soportado: '{engine}'. Use 'postgresql' o 'mysql'.")
    except Exception as exc:
        logger.error("Error al consultar métricas de BD | db_id=%s | error=%s", db_id, exc)
        raise

    # Obtener métricas de disco
    disk_used_gb, disk_total_gb, disk_free_gb, disk_usage_pct = _get_disk_metrics(db_config)

    snapshot = CapacitySnapshot(
        db_id=db_id,
        timestamp=timestamp,
        db_size_mb=round(db_size_mb, 3),
        disk_used_gb=round(disk_used_gb, 3),
        disk_total_gb=round(disk_total_gb, 3),
        disk_free_gb=round(disk_free_gb, 3),
        disk_usage_percent=round(disk_usage_pct, 2),
        largest_tables=largest_tables,
    )

    # Persistir en historial SQLite
    _save_snapshot(snapshot)

    logger.info(
        "Métricas recopiladas exitosamente | db_id=%s | db_size_mb=%.2f | disk_pct=%.1f%%",
        db_id, snapshot.db_size_mb, snapshot.disk_usage_percent,
    )
    return snapshot


# ---------------------------------------------------------------------------
# Regresión lineal simple (sin numpy, usando solo stdlib)
# ---------------------------------------------------------------------------

def _linear_regression(x_values: list[float], y_values: list[float]) -> tuple[float, float]:
    """
    Calcula los coeficientes de regresión lineal simple: y = slope * x + intercept.
    Implementación manual sin dependencias externas (usa solo operaciones stdlib).

    Args:
        x_values: Lista de valores del eje X (ej. días desde el primer snapshot).
        y_values: Lista de valores del eje Y (ej. db_size_mb).

    Returns:
        Tupla (slope, intercept).
    """
    n = len(x_values)
    if n < 2:
        return 0.0, y_values[0] if y_values else 0.0

    sum_x = sum(x_values)
    sum_y = sum(y_values)
    sum_xy = sum(x * y for x, y in zip(x_values, y_values))
    sum_x2 = sum(x ** 2 for x in x_values)

    denom = n * sum_x2 - sum_x ** 2
    if denom == 0:
        return 0.0, sum_y / n

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    return slope, intercept


def _detect_trend(slope: float, y_values: list[float]) -> str:
    """
    Determina la tendencia de crecimiento basada en la pendiente y dispersión.

    Args:
        slope: Pendiente de la regresión lineal (MB/día).
        y_values: Valores históricos de tamaño.

    Returns:
        'stable' | 'growing' | 'accelerating'
    """
    if abs(slope) < 0.1:
        return "stable"

    # Comparar primera mitad vs segunda mitad para detectar aceleración
    n = len(y_values)
    if n >= 4:
        mid = n // 2
        avg_first_half = sum(y_values[:mid]) / mid
        avg_second_half = sum(y_values[mid:]) / (n - mid)
        # Si la segunda mitad creció más del 20% respecto a la primera
        if avg_first_half > 0 and (avg_second_half / avg_first_half) > 1.20:
            return "accelerating"

    return "growing"


# ---------------------------------------------------------------------------
# Función: calculate_growth_rate
# ---------------------------------------------------------------------------

def calculate_growth_rate(db_id: str, window_days: int = 30) -> GrowthRate:
    """
    Consulta los snapshots históricos en SQLite y calcula la tasa de crecimiento
    mediante regresión lineal simple. Proyecta el tamaño a 30, 60 y 90 días y
    estima cuántos días faltan hasta alcanzar el umbral crítico de disco.

    Args:
        db_id: Identificador de la base de datos a analizar.
        window_days: Ventana temporal en días para el análisis (default: 30).

    Returns:
        GrowthRate con todas las métricas calculadas.

    Raises:
        ValueError: Si no hay suficientes snapshots para el análisis.
    """
    _init_capacity_db()

    since_ts = (datetime.utcnow() - timedelta(days=window_days)).isoformat()
    conn = sqlite3.connect(CAPACITY_DB_PATH)
    try:
        cursor = conn.execute(
            """
            SELECT timestamp, db_size_mb, disk_total_gb, disk_free_gb, disk_usage_percent
            FROM capacity_snapshots
            WHERE db_id = ? AND timestamp >= ?
            ORDER BY timestamp ASC
            """,
            (db_id, since_ts),
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    calculated_at = datetime.utcnow().isoformat()

    if len(rows) < 2:
        logger.warning(
            "Insuficientes snapshots para calcular crecimiento | db_id=%s | samples=%d",
            db_id, len(rows),
        )
        # Retornar objeto con datos vacíos pero sin crash
        return GrowthRate(
            db_id=db_id,
            window_days=window_days,
            samples=len(rows),
            avg_growth_mb_day=0.0,
            projection_30d_gb=0.0,
            projection_60d_gb=0.0,
            projection_90d_gb=0.0,
            time_to_exhaustion_days=None,
            trend="stable",
            calculated_at=calculated_at,
        )

    # Construir ejes X (días desde el primer snapshot) e Y (tamaño en MB)
    t0 = datetime.fromisoformat(rows[0][0])
    x_days = []
    y_size_mb = []
    last_total_gb = 0.0
    last_disk_pct = 0.0

    for ts_str, size_mb, total_gb, free_gb, disk_pct in rows:
        ts = datetime.fromisoformat(ts_str)
        elapsed_days = (ts - t0).total_seconds() / 86400.0
        x_days.append(elapsed_days)
        y_size_mb.append(float(size_mb))
        last_total_gb = float(total_gb)
        last_disk_pct = float(disk_pct)

    # Regresión lineal: slope = MB/día
    slope, intercept = _linear_regression(x_days, y_size_mb)
    avg_growth_mb_day = slope  # positivo = crecimiento, negativo = reducción

    # Proyecciones desde el último snapshot
    last_x = x_days[-1]
    last_size_mb = y_size_mb[-1]

    def project(future_days: int) -> float:
        """Proyecta el tamaño en un número de días en el futuro."""
        projected_mb = last_size_mb + avg_growth_mb_day * future_days
        return max(0.0, projected_mb / 1024.0)  # Convertir a GiB

    projection_30d_gb = round(project(30), 3)
    projection_60d_gb = round(project(60), 3)
    projection_90d_gb = round(project(90), 3)

    # Calcular días hasta agotar el disco (umbral crítico)
    time_to_exhaustion_days = None
    if avg_growth_mb_day > 0 and last_total_gb > 0:
        # Espacio libre actual en MB
        current_free_mb = (last_total_gb * 1024) * (1 - DISCO_UMBRAL_CRITICO_PCT / 100.0)
        # Espacio libre disponible en MB considerando el umbral
        current_used_mb = last_size_mb
        available_mb = (last_total_gb * 1024 * (DISCO_UMBRAL_CRITICO_PCT / 100.0)) - current_used_mb
        if available_mb > 0:
            time_to_exhaustion_days = round(available_mb / avg_growth_mb_day, 1)
        else:
            time_to_exhaustion_days = 0.0  # Ya superó el umbral

    trend = _detect_trend(slope, y_size_mb)

    logger.info(
        "Tasa de crecimiento calculada | db_id=%s | slope=%.3f MB/día | trend=%s | exhaustion=%s días",
        db_id, avg_growth_mb_day, trend,
        f"{time_to_exhaustion_days:.0f}" if time_to_exhaustion_days is not None else "N/A",
    )

    return GrowthRate(
        db_id=db_id,
        window_days=window_days,
        samples=len(rows),
        avg_growth_mb_day=round(avg_growth_mb_day, 4),
        projection_30d_gb=projection_30d_gb,
        projection_60d_gb=projection_60d_gb,
        projection_90d_gb=projection_90d_gb,
        time_to_exhaustion_days=time_to_exhaustion_days,
        trend=trend,
        calculated_at=calculated_at,
    )


# ---------------------------------------------------------------------------
# Función: generate_capacity_report
# ---------------------------------------------------------------------------

def generate_capacity_report(db_id: str = None) -> CapacityReport:
    """
    Genera un reporte consolidado de capacidad con snapshots, tasas de crecimiento,
    alertas y recomendaciones textuales para el especialista Cloud.

    Args:
        db_id: Si se especifica, genera el reporte solo para esa BD.
               Si es None, genera el reporte para todas las BDs en el historial.

    Returns:
        CapacityReport con toda la información de capacidad.
    """
    _init_capacity_db()
    generated_at = datetime.utcnow().isoformat()
    conn = sqlite3.connect(CAPACITY_DB_PATH)

    try:
        # Obtener lista de db_ids a reportar
        if db_id:
            db_ids = [db_id]
        else:
            cursor = conn.execute(
                "SELECT DISTINCT db_id FROM capacity_snapshots ORDER BY db_id"
            )
            db_ids = [row[0] for row in cursor.fetchall()]

        all_snapshots = []
        all_growth_rates = []
        all_alerts = []
        all_recommendations = []

        for did in db_ids:
            # Último snapshot de cada BD
            cursor = conn.execute(
                """
                SELECT db_id, timestamp, db_size_mb, disk_used_gb, disk_total_gb,
                       disk_free_gb, disk_usage_percent, largest_tables_json
                FROM capacity_snapshots
                WHERE db_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (did,),
            )
            row = cursor.fetchone()
            if row:
                snap = CapacitySnapshot(
                    db_id=row[0],
                    timestamp=row[1],
                    db_size_mb=row[2],
                    disk_used_gb=row[3],
                    disk_total_gb=row[4],
                    disk_free_gb=row[5],
                    disk_usage_percent=row[6],
                    largest_tables=json.loads(row[7] or "[]"),
                )
                all_snapshots.append(asdict(snap))

            # Calcular tasa de crecimiento
            try:
                gr = calculate_growth_rate(did, window_days=30)
                all_growth_rates.append(asdict(gr))

                # Generar recomendaciones basadas en los datos
                recs = _generate_recommendations(did, snap if row else None, gr)
                all_recommendations.extend(recs)

                # Verificar alertas de capacidad
                if snap and row:
                    if snap.disk_usage_percent >= DISCO_UMBRAL_CRITICO_PCT:
                        all_alerts.append(asdict(Alert(
                            db_id=did,
                            level="CRITICAL",
                            category="DISK_ALERT",
                            message=f"Uso de disco CRÍTICO: {snap.disk_usage_percent:.1f}% ≥ {DISCO_UMBRAL_CRITICO_PCT}%",
                            value=snap.disk_usage_percent,
                            threshold=DISCO_UMBRAL_CRITICO_PCT,
                        )))
                    elif snap.disk_usage_percent >= DISCO_UMBRAL_CRITICO_PCT * 0.85:
                        all_alerts.append(asdict(Alert(
                            db_id=did,
                            level="WARNING",
                            category="DISK_ALERT",
                            message=f"Uso de disco ELEVADO: {snap.disk_usage_percent:.1f}%",
                            value=snap.disk_usage_percent,
                            threshold=DISCO_UMBRAL_CRITICO_PCT * 0.85,
                        )))

                    if gr.time_to_exhaustion_days is not None and gr.time_to_exhaustion_days < 30:
                        all_alerts.append(asdict(Alert(
                            db_id=did,
                            level="CRITICAL",
                            category="CAPACITY_ALERT",
                            message=f"Agotamiento de disco proyectado en {gr.time_to_exhaustion_days:.0f} días",
                            value=gr.time_to_exhaustion_days,
                            threshold=30.0,
                        )))

            except Exception as exc:
                logger.warning("No se pudo calcular crecimiento para db_id=%s: %s", did, exc)

    finally:
        conn.close()

    report = CapacityReport(
        generated_at=generated_at,
        db_id=db_id,
        snapshots=all_snapshots,
        growth_rates=all_growth_rates,
        alerts=all_alerts,
        recommendations=all_recommendations,
    )

    logger.info(
        "Reporte de capacidad generado | db_id=%s | BDs analizadas=%d | alertas=%d",
        db_id or "ALL", len(db_ids), len(all_alerts),
    )
    return report


def _generate_recommendations(db_id: str, snapshot: Optional[CapacitySnapshot], gr: GrowthRate) -> list[str]:
    """
    Genera recomendaciones textuales para el especialista Cloud basadas en el
    análisis de capacidad de la base de datos.

    Args:
        db_id: Identificador de la BD.
        snapshot: Último snapshot de capacidad.
        gr: Objeto GrowthRate con las proyecciones.

    Returns:
        Lista de strings con recomendaciones.
    """
    recs = []

    if snapshot is None:
        return [f"[{db_id}] Sin datos suficientes para generar recomendaciones."]

    # Recomendaciones basadas en uso de disco
    if snapshot.disk_usage_percent >= DISCO_UMBRAL_CRITICO_PCT:
        recs.append(
            f"[{db_id}] ACCIÓN INMEDIATA: El disco ha superado el umbral crítico "
            f"({snapshot.disk_usage_percent:.1f}%). Ampliar capacidad de almacenamiento "
            f"o ejecutar purga de datos históricos antes de las próximas 24 horas."
        )
    elif snapshot.disk_usage_percent >= 70:
        recs.append(
            f"[{db_id}] Planificar ampliación de disco. Uso actual: "
            f"{snapshot.disk_usage_percent:.1f}%. Se recomienda provisionar almacenamiento "
            f"adicional en los próximos 30 días."
        )

    # Recomendaciones basadas en tendencia de crecimiento
    if gr.trend == "accelerating":
        recs.append(
            f"[{db_id}] ALERTA DE TENDENCIA: El crecimiento está acelerándose. "
            f"Revisar si hay procesos de carga masiva de datos no planificados. "
            f"Proyección a 90 días: {gr.projection_90d_gb:.2f} GB."
        )
    elif gr.trend == "growing" and gr.avg_growth_mb_day > 100:
        recs.append(
            f"[{db_id}] Crecimiento sostenido de {gr.avg_growth_mb_day:.1f} MB/día. "
            f"Considerar política de archivado o particionamiento de tablas históricas."
        )

    # Recomendaciones basadas en tiempo hasta agotamiento
    if gr.time_to_exhaustion_days is not None:
        if gr.time_to_exhaustion_days < 14:
            recs.append(
                f"[{db_id}] URGENTE: Al ritmo actual de crecimiento el disco se agotará "
                f"en aproximadamente {gr.time_to_exhaustion_days:.0f} días. "
                f"Escalar volumen de almacenamiento inmediatamente."
            )
        elif gr.time_to_exhaustion_days < 60:
            recs.append(
                f"[{db_id}] Iniciar proceso de solicitud de ampliación de disco. "
                f"Tiempo estimado hasta límite: {gr.time_to_exhaustion_days:.0f} días."
            )

    # Recomendación de tablas más grandes
    if snapshot.largest_tables:
        top_table = snapshot.largest_tables[0]
        if top_table["size_mb"] > 1024:
            recs.append(
                f"[{db_id}] La tabla '{top_table['tabla']}' ocupa {top_table['size_mb']:.0f} MB. "
                f"Evaluar estrategia de particionamiento o archivado para esta tabla."
            )

    if not recs:
        recs.append(
            f"[{db_id}] Capacidad dentro de parámetros normales. "
            f"Uso de disco: {snapshot.disk_usage_percent:.1f}% | "
            f"Crecimiento: {gr.avg_growth_mb_day:.2f} MB/día."
        )

    return recs


# ---------------------------------------------------------------------------
# Función: check_capacity_alerts
# ---------------------------------------------------------------------------

def check_capacity_alerts(db_config: dict, alert_rules: dict) -> list[Alert]:
    """
    Verifica si el disco o la base de datos superan los umbrales configurados
    y emite una lista de alertas activas.

    Args:
        db_config: Configuración de la base de datos (mismo formato que collect_current_metrics).
        alert_rules: Diccionario con umbrales de alerta:
            - disk_warning_pct (float): Umbral de advertencia de disco. Default: 75.0
            - disk_critical_pct (float): Umbral crítico de disco. Default: 85.0
            - db_size_warning_mb (float): Tamaño de BD en MB que dispara WARNING.
            - db_size_critical_mb (float): Tamaño de BD en MB que dispara CRITICAL.
            - exhaustion_warning_days (int): Días hasta agotamiento para WARNING. Default: 60
            - exhaustion_critical_days (int): Días hasta agotamiento para CRITICAL. Default: 14

    Returns:
        Lista de objetos Alert con las alertas activas.
    """
    db_id = db_config.get("db_id", db_config.get("database", "unknown"))
    alerts = []

    # Configurar umbrales con defaults
    disk_warn_pct = float(alert_rules.get("disk_warning_pct", 75.0))
    disk_crit_pct = float(alert_rules.get("disk_critical_pct", 85.0))
    db_size_warn_mb = float(alert_rules.get("db_size_warning_mb", 5120.0))   # 5 GB
    db_size_crit_mb = float(alert_rules.get("db_size_critical_mb", 10240.0)) # 10 GB
    exhaust_warn_days = int(alert_rules.get("exhaustion_warning_days", 60))
    exhaust_crit_days = int(alert_rules.get("exhaustion_critical_days", 14))

    # Recopilar métricas actuales
    try:
        snapshot = collect_current_metrics(db_config)
    except Exception as exc:
        logger.error("No se pudo recopilar métricas para verificar alertas | db_id=%s | error=%s", db_id, exc)
        alerts.append(Alert(
            db_id=db_id,
            level="CRITICAL",
            category="COLLECTION_ERROR",
            message=f"Error al recopilar métricas de capacidad: {exc}",
            value=0.0,
            threshold=0.0,
        ))
        return alerts

    # --- Verificar uso de disco ---
    if snapshot.disk_usage_percent >= disk_crit_pct:
        alerts.append(Alert(
            db_id=db_id,
            level="CRITICAL",
            category="DISK_ALERT",
            message=(
                f"Uso de disco CRÍTICO en {db_id}: {snapshot.disk_usage_percent:.1f}% "
                f"(umbral: {disk_crit_pct}%). Libre: {snapshot.disk_free_gb:.2f} GB."
            ),
            value=snapshot.disk_usage_percent,
            threshold=disk_crit_pct,
        ))
    elif snapshot.disk_usage_percent >= disk_warn_pct:
        alerts.append(Alert(
            db_id=db_id,
            level="WARNING",
            category="DISK_ALERT",
            message=(
                f"Uso de disco ELEVADO en {db_id}: {snapshot.disk_usage_percent:.1f}% "
                f"(umbral: {disk_warn_pct}%). Libre: {snapshot.disk_free_gb:.2f} GB."
            ),
            value=snapshot.disk_usage_percent,
            threshold=disk_warn_pct,
        ))

    # --- Verificar tamaño de la BD ---
    if snapshot.db_size_mb >= db_size_crit_mb:
        alerts.append(Alert(
            db_id=db_id,
            level="CRITICAL",
            category="DB_SIZE_ALERT",
            message=(
                f"Tamaño de BD {db_id} CRÍTICO: {snapshot.db_size_mb:.0f} MB "
                f"(umbral: {db_size_crit_mb:.0f} MB)."
            ),
            value=snapshot.db_size_mb,
            threshold=db_size_crit_mb,
        ))
    elif snapshot.db_size_mb >= db_size_warn_mb:
        alerts.append(Alert(
            db_id=db_id,
            level="WARNING",
            category="DB_SIZE_ALERT",
            message=(
                f"Tamaño de BD {db_id} ELEVADO: {snapshot.db_size_mb:.0f} MB "
                f"(umbral: {db_size_warn_mb:.0f} MB)."
            ),
            value=snapshot.db_size_mb,
            threshold=db_size_warn_mb,
        ))

    # --- Verificar proyección de agotamiento ---
    try:
        gr = calculate_growth_rate(db_id, window_days=30)
        if gr.time_to_exhaustion_days is not None:
            if gr.time_to_exhaustion_days <= exhaust_crit_days:
                alerts.append(Alert(
                    db_id=db_id,
                    level="CRITICAL",
                    category="CAPACITY_ALERT",
                    message=(
                        f"Agotamiento de disco proyectado en {gr.time_to_exhaustion_days:.0f} días "
                        f"para {db_id} (umbral crítico: {exhaust_crit_days} días)."
                    ),
                    value=gr.time_to_exhaustion_days,
                    threshold=float(exhaust_crit_days),
                ))
            elif gr.time_to_exhaustion_days <= exhaust_warn_days:
                alerts.append(Alert(
                    db_id=db_id,
                    level="WARNING",
                    category="CAPACITY_ALERT",
                    message=(
                        f"Agotamiento de disco proyectado en {gr.time_to_exhaustion_days:.0f} días "
                        f"para {db_id} (umbral advertencia: {exhaust_warn_days} días)."
                    ),
                    value=gr.time_to_exhaustion_days,
                    threshold=float(exhaust_warn_days),
                ))
    except Exception as exc:
        logger.warning("No se pudo calcular proyección de agotamiento | db_id=%s: %s", db_id, exc)

    logger.info(
        "Verificación de alertas de capacidad completada | db_id=%s | alertas_emitidas=%d",
        db_id, len(alerts),
    )
    return alerts


# ---------------------------------------------------------------------------
# Función: run_capacity_collection_all
# ---------------------------------------------------------------------------

def run_capacity_collection_all() -> dict:
    """
    Recorre el inventario de bases de datos configuradas y recopila las métricas
    de capacidad de todas ellas. Lee el inventario desde config/databases.yaml.
    """
    import yaml
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    inventory_path = os.path.join(BASE_DIR, "config", "databases.yaml")

    if not os.path.exists(inventory_path):
        logger.error("Archivo de inventario no encontrado: %s", inventory_path)
        return {"success": [], "failed": [{"error": f"Inventario no encontrado: {inventory_path}"}]}

    with open(inventory_path, "r", encoding="utf-8") as f:
        raw_text = f.read()
        for key, value in os.environ.items():
            raw_text = raw_text.replace(f"${{{key}}}", value)
        config = yaml.safe_load(raw_text) or {}

    raw_dbs = config.get("databases", [])
    if isinstance(raw_dbs, dict):
        databases = [{"id": k, **v} for k, v in raw_dbs.items()]
    elif isinstance(raw_dbs, list):
        databases = raw_dbs
    else:
        databases = []

    if not databases:
        logger.warning("No se encontraron bases de datos en el inventario.")
        return {"success": [], "failed": []}

    results = {"success": [], "failed": []}

    for db_conf in databases:
        db_id = db_conf.get("id", db_conf.get("db_id", "unknown"))
        try:
            logger.info("Recopilando métricas de capacidad para: %s", db_id)
            snapshot = collect_current_metrics(db_conf)
            results["success"].append({
                "db_id": db_id,
                "db_size_mb": snapshot.db_size_mb,
                "disk_usage_percent": snapshot.disk_usage_percent,
                "timestamp": snapshot.timestamp,
            })
        except Exception as exc:
            logger.error("Fallo al recopilar métricas | db_id=%s | error=%s", db_id, exc)
            results["failed"].append({"db_id": db_id, "error": str(exc)})

    logger.info(
        "Recopilación de capacidad finalizada | exitosas=%d | fallidas=%d",
        len(results["success"]), len(results["failed"]),
    )
    return results


# ---------------------------------------------------------------------------
# Punto de entrada para ejecución directa
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    """
    Ejecución directa para pruebas. Recopila y genera un reporte de capacidad de todas las BDs.
    """
    import sys
    print("=== CloudDB Sentinel - Capacity Planner ===")
    run_capacity_collection_all()
    db_arg = sys.argv[1] if len(sys.argv) > 1 else None
    report = generate_capacity_report(db_id=db_arg)
    print(f"Reporte generado: {report.generated_at}")
    print(f"Snapshots: {len(report.snapshots)} | Alertas: {len(report.alerts)}")
    for alert in report.alerts:
        print(f"  [{alert['level']}] {alert['message']}")
    for rec in report.recommendations:
        print(f"  REC: {rec}")
