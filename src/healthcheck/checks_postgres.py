"""
checks_postgres.py — CloudDB Sentinel
======================================
Módulo de health checks para bases de datos PostgreSQL.

Ejecuta 15 verificaciones diagnósticas sobre una instancia PostgreSQL y
retorna un diccionario estructurado con el resultado de cada check.

Autor: Equipo de Plataformas Cloud
Versión: 1.0.0
"""

import logging
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Optional

# psycopg2 es la librería oficial para conexión a PostgreSQL desde Python
try:
    import psycopg2
    import psycopg2.extras
except ImportError as exc:
    raise ImportError(
        "Dependencia faltante: instale psycopg2-binary con "
        "'pip install psycopg2-binary'"
    ) from exc

# Logger con nombre jerárquico para integración con el sistema de logging central
logger = logging.getLogger("clouddb_sentinel.healthcheck.postgres")

# ---------------------------------------------------------------------------
# CONSTANTES DE UMBRALES POR DEFECTO
# Los valores pueden sobreescribirse desde alert_rules.yaml
# ---------------------------------------------------------------------------
DEFAULT_THRESHOLDS = {
    "connection_latency_warning_ms": 100,
    "connection_latency_critical_ms": 500,
    "connections_warning_pct": 70,
    "connections_critical_pct": 90,
    "cache_hit_warning_pct": 95,
    "cache_hit_critical_pct": 90,
    "locks_warning_count": 5,
    "locks_critical_count": 20,
    "long_query_warning_count": 3,
    "long_query_critical_count": 10,
    "long_query_threshold_seconds": 30,
    "dead_tuples_warning": 1000,
    "dead_tuples_critical": 10000,
    "replication_lag_warning_bytes": 52428800,    # 50 MB
    "replication_lag_critical_bytes": 209715200,  # 200 MB
    "checkpoint_req_warning_pct": 20,             # % de checkpoints forzados
    "temp_files_warning_count": 10,
    "bloat_warning_pct": 30,
    "vacuum_stale_days": 7,
}


# ---------------------------------------------------------------------------
# FUNCIONES AUXILIARES
# ---------------------------------------------------------------------------

