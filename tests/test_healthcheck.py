"""
test_healthcheck.py — Pruebas Unitarias para el Motor de Health Check
=======================================================================
Valida la carga de inventario YAML, reglas de alerta y estructuración de reportes.
"""

import pytest
import yaml
from pathlib import Path

from src.healthcheck.engine import (
    _load_database_configs,
    _load_alert_rules,
    HealthReport,
    CheckSummary,
    DatabaseHealthResult,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_database_inventory_loads_correctly():
    """Verifica que el catálogo config/databases.yaml sea válido y contenga clientes B2B."""
    dbs = _load_database_configs()
    assert isinstance(dbs, list)
    assert len(dbs) >= 2, "Debe haber al menos 2 bases de datos en el inventario (Postgres y MySQL)"
    
    pg_db = next((db for db in dbs if db.get("type") == "postgres"), None)
    assert pg_db is not None, "Debe existir una base de datos PostgreSQL configurada"
    assert "sla" in pg_db, "La base de datos debe tener especificación de SLA"
    assert pg_db["sla"]["rpo_hours"] <= 24


def test_alert_rules_load_correctly():
    """Verifica que las reglas de alerta contengan los umbrales críticos."""
    rules = _load_alert_rules()
    assert isinstance(rules, dict)
    assert "rules" in rules or "connection_latency" in rules
    
    rules_dict = rules.get("rules", rules)
    assert "active_connections_pct" in rules_dict
    assert "cache_hit_ratio_pct" in rules_dict
    assert "disk_usage_pct" in rules_dict


def test_health_report_serialization():
    """Valida que el reporte de salud se serialice correctamente a JSON."""
    report = HealthReport(
        report_id="TEST-REPORT-001",
        generated_at="2026-08-26T23:00:00Z",
        sentinel_version="1.0.0",
    )
    db_result = DatabaseHealthResult(
        db_id="test-pg",
        db_type="postgres",
        db_host="localhost",
        db_name="test_db",
        environment="test",
        summary=CheckSummary(total=15, ok=14, warning=1, critical=0),
    )
    report.databases["test-pg"] = db_result
    
    json_output = report.to_json()
    assert "TEST-REPORT-001" in json_output
    assert "test-pg" in json_output
    assert "summary" in json_output
