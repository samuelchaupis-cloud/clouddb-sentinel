"""
test_security.py — CloudDB Sentinel (Fase 5 Enterprise)
=========================================================
Suite de pruebas unitarias y de integración para el motor de auditoría de seguridad
y generador de certificados de cumplimiento ISO 27001 / CIS Benchmarks.
"""

import json
from unittest.mock import MagicMock

import pytest

from src.security.auditor import (
    DatabaseSecurityAuditor,
    SecurityAuditResult,
)


@pytest.fixture
def auditor(tmp_path):
    """Fixture que proporciona un auditor con directorio temporal de certificados."""
    certs_dir = tmp_path / "security_certs"
    return DatabaseSecurityAuditor(certificates_dir=certs_dir)


def test_ssl_enforcement_positive(auditor):
    """Valida que una conexión con sslmode=require o verify-full pase la auditoría SSL."""
    conn_params = {
        "host": "db.cloud.internal",
        "port": 5432,
        "database": "prod_db",
        "user": "app_user",
        "password": "StrongSecret2026!#",
        "sslmode": "verify-full",
    }
    finding = auditor.audit_ssl_enforcement("postgres", conn_params)
    assert finding.passed is True
    assert finding.severity == "PASSED"
    assert "SSL/TLS" in finding.title
    assert "ISO 27001" in finding.iso_control


def test_ssl_enforcement_negative(auditor):
    """Valida que una conexión sin SSL genere un hallazgo CRITICAL."""
    conn_params = {
        "host": "127.0.0.1",
        "port": 5432,
        "database": "prod_db",
        "user": "app_user",
        "password": "StrongSecret2026!#",
        "sslmode": "disable",
    }
    finding = auditor.audit_ssl_enforcement("postgres", conn_params)
    assert finding.passed is False
    assert finding.severity == "CRITICAL"
    assert "Deshabilitado" in finding.title or "Inactivo" in finding.title


def test_weak_password_detection(auditor):
    """Valida la detección de contraseñas por defecto o conocidas."""
    # Caso 1: Contraseña por defecto conocida
    conn_params_1 = {"user": "admin_cloud", "password": "SecureCloudPass2026!", "database": "prod_db"}
    finding_1 = auditor.audit_weak_passwords(conn_params_1)
    assert finding_1.passed is False
    assert finding_1.severity == "CRITICAL"

    # Caso 2: Contraseña corta e idéntica al usuario
    conn_params_2 = {"user": "postgres", "password": "postgres", "database": "postgres"}
    finding_2 = auditor.audit_weak_passwords(conn_params_2)
    assert finding_2.passed is False
    assert any("idéntica" in issue for issue in finding_2.details["issues"])


def test_strong_password_passed(auditor):
    """Valida que una contraseña compleja y criptográfica supere la auditoría."""
    conn_params = {
        "user": "billing_service_user",
        "password": "K9#m$X9v!Lq2@zP8&wE5",
        "database": "billing_prod",
    }
    finding = auditor.audit_weak_passwords(conn_params)
    assert finding.passed is True
    assert finding.severity == "PASSED"


def test_superuser_audit(auditor):
    """Valida la detección de cuentas de servicio operando como superusuario."""
    # Cuenta admin/root
    conn_root = {"user": "root", "password": "StrongPassword2026!#"}
    finding_root = auditor.audit_least_privilege("mysql", conn_root)
    assert finding_root.passed is False
    assert finding_root.severity == "HIGH"

    # Cuenta de servicio estándar
    conn_service = {"user": "sentinel_collector", "password": "StrongPassword2026!#"}
    finding_service = auditor.audit_least_privilege("postgres", conn_service)
    assert finding_service.passed is True
    assert finding_service.severity == "PASSED"


def test_public_schema_permissions_mock(auditor):
    """Valida la verificación de permisos en el schema public de PostgreSQL."""
    # Mock de conexión con permiso de creación revocado (seguro)
    mock_conn_safe = MagicMock()
    mock_cursor_safe = MagicMock()
    mock_cursor_safe.fetchone.return_value = [False]  # has_schema_privilege = False
    mock_conn_safe.cursor.return_value.__enter__.return_value = mock_cursor_safe

    finding_safe = auditor.audit_public_schema_permissions("postgres", mock_conn_safe)
    assert finding_safe.passed is True
    assert finding_safe.severity == "PASSED"

    # Mock de conexión con permiso de creación abierto (inseguro)
    mock_conn_vuln = MagicMock()
    mock_cursor_vuln = MagicMock()
    mock_cursor_vuln.fetchone.return_value = [True]  # has_schema_privilege = True
    mock_conn_vuln.cursor.return_value.__enter__.return_value = mock_cursor_vuln

    finding_vuln = auditor.audit_public_schema_permissions("postgres", mock_conn_vuln)
    assert finding_vuln.passed is False
    assert finding_vuln.severity == "HIGH"


def test_compliance_score_and_certificate(auditor, tmp_path):
    """Valida el cálculo de score y la emisión formal del certificado JSON."""
    db_config = {
        "id": "cliente-a-pg",
        "type": "postgres",
        "host": "localhost",
        "port": 5432,
        "database": "cliente_a_prod",
        "sslmode": "require",
        "credentials": {
            "username": "app_crm_agent",
            "password": "K9#m$X9v!Lq2@zP8&wE5",
        },
        "tags": {
            "environment": "production",
        }
    }

    result = auditor.audit_database(db_config)

    assert isinstance(result, SecurityAuditResult)
    assert result.db_id == "cliente-a-pg"
    assert result.compliance_score >= 90.0
    assert result.overall_status == "COMPLIANT"
    assert result.total_checks == 4
    assert result.passed_checks == 4

    # Verificar que el certificado JSON se guardó en disco
    certs = list(auditor.certificates_dir.glob("SEC_CERT_cliente-a-pg_*.json"))
    assert len(certs) == 1

    with open(certs[0], "r", encoding="utf-8") as f:
        cert_data = json.load(f)

    assert cert_data["evaluation_summary"]["database_id"] == "cliente-a-pg"
    assert cert_data["evaluation_summary"]["status"] == "COMPLIANT"
    assert len(cert_data["findings_details"]) == 4