def _build_result(
    check_name: str,
    status: str,
    value: Any,
    threshold: Any,
    message: str,
    duration_ms: float,
    details: Optional[dict] = None,
) -> dict:
    """
    Construye el diccionario estandarizado de resultado de un check.

    Parámetros
    ----------
    check_name : str
        Nombre interno del check (snake_case).
    status : str
        Estado resultante: 'OK', 'WARNING' o 'CRITICAL'.
    value : Any
        Valor medido en el check.
    threshold : Any
        Umbral aplicado para determinar el estado.
    message : str
        Mensaje descriptivo legible para el operador.
    duration_ms : float
        Tiempo de ejecución del check en milisegundos.
    details : dict, opcional
        Información adicional estructurada (filas, listas, etc.).

    Retorna
    -------
    dict
        Resultado estandarizado del check.
    """
    result = {
        "check_name": check_name,
        "status": status,
        "value": value,
        "threshold": threshold,
        "message": message,
        "duration_ms": round(duration_ms, 3),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if details is not None:
        result["details"] = details
    return result


def _elapsed_ms(start: float) -> float:
    """Calcula milisegundos transcurridos desde `start` (time.perf_counter)."""
    return (time.perf_counter() - start) * 1000


def _safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """División segura que retorna `default` si el denominador es cero."""
    if denominator == 0:
        return default
    return numerator / denominator


# ---------------------------------------------------------------------------
# CHECKS INDIVIDUALES
# ---------------------------------------------------------------------------

def check_connection(conn_params: dict, thresholds: dict) -> dict:
    """
    CHECK 1 — Verificación de conectividad y latencia.

    Intenta abrir una conexión a PostgreSQL, ejecuta 'SELECT 1' y mide
    la latencia total en milisegundos.

    Parámetros
    ----------
    conn_params : dict
        Parámetros de conexión psycopg2 (host, port, dbname, user, password).
    thresholds : dict
        Umbrales para clasificar el estado.

    Retorna
    -------
    dict
        Resultado estandarizado con latencia medida.
    """
    check_name = "connection_check"
    t0 = time.perf_counter()
    try:
        conn = psycopg2.connect(**conn_params, connect_timeout=10)
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.close()

        latency_ms = _elapsed_ms(t0)

        if latency_ms >= thresholds["connection_latency_critical_ms"]:
            status = "CRITICAL"
            msg = f"Latencia crítica de conexión: {latency_ms:.1f} ms"
        elif latency_ms >= thresholds["connection_latency_warning_ms"]:
            status = "WARNING"
            msg = f"Latencia de conexión elevada: {latency_ms:.1f} ms"
        else:
            status = "OK"
            msg = f"Conexión exitosa con latencia normal: {latency_ms:.1f} ms"

        logger.debug("[%s] %s — latencia=%.1f ms", check_name, status, latency_ms)
        return _build_result(check_name, status, latency_ms,
                             thresholds["connection_latency_warning_ms"], msg, latency_ms)

    except psycopg2.OperationalError as exc:
        duration = _elapsed_ms(t0)
        msg = f"No se pudo conectar a PostgreSQL: {exc}"
        logger.error("[%s] CRITICAL — %s", check_name, msg)
        return _build_result(check_name, "CRITICAL", None, None, msg, duration)
    except Exception as exc:
        duration = _elapsed_ms(t0)
        msg = f"Error inesperado en connection_check: {exc}"
        logger.exception("[%s] ERROR — %s", check_name, msg)
        return _build_result(check_name, "CRITICAL", None, None, msg, duration)


def check_active_connections(conn, thresholds: dict) -> dict:
    """
    CHECK 2 — Conexiones activas vs. límite configurado.

    Consulta pg_stat_activity para obtener el número de conexiones activas
    y lo compara con max_connections para calcular el porcentaje de uso.

    Parámetros
    ----------
    conn : psycopg2.connection
        Conexión activa a PostgreSQL.
    thresholds : dict
        Umbrales de porcentaje (warning_pct, critical_pct).

    Retorna
    -------
    dict
        Resultado con: activas, máximo y porcentaje de uso.
    """
    check_name = "active_connections"
    t0 = time.perf_counter()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Obtener límite máximo de conexiones configurado
            cur.execute("SHOW max_connections")
            max_conn = int(cur.fetchone()[0])

            # Conexiones actuales excluyendo la sesión de monitoreo
            cur.execute("""
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE state = 'active') AS active,
                       COUNT(*) FILTER (WHERE state = 'idle') AS idle,
                       COUNT(*) FILTER (WHERE state = 'idle in transaction') AS idle_in_txn
                FROM pg_stat_activity
                WHERE pid <> pg_backend_pid()
            """)
            row = cur.fetchone()
            total = row["total"]
            active = row["active"]
            idle_in_txn = row["idle_in_txn"]

        usage_pct = _safe_divide(total, max_conn) * 100
        duration = _elapsed_ms(t0)

        if usage_pct >= thresholds["connections_critical_pct"]:
            status = "CRITICAL"
            msg = (f"Uso crítico de conexiones: {total}/{max_conn} "
                   f"({usage_pct:.1f}%)")
        elif usage_pct >= thresholds["connections_warning_pct"]:
            status = "WARNING"
            msg = (f"Uso elevado de conexiones: {total}/{max_conn} "
                   f"({usage_pct:.1f}%)")
        else:
            status = "OK"
            msg = (f"Conexiones en rango normal: {total}/{max_conn} "
                   f"({usage_pct:.1f}%)")

        logger.debug("[%s] %s — %d/%d (%.1f%%)", check_name, status, total, max_conn, usage_pct)
        return _build_result(
            check_name, status,
            value={"total": total, "active": active, "idle_in_txn": idle_in_txn, "usage_pct": round(usage_pct, 2)},
            threshold={"warning_pct": thresholds["connections_warning_pct"],
                       "critical_pct": thresholds["connections_critical_pct"],
                       "max_connections": max_conn},
            message=msg,
            duration_ms=duration,
        )
    except Exception as exc:
        duration = _elapsed_ms(t0)
        msg = f"Error en active_connections: {exc}"
        logger.exception("[%s] ERROR — %s", check_name, msg)
        return _build_result(check_name, "CRITICAL", None, None, msg, duration)


def check_cache_hit_ratio(conn, thresholds: dict) -> dict:
    """
    CHECK 3 — Ratio de aciertos de caché (buffer cache hit ratio).

    Calcula heap_blks_hit / (heap_blks_hit + heap_blks_read) sobre
    pg_statio_user_tables. Un ratio bajo indica presión de I/O en disco.

    Parámetros
    ----------
    conn : psycopg2.connection
        Conexión activa a PostgreSQL.
    thresholds : dict
        Umbrales de porcentaje mínimo aceptable.

    Retorna
    -------
    dict
        Resultado con el ratio de caché en porcentaje.
    """
    check_name = "cache_hit_ratio"
    t0 = time.perf_counter()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    SUM(heap_blks_hit)  AS hits,
                    SUM(heap_blks_read) AS reads
                FROM pg_statio_user_tables
            """)
            row = cur.fetchone()
            hits = row[0] or 0
            reads = row[1] or 0

        ratio_pct = _safe_divide(hits, hits + reads, default=100.0) * 100
        duration = _elapsed_ms(t0)

        if ratio_pct < thresholds["cache_hit_critical_pct"]:
            status = "CRITICAL"
            msg = f"Cache hit ratio crítico: {ratio_pct:.2f}% (mín. recomendado 90%)"
        elif ratio_pct < thresholds["cache_hit_warning_pct"]:
            status = "WARNING"
            msg = f"Cache hit ratio bajo: {ratio_pct:.2f}% (se recomienda ≥95%)"
        else:
            status = "OK"
            msg = f"Cache hit ratio saludable: {ratio_pct:.2f}%"

        logger.debug("[%s] %s — ratio=%.2f%%", check_name, status, ratio_pct)
        return _build_result(
            check_name, status,
            value={"cache_hit_ratio_pct": round(ratio_pct, 4), "total_hits": hits, "total_reads": reads},
            threshold={"warning_pct": thresholds["cache_hit_warning_pct"],
                       "critical_pct": thresholds["cache_hit_critical_pct"]},
            message=msg,
            duration_ms=duration,
        )
    except Exception as exc:
        duration = _elapsed_ms(t0)
        msg = f"Error en cache_hit_ratio: {exc}"
        logger.exception("[%s] ERROR — %s", check_name, msg)
        return _build_result(check_name, "CRITICAL", None, None, msg, duration)


def check_locks(conn, thresholds: dict) -> dict:
    """
    CHECK 4 — Bloqueos en espera (blocked locks).

    Consulta pg_locks filtrando granted=false para detectar sesiones
    bloqueadas. Un número elevado indica contención de recursos.

    Parámetros
    ----------
    conn : psycopg2.connection
        Conexión activa a PostgreSQL.
    thresholds : dict
        Umbrales de cantidad de locks en espera.

    Retorna
    -------
    dict
        Resultado con número de locks en espera y detalle de los mismos.
    """
    check_name = "locks_check"
    t0 = time.perf_counter()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT
                    l.pid,
                    l.locktype,
                    l.mode,
                    l.relation::regclass AS table_name,
                    a.query,
                    a.query_start,
                    a.wait_event_type,
                    a.wait_event
                FROM pg_locks l
                JOIN pg_stat_activity a ON l.pid = a.pid
                WHERE l.granted = false
                ORDER BY a.query_start
                LIMIT 50
            """)
            blocked = [dict(row) for row in cur.fetchall()]

        # Serializar los objetos datetime para JSON
        for row in blocked:
            if row.get("query_start") and hasattr(row["query_start"], "isoformat"):
                row["query_start"] = row["query_start"].isoformat()

        count = len(blocked)
        duration = _elapsed_ms(t0)

        if count >= thresholds["locks_critical_count"]:
            status = "CRITICAL"
            msg = f"Número crítico de locks en espera: {count}"
        elif count >= thresholds["locks_warning_count"]:
            status = "WARNING"
            msg = f"Locks en espera detectados: {count}"
        else:
            status = "OK"
            msg = f"Sin contención significativa de locks: {count} en espera"

        logger.debug("[%s] %s — %d locks en espera", check_name, status, count)
        return _build_result(
            check_name, status,
            value=count,
            threshold={"warning": thresholds["locks_warning_count"],
                       "critical": thresholds["locks_critical_count"]},
            message=msg,
            duration_ms=duration,
            details={"blocked_sessions": blocked},
        )
    except Exception as exc:
        duration = _elapsed_ms(t0)
        msg = f"Error en locks_check: {exc}"
        logger.exception("[%s] ERROR — %s", check_name, msg)
        return _build_result(check_name, "CRITICAL", None, None, msg, duration)


