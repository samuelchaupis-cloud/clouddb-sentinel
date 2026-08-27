"""
engine.py — CloudDB Sentinel
==============================
Orquestador principal del sistema de Health Checks.

Lee el inventario de bases de datos desde config/databases.yaml y
los umbrales de alerta desde config/alert_rules.yaml, ejecuta el
checker correspondiente para cada base de datos (PostgreSQL o MySQL),
consolida los resultados en un HealthReport estructurado, lo persiste
en disco como JSON y dispara notificaciones si hay alertas activas.

Autor: Equipo de Plataformas Cloud
Versión: 1.0.0
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Importar checkers específicos de cada motor
from src.healthcheck import checks_postgres, checks_mysql

# Librería para leer archivos YAML de configuración
try:
    import yaml
except ImportError as exc:
    raise ImportError(
        "Dependencia faltante: instale PyYAML con 'pip install pyyaml'"
    ) from exc

# Logger del módulo
logger = logging.getLogger("clouddb_sentinel.healthcheck.engine")

# ---------------------------------------------------------------------------
# RUTAS DE CONFIGURACIÓN Y OUTPUTS
# ---------------------------------------------------------------------------
# Directorio raíz del proyecto (dos niveles arriba de este archivo)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATABASES_YAML = CONFIG_DIR / "databases.yaml"
ALERT_RULES_YAML = CONFIG_DIR / "alert_rules.yaml"
REPORTS_DIR = PROJECT_ROOT / "logs" / "health_reports"


# ---------------------------------------------------------------------------
# DATACLASSES DE RESULTADO
# ---------------------------------------------------------------------------

@dataclass
class CheckSummary:
    """
    Resumen estadístico de los checks ejecutados sobre una base de datos.

    Atributos
    ----------
    total : int
        Número total de checks ejecutados.
    ok : int
        Checks con estado OK.
    warning : int
        Checks con estado WARNING.
    critical : int
        Checks con estado CRITICAL.
    info : int
        Checks de tipo informativo (sin umbral de alerta).
    errors : int
        Checks que fallaron con error de ejecución.
    """
    total: int = 0
    ok: int = 0
    warning: int = 0
    critical: int = 0
    info: int = 0
    errors: int = 0


@dataclass
class DatabaseHealthResult:
    """
    Resultado completo del health check de una sola base de datos.

    Atributos
    ----------
    db_id : str
        Identificador único de la base de datos en el inventario.
    db_type : str
        Motor de base de datos: 'postgres' o 'mysql'.
    db_host : str
        Hostname o IP del servidor.
    db_name : str
        Nombre de la base de datos.
    environment : str
        Entorno: 'production', 'staging', 'development'.
    status : str
        Estado global: 'HEALTHY', 'DEGRADED' o 'CRITICAL'.
    execution_timestamp : str
        Timestamp ISO 8601 de inicio de ejecución.
    total_duration_ms : float
        Duración total de todos los checks en milisegundos.
    checks : dict
        Diccionario con el resultado de cada check individual.
    summary : CheckSummary
        Resumen estadístico de los checks.
    error : Optional[str]
        Mensaje de error si el check global falló (ej. sin conexión).
    """
    db_id: str = ""
    db_type: str = ""
    db_host: str = ""
    db_name: str = ""
    environment: str = "production"
    status: str = "UNKNOWN"
    execution_timestamp: str = ""
    total_duration_ms: float = 0.0
    checks: dict = field(default_factory=dict)
    summary: CheckSummary = field(default_factory=CheckSummary)
    error: Optional[str] = None


@dataclass
class ExecutiveSummary:
    """
    Resumen ejecutivo del health check completo del sistema.

    Agrega los conteos de todos los checks de todas las bases de datos
    del inventario para proveer una vista de nivel directivo.

    Atributos
    ----------
    total_databases : int
        Total de bases de datos en el inventario monitoreado.
    healthy_databases : int
        Bases de datos con estado HEALTHY.
    degraded_databases : int
        Bases de datos con estado DEGRADED (uno o más warnings).
    critical_databases : int
        Bases de datos con estado CRITICAL (uno o más criticals).
    unreachable_databases : int
        Bases de datos que no pudieron ser contactadas.
    total_checks : int
        Suma de todos los checks individuales ejecutados.
    total_ok : int
        Total de checks con resultado OK.
    total_warnings : int
        Total de checks con resultado WARNING.
    total_criticals : int
        Total de checks con resultado CRITICAL.
    overall_status : str
        Estado global del sistema: 'HEALTHY', 'DEGRADED' o 'CRITICAL'.
    """
    total_databases: int = 0
    healthy_databases: int = 0
    degraded_databases: int = 0
    critical_databases: int = 0
    unreachable_databases: int = 0
    total_checks: int = 0
    total_ok: int = 0
    total_warnings: int = 0
    total_criticals: int = 0
    overall_status: str = "UNKNOWN"


@dataclass
class HealthReport:
    """
    Reporte de health check del sistema CloudDB Sentinel.

    Estructura de datos completa que encapsula todos los resultados
    de una ejecución del health check, incluyendo metadatos, resultados
    por base de datos y resumen ejecutivo.

    Atributos
    ----------
    report_id : str
        Identificador único del reporte (timestamp formateado).
    generated_at : str
        Timestamp ISO 8601 de generación del reporte.
    sentinel_version : str
        Versión del sistema CloudDB Sentinel.
    databases : dict[str, DatabaseHealthResult]
        Resultados por identificador de base de datos.
    executive_summary : ExecutiveSummary
        Resumen ejecutivo agregado del sistema.
    report_path : Optional[str]
        Ruta en disco donde se guardó el reporte JSON.
    alerts_fired : list[dict]
        Lista de alertas disparadas durante esta ejecución.
    """
    report_id: str = ""
    generated_at: str = ""
    sentinel_version: str = "1.0.0"
    databases: dict = field(default_factory=dict)
    executive_summary: ExecutiveSummary = field(default_factory=ExecutiveSummary)
    report_path: Optional[str] = None
    alerts_fired: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """
        Serializa el reporte completo a un diccionario JSON-serializable.

        Retorna
        -------
        dict
            Representación completa del reporte como diccionario.
        """
        data = asdict(self)
        # Convertir DatabaseHealthResult anidados a dict con CheckSummary resuelto
        databases_dict = {}
        for db_id, db_result in self.databases.items():
            if isinstance(db_result, DatabaseHealthResult):
                db_dict = asdict(db_result)
                databases_dict[db_id] = db_dict
            else:
                databases_dict[db_id] = db_result
        data["databases"] = databases_dict

        if isinstance(self.executive_summary, ExecutiveSummary):
            data["executive_summary"] = asdict(self.executive_summary)

        return data

    def to_json(self, indent: int = 2) -> str:
        """
        Serializa el reporte a formato JSON con indentación legible.

        Parámetros
        ----------
        indent : int
            Nivel de indentación JSON (default: 2).

        Retorna
        -------
        str
            Representación JSON del reporte.
        """
        return json.dumps(self.to_dict(), indent=indent, default=str, ensure_ascii=False)


# ---------------------------------------------------------------------------
# FUNCIONES DE CARGA DE CONFIGURACIÓN
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict:
    """
    Carga y parsea un archivo YAML de configuración.

    Parámetros
    ----------
    path : Path
        Ruta absoluta al archivo YAML.

    Retorna
    -------
    dict
        Contenido parseado del archivo YAML.

    Raises
    ------
    FileNotFoundError
        Si el archivo no existe en la ruta especificada.
    yaml.YAMLError
        Si el archivo tiene errores de sintaxis YAML.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Archivo de configuración no encontrado: {path}\n"
            "Asegúrese de que el archivo existe antes de ejecutar el engine."
        )
    with open(path, encoding="utf-8") as fh:
        content = yaml.safe_load(fh)
    if not content:
        logger.warning("Archivo YAML vacío o nulo: %s", path)
        return {}
    logger.debug("Configuración cargada: %s (%d claves)", path.name, len(content))
    return content


