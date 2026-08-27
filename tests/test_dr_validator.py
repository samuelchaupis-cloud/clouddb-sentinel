"""
test_dr_validator.py — Pruebas Unitarias para Disaster Recovery Validator
==========================================================================
Valida la verificación criptográfica SHA-256 y estructura de certificados DR.
"""

import hashlib
import tempfile
from pathlib import Path
import pytest

from src.backup.dr_validator import (
    verify_file_checksum,
    DRValidationResult,
    DisasterRecoveryValidator,
)


def test_verify_file_checksum_valid():
    """Valida que un archivo con su checksum SHA-256 exacto pase la verificación."""
    content = b"CloudDB Sentinel Backup Mock Data Content 2026"
    expected_hash = hashlib.sha256(content).hexdigest()
    
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        assert verify_file_checksum(tmp_path, expected_hash) is True
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_verify_file_checksum_corrupted():
    """Valida que un archivo modificado o con checksum incorrecto sea rechazado."""
    content = b"Original Backup Content"
    wrong_hash = "0000000000000000000000000000000000000000000000000000000000000000"
    
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        assert verify_file_checksum(tmp_path, wrong_hash) is False
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_dr_validation_result_structure():
    """Valida que el resultado de DR contenga los campos requeridos para auditoría."""
    result = DRValidationResult(
        backup_id=42,
        db_id="cliente-a-pg",
        timestamp="2026-08-26T23:00:00Z",
        success=True,
        checksum_verified=True,
        tables_count=12,
        total_rows_verified=4500,
        duration_seconds=3.25,
    )
    
    res_dict = result.to_dict()
    assert res_dict["backup_id"] == 42
    assert res_dict["db_id"] == "cliente-a-pg"
    assert res_dict["success"] is True
    assert res_dict["tables_count"] == 12