def check_long_running_queries(conn, thresholds: dict) -> dict:
    """
    CHECK 5 — Consultas de larga duración en ejecución.

    Detecta queries activos con duración superior al umbral configurado
    (default: 30 segundos). Estas consultas pueden causar contención
    y degradación del rendimiento.

    Parámetros
    ----------
    conn : psycopg2.connection
        Conexión activa a PostgreSQL.
    thresholds : dict
        Umbral en segundos y conteos de warning/critical.

    Retorna
    -------
    dict
        Resultado con lista de queries problemáticos y su duración.
    """
    check_name = "long_running_queries"
    t0 = time.perf_counter()
    threshold_sec = thresholds.get("long_query_threshold_seconds", 30)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT
                    pid,
                    usename AS username,
                    application_name,
                    client_addr,
                    state,
                    wait_event_type,
                    wait_event,
                    EXTRACT(EPOCH FROM (now() - query_start))::int AS duration_seconds,
                    LEFT(query, 200) AS query_snippet,
                    query_start
                FROM pg_stat_activity
                WHERE state = 'active'
                  AND query_start < now() - INTERVAL '{sec} seconds'
                  AND pid <> pg_backend_pid()
                ORDER BY query_start ASC
                LIMIT 50
            """.format(sec=threshold_sec))
            long_queries = [dict(row) for row in cur.fetchall()]

        # Serializar datetimes
        for row in long_queries:
            if row.get("query_start") and hasattr(row["query_start"], "isoformat"):
                row["query_start"] = row["query_start"].isoformat()

        count = len(long_queries)
        duration = _elapsed_ms(t0)

        if count >= thresholds["long_query_critical_count"]:
            status = "CRITICAL"
            msg = f"Número crítico de queries lentos (>{threshold_sec}s): {count}"
        elif count >= thresholds["long_query_warning_count"]:
            status = "WARNING"
            msg = f"Queries de larga duración detectados (>{threshold_sec}s): {count}"
        else:
            status = "OK"
            msg = f"Sin queries problemáticos (>{threshold_sec}s): {count}"

        logger.debug("[%s] %s — %d queries lentos", check_name, status, count)
        return _build_result(
            check_name, status,
            value=count,
            threshold={"seconds": threshold_sec,
                       "warning_count": thresholds["long_query_warning_count"],
                       "critical_count": thresholds["long_query_critical_count"]},
            message=msg,
            duration_ms=duration,
            details={"long_running": long_queries},
        )
    except Exception as exc:
        duration = _elapsed_ms(t0)
        msg = f"Error en long_running_queries: {exc}"
        logger.exception("[%s] ERROR — %s", check_name, msg)
        return _build_result(check_name, "CRITICAL", None, None, msg, duration)


def check_table_sizes(conn, thresholds: dict) -> dict:  # noqa: ARG001
    """
    CHECK 6 — Top 10 tablas más grandes (informativo).

    Obtiene el ranking de tablas por tamaño total (datos + índices)
    usando pg_total_relation_size. Este check es siempre informativo
    y no genera alertas.

    Parámetros
    ----------
    conn : psycopg2.connection
        Conexión activa a PostgreSQL.
    thresholds : dict
        No utilizado en este check (informativo).

    Retorna
    -------
    dict
        Resultado con lista de las 10 tablas más grandes.
    """
    check_name = "table_sizes"
    t0 = time.perf_counter()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT
                    schemaname,
                    relname AS table_name,
                    pg_size_pretty(pg_total_relation_size(oid)) AS total_size,
                    pg_total_relation_size(oid) AS total_bytes,
                    pg_size_pretty(pg_relation_size(oid)) AS data_size,
                    pg_size_pretty(pg_indexes_size(oid)) AS index_size
                FROM pg_class
                WHERE relkind = 'r'
                  AND schemaname NOT IN ('pg_catalog', 'information_schema')
                ORDER BY pg_total_relation_size(oid) DESC
                LIMIT 10
            """)
            rows = [dict(r) for r in cur.fetchall()]

        duration = _elapsed_ms(t0)
        msg = f"Top {len(rows)} tablas por tamaño recuperadas correctamente"
        logger.debug("[%s] OK — %d tablas listadas", check_name, len(rows))
        return _build_result(
            check_name, "INFO",
            value=len(rows),
            threshold=None,
            message=msg,
            duration_ms=duration,
            details={"top_tables": rows},
        )
    except Exception as exc:
        duration = _elapsed_ms(t0)
        msg = f"Error en table_sizes: {exc}"
        logger.exception("[%s] ERROR — %s", check_name, msg)
        return _build_result(check_name, "CRITICAL", None, None, msg, duration)