def _load_databases_config() -> dict:
    """
    Carga el inventario de bases de datos desde config/databases.yaml.

    Retorna
    -------
    dict
        Diccionario con el inventario de bases de datos indexado por db_id.

    Estructura esperada del YAML:
    ```yaml
    databases:
      prod_postgres_01:
        type: postgres
        host: 10.0.0.1
        port: 5432
        dbname: ventas_produccion
        user: sentinel
        password: "{{ SENTINEL_PG_PASS }}"
        environment: production
        tags: [critical, billing]
      prod_mysql_01:
        type: mysql
        host: 10.0.0.2
        port: 3306
        database: erp_core
        user: sentinel
        password: "{{ SENTINEL_MYSQL_PASS }}"
        environment: production
    ```
    """
    config = _load_yaml(DATABASES_YAML)
    databases = config.get("databases", {})
    if not databases:
        logger.warning("No se encontraron bases de datos en %s", DATABASES_YAML)
    else:
        logger.info("Inventario cargado: %d bases de datos", len(databases))
    return databases


def _load_alert_rules() -> dict:
    """
    Carga las reglas de alerta desde config/alert_rules.yaml.

    Retorna
    -------
    dict
        Diccionario con umbrales globales y por tipo de motor.
    """
    try:
        config = _load_yaml(ALERT_RULES_YAML)
        return config.get("thresholds", {})
    except FileNotFoundError:
        logger.warning(
            "alert_rules.yaml no encontrado — usando umbrales por defecto"
        )
        return {}


