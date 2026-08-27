"""
test_reporting.py — Pruebas Unitarias para Generación de Reportes
===================================================================
Valida la lógica de consolidación de estado y renderizado de plantillas HTML.
"""

import pytest
from src.reporting.generator import (
    _determine_overall_status,
    _get_jinja_env,
    generate_html_report,
)


def test_determine_overall_status_healthy():
    """Valida que sin alertas críticas ni warnings el estado sea 'healthy'."""
    health_report = {"checks": [{"status": "OK"}]}
    backup_status = {"backups": [{"status": "SUCCESS"}]}
    capacity_report = {"alerts": []}
    
    status = _determine_overall_status(health_report, backup_status, capacity_report)
    assert status == "healthy"


def test_determine_overall_status_critical():
    """Valida que una falla crítica fuerce el estado a 'critical'."""
    health_report = {"checks": [{"status": "CRITICAL"}]}
    backup_status = {"backups": [{"status": "SUCCESS"}]}
    capacity_report = {"alerts": []}
    
    status = _determine_overall_status(health_report, backup_status, capacity_report)
    assert status == "critical"


def test_jinja_env_loads_template():
    """Valida que Jinja2 cargue template.html y aplique filtros personalizados."""
    env = _get_jinja_env()
    assert "human_bytes" in env.filters
    
    # Probar filtro human_bytes
    assert env.filters["human_bytes"](2048, "MB") == "2.00 GB"
    assert env.filters["human_bytes"](500, "MB") == "500 MB"


def test_generate_html_report_renders_successfully():
    """Valida la generación completa de HTML con datos de prueba."""
    health_mock = {
        "report_id": "TEST-2026",
        "generated_at": "2026-08-26T23:00:00Z",
        "databases": {},
        "executive_summary": {
            "overall_status": "HEALTHY",
            "total_checks": 15,
            "total_ok": 15,
            "total_warnings": 0,
            "total_criticals": 0,
        },
    }
    backup_mock = {"backups": []}
    capacity_mock = {"snapshots": [], "growth_rates": [], "alerts": [], "recommendations": []}
    
    html = generate_html_report(health_mock, backup_mock, capacity_mock)
    assert isinstance(html, str)
    assert "CloudDB Sentinel" in html
    assert "HEALTHY" in html or "Saludable" in html or "Reporte" in html