def check_dead_tuples(conn, thresholds: dict) -> dict:
    """
    CHECK 7 — Tablas con acumulación de dead tuples (fragmentación).

    Detecta tablas con n_dead_tup por encima del umbral. Un número
    elevado de dead tuples indica que VACUUM no ha sido ejecutado
    recientemente y puede degradar el rendimiento de queries.

    Parámetros
    ----------
    conn : psycopg2.connection
        Conexión activa a PostgreSQL.
    thresholds : dict
        Umbral mínimo de dead tuples para alertar.

    Retorna
    -------
    dict
        Resultado con lista de tablas afectadas.
    """
    check_name = "dead_tuples"
    t0 = time.perf_counter()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT
                    schemaname,
                    relname AS table_name,
                    n_dead_tup,
                    n_live_tup,
                    ROUND(n_dead_tup::numeric / NULLIF(n_live_tup + n_dead_tup, 0) * 100, 2) AS dead_ratio_pct,
                    last_autovacuum,
                    last_vacuum
                FROM pg_stat_user_tables
                WHERE n_dead_tup > %(threshold)s
                ORDER BY n_dead_tup DESC
                LIMIT 30
            """, {"threshold": thresholds["dead_tuples_warning"]})
            rows = [dict(r) for r in cur.fetchall()]

        # Serializar datetimes
        for row in rows:
            for field in ("last_autovacuum", "last_vacuum"):
                if row.get(field) and hasattr(row[field], "isoformat"):
                    row[field] = row[field].isoformat()

        count = len(rows)
        critical_tables = [r for r in rows if r["n_dead_tup"] >= thresholds["dead_tuples_critical"]]
        duration = _elapsed_ms(t0)

        if critical_tables:
            status = "CRITICAL"
            msg = (f"{len(critical_tables)} tabla(s) con dead tuples críticos "
                   f"(>{thresholds['dead_tuples_critical']:,})")
        elif count > 0:
            status = "WARNING"
            msg = f"{count} tabla(s) requieren VACUUM urgente"
        else:
            status = "OK"
            msg = "Sin acumulación significativa de dead tuples"

        logger.debug("[%s] %s — %d tablas con dead tuples", check_name, status, count)
        return _build_result(
            check_name, status,
            value=count,
            threshold={"warning": thresholds["dead_tuples_warning"],
                       "critical": thresholds["dead_tuples_critical"]},
            message=msg,
            duration_ms=duration,
            details={"tables": rows},
        )
    except Exception as exc:
        duration = _elapsed_ms(t0)
        msg = f"Error en dead_tuples: {exc}"
        logger.exception("[%s] ERROR — %s", check_name, msg)
        return _build_result(check_name, "CRITICAL", None, None, msg, duration)


def check_index_usage(conn, thresholds: dict) -> dict:  # noqa: ARG001
    """
    CHECK 8 — Índices nunca utilizados (idx_scan = 0).

    Identifica índices que jamás han sido utilizados por el planificador
    de consultas. Estos índices consumen espacio y aumentan el costo de
    las operaciones de escritura sin aportar beneficio.

    Parámetros
    ----------
    conn : psycopg2.connection
        Conexión activa a PostgreSQL.
    thresholds : dict
        No se usa en este check (informativo/warning).

    Retorna
    -------
    dict
        Resultado con lista de índices sin uso.
    """
    check_name = "index_usage"
    t0 = time.perf_counter()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT
                    s.schemaname,
                    s.relname AS table_name,
                    s.indexrelname AS index_name,
                    s.idx_scan,
                    pg_size_pretty(pg_relation_size(s.indexrelid)) AS index_size,
                    pg_relation_size(s.indexrelid) AS index_bytes
                FROM pg_stat_user_indexes s
                JOIN pg_index i ON s.indexrelid = i.indexrelid
                WHERE s.idx_scan = 0
                  AND i.indisunique IS FALSE   -- excluir índices únicos (pueden ser constraints)
                  AND i.indisprimary IS FALSE  -- excluir primary keys
                ORDER BY pg_relation_size(s.indexrelid) DESC
                LIMIT 50
            """)
            unused = [dict(r) for r in cur.fetchall()]

        count = len(unused)
        total_wasted_bytes = sum(r["index_bytes"] for r in unused)
        duration = _elapsed_ms(t0)

        if count > 10:
            status = "WARNING"
            msg = (f"{count} índices sin uso detectados — "
                   f"espacio desperdiciado: {total_wasted_bytes // 1024 // 1024} MB")
        else:
            status = "OK"
            msg = f"{count} índices sin uso (dentro de lo aceptable)"

        logger.debug("[%s] %s — %d índices sin uso", check_name, status, count)
        return _build_result(
            check_name, status,
            value={"unused_index_count": count, "wasted_bytes": total_wasted_bytes},
            threshold={"max_acceptable": 10},
            message=msg,
            duration_ms=duration,
            details={"unused_indexes": unused},
        )
    except Exception as exc:
        duration = _elapsed_ms(t0)
        msg = f"Error en index_usage: {exc}"
        logger.exception("[%s] ERROR — %s", check_name, msg)
        return _build_result(check_name, "CRITICAL", None, None, msg, duration)


