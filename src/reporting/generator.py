"""
generator.py - Generador de Reportes para CloudDB Sentinel v1.0
================================================================
Combina los datos de los módulos de health check, backup y capacity planning
para producir reportes HTML y PDF de calidad corporativa B2B.

Soporta dos motores de exportación a PDF:
  1. weasyprint  (preferido - produce PDF de alta calidad)
  2. Fallback a HTML si weasyprint no está instalado

Autor: CloudDB Sentinel - Equipo de Ingeniería de Plataformas
Fecha: 2026
"""

import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

# ---------------------------------------------------------------------------
# Logging estructurado
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

# ---------------------------------------------------------------------------
# Rutas del proyecto
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = BASE_DIR / "reports"


# ---------------------------------------------------------------------------
# Motor de templates Jinja2
# ---------------------------------------------------------------------------

def _get_jinja_env() -> Environment:
    """
    Crea y retorna el entorno Jinja2 configurado con el directorio de templates.

    Returns:
        Entorno Jinja2 listo para renderizar.
    """
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    # Filtro personalizado: formatear bytes a formato humano
    def human_bytes(value: float, unit: str = "MB") -> str:
        """Convierte un valor numérico a representación legible."""
        try:
            v = float(value)
        except (TypeError, ValueError):
            return "—"
        if unit == "MB":
            if v >= 1024:
                return f"{v / 1024:.2f} GB"
            return f"{v:.0f} MB"
        return str(value)

    env.filters["human_bytes"] = human_bytes
    return env


# ---------------------------------------------------------------------------
# Helpers para construir el contexto de renderizado
# ---------------------------------------------------------------------------

def _determine_overall_status(health_report: dict, backup_status: dict, capacity_report: dict) -> str:
    """
    Determina el estado general del sistema basado en los datos de los tres módulos.

    Args:
        health_report:   Datos del módulo de health check.
        backup_status:   Datos del módulo de backup.
        capacity_report: Datos del módulo de capacity planning.

    Returns:
        'healthy' | 'degraded' | 'critical'
    """
    has_critical = False
    has_warning = False

    # Evaluar alertas de health check
    for check in health_report.get("checks", []):
        st = check.get("status", "OK")
        if st == "CRITICAL":
            has_critical = True
        elif st == "WARNING":
            has_warning = True

    # Evaluar backups fallidos
    for bk in backup_status.get("backups", []):
        if bk.get("status") == "FAILED":
            has_critical = True
        elif bk.get("status") == "PARTIAL":
            has_warning = True

    # Evaluar alertas de capacidad
    for alert in capacity_report.get("alerts", []):
        if alert.get("level") == "CRITICAL":
            has_critical = True
        elif alert.get("level") == "WARNING":
            has_warning = True

    if has_critical:
        return "critical"
    if has_warning:
        return "degraded"
    return "healthy"


def _build_summary(health_report: dict, backup_status: dict, capacity_report: dict) -> dict:
    """
    Construye el bloque de resumen con contadores de KPIs para el panel de estado general.

    Args:
        health_report:   Datos del módulo de health check.
        backup_status:   Datos del módulo de backup.
        capacity_report: Datos del módulo de capacity planning.

    Returns:
        Diccionario con los contadores del resumen.
    """
    # Contar BDs por estado desde health checks
    healthy_dbs = 0
    warning_dbs = 0
    critical_dbs = 0

    db_states: dict[str, str] = {}
    for check in health_report.get("checks", []):
        db_id = check.get("db_id", "unknown")
        st = check.get("status", "OK")
        prev = db_states.get(db_id, "OK")
        # Escalada: mantener el estado más grave por BD
        priority = {"OK": 0, "WARNING": 1, "CRITICAL": 2}
        if priority.get(st, 0) > priority.get(prev, 0):
            db_states[db_id] = st

    for db_id, st in db_states.items():
        if st == "CRITICAL":
            critical_dbs += 1
        elif st == "WARNING":
            warning_dbs += 1
        else:
            healthy_dbs += 1

    # Contar backups
    backups = backup_status.get("backups", [])
    successful_backups = sum(1 for b in backups if b.get("status") == "SUCCESS")
    failed_backups = sum(1 for b in backups if b.get("status") == "FAILED")

    # Contar alertas activas
    active_alerts = (
        len(capacity_report.get("alerts", []))
        + sum(1 for c in health_report.get("checks", []) if c.get("status") in ("WARNING", "CRITICAL"))
    )

    return {
        "healthy_dbs": healthy_dbs,
        "warning_dbs": warning_dbs,
        "critical_dbs": critical_dbs,
        "successful_backups": successful_backups,
        "failed_backups": failed_backups,
        "active_alerts": active_alerts,
        "total_dbs": len(db_states),
    }


