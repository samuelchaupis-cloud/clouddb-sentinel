"""
checks_mysql.py — CloudDB Sentinel
=====================================
Módulo de health checks para bases de datos MySQL / MariaDB.

Ejecuta 12 verificaciones diagnósticas sobre una instancia MySQL y
retorna un diccionario estructurado con el resultado de cada check.
Sigue el mismo patrón que checks_postgres.py para consistencia en
el pipeline de monitoreo.

Autor: Equipo de Plataformas Cloud
Versión: 1.0.0
"""

import logging
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Optional

# mysql-connector-python es el conector oficial de Oracle para MySQL
try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
except ImportError as exc:
    raise ImportError(
        "Dependencia faltante: instale el conector con "
        "'pip install mysql-connector-python'"
    ) from exc

# Logger con nombre jerárquico para integración con el sistema de logging central
logger = logging.getLogger("clouddb_sentinel.healthcheck.mysql")

# ---------------------------------------------------------------------------
# CONSTANTES DE UMBRALES POR DEFECTO
# ---------------------------------------------------------------------------
DEFAULT_THRESHOLDS = {
    "connection_latency_warning_ms": 100,
    "connection_latency_critical_ms": 500,
    "connections_warning_pct": 70,
    "connections_critical_pct": 90,
    "cache_hit_warning_pct": 95,
    "cache_hit_critical_pct": 90,
    "locks_warning_trx": 5,
    "locks_critical_trx": 20,
    "long_query_threshold_seconds": 30,
    "long_query_warning_count": 3,
    "long_query_critical_count": 10,
    "slow_queries_warning": 100,
    "replication_lag_warning_sec": 30,
    "replication_lag_critical_sec": 120,
    "open_tables_warning": 400,
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
        Estado resultante: 'OK', 'WARNING', 'CRITICAL' o 'INFO'.
    value : Any
        Valor medido en el check.
    threshold : Any
        Umbral aplicado para determinar el estado.
    message : str
        Mensaje descriptivo legible para el operador.
    duration_ms : float
        Tiempo de ejecución del check en milisegundos.
    details : dict, opcional
        Información adicional estructurada.

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


def _fetch_global_status(cursor, variable_name: str) -> Optional[int]:
    """
    Recupera un valor de SHOW GLOBAL STATUS para una variable específica.

    Parámetros
    ----------
    cursor : mysql.connector.cursor
        Cursor de conexión activo.
    variable_name : str
        Nombre de la variable de estado MySQL.

    Retorna
    -------
    int o None
        Valor entero de la variable o None si no existe.
    """
    cursor.execute("SHOW GLOBAL STATUS LIKE %s", (variable_name,))
    row = cursor.fetchone()
    if row:
        try:
            return int(row[1])
        except (ValueError, TypeError):
            return None
    return None


def _fetch_global_variable(cursor, variable_name: str) -> Optional[str]:
    """
    Recupera el valor de una variable de configuración de MySQL.

    Parámetros
    ----------
    cursor : mysql.connector.cursor
        Cursor de conexión activo.
    variable_name : str
        Nombre de la variable de sistema MySQL.

    Retorna
    -------
    str o None
        Valor de la variable como cadena, o None si no existe.
    """
    cursor.execute("SHOW GLOBAL VARIABLES LIKE %s", (variable_name,))
    row = cursor.fetchone()
    return row[1] if row else None


# ---------------------------------------------------------------------------
# CHECKS INDIVIDUALES
# ---------------------------------------------------------------------------

def check_connection(conn_params: dict, thresholds: dict) -> dict:
    """
    CHECK 1 — Verificación de conectividad y latencia de conexión.

    Intenta abrir una nueva conexión a MySQL, ejecuta 'SELECT 1' y mide
    la latencia total de apertura de conexión en milisegundos.

    Parámetros
    ----------
    conn_params : dict
        Parámetros de conexión mysql.connector (host, port, database, user, password).
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
        conn = mysql.connector.connect(
            **conn_params,
            connection_timeout=10,
            use_pure=True,
        )
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchall()
        cursor.close()
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

    except MySQLError as exc:
        duration = _elapsed_ms(t0)
        msg = f"No se pudo conectar a MySQL: {exc}"
        logger.error("[%s] CRITICAL — %s", check_name, msg)
        return _build_result(check_name, "CRITICAL", None, None, msg, duration)
    except Exception as exc:
        duration = _elapsed_ms(t0)
        msg = f"Error inesperado en connection_check: {exc}"
        logger.exception("[%s] ERROR — %s", check_name, msg)
        return _build_result(check_name, "CRITICAL", None, None, msg, duration)


def check_active_connections(conn, thresholds: dict) -> dict:
    """
    CHECK 2 — Conexiones activas vs. max_connections.

    Consulta las variables de estado 'Threads_connected' y la variable de
    configuración 'max_connections' para calcular el porcentaje de uso del
    pool de conexiones disponible.

    Parámetros
    ----------
    conn : mysql.connector.connection
        Conexión activa a MySQL.
    thresholds : dict
        Umbrales de porcentaje para warning y critical.

    Retorna
    -------
    dict
        Resultado con conexiones actuales, máximo y porcentaje de uso.
    """
    check_name = "active_connections"
    t0 = time.perf_counter()
    try:
        cursor = conn.cursor()

        # Conexiones actuales establecidas
        threads_connected = _fetch_global_status(cursor, "Threads_connected") or 0
        # Conexiones en ejecución activa (ejecutando query)
        threads_running = _fetch_global_status(cursor, "Threads_running") or 0
        # Límite máximo configurado
        max_connections_str = _fetch_global_variable(cursor, "max_connections")
        max_connections = int(max_connections_str) if max_connections_str else 151

        cursor.close()

        usage_pct = _safe_divide(threads_connected, max_connections) * 100
        duration = _elapsed_ms(t0)

        if usage_pct >= thresholds["connections_critical_pct"]:
            status = "CRITICAL"
            msg = (f"Uso crítico de conexiones: {threads_connected}/{max_connections} "
                   f"({usage_pct:.1f}%)")
        elif usage_pct >= thresholds["connections_warning_pct"]:
            status = "WARNING"
            msg = (f"Uso elevado de conexiones: {threads_connected}/{max_connections} "
                   f"({usage_pct:.1f}%)")
        else:
            status = "OK"
            msg = (f"Conexiones en rango normal: {threads_connected}/{max_connections} "
                   f"({usage_pct:.1f}%)")

        logger.debug("[%s] %s — %d/%d (%.1f%%)", check_name, status,
                     threads_connected, max_connections, usage_pct)
        return _build_result(
            check_name, status,
            value={"threads_connected": threads_connected,
                   "threads_running": threads_running,
                   "max_connections": max_connections,
                   "usage_pct": round(usage_pct, 2)},
            threshold={"warning_pct": thresholds["connections_warning_pct"],
                       "critical_pct": thresholds["connections_critical_pct"],
                       "max_connections": max_connections},
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
    CHECK 3 — InnoDB Buffer Pool Hit Ratio (cache hit ratio).

    Calcula la eficiencia del buffer pool de InnoDB:
    hit_ratio = (read_requests - physical_reads) / read_requests.
    Un ratio bajo indica presión de I/O en disco y posible necesidad
    de incrementar innodb_buffer_pool_size.

    Parámetros
    ----------
    conn : mysql.connector.connection
        Conexión activa a MySQL.
    thresholds : dict
        Umbrales de porcentaje mínimo aceptable.

    Retorna
    -------
    dict
        Resultado con el ratio de hit del buffer pool en porcentaje.
    """
    check_name = "cache_hit_ratio"
    t0 = time.perf_counter()
    try:
        cursor = conn.cursor()

        # Lecturas totales solicitadas al buffer pool
        read_requests = _fetch_global_status(cursor, "Innodb_buffer_pool_read_requests") or 0
        # Lecturas físicas desde disco (cache misses)
        physical_reads = _fetch_global_status(cursor, "Innodb_buffer_pool_reads") or 0

        cursor.close()

        # Hit ratio: solicitudes que encontraron datos en memoria
        cache_hits = read_requests - physical_reads
        ratio_pct = _safe_divide(cache_hits, read_requests, default=100.0) * 100
        duration = _elapsed_ms(t0)

        if ratio_pct < thresholds["cache_hit_critical_pct"]:
            status = "CRITICAL"
            msg = f"InnoDB buffer pool hit ratio crítico: {ratio_pct:.2f}%"
        elif ratio_pct < thresholds["cache_hit_warning_pct"]:
            status = "WARNING"
            msg = f"InnoDB buffer pool hit ratio bajo: {ratio_pct:.2f}% (recomendado ≥95%)"
        else:
            status = "OK"
            msg = f"InnoDB buffer pool hit ratio saludable: {ratio_pct:.2f}%"

        logger.debug("[%s] %s — ratio=%.2f%%", check_name, status, ratio_pct)
        return _build_result(
            check_name, status,
            value={"hit_ratio_pct": round(ratio_pct, 4),
                   "read_requests": read_requests,
                   "physical_reads": physical_reads,
                   "cache_hits": cache_hits},
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
    CHECK 4 — Transacciones InnoDB con locks activos.

    Consulta INFORMATION_SCHEMA.INNODB_TRX para detectar transacciones
    con bloqueos activos (trx_lock_structs > 0). Identifica además
    transacciones de larga duración que podrían bloquear otras sesiones.

    Parámetros
    ----------
    conn : mysql.connector.connection
        Conexión activa a MySQL.
    thresholds : dict
        Umbrales de conteo de transacciones con locks.

    Retorna
    -------
    dict
        Resultado con transacciones bloqueantes y detalle de las mismas.
    """
    check_name = "locks_check"
    t0 = time.perf_counter()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                trx_id,
                trx_state,
                trx_started,
                trx_mysql_thread_id AS thread_id,
                trx_lock_structs AS lock_count,
                trx_rows_locked AS rows_locked,
                trx_rows_modified AS rows_modified,
                TIMESTAMPDIFF(SECOND, trx_started, NOW()) AS duration_seconds,
                LEFT(trx_query, 200) AS query_snippet
            FROM information_schema.INNODB_TRX
            WHERE trx_lock_structs > 0
            ORDER BY trx_started ASC
            LIMIT 50
        """)
        locked_trx = cursor.fetchall()

        # Serializar datetimes
        for row in locked_trx:
            if row.get("trx_started") and hasattr(row["trx_started"], "isoformat"):
                row["trx_started"] = row["trx_started"].isoformat()

        cursor.close()
        count = len(locked_trx)
        duration = _elapsed_ms(t0)

        if count >= thresholds["locks_critical_trx"]:
            status = "CRITICAL"
            msg = f"Número crítico de transacciones con locks activos: {count}"
        elif count >= thresholds["locks_warning_trx"]:
            status = "WARNING"
            msg = f"Transacciones con locks detectadas: {count}"
        else:
            status = "OK"
            msg = f"Sin contención significativa de locks InnoDB: {count}"

        logger.debug("[%s] %s — %d transacciones con locks", check_name, status, count)
        return _build_result(
            check_name, status,
            value=count,
            threshold={"warning": thresholds["locks_warning_trx"],
                       "critical": thresholds["locks_critical_trx"]},
            message=msg,
            duration_ms=duration,
            details={"locked_transactions": locked_trx},
        )
    except Exception as exc:
        duration = _elapsed_ms(t0)
        if "Access denied" in str(exc) or "1227" in str(exc):
            return _build_result(check_name, "INFO", 0, None, "Check omitido: el usuario de monitoreo no tiene privilegio PROCESS", duration)
        msg = f"Error en locks_check: {exc}"
        logger.exception("[%s] ERROR — %s", check_name, msg)
        return _build_result(check_name, "CRITICAL", None, None, msg, duration)


def check_long_running_queries(conn, thresholds: dict) -> dict:
    """
    CHECK 5 — Queries de larga duración en PROCESSLIST.

    Consulta INFORMATION_SCHEMA.PROCESSLIST para detectar procesos con
    TIME superior al umbral configurado (default: 30 segundos) y que
    estén ejecutando una query activa (Command = 'Query').

    Parámetros
    ----------
    conn : mysql.connector.connection
        Conexión activa a MySQL.
    thresholds : dict
        Umbral en segundos y conteos de warning/critical.

    Retorna
    -------
    dict
        Resultado con lista de queries lentos en ejecución.
    """
    check_name = "long_running_queries"
    t0 = time.perf_counter()
    threshold_sec = thresholds.get("long_query_threshold_seconds", 30)
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                ID AS thread_id,
                USER AS username,
                HOST AS client_host,
                DB AS database_name,
                COMMAND AS command,
                TIME AS duration_seconds,
                STATE AS state,
                LEFT(INFO, 200) AS query_snippet
            FROM information_schema.PROCESSLIST
            WHERE COMMAND = 'Query'
              AND TIME > %s
              AND ID <> CONNECTION_ID()
            ORDER BY TIME DESC
            LIMIT 50
        """, (threshold_sec,))
        long_queries = cursor.fetchall()
        cursor.close()

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

    Consulta information_schema.TABLES para obtener el ranking de tablas
    por tamaño total (data_length + index_length).

    Parámetros
    ----------
    conn : mysql.connector.connection
        Conexión activa a MySQL.
    thresholds : dict
        No utilizado (informativo).

    Retorna
    -------
    dict
        Resultado con lista de las 10 tablas más grandes.
    """
    check_name = "table_sizes"
    t0 = time.perf_counter()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                TABLE_SCHEMA AS schema_name,
                TABLE_NAME AS table_name,
                TABLE_ROWS AS estimated_rows,
                ROUND((DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024, 2) AS total_size_mb,
                ROUND(DATA_LENGTH / 1024 / 1024, 2) AS data_size_mb,
                ROUND(INDEX_LENGTH / 1024 / 1024, 2) AS index_size_mb,
                ENGINE AS engine
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys')
              AND TABLE_TYPE = 'BASE TABLE'
            ORDER BY (DATA_LENGTH + INDEX_LENGTH) DESC
            LIMIT 10
        """)
        rows = cursor.fetchall()
        cursor.close()

        duration = _elapsed_ms(t0)
        msg = f"Top {len(rows)} tablas por tamaño recuperadas correctamente"
        logger.debug("[%s] INFO — %d tablas listadas", check_name, len(rows))
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


def check_dead_rows(conn, thresholds: dict) -> dict:  # noqa: ARG001
    """
    CHECK 7 — Verificación de dead rows (no disponible en MySQL/InnoDB).

    En MySQL con motor InnoDB, el concepto de 'dead tuples' análogo al de
    PostgreSQL no está disponible en el catálogo del sistema. InnoDB gestiona
    la purga de versiones antiguas (MVCC) de forma automática mediante el
    thread de purga en segundo plano. Este check retorna estado INFO con una
    nota explicativa y alternativas de monitoreo.

    Para verificar el estado de purga InnoDB, se consulta
    'Innodb_history_list_length' como indicador indirecto.

    Parámetros
    ----------
    conn : mysql.connector.connection
        Conexión activa a MySQL.
    thresholds : dict
        No aplicable.

    Retorna
    -------
    dict
        Resultado informativo con indicadores de purga InnoDB.
    """
    check_name = "dead_rows"
    t0 = time.perf_counter()
    try:
        cursor = conn.cursor()
        # Longitud de la lista de historia MVCC — un valor elevado indica
        # que el thread de purga está atrasado (análogo a dead tuples en PG)
        history_list_length = _fetch_global_status(cursor, "Innodb_history_list_length") or 0
        cursor.close()

        duration = _elapsed_ms(t0)

        # La lista de historia larga puede indicar transacciones activas largas
        # que impiden la purga de versiones antiguas
        if history_list_length > 10000:
            status = "WARNING"
            msg = (f"InnoDB History List Length elevado ({history_list_length:,}): "
                   "posibles transacciones largas bloqueando purga MVCC.")
        else:
            status = "INFO"
            msg = (f"MySQL/InnoDB gestiona dead rows automáticamente (MVCC purge). "
                   f"History List Length: {history_list_length:,}. "
                   "No requiere acción manual equivalente a VACUUM en PostgreSQL.")

        note = ("NOTA: En MySQL/InnoDB, la limpieza de versiones antiguas (equivalente "
                "a dead tuples en PostgreSQL) es automática. Para monitorear la salud "
                "del proceso de purga, observe Innodb_history_list_length y "
                "Innodb_purge_trx_id_age en SHOW ENGINE INNODB STATUS.")

        logger.debug("[%s] %s — history_list=%d", check_name, status, history_list_length)
        return _build_result(
            check_name, status,
            value={"innodb_history_list_length": history_list_length,
                   "feature_note": note},
            threshold={"history_list_warning": 10000},
            message=msg,
            duration_ms=duration,
        )
    except Exception as exc:
        duration = _elapsed_ms(t0)
        msg = f"Error en dead_rows: {exc}"
        logger.exception("[%s] ERROR — %s", check_name, msg)
        return _build_result(check_name, "CRITICAL", None, None, msg, duration)


def check_slow_queries_status(conn, thresholds: dict) -> dict:
    """
    CHECK 8 — Contador global de slow queries.

    Consulta la variable de estado 'Slow_queries' que lleva el contador
    acumulado de queries que superaron long_query_time. Un incremento
    sostenido indica degradación de rendimiento en la aplicación.

    Parámetros
    ----------
    conn : mysql.connector.connection
        Conexión activa a MySQL.
    thresholds : dict
        Umbral de número de slow queries para warning.

    Retorna
    -------
    dict
        Resultado con contador de slow queries y configuración del umbral.
    """
    check_name = "slow_queries_status"
    t0 = time.perf_counter()
    try:
        cursor = conn.cursor()
        slow_queries = _fetch_global_status(cursor, "Slow_queries") or 0
        long_query_time = _fetch_global_variable(cursor, "long_query_time") or "N/A"
        slow_log_enabled = _fetch_global_variable(cursor, "slow_query_log") or "OFF"
        cursor.close()

        duration = _elapsed_ms(t0)

        if slow_queries >= thresholds["slow_queries_warning"]:
            status = "WARNING"
            msg = (f"Contador de slow queries elevado: {slow_queries:,} "
                   f"(long_query_time={long_query_time}s)")
        else:
            status = "OK"
            msg = (f"Slow queries dentro de rango: {slow_queries:,} "
                   f"(long_query_time={long_query_time}s)")

        logger.debug("[%s] %s — slow_queries=%d", check_name, status, slow_queries)
        return _build_result(
            check_name, status,
            value={"slow_queries_total": slow_queries,
                   "long_query_time_sec": long_query_time,
                   "slow_log_enabled": slow_log_enabled},
            threshold={"warning_count": thresholds["slow_queries_warning"]},
            message=msg,
            duration_ms=duration,
        )
    except Exception as exc:
        duration = _elapsed_ms(t0)
        msg = f"Error en slow_queries_status: {exc}"
        logger.exception("[%s] ERROR — %s", check_name, msg)
        return _build_result(check_name, "CRITICAL", None, None, msg, duration)


def check_database_size(conn, thresholds: dict) -> dict:  # noqa: ARG001
    """
    CHECK 9 — Tamaño total de las bases de datos del servidor MySQL.

    Suma data_length + index_length de todas las tablas en
    information_schema.TABLES, agrupando por schema para obtener un
    panorama completo del uso de espacio.

    Parámetros
    ----------
    conn : mysql.connector.connection
        Conexión activa a MySQL.
    thresholds : dict
        No utilizado (informativo).

    Retorna
    -------
    dict
        Resultado con tamaño por schema y total del servidor.
    """
    check_name = "database_size"
    t0 = time.perf_counter()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                TABLE_SCHEMA AS schema_name,
                ROUND(SUM(DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024, 2) AS total_size_mb,
                ROUND(SUM(DATA_LENGTH) / 1024 / 1024, 2) AS data_size_mb,
                ROUND(SUM(INDEX_LENGTH) / 1024 / 1024, 2) AS index_size_mb,
                COUNT(TABLE_NAME) AS table_count
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA NOT IN ('information_schema', 'performance_schema')
              AND TABLE_TYPE = 'BASE TABLE'
            GROUP BY TABLE_SCHEMA
            ORDER BY total_size_mb DESC
        """)
        schemas = cursor.fetchall()

        total_size_mb = sum(r["total_size_mb"] or 0 for r in schemas)
        cursor.close()

        duration = _elapsed_ms(t0)
        msg = f"Tamaño total del servidor MySQL: {total_size_mb:.2f} MB ({len(schemas)} schemas)"
        logger.debug("[%s] INFO — total=%.2f MB", check_name, total_size_mb)
        return _build_result(
            check_name, "INFO",
            value={"total_size_mb": round(total_size_mb, 2), "schema_count": len(schemas)},
            threshold=None,
            message=msg,
            duration_ms=duration,
            details={"schemas": schemas},
        )
    except Exception as exc:
        duration = _elapsed_ms(t0)
        msg = f"Error en database_size: {exc}"
        logger.exception("[%s] ERROR — %s", check_name, msg)
        return _build_result(check_name, "CRITICAL", None, None, msg, duration)


def check_replication_lag(conn, thresholds: dict) -> dict:
    """
    CHECK 10 — Lag de replicación MySQL (Seconds_Behind_Source).

    Ejecuta 'SHOW REPLICA STATUS' (o 'SHOW SLAVE STATUS' en versiones
    anteriores) para obtener el lag de replicación en segundos.
    Un valor NULL indica que la réplica no está conectada al primario.

    Parámetros
    ----------
    conn : mysql.connector.connection
        Conexión activa a MySQL.
    thresholds : dict
        Umbrales en segundos para warning y critical.

    Retorna
    -------
    dict
        Resultado con lag en segundos o indicación de servidor primario.
    """
    check_name = "replication_lag"
    t0 = time.perf_counter()
    try:
        cursor = conn.cursor(dictionary=True)

        # Intentar sintaxis moderna (MySQL 8.0.22+) con fallback a antigua
        replica_status = None
        for query in ("SHOW REPLICA STATUS", "SHOW SLAVE STATUS"):
            try:
                cursor.execute(query)
                replica_status = cursor.fetchone()
                break
            except MySQLError:
                continue

        cursor.close()
        duration = _elapsed_ms(t0)

        if replica_status is None:
            # No es réplica — es servidor primario
            msg = "Este servidor es nodo primario (no es réplica)"
            logger.debug("[%s] INFO — servidor primario", check_name)
            return _build_result(
                check_name, "INFO",
                value={"is_primary": True},
                threshold=None,
                message=msg,
                duration_ms=duration,
            )

        # Extraer métricas de replicación
        lag_seconds = replica_status.get("Seconds_Behind_Source") or replica_status.get("Seconds_Behind_Master")
        io_running = replica_status.get("Replica_IO_Running") or replica_status.get("Slave_IO_Running", "No")
        sql_running = replica_status.get("Replica_SQL_Running") or replica_status.get("Slave_SQL_Running", "No")
        last_error = replica_status.get("Last_Error", "") or replica_status.get("Last_SQL_Error", "")
        source_host = replica_status.get("Source_Host") or replica_status.get("Master_Host", "unknown")

        # lag_seconds puede ser None si la réplica no está conectada
        if lag_seconds is None:
            status = "CRITICAL"
            msg = (f"Réplica desconectada del primario {source_host}. "
                   f"IO: {io_running}, SQL: {sql_running}. Error: {last_error}")
        elif lag_seconds >= thresholds["replication_lag_critical_sec"]:
            status = "CRITICAL"
            msg = f"Lag de replicación crítico: {lag_seconds}s (primario: {source_host})"
        elif lag_seconds >= thresholds["replication_lag_warning_sec"]:
            status = "WARNING"
            msg = f"Lag de replicación elevado: {lag_seconds}s (primario: {source_host})"
        else:
            status = "OK"
            msg = f"Replicación saludable: {lag_seconds}s de lag (primario: {source_host})"

        if io_running != "Yes" or sql_running != "Yes":
            status = "CRITICAL"
            msg += f" | ALERTA: IO_Thread={io_running}, SQL_Thread={sql_running}"

        logger.debug("[%s] %s — lag=%s s", check_name, status, lag_seconds)
        return _build_result(
            check_name, status,
            value={"lag_seconds": lag_seconds, "io_running": io_running,
                   "sql_running": sql_running, "source_host": source_host},
            threshold={"warning_sec": thresholds["replication_lag_warning_sec"],
                       "critical_sec": thresholds["replication_lag_critical_sec"]},
            message=msg,
            duration_ms=duration,
            details={"last_error": last_error},
        )
    except Exception as exc:
        duration = _elapsed_ms(t0)
        msg = f"Error en replication_lag: {exc}"
        logger.exception("[%s] ERROR — %s", check_name, msg)
        return _build_result(check_name, "CRITICAL", None, None, msg, duration)


def check_innodb_status(conn, thresholds: dict) -> dict:  # noqa: ARG001
    """
    CHECK 11 — Análisis del estado de InnoDB para detección de errores.

    Ejecuta 'SHOW ENGINE INNODB STATUS' y analiza la salida buscando
    indicadores de problemas: deadlocks, transacciones largas,
    problemas de purge y errores en el log de semáforos.

    Parámetros
    ----------
    conn : mysql.connector.connection
        Conexión activa a MySQL.
    thresholds : dict
        No se aplican umbrales específicos en este check.

    Retorna
    -------
    dict
        Resultado con resumen de estado de InnoDB e indicadores de salud.
    """
    check_name = "innodb_status"
    t0 = time.perf_counter()
    try:
        cursor = conn.cursor()
        cursor.execute("SHOW ENGINE INNODB STATUS")
        rows = cursor.fetchall()
        cursor.close()

        # El resultado tiene 3 columnas: Type, Name, Status
        innodb_text = rows[0][2] if rows else ""

        # Extraer sección relevante para identificar problemas conocidos
        indicators = {
            "has_deadlock": "DEADLOCK" in innodb_text.upper(),
            "has_lock_wait_timeout": "LOCK WAIT TIMEOUT" in innodb_text.upper(),
            "has_transactions_section": "TRANSACTIONS" in innodb_text,
            "has_semaphore_waits": "reservation_count" in innodb_text.lower() or "Mutex spin waits" in innodb_text,
        }

        # Contar deadlocks recientes mencionados en el texto
        deadlock_mentions = innodb_text.upper().count("DEADLOCK")

        duration = _elapsed_ms(t0)

        if indicators["has_deadlock"] and deadlock_mentions > 1:
            status = "WARNING"
            msg = f"InnoDB reporta deadlocks recientes ({deadlock_mentions} menciones en status)"
        else:
            status = "OK"
            msg = "InnoDB operando con normalidad — sin alertas críticas detectadas"

        logger.debug("[%s] %s — deadlocks=%d", check_name, status, deadlock_mentions)
        return _build_result(
            check_name, status,
            value={"deadlock_mentions": deadlock_mentions, **indicators},
            threshold=None,
            message=msg,
            duration_ms=duration,
            details={"innodb_status_excerpt": innodb_text[:2000]},
        )
    except Exception as exc:
        duration = _elapsed_ms(t0)
        if "Access denied" in str(exc) or "1227" in str(exc):
            return _build_result(check_name, "INFO", None, None, "Check omitido: privilegio PROCESS requerido para SHOW ENGINE INNODB STATUS", duration)
        msg = f"Error en innodb_status: {exc}"
        logger.exception("[%s] ERROR — %s", check_name, msg)
        return _build_result(check_name, "CRITICAL", None, None, msg, duration)


def check_open_tables(conn, thresholds: dict) -> dict:
    """
    CHECK 12 — Tablas abiertas en caché (Open_tables).

    Consulta la variable de estado 'Open_tables' para evaluar si el
    caché de tablas está saturado. Si Open_tables se acerca a
    table_open_cache, MySQL debe cerrar y reabrir handles frecuentemente,
    lo que degrada el rendimiento.

    Parámetros
    ----------
    conn : mysql.connector.connection
        Conexión activa a MySQL.
    thresholds : dict
        Umbral de número de tablas abiertas para warning.

    Retorna
    -------
    dict
        Resultado con tablas abiertas, caché configurado y porcentaje de uso.
    """
    check_name = "open_tables"
    t0 = time.perf_counter()
    try:
        cursor = conn.cursor()
        open_tables = _fetch_global_status(cursor, "Open_tables") or 0
        opened_tables = _fetch_global_status(cursor, "Opened_tables") or 0
        table_open_cache_str = _fetch_global_variable(cursor, "table_open_cache")
        table_open_cache = int(table_open_cache_str) if table_open_cache_str else 2000
        cursor.close()

        usage_pct = _safe_divide(open_tables, table_open_cache) * 100
        duration = _elapsed_ms(t0)

        if open_tables >= thresholds["open_tables_warning"]:
            status = "WARNING"
            msg = (f"Tablas abiertas elevadas: {open_tables}/{table_open_cache} "
                   f"({usage_pct:.1f}%). Evaluar incrementar table_open_cache.")
        else:
            status = "OK"
            msg = (f"Tablas abiertas dentro de rango: {open_tables}/{table_open_cache} "
                   f"({usage_pct:.1f}%)")

        logger.debug("[%s] %s — %d/%d (%.1f%%)", check_name, status,
                     open_tables, table_open_cache, usage_pct)
        return _build_result(
            check_name, status,
            value={"open_tables": open_tables,
                   "opened_tables_total": opened_tables,
                   "table_open_cache": table_open_cache,
                   "usage_pct": round(usage_pct, 2)},
            threshold={"warning_count": thresholds["open_tables_warning"],
                       "table_open_cache": table_open_cache},
            message=msg,
            duration_ms=duration,
        )
    except Exception as exc:
        duration = _elapsed_ms(t0)
        msg = f"Error en open_tables: {exc}"
        logger.exception("[%s] ERROR — %s", check_name, msg)
        return _build_result(check_name, "CRITICAL", None, None, msg, duration)


# ---------------------------------------------------------------------------
# FUNCIÓN PRINCIPAL DE ORQUESTACIÓN
# ---------------------------------------------------------------------------

def run_all_checks(conn_params: dict, thresholds: Optional[dict] = None) -> dict:
    """
    Ejecuta todos los health checks sobre una instancia MySQL.

    Función de entrada principal del módulo. Establece una única conexión
    reutilizable para todos los checks (excepto el de conectividad que mide
    latencia de apertura de conexión), ejecuta los 12 checks en secuencia
    y retorna el resultado consolidado.

    Parámetros
    ----------
    conn_params : dict
        Parámetros de conexión mysql.connector:
        - host (str): Hostname o IP del servidor.
        - port (int): Puerto TCP (default: 3306).
        - database (str): Nombre de la base de datos.
        - user (str): Usuario de conexión.
        - password (str): Contraseña del usuario.
        - ssl_ca (str, opcional): Ruta al certificado CA para SSL.
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
    """
    # Fusionar umbrales por defecto con los personalizados
    active_thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    db_host = conn_params.get("host", "unknown")
    db_name = conn_params.get("database", "unknown")
    execution_start = time.perf_counter()
    execution_timestamp = datetime.now(timezone.utc).isoformat()

    logger.info(
        "Iniciando health checks MySQL — host=%s db=%s",
        db_host, db_name
    )

    results = {}

    # CHECK 1: Latencia de conexión (usa conexión separada para medir correctamente)
    logger.info("Ejecutando check: connection_check")
    results["connection_check"] = check_connection(conn_params, active_thresholds)

    # Si la conexión falló, abortar el resto de checks
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
            "error": "No se pudo establecer conexión con MySQL",
        }

    # Abrir conexión reutilizable para el resto de checks
    conn = None
    try:
        conn = mysql.connector.connect(**conn_params, connection_timeout=10)

        # Mapa de checks: nombre → (función, argumentos)
        check_functions = {
            "active_connections":    (check_active_connections,   [conn, active_thresholds]),
            "cache_hit_ratio":       (check_cache_hit_ratio,      [conn, active_thresholds]),
            "locks_check":           (check_locks,                [conn, active_thresholds]),
            "long_running_queries":  (check_long_running_queries, [conn, active_thresholds]),
            "table_sizes":           (check_table_sizes,          [conn, active_thresholds]),
            "dead_rows":             (check_dead_rows,            [conn, active_thresholds]),
            "slow_queries_status":   (check_slow_queries_status,  [conn, active_thresholds]),
            "database_size":         (check_database_size,        [conn, active_thresholds]),
            "replication_lag":       (check_replication_lag,      [conn, active_thresholds]),
            "innodb_status":         (check_innodb_status,        [conn, active_thresholds]),
            "open_tables":           (check_open_tables,          [conn, active_thresholds]),
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

    except MySQLError as exc:
        logger.exception("Error de conexión MySQL durante checks: %s", exc)
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