def check_database_size(conn, thresholds: dict) -> dict:  # noqa: ARG001
    """
    CHECK 9 — Tamaño total de la base de datos activa.

    Mide el tamaño en MB de la base de datos a la que está conectado
    el monitor. Informativo con potencial de alertas si se integra con
    historial previo.

    Parámetros
    ----------
    conn : psycopg2.connection
        Conexión activa a PostgreSQL.
    thresholds : dict
        No utilizado (informativo).

    Retorna
    -------
    dict
        Resultado con tamaño en MB y nombre de la base de datos.
    """
    check_name = "database_size"
    t0 = time.perf_counter()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    current_database() AS dbname,
                    pg_database_size(current_database()) AS size_bytes,
                    pg_size_pretty(pg_database_size(current_database())) AS size_pretty
            """)
            row = cur.fetchone()
            dbname = row[0]
            size_bytes = row[1]
            size_pretty = row[2]
            size_mb = round(size_bytes / 1024 / 1024, 2)

        duration = _elapsed_ms(t0)
        msg = f"Base de datos '{dbname}': tamaño total {size_pretty}"
        logger.debug("[%s] INFO — %s = %s", check_name, dbname, size_pretty)
        return _build_result(
            check_name, "INFO",
            value={"size_mb": size_mb, "size_bytes": size_bytes, "size_pretty": size_pretty, "dbname": dbname},
            threshold=None,
            message=msg,
            duration_ms=duration,
        )
    except Exception as exc:
        duration = _elapsed_ms(t0)
        msg = f"Error en database_size: {exc}"
        logger.exception("[%s] ERROR — %s", check_name, msg)
        return _build_result(check_name, "CRITICAL", None, None, msg, duration)


def check_replication_lag(conn, thresholds: dict) -> dict:
    """
    CHECK 10 — Lag de replicación en servidores réplica (standby).

    Verifica si el servidor es una réplica mediante pg_is_in_recovery().
    Si lo es, mide el lag de replicación en bytes usando
    pg_wal_lsn_diff. Un lag elevado indica riesgo de pérdida de datos
    ante un failover.

    Parámetros
    ----------
    conn : psycopg2.connection
        Conexión activa a PostgreSQL.
    thresholds : dict
        Umbrales en bytes para warning y critical.

    Retorna
    -------
    dict
        Resultado con lag en bytes y MB, o indicación de que el
        servidor es primario (no aplica).
    """
    check_name = "replication_lag"
    t0 = time.perf_counter()
    try:
        with conn.cursor() as cur:
            # Verificar si es réplica
            cur.execute("SELECT pg_is_in_recovery()")
            is_replica = cur.fetchone()[0]

            if not is_replica:
                # Es servidor primario — verificar réplicas conectadas
                cur.execute("""
                    SELECT
                        client_addr,
                        state,
                        sent_lsn,
                        write_lsn,
                        flush_lsn,
                        replay_lsn,
                        pg_wal_lsn_diff(sent_lsn, replay_lsn) AS lag_bytes
                    FROM pg_stat_replication
                """)
                replicas = cur.fetchall()
                replica_info = [
                    {
                        "client_addr": str(r[0]),
                        "state": r[1],
                        "lag_bytes": r[6],
                        "lag_mb": round((r[6] or 0) / 1024 / 1024, 2),
                    }
                    for r in replicas
                ]
                max_lag = max((r["lag_bytes"] or 0 for r in replica_info), default=0)
                duration = _elapsed_ms(t0)

                if max_lag >= thresholds["replication_lag_critical_bytes"]:
                    status = "CRITICAL"
                    msg = f"Réplica con lag crítico: {max_lag // 1024 // 1024} MB"
                elif max_lag >= thresholds["replication_lag_warning_bytes"]:
                    status = "WARNING"
                    msg = f"Réplica con lag elevado: {max_lag // 1024 // 1024} MB"
                else:
                    status = "OK" if replica_info else "INFO"
                    msg = (f"Replicación saludable ({len(replica_info)} réplica(s))"
                           if replica_info else "Sin réplicas conectadas al primario")

                return _build_result(
                    check_name, status,
                    value={"is_primary": True, "replica_count": len(replica_info), "max_lag_bytes": max_lag},
                    threshold={"warning_bytes": thresholds["replication_lag_warning_bytes"],
                               "critical_bytes": thresholds["replication_lag_critical_bytes"]},
                    message=msg,
                    duration_ms=duration,
                    details={"replicas": replica_info},
                )
            else:
                # Es réplica — medir lag propio
                cur.execute("""
                    SELECT
                        pg_wal_lsn_diff(pg_last_wal_receive_lsn(), pg_last_wal_replay_lsn()) AS lag_bytes,
                        now() - pg_last_xact_replay_timestamp() AS replay_delay
                """)
                row = cur.fetchone()
                lag_bytes = row[0] or 0
                replay_delay = row[1]
                lag_mb = round(lag_bytes / 1024 / 1024, 2)
                duration = _elapsed_ms(t0)

                if lag_bytes >= thresholds["replication_lag_critical_bytes"]:
                    status = "CRITICAL"
                    msg = f"Lag de replicación crítico: {lag_mb} MB"
                elif lag_bytes >= thresholds["replication_lag_warning_bytes"]:
                    status = "WARNING"
                    msg = f"Lag de replicación elevado: {lag_mb} MB"
                else:
                    status = "OK"
                    msg = f"Lag de replicación aceptable: {lag_mb} MB"

                logger.debug("[%s] %s — lag=%d bytes", check_name, status, lag_bytes)
                return _build_result(
                    check_name, status,
                    value={"is_replica": True, "lag_bytes": lag_bytes, "lag_mb": lag_mb,
                           "replay_delay_seconds": replay_delay.total_seconds() if replay_delay else None},
                    threshold={"warning_bytes": thresholds["replication_lag_warning_bytes"],
                               "critical_bytes": thresholds["replication_lag_critical_bytes"]},
                    message=msg,
                    duration_ms=duration,
                )
    except Exception as exc:
        duration = _elapsed_ms(t0)
        msg = f"Error en replication_lag: {exc}"
        logger.exception("[%s] ERROR — %s", check_name, msg)
        return _build_result(check_name, "CRITICAL", None, None, msg, duration)


def check_checkpoint_stats(conn, thresholds: dict) -> dict:
    """
    CHECK 11 — Estadísticas de checkpoints en PostgreSQL.

    Analiza pg_stat_bgwriter para detectar si hay una proporción elevada
    de checkpoints forzados (checkpoints_req) vs. checkpoints programados
    (checkpoints_timed). Checkpoints frecuentes forzados indican alta
    actividad de escritura y posible necesidad de ajustar checkpoint_completion_target.

    Parámetros
    ----------
    conn : psycopg2.connection
        Conexión activa a PostgreSQL.
    thresholds : dict
        Umbral de porcentaje de checkpoints forzados.

    Retorna
    -------
    dict
        Resultado con conteos de checkpoints y porcentaje de forzados.
    """
    check_name = "checkpoint_stats"
    t0 = time.perf_counter()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT
                    checkpoints_timed,
                    checkpoints_req,
                    checkpoint_write_time,
                    checkpoint_sync_time,
                    buffers_checkpoint,
                    buffers_clean,
                    buffers_backend,
                    stats_reset
                FROM pg_stat_bgwriter
            """)
            row = dict(cur.fetchone())

        timed = row["checkpoints_timed"] or 0
        req = row["checkpoints_req"] or 0
        total = timed + req
        req_pct = _safe_divide(req, total) * 100
        duration = _elapsed_ms(t0)

        if row.get("stats_reset") and hasattr(row["stats_reset"], "isoformat"):
            row["stats_reset"] = row["stats_reset"].isoformat()

        if req_pct >= thresholds["checkpoint_req_warning_pct"]:
            status = "WARNING"
            msg = (f"Alto porcentaje de checkpoints forzados: {req_pct:.1f}% "
                   f"({req}/{total}). Revisar checkpoint_completion_target.")
        else:
            status = "OK"
            msg = f"Checkpoints saludables: {req_pct:.1f}% forzados ({req}/{total})"

        logger.debug("[%s] %s — req_pct=%.1f%%", check_name, status, req_pct)
        return _build_result(
            check_name, status,
            value={"checkpoints_timed": timed, "checkpoints_req": req,
                   "req_pct": round(req_pct, 2), "total": total},
            threshold={"warning_req_pct": thresholds["checkpoint_req_warning_pct"]},
            message=msg,
            duration_ms=duration,
            details=row,
        )
    except Exception as exc:
        duration = _elapsed_ms(t0)
        msg = f"Error en checkpoint_stats: {exc}"
        logger.exception("[%s] ERROR — %s", check_name, msg)
        return _build_result(check_name, "CRITICAL", None, None, msg, duration)