def _build_capacity_rows(capacity_report: dict) -> list[dict]:
    """
    Combina snapshots con growth_rates para construir las filas de la tabla de capacidad.

    Args:
        capacity_report: Reporte de capacity planning.

    Returns:
        Lista de diccionarios con los datos de cada fila.
    """
    snapshots = {s["db_id"]: s for s in capacity_report.get("snapshots", [])}
    growth_rates = {g["db_id"]: g for g in capacity_report.get("growth_rates", [])}

    rows = []
    for db_id, snap in snapshots.items():
        gr = growth_rates.get(db_id, {})
        rows.append({
            "db_id": db_id,
            "db_size_mb": snap.get("db_size_mb", 0),
            "disk_usage_percent": snap.get("disk_usage_percent", 0),
            "avg_growth_mb_day": gr.get("avg_growth_mb_day", 0),
            "projection_90d_gb": gr.get("projection_90d_gb", 0),
            "time_to_exhaustion_days": gr.get("time_to_exhaustion_days"),
            "trend": gr.get("trend", "stable"),
        })

    # Ordenar por uso de disco descendente (más críticas arriba)
    rows.sort(key=lambda r: float(r.get("disk_usage_percent", 0)), reverse=True)
    return rows


# ---------------------------------------------------------------------------
# Función principal: generate_html_report
# ---------------------------------------------------------------------------

def generate_html_report(
    health_report: dict,
    backup_status: dict,
    capacity_report: dict,
    extra_context: Optional[dict] = None,
) -> str:
    """
    Combina los datos de los tres módulos (health, backup, capacity), renderiza
    la plantilla Jinja2 y retorna el HTML completo como string.

    Args:
        health_report:   Dict con los resultados del health check. Estructura esperada:
                         {'checks': [...], 'generated_at': '...'}
        backup_status:   Dict con el estado de los backups. Estructura esperada:
                         {'backups': [...], 'generated_at': '...'}
        capacity_report: Dict o CapacityReport.asdict() con datos de capacidad.
        extra_context:   Contexto adicional opcional (client_name, environment, etc.)

    Returns:
        String con el HTML completo renderizado.

    Raises:
        jinja2.TemplateNotFound: Si el archivo template.html no se encuentra.
    """
    now = datetime.utcnow()
    report_date = now.strftime("%Y-%m-%d")
    generated_at = now.strftime("%Y-%m-%d %H:%M:%S")

    # Período del reporte: últimas 24 horas
    period_start = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M")
    period_end = now.strftime("%Y-%m-%d %H:%M")

    overall_status = _determine_overall_status(health_report, backup_status, capacity_report)
    summary = _build_summary(health_report, backup_status, capacity_report)
    capacity_rows = _build_capacity_rows(capacity_report)

    # Recopilar todas las alertas (health + capacidad)
    all_alerts = list(capacity_report.get("alerts", []))
    for check in health_report.get("checks", []):
        if check.get("status") in ("WARNING", "CRITICAL"):
            all_alerts.append({
                "db_id": check.get("db_id", "—"),
                "level": check.get("status"),
                "category": "HEALTH_CHECK",
                "message": f"{check.get('check_name', '—')}: valor {check.get('value', '—')} vs umbral {check.get('threshold', '—')}",
                "value": check.get("value", 0),
                "threshold": check.get("threshold", 0),
                "timestamp": check.get("timestamp", generated_at),
            })

    # Ordenar alertas: CRITICAL primero
    all_alerts.sort(key=lambda a: 0 if a.get("level") == "CRITICAL" else 1)

    context = {
        "report_date": report_date,
        "generated_at": generated_at,
        "period_start": period_start,
        "period_end": period_end,
        "overall_status": overall_status,
        "summary": summary,
        "total_databases": summary["total_dbs"],
        "health_checks": health_report.get("checks", []),
        "backups": backup_status.get("backups", []),
        "capacity_data": capacity_rows,
        "alerts": all_alerts,
        "environment": "Producción",
        "client_name": "Corporativo B2B",
    }

    # Fusionar contexto extra si se proporciona
    if extra_context:
        context.update(extra_context)

    env = _get_jinja_env()
    template = env.get_template("template.html")
    html_content = template.render(**context)

    logger.info(
        "Reporte HTML generado | estado=%s | health_checks=%d | backups=%d | alertas=%d",
        overall_status,
        len(context["health_checks"]),
        len(context["backups"]),
        len(all_alerts),
    )
    return html_content