def _resolve_env_vars(conn_params: dict) -> dict:
    """
    Resuelve variables de entorno en los parámetros de conexión.

    Permite usar referencias del tipo '{{ VAR_NAME }}' o '$VAR_NAME'
    en el YAML para mantener las credenciales fuera del código fuente.

    Parámetros
    ----------
    conn_params : dict
        Parámetros que pueden contener referencias a variables de entorno.

    Retorna
    -------
    dict
        Parámetros con las variables de entorno resueltas.
    """
    resolved = {}
    for key, value in conn_params.items():
        if isinstance(value, str):
            # Soporte para formato {{ ENV_VAR }} y $ENV_VAR
            if value.startswith("{{") and value.endswith("}}"):
                env_var = value.strip("{{ }}").strip()
                resolved[key] = os.environ.get(env_var, value)
                if resolved[key] == value:
                    logger.warning(
                        "Variable de entorno '%s' no definida para parámetro '%s'",
                        env_var, key
                    )
            elif value.startswith("$"):
                env_var = value[1:]
                resolved[key] = os.environ.get(env_var, value)
            else:
                resolved[key] = value
        else:
            resolved[key] = value
    return resolved


# ---------------------------------------------------------------------------
# CONSTRUCCIÓN DE PARÁMETROS DE CONEXIÓN
# ---------------------------------------------------------------------------

def _build_conn_params(db_config: dict, db_type: str) -> dict:
    """
    Construye el diccionario de parámetros de conexión según el motor.

    Mapea los campos del YAML de inventario a los parámetros esperados
    por psycopg2 (PostgreSQL) o mysql.connector (MySQL).

    Parámetros
    ----------
    db_config : dict
        Configuración de la base de datos desde databases.yaml.
    db_type : str
        Tipo de motor: 'postgres' o 'mysql'.

    Retorna
    -------
    dict
        Parámetros de conexión listos para usar con el conector.
    """
    resolved = _resolve_env_vars(db_config)

    if db_type == "postgres":
        params = {
            "host": resolved.get("host", "localhost"),
            "port": int(resolved.get("port", 5432)),
            "dbname": resolved.get("dbname", resolved.get("database", "postgres")),
            "user": resolved.get("user", resolved.get("username", "postgres")),
            "password": resolved.get("password", ""),
        }
        # Opcional: SSL
        if resolved.get("sslmode"):
            params["sslmode"] = resolved["sslmode"]
        if resolved.get("sslrootcert"):
            params["sslrootcert"] = resolved["sslrootcert"]

    elif db_type == "mysql":
        params = {
            "host": resolved.get("host", "localhost"),
            "port": int(resolved.get("port", 3306)),
            "database": resolved.get("database", resolved.get("dbname", "mysql")),
            "user": resolved.get("user", resolved.get("username", "root")),
            "password": resolved.get("password", ""),
        }
        # Opcional: SSL/TLS
        if resolved.get("ssl_ca"):
            params["ssl_ca"] = resolved["ssl_ca"]
        if resolved.get("ssl_cert"):
            params["ssl_cert"] = resolved["ssl_cert"]

    else:
        raise ValueError(f"Tipo de base de datos no soportado: '{db_type}'")

    return params


# ---------------------------------------------------------------------------
# EVALUACIÓN DE ESTADO GLOBAL DE UNA BASE DE DATOS
# ---------------------------------------------------------------------------

def _evaluate_db_status(summary: CheckSummary) -> str:
    """
    Determina el estado global de una base de datos según su resumen de checks.

    Parámetros
    ----------
    summary : CheckSummary
        Resumen estadístico de los checks ejecutados.

    Retorna
    -------
    str
        Estado global: 'CRITICAL', 'DEGRADED' o 'HEALTHY'.
    """
    if summary.critical > 0 or summary.errors > 0:
        return "CRITICAL"
    elif summary.warning > 0:
        return "DEGRADED"
    else:
        return "HEALTHY"