def check_temp_files(conn, thresholds: dict) -> dict:
    """
    CHECK 12 — Uso de archivos temporales (sort en disco).

    Consulta pg_stat_database para detectar uso de archivos temporales.
    Un número elevado de temp_files indica que PostgreSQL necesita
    ordenar datos en disco (sort spill), lo que degrada el rendimiento.
    Se puede mitigar incrementando work_mem.

    Parámetros
    ----------
    conn : psycopg2.connection
        Conexión activa a PostgreSQL.
    thresholds : dict
        Umbral de número de temp files para warning.

    Retorna
    -------
    dict
        Resultado con número de archivos temp y tamaño acumulado.
    """
    check_name = "temp_files"
    t0 = time.perf_counter()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    temp_files,
                    temp_bytes,
                    pg_size_pretty(temp_bytes) AS temp_size_pretty
                FROM pg_stat_database
                WHERE datname = current_database()
            """)
            row = cur.fetchone()
            temp_files = row[0] or 0
            temp_bytes = row[1] or 0
            temp_size_pretty = row[2]

        duration = _elapsed_ms(t0)

        if temp_files >= thresholds["temp_files_warning_count"]:
            status = "WARNING"
            msg = (f"Uso elevado de archivos temporales: {temp_files} archivos "
                   f"({temp_size_pretty}). Evaluar incremento de work_mem.")
        else:
            status = "OK"
            msg = f"Archivos temporales dentro de rango: {temp_files} ({temp_size_pretty})"

        logger.debug("[%s] %s — %d temp files", check_name, status, temp_files)
        return _build_result(
            check_name, status,
            value={"temp_files": temp_files, "temp_bytes": temp_bytes, "temp_size_pretty": temp_size_pretty},
            threshold={"warning_count": thresholds["temp_files_warning_count"]},
            message=msg,
            duration_ms=duration,
        )
    except Exception as exc:
        duration = _elapsed_ms(t0)
        msg = f"Error en temp_files: {exc}"
        logger.exception("[%s] ERROR — %s", check_name, msg)
        return _build_result(check_name, "CRITICAL", None, None, msg, duration)


def check_bloat(conn, thresholds: dict) -> dict:
    """
    CHECK 13 — Estimación de bloat (fragmentación) en tablas.

    Usa la query estándar de estimación de bloat basada en estadísticas
    del catálogo. El bloat es espacio muerto dentro de páginas que no
    ha sido reclamado por VACUUM. Afecta rendimiento y tamaño en disco.

    Parámetros
    ----------
    conn : psycopg2.connection
        Conexión activa a PostgreSQL.
    thresholds : dict
        Umbral de porcentaje de bloat para warning.

    Retorna
    -------
    dict
        Resultado con tablas con mayor bloat estimado.
    """
    check_name = "bloat_check"
    t0 = time.perf_counter()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Query estándar de estimación de bloat (simplificada para compatibilidad)
            cur.execute("""
                SELECT
                    schemaname,
                    relname AS table_name,
                    n_dead_tup,
                    n_live_tup,
                    CASE
                        WHEN (n_live_tup + n_dead_tup) > 0
                        THEN ROUND(n_dead_tup::numeric / (n_live_tup + n_dead_tup) * 100, 2)
                        ELSE 0
                    END AS bloat_pct,
                    pg_size_pretty(pg_total_relation_size(relid)) AS total_size
                FROM pg_stat_user_tables
                WHERE (n_live_tup + n_dead_tup) > 1000
                ORDER BY bloat_pct DESC
                LIMIT 20
            """)
            rows = [dict(r) for r in cur.fetchall()]

        high_bloat = [r for r in rows if r["bloat_pct"] >= thresholds["bloat_warning_pct"]]
        duration = _elapsed_ms(t0)

        if high_bloat:
            status = "WARNING"
            msg = (f"{len(high_bloat)} tabla(s) con bloat elevado "
                   f"(>={thresholds['bloat_warning_pct']}%): "
                   f"{high_bloat[0]['table_name']} ({high_bloat[0]['bloat_pct']}%)")
        else:
            status = "OK"
            msg = f"Bloat dentro de rangos aceptables (umbral: {thresholds['bloat_warning_pct']}%)"

        logger.debug("[%s] %s — %d tablas con bloat alto", check_name, status, len(high_bloat))
        return _build_result(
            check_name, status,
            value={"high_bloat_tables": len(high_bloat)},
            threshold={"warning_pct": thresholds["bloat_warning_pct"]},
            message=msg,
            duration_ms=duration,
            details={"tables": rows},
        )
    except Exception as exc:
        duration = _elapsed_ms(t0)
        msg = f"Error en bloat_check: {exc}"
        logger.exception("[%s] ERROR — %s", check_name, msg)
        return _build_result(check_name, "CRITICAL", None, None, msg, duration)


def check_vacuum_analyze_needed(conn, thresholds: dict) -> dict:
    """
    CHECK 14 — Tablas sin ANALYZE reciente (>N días).

    Identifica tablas cuyas estadísticas de planificación no han sido
    actualizadas en los últimos N días (default: 7). El planificador
    de consultas depende de estadísticas frescas para generar planes
    de ejecución óptimos.

    Parámetros
    ----------
    conn : psycopg2.connection
        Conexión activa a PostgreSQL.
    thresholds : dict
        Número de días sin analyze para considerar stale.

    Retorna
    -------
    dict
        Resultado con lista de tablas sin analyze reciente.
    """
    check_name = "vacuum_analyze_needed"
    t0 = time.perf_counter()
    stale_days = thresholds.get("vacuum_stale_days", 7)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT
                    schemaname,
                    relname AS table_name,
                    last_analyze,
                    last_autoanalyze,
                    last_vacuum,
                    last_autovacuum,
                    n_live_tup,
                    COALESCE(last_analyze, last_autoanalyze) AS last_any_analyze
                FROM pg_stat_user_tables
                WHERE n_live_tup > 100
                  AND (
                      COALESCE(last_analyze, last_autoanalyze) IS NULL
                      OR COALESCE(last_analyze, last_autoanalyze) < now() - INTERVAL '{days} days'
                  )
                ORDER BY n_live_tup DESC
                LIMIT 30
            """.format(days=stale_days))
            stale_tables = [dict(r) for r in cur.fetchall()]

        # Serializar datetimes
        for row in stale_tables:
            for field in ("last_analyze", "last_autoanalyze", "last_vacuum", "last_autovacuum", "last_any_analyze"):
                if row.get(field) and hasattr(row[field], "isoformat"):
                    row[field] = row[field].isoformat()

        count = len(stale_tables)
        duration = _elapsed_ms(t0)

        if count > 0:
            status = "WARNING"
            msg = f"{count} tabla(s) sin ANALYZE en los últimos {stale_days} días"
        else:
            status = "OK"
            msg = f"Todas las tablas tienen estadísticas frescas (<{stale_days} días)"

        logger.debug("[%s] %s — %d tablas sin analyze reciente", check_name, status, count)
        return _build_result(
            check_name, status,
            value=count,
            threshold={"stale_days": stale_days},
            message=msg,
            duration_ms=duration,
            details={"stale_tables": stale_tables},
        )
    except Exception as exc:
        duration = _elapsed_ms(t0)
        msg = f"Error en vacuum_analyze_needed: {exc}"
        logger.exception("[%s] ERROR — %s", check_name, msg)
        return _build_result(check_name, "CRITICAL", None, None, msg, duration)