# ---------------------------------------------------------------------------
# Función: generate_pdf_report
# ---------------------------------------------------------------------------

def generate_pdf_report(html_content: str, output_path: str) -> str:
    """
    Convierte el HTML a PDF usando WeasyPrint. Si weasyprint no está disponible,
    guarda el HTML con extensión .html como fallback y retorna ese path.

    Args:
        html_content: String con el HTML a convertir.
        output_path:  Ruta de destino para el PDF (ej. 'reports/reporte.pdf').

    Returns:
        Ruta absoluta del archivo generado (.pdf o .html en caso de fallback).
    """
    output_path = str(output_path)
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Intentar usar WeasyPrint
    try:
        from weasyprint import HTML as WeasyHTML
        logger.info("Generando PDF con WeasyPrint | destino=%s", output_path)
        WeasyHTML(string=html_content).write_pdf(output_path)
        logger.info("PDF generado exitosamente | path=%s", output_path)
        return output_path
    except ImportError:
        logger.warning(
            "WeasyPrint no está instalado. Guardando reporte como HTML. "
            "Instale WeasyPrint con: pip install weasyprint"
        )
    except Exception as exc:
        logger.error("Error al generar PDF con WeasyPrint: %s. Usando fallback HTML.", exc)

    # Fallback: guardar como HTML
    html_path = output_path.replace(".pdf", ".html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    logger.info("Reporte HTML guardado como fallback | path=%s", html_path)
    return html_path


# ---------------------------------------------------------------------------
# Función: generate_daily_report
# ---------------------------------------------------------------------------

def generate_daily_report(output_dir: str = "reports/", extra_context: Optional[dict] = None) -> str:
    """
    Función principal del ciclo de reporte diario. Recopila datos de todos los módulos,
    genera el reporte HTML + PDF y lo guarda con nombre estándar de operaciones.

    El nombre del archivo sigue el formato:
        CloudDB_Sentinel_Report_YYYY-MM-DD.pdf

    Args:
        output_dir:    Directorio donde se guardan los reportes. Default: 'reports/'.
        extra_context: Contexto Jinja2 adicional (client_name, environment, etc.)

    Returns:
        Ruta absoluta del reporte generado (.pdf o .html).
    """
    logger.info("=== Iniciando generación de reporte diario CloudDB Sentinel ===")
    now = datetime.utcnow()
    date_str = now.strftime("%Y-%m-%d")

    # Asegurar que el directorio de salida exista
    output_dir_path = Path(BASE_DIR) / output_dir
    output_dir_path.mkdir(parents=True, exist_ok=True)

    # --- Recopilar datos de cada módulo ---
    health_report = _fetch_health_report()
    backup_status = _fetch_backup_status()
    capacity_report = _fetch_capacity_report()

    # --- Generar HTML ---
    try:
        html_content = generate_html_report(
            health_report=health_report,
            backup_status=backup_status,
            capacity_report=capacity_report,
            extra_context=extra_context,
        )
    except Exception as exc:
        logger.error("Error al generar HTML del reporte: %s", exc)
        raise

    # --- Guardar también el HTML para referencia ---
    html_path = output_dir_path / f"CloudDB_Sentinel_Report_{date_str}.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    logger.info("HTML del reporte guardado en: %s", html_path)

    # --- Generar PDF ---
    pdf_path = output_dir_path / f"CloudDB_Sentinel_Report_{date_str}.pdf"
    final_path = generate_pdf_report(html_content, str(pdf_path))

    logger.info("=== Reporte diario generado exitosamente | path=%s ===", final_path)
    return final_path


def _fetch_health_report() -> dict:
    """
    Obtiene el reporte de health check del módulo correspondiente.
    """
    try:
        from src.healthcheck.engine import run_health_check
        report = run_health_check()
        return report.to_dict()
    except Exception as exc:
        logger.warning("Error al obtener health report directo: %s", exc)
        return {"checks": [], "generated_at": datetime.now().isoformat()}


def _fetch_backup_status() -> dict:
    """
    Obtiene el estado de los backups del módulo de backup.
    """
    try:
        from src.backup.backup_manager import run_backup_all
        results = run_backup_all()
        return {
            "backups": [r.to_dict() for r in results],
            "generated_at": datetime.now().isoformat()
        }
    except Exception as exc:
        logger.warning("Error al obtener backup status directo: %s", exc)
        return {"backups": [], "generated_at": datetime.now().isoformat()}


def _fetch_capacity_report() -> dict:
    """
    Obtiene el reporte de capacidad del módulo de capacity planning.

    Returns:
        Diccionario con el reporte de capacidad.
    """
    try:
        from src.capacity.capacity_planner import generate_capacity_report
        from dataclasses import asdict
        report = generate_capacity_report()
        return asdict(report)
    except ImportError:
        logger.warning("Módulo de capacity planning no disponible. Usando datos vacíos.")
        return {"snapshots": [], "growth_rates": [], "alerts": [], "recommendations": []}
    except Exception as exc:
        logger.error("Error al obtener capacity report: %s", exc)
        return {"snapshots": [], "growth_rates": [], "alerts": [], "recommendations": [], "error": str(exc)}


# ---------------------------------------------------------------------------
# Función: generate_checklist_report
# ---------------------------------------------------------------------------

def generate_checklist_report(health_report: dict) -> str:
    """
    Genera una versión simplificada 'estilo operador' del reporte en texto plano.
    Ideal para imprimir o incluir en tickets de ITSM. Usa checkmarks ✓/✗.

    Formato de salida:
        ╔══════════════════════════════════════╗
        ║   CloudDB Sentinel - Checklist        ║
        ╚══════════════════════════════════════╝
        ✓ [OK]       crm-prod-pg01  | Conexión
        ✗ [CRITICAL] crm-prod-pg01  | Replicación lag > umbral

    Args:
        health_report: Dict con los resultados del health check.

    Returns:
        String con el checklist formateado para consola/impresión.
    """
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "╔══════════════════════════════════════════════════════════════╗",
        "║         CloudDB Sentinel v1.0 — Checklist de Operaciones     ║",
        "╚══════════════════════════════════════════════════════════════╝",
        f"  Generado: {now} UTC",
        "  " + "─" * 62,
        "",
    ]

    checks = health_report.get("checks", [])
    if not checks:
        lines.append("  (Sin datos de health check disponibles)")
    else:
        current_db = None
        for check in checks:
            db_id = check.get("db_id", "—")
            check_name = check.get("check_name", "—")
            status = check.get("status", "OK")
            value = check.get("value", "—")
            threshold = check.get("threshold", "—")

            # Separador por base de datos
            if db_id != current_db:
                if current_db is not None:
                    lines.append("")
                lines.append(f"  📦 BASE DE DATOS: {db_id}")
                lines.append("  " + "─" * 50)
                current_db = db_id

            # Símbolo y formato según estado
            if status == "OK":
                symbol = "✓"
                label = f"[OK      ]"
            elif status == "WARNING":
                symbol = "⚠"
                label = f"[WARNING ]"
            elif status == "CRITICAL":
                symbol = "✗"
                label = f"[CRITICAL]"
            else:
                symbol = "?"
                label = f"[UNKNOWN ]"

            rec = check.get("recommendation", "")
            rec_str = f" → {rec}" if rec else ""

            lines.append(
                f"  {symbol} {label} {check_name:<35s} | Valor: {str(value):<10s} | Umbral: {str(threshold)}{rec_str}"
            )

    lines.extend([
        "",
        "  " + "─" * 62,
        f"  Total checks: {len(checks)} | "
        f"OK: {sum(1 for c in checks if c.get('status') == 'OK')} | "
        f"WARNING: {sum(1 for c in checks if c.get('status') == 'WARNING')} | "
        f"CRITICAL: {sum(1 for c in checks if c.get('status') == 'CRITICAL')}",
        "  Reporte generado por CloudDB Sentinel v1.0 — Confidencial B2B",
        "╚══════════════════════════════════════════════════════════════╝",
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Punto de entrada para ejecución directa
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    """
    Ejecución directa: genera el reporte diario completo.
    Uso: python -m src.reporting.generator [output_dir]
    """
    import sys
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "reports/"
    print(f"Generando reporte diario CloudDB Sentinel → {out_dir}")
    path = generate_daily_report(output_dir=out_dir)
    print(f"✅ Reporte generado: {path}")