def _evaluate_overall_status(executive: ExecutiveSummary) -> str:
    """
    Determina el estado global del sistema basado en el resumen ejecutivo.

    Parámetros
    ----------
    executive : ExecutiveSummary
        Resumen ejecutivo agregado del sistema completo.

    Retorna
    -------
    str
        Estado global del sistema: 'CRITICAL', 'DEGRADED' o 'HEALTHY'.
    """
    if executive.critical_databases > 0 or executive.unreachable_databases > 0:
        return "CRITICAL"
    elif executive.degraded_databases > 0:
        return "DEGRADED"
    else:
        return "HEALTHY"


# ---------------------------------------------------------------------------
# EJECUCIÓN DE CHECKS PARA UNA BASE DE DATOS
# ---------------------------------------------------------------------------

def _run_checks_for_db(
    db_id: str,
    db_config: dict,
    global_thresholds: dict,
) -> DatabaseHealthResult:
    """
    Ejecuta el health check completo para una base de datos específica.

    Determina el tipo de motor, construye los parámetros de conexión,
    obtiene los umbrales aplicables y delega al módulo de checks
    correspondiente (checks_postgres o checks_mysql).

    Parámetros
    ----------
    db_id : str
        Identificador único de la base de datos en el inventario.
    db_config : dict
        Configuración completa de la base de datos desde databases.yaml.
    global_thresholds : dict
        Umbrales de alert_rules.yaml para aplicar a los checks.

    Retorna
    -------
    DatabaseHealthResult
        Resultado completo del health check de la base de datos.
    """
    db_type = db_config.get("type", "").lower()
    environment = db_config.get("environment", "production")
    db_host = db_config.get("host", "unknown")
    db_name = db_config.get("dbname", db_config.get("database", "unknown"))

    logger.info(
        "═══ Iniciando checks: %s (%s) | %s @ %s ═══",
        db_id, db_type.upper(), db_name, db_host
    )

    result = DatabaseHealthResult(
        db_id=db_id,
        db_type=db_type,
        db_host=db_host,
        db_name=db_name,
        environment=environment,
        execution_timestamp=datetime.now(timezone.utc).isoformat(),
    )

    try:
        # Construir parámetros de conexión (resuelve variables de entorno)
        conn_params = _build_conn_params(db_config, db_type)

        # Obtener umbrales específicos del motor o usar los globales
        thresholds = {
            **global_thresholds.get("global", {}),
            **global_thresholds.get(db_type, {}),
            **db_config.get("thresholds", {}),  # Umbrales específicos por BD
        }

        # Ejecutar checks según el motor
        if db_type == "postgres":
            raw_result = checks_postgres.run_all_checks(conn_params, thresholds or None)
        elif db_type == "mysql":
            raw_result = checks_mysql.run_all_checks(conn_params, thresholds or None)
        else:
            error_msg = f"Motor de base de datos no soportado: '{db_type}'"
            logger.error("[%s] %s", db_id, error_msg)
            result.status = "CRITICAL"
            result.error = error_msg
            return result

        # Poblar el resultado con los datos del checker
        result.checks = raw_result.get("checks", {})
        result.total_duration_ms = raw_result.get("total_duration_ms", 0.0)

        if raw_result.get("error"):
            result.error = raw_result["error"]

        # Construir CheckSummary desde el resumen del checker
        raw_summary = raw_result.get("summary", {})
        result.summary = CheckSummary(
            total=raw_summary.get("total", 0),
            ok=raw_summary.get("ok", 0),
            warning=raw_summary.get("warning", 0),
            critical=raw_summary.get("critical", 0),
            info=raw_summary.get("info", 0),
            errors=raw_summary.get("errors", 0),
        )

        result.status = _evaluate_db_status(result.summary)

    except FileNotFoundError as exc:
        error_msg = f"Archivo de configuración no encontrado: {exc}"
        logger.error("[%s] %s", db_id, error_msg)
        result.status = "CRITICAL"
        result.error = error_msg
    except ValueError as exc:
        error_msg = f"Error de configuración: {exc}"
        logger.error("[%s] %s", db_id, error_msg)
        result.status = "CRITICAL"
        result.error = error_msg
    except Exception as exc:
        error_msg = f"Error inesperado ejecutando checks para {db_id}: {exc}"
        logger.exception("[%s] %s", db_id, error_msg)
        result.status = "CRITICAL"
        result.error = error_msg

    logger.info(
        "Checks completados: %s | Estado: %s | OK:%d WARN:%d CRIT:%d | %.0f ms",
        db_id, result.status,
        result.summary.ok, result.summary.warning, result.summary.critical,
        result.total_duration_ms,
    )
    return result