def check_wal_size(conn, thresholds: dict) -> dict:  # noqa: ARG001
    """
    CHECK 15 — Tamaño de archivos WAL (Write-Ahead Log) pendientes.

    Mide el volumen de WAL generado y, si está disponible, el espacio
    en uso del directorio pg_wal. Un volumen excesivo puede indicar
    alta carga de escrituras o acumulación por réplicas lentas.

    Parámetros
    ----------
    conn : psycopg2.connection
        Conexión activa a PostgreSQL.
    thresholds : dict
        No se aplica umbral en esta versión (informativo).

    Retorna
    -------
    dict
        Resultado con información del tamaño de WAL.
    """
    check_name = "wal_size"
    t0 = time.perf_counter()
    try:
        with conn.cursor() as cur:
            # pg_wal_lsn_diff entre lsn actual y el del inicio de WAL disponible
            cur.execute("""
                SELECT
                    pg_current_wal_lsn() AS current_lsn,
                    pg_walfile_name(pg_current_wal_lsn()) AS current_wal_file,
                    current_setting('wal_segment_size')::int AS wal_segment_size_bytes
            """)
            row = cur.fetchone()
            current_wal_file = row[1]
            wal_segment_size = row[2]

            # Intentar obtener tamaño del directorio WAL (PostgreSQL 10+)
            try:
                cur.execute("SELECT pg_size_pretty(sum(size)) FROM pg_ls_waldir()")
                wal_dir_size = cur.fetchone()[0]
            except Exception:
                wal_dir_size = "No disponible (requiere superusuario)"

        duration = _elapsed_ms(t0)
        segment_size_mb = round(wal_segment_size / 1024 / 1024, 2)
        msg = (f"WAL activo: {current_wal_file} | "
               f"Segmento: {segment_size_mb} MB | "
               f"Directorio WAL: {wal_dir_size}")
        logger.debug("[%s] INFO — %s", check_name, current_wal_file)
        return _build_result(
            check_name, "INFO",
            value={"current_wal_file": current_wal_file,
                   "wal_segment_size_mb": segment_size_mb,
                   "wal_dir_size_pretty": wal_dir_size},
            threshold=None,
            message=msg,
            duration_ms=duration,
        )
    except Exception as exc:
        duration = _elapsed_ms(t0)
        msg = f"Error en wal_size: {exc}"
        logger.exception("[%s] ERROR — %s", check_name, msg)
        return _build_result(check_name, "CRITICAL", None, None, msg, duration)


# ---------------------------------------------------------------------------
# FUNCIÓN PRINCIPAL DE ORQUESTACIÓN
# ---------------------------------------------------------------------------