# ---------------------------------------------------------------------------
# PERSISTENCIA DEL REPORTE
# ---------------------------------------------------------------------------

def _save_report(report: HealthReport) -> str:
    """
    Persiste el HealthReport como archivo JSON en el directorio de reportes.

    El archivo se nombra con el formato YYYY-MM-DD_HH-MM.json para
    facilitar su identificación y ordenamiento cronológico.

    Parámetros
    ----------
    report : HealthReport
        Reporte completo a persistir.

    Retorna
    -------
    str
        Ruta absoluta del archivo JSON generado.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Nombre del archivo basado en timestamp de generación
    timestamp_part = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"{timestamp_part}.json"
    report_path = REPORTS_DIR / filename

    # Evitar sobreescritura si se ejecuta más de una vez por minuto
    if report_path.exists():
        timestamp_part = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{timestamp_part}.json"
        report_path = REPORTS_DIR / filename

    json_content = report.to_json()
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(json_content)

    logger.info("Reporte guardado en: %s (%d bytes)", report_path, len(json_content))
    return str(report_path)


# ---------------------------------------------------------------------------
# INTEGRACIÓN CON MÓDULO DE ALERTAS
# ---------------------------------------------------------------------------

def _fire_alerts(report: HealthReport) -> list[dict]:
    """
    Evalúa el reporte y dispara alertas si hay condiciones críticas.

    Intenta importar el módulo src.alerting.notifier. Si no está disponible,
    registra una advertencia pero no interrumpe el flujo del engine.

    Parámetros
    ----------
    report : HealthReport
        Reporte generado con todos los resultados de checks.

    Retorna
    -------
    list[dict]
        Lista de alertas enviadas durante esta evaluación.
    """
    alerts_fired = []

    try:
        from src.alerting import notifier  # type: ignore

        for db_id, db_result in report.databases.items():
            if not isinstance(db_result, DatabaseHealthResult):
                continue

            if db_result.status in ("CRITICAL", "DEGRADED"):
                alert = {
                    "db_id": db_id,
                    "db_host": db_result.db_host,
                    "db_name": db_result.db_name,
                    "db_type": db_result.db_type,
                    "environment": db_result.environment,
                    "status": db_result.status,
                    "summary": asdict(db_result.summary),
                    "critical_checks": [
                        {"check": name, "message": data.get("message", ""), "value": data.get("value")}
                        for name, data in db_result.checks.items()
                        if data.get("status") in ("CRITICAL", "WARNING")
                    ],
                    "report_id": report.report_id,
                    "timestamp": report.generated_at,
                }
                try:
                    notifier.send_alert(alert)
                    alerts_fired.append(alert)
                    logger.info("Alerta enviada para %s (estado: %s)", db_id, db_result.status)
                except Exception as notify_exc:
                    logger.error(
                        "Error al enviar alerta para %s: %s", db_id, notify_exc
                    )

    except ImportError:
        logger.warning(
            "Módulo src.alerting.notifier no disponible — "
            "notificaciones de alerta deshabilitadas"
        )
    except Exception as exc:
        logger.exception("Error inesperado en módulo de alertas: %s", exc)

    return alerts_fired


# ---------------------------------------------------------------------------
# FUNCIÓN PRINCIPAL DE EJECUCIÓN
# ---------------------------------------------------------------------------

def run_health_check(db_id: Optional[str] = None) -> HealthReport:
    """
    Ejecuta el health check del sistema CloudDB Sentinel.

    Función de entrada principal del engine. Carga la configuración,
    ejecuta los checks de todas (o una específica) base de datos del
    inventario, genera el HealthReport consolidado, lo persiste en disco
    y dispara alertas si es necesario.

    Parámetros
    ----------
    db_id : str, opcional
        Identificador de una base de datos específica a verificar.
        Si es None, se verifican todas las bases de datos del inventario.

    Retorna
    -------
    HealthReport
        Objeto completo con todos los resultados, resumen ejecutivo
        y metadatos de la ejecución.

    Ejemplos
    --------
    Verificar todas las bases de datos:
    >>> from src.healthcheck.engine import run_health_check
    >>> report = run_health_check()
    >>> print(report.executive_summary.overall_status)

    Verificar una base de datos específica:
    >>> report = run_health_check(db_id="prod_postgres_01")
    >>> print(report.databases["prod_postgres_01"].status)
    """
    global_start = time.perf_counter()
    generated_at = datetime.now(timezone.utc).isoformat()
    report_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    logger.info("╔══════════════════════════════════════════╗")
    logger.info("║  CloudDB Sentinel — Health Check Engine  ║")
    logger.info("║  Ejecución: %s             ║", report_id)
    logger.info("╚══════════════════════════════════════════╝")

    # Inicializar el reporte
    report = HealthReport(
        report_id=report_id,
        generated_at=generated_at,
    )

    # Cargar configuración
    try:
        all_databases = _load_databases_config()
        global_thresholds = _load_alert_rules()
    except Exception as exc:
        logger.exception("Error crítico cargando configuración: %s", exc)
        report.executive_summary.overall_status = "CRITICAL"
        return report

    # Filtrar bases de datos a verificar
    if db_id is not None:
        if db_id not in all_databases:
            logger.error(
                "Base de datos '%s' no encontrada en el inventario. "
                "IDs disponibles: %s",
                db_id, list(all_databases.keys())
            )
            report.executive_summary.overall_status = "CRITICAL"
            return report
        databases_to_check = {db_id: all_databases[db_id]}
    else:
        databases_to_check = all_databases

    if not databases_to_check:
        logger.warning("No hay bases de datos configuradas para verificar")
        report.executive_summary.overall_status = "HEALTHY"
        return report

    logger.info(
        "Verificando %d base(s) de datos: %s",
        len(databases_to_check),
        list(databases_to_check.keys())
    )

    # Ejecutar checks para cada base de datos
    executive = ExecutiveSummary(total_databases=len(databases_to_check))

    for current_db_id, current_db_config in databases_to_check.items():
        db_result = _run_checks_for_db(
            current_db_id,
            current_db_config,
            global_thresholds,
        )
        report.databases[current_db_id] = db_result

        # Agregar al resumen ejecutivo
        executive.total_checks += db_result.summary.total
        executive.total_ok += db_result.summary.ok
        executive.total_warnings += db_result.summary.warning
        executive.total_criticals += db_result.summary.critical

        if db_result.status == "HEALTHY":
            executive.healthy_databases += 1
        elif db_result.status == "DEGRADED":
            executive.degraded_databases += 1
        elif db_result.status == "CRITICAL":
            if db_result.error and "No se pudo conectar" in str(db_result.error):
                executive.unreachable_databases += 1
            else:
                executive.critical_databases += 1
        else:
            executive.unreachable_databases += 1

    # Determinar estado global del sistema
    executive.overall_status = _evaluate_overall_status(executive)
    report.executive_summary = executive

    # Persistir reporte en disco
    try:
        report_path = _save_report(report)
        report.report_path = report_path
    except Exception as exc:
        logger.error("Error al guardar reporte en disco: %s", exc)

    # Disparar alertas si hay condiciones críticas o de degradación
    if executive.overall_status in ("CRITICAL", "DEGRADED"):
        report.alerts_fired = _fire_alerts(report)

    total_elapsed = (time.perf_counter() - global_start) * 1000
    logger.info(
        "══════════════════════════════════════════════════════"
    )
    logger.info(
        "RESULTADO: %s | DBs: %d total / %d OK / %d DEGRADED / %d CRITICAL",
        executive.overall_status,
        executive.total_databases,
        executive.healthy_databases,
        executive.degraded_databases,
        executive.critical_databases,
    )
    logger.info(
        "Checks: %d total / %d OK / %d WARNING / %d CRITICAL | %.0f ms total",
        executive.total_checks, executive.total_ok,
        executive.total_warnings, executive.total_criticals,
        total_elapsed,
    )
    logger.info("Reporte: %s", report.report_path or "No guardado")
    logger.info(
        "══════════════════════════════════════════════════════"
    )

    return report


# ---------------------------------------------------------------------------
# PUNTO DE ENTRADA PARA EJECUCIÓN DIRECTA
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Configuración básica de logging para ejecución directa
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Soporte para filtrar por db_id desde línea de comandos
    target_db = sys.argv[1] if len(sys.argv) > 1 else None

    if target_db:
        logger.info("Modo de verificación específica: %s", target_db)
    else:
        logger.info("Modo de verificación completa — todas las bases de datos")

    reporte = run_health_check(db_id=target_db)
    print(reporte.to_json())
    sys.exit(0 if reporte.executive_summary.overall_status == "HEALTHY" else 1)