def run_all_checks(conn_params: dict, thresholds: Optional[dict] = None) -> dict:
    """
    Ejecuta todos los health checks sobre una instancia PostgreSQL.

    Función de entrada principal del módulo. Establece una única conexión
    reutilizable para todos los checks (excepto el de conectividad que mide
    latencia de apertura de conexión), ejecuta los 15 checks en secuencia
    y retorna el resultado consolidado.

    Parámetros
    ----------
    conn_params : dict
        Parámetros de conexión psycopg2:
        - host (str): Hostname o IP del servidor.
        - port (int): Puerto TCP (default: 5432).
        - dbname (str): Nombre de la base de datos.
        - user (str): Usuario de conexión.
        - password (str): Contraseña del usuario.
        - sslmode (str, opcional): 'require', 'verify-full', etc.
    thresholds : dict, opcional
        Umbrales personalizados. Si no se provee, se usan DEFAULT_THRESHOLDS.

    Retorna
    -------
    dict
        Estructura completa con todos los resultados:
        {
            "db_host": str,
            "db_name": str,
            "execution_timestamp": str (ISO 8601),
            "total_duration_ms": float,
            "checks": {check_name: dict, ...},
            "summary": {
                "total": int,
                "ok": int,
                "warning": int,
                "critical": int,
                "info": int,
                "errors": int,
            }
        }

    Ejemplo
    -------
    >>> params = {
    ...     "host": "10.0.0.1",
    ...     "port": 5432,
    ...     "dbname": "produccion",
    ...     "user": "sentinel",
    ...     "password": "s3cr3t",
    ... }
    >>> resultado = run_all_checks(params)
    >>> print(resultado["summary"])
    """
    # Fusionar umbrales por defecto con los personalizados
    active_thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    db_host = conn_params.get("host", "unknown")
    db_name = conn_params.get("dbname", "unknown")
    execution_start = time.perf_counter()
    execution_timestamp = datetime.now(timezone.utc).isoformat()

    logger.info(
        "Iniciando health checks PostgreSQL — host=%s db=%s",
        db_host, db_name
    )

    results = {}

    # CHECK 1: Latencia de conexión (usa conexión separada para medir correctamente)
    logger.info("Ejecutando check: connection_check")
    results["connection_check"] = check_connection(conn_params, active_thresholds)

    # Si la conexión falló, no tiene sentido continuar con el resto
    if results["connection_check"]["status"] == "CRITICAL":
        logger.error(
            "Conexión fallida a %s/%s — abortando checks restantes",
            db_host, db_name
        )
        total_duration = _elapsed_ms(execution_start)
        return {
            "db_host": db_host,
            "db_name": db_name,
            "execution_timestamp": execution_timestamp,
            "total_duration_ms": round(total_duration, 3),
            "checks": results,
            "summary": _build_summary(results),
            "error": "No se pudo establecer conexión con PostgreSQL",
        }

    # Abrir conexión reutilizable para el resto de checks
    conn = None
    try:
        conn = psycopg2.connect(**conn_params, connect_timeout=10)
        conn.set_session(readonly=True, autocommit=True)

        # Mapa de checks: nombre → función
        check_functions = {
            "active_connections":     (check_active_connections,     [conn, active_thresholds]),
            "cache_hit_ratio":        (check_cache_hit_ratio,        [conn, active_thresholds]),
            "locks_check":            (check_locks,                  [conn, active_thresholds]),
            "long_running_queries":   (check_long_running_queries,   [conn, active_thresholds]),
            "table_sizes":            (check_table_sizes,            [conn, active_thresholds]),
            "dead_tuples":            (check_dead_tuples,            [conn, active_thresholds]),
            "index_usage":            (check_index_usage,            [conn, active_thresholds]),
            "database_size":          (check_database_size,          [conn, active_thresholds]),
            "replication_lag":        (check_replication_lag,        [conn, active_thresholds]),
            "checkpoint_stats":       (check_checkpoint_stats,       [conn, active_thresholds]),
            "temp_files":             (check_temp_files,             [conn, active_thresholds]),
            "bloat_check":            (check_bloat,                  [conn, active_thresholds]),
            "vacuum_analyze_needed":  (check_vacuum_analyze_needed,  [conn, active_thresholds]),
            "wal_size":               (check_wal_size,               [conn, active_thresholds]),
        }

        for check_name, (func, args) in check_functions.items():
            logger.info("Ejecutando check: %s", check_name)
            try:
                results[check_name] = func(*args)
            except Exception as exc:
                logger.exception("Fallo inesperado en check '%s': %s", check_name, exc)
                results[check_name] = _build_result(
                    check_name, "CRITICAL", None, None,
                    f"Error interno no capturado: {exc}", 0.0
                )

    except psycopg2.Error as exc:
        logger.exception("Error de conexión PostgreSQL durante checks: %s", exc)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    total_duration = _elapsed_ms(execution_start)
    summary = _build_summary(results)

    logger.info(
        "Health checks completados — host=%s db=%s | OK=%d WARN=%d CRIT=%d | %.0f ms",
        db_host, db_name,
        summary["ok"], summary["warning"], summary["critical"],
        total_duration,
    )

    return {
        "db_host": db_host,
        "db_name": db_name,
        "execution_timestamp": execution_timestamp,
        "total_duration_ms": round(total_duration, 3),
        "checks": results,
        "summary": summary,
    }


def _build_summary(results: dict) -> dict:
    """
    Genera el resumen de conteos de estados de todos los checks.

    Parámetros
    ----------
    results : dict
        Diccionario de resultados de checks.

    Retorna
    -------
    dict
        Conteos por estado y total.
    """
    summary = {"total": 0, "ok": 0, "warning": 0, "critical": 0, "info": 0, "errors": 0}
    for check_result in results.values():
        status = check_result.get("status", "").upper()
        summary["total"] += 1
        if status == "OK":
            summary["ok"] += 1
        elif status == "WARNING":
            summary["warning"] += 1
        elif status == "CRITICAL":
            summary["critical"] += 1
        elif status == "INFO":
            summary["info"] += 1
        else:
            summary["errors"] += 1
    return summary
