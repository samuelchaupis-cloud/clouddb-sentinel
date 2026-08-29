"""
test_alerting.py — Pruebas Unitarias para el Módulo de Alertas
================================================================
Valida la creación de tickets ITSM, prioridad P1-P4 y registro SQLite.
"""

from src.alerting.notifier import (
    Alert,
    AlertManager,
    _get_ticket_priority,
)


def test_ticket_priority_mapping():
    """Valida la asignación correcta de prioridad ITIL P1 a P4 según la categoría y nivel."""
    # CRITICAL en Salud o Backup debe ser P1
    assert _get_ticket_priority("CRITICAL", "HEALTH_CRITICAL") == "P1"
    assert _get_ticket_priority("CRITICAL", "BACKUP_FAILURE") == "P1"

    # WARNING debe ser P2 o P3
    assert _get_ticket_priority("WARNING", "CAPACITY_ALERT") in ("P2", "P3")

    # INFO debe ser P4
    assert _get_ticket_priority("INFO", "ROUTINE_CHECK") == "P4"


def test_create_itsm_ticket():
    """Valida que AlertManager genere un ticket formal con identificador correlativo."""
    manager = AlertManager()
    alert = Alert(
        db_id="cliente-a-pg",
        level="CRITICAL",
        category="BACKUP_FAILURE",
        message="Fallo en respaldo diario programado: RPO excedido.",
        value=28.0,
        threshold=24.0,
    )

    ticket = manager.create_itsm_ticket(alert)

    assert isinstance(ticket, dict)
    assert "ticket_id" in ticket
    assert ticket["priority"] == "P1"
    assert ticket["db_id"] == "cliente-a-pg"
    assert ticket["status"] == "OPEN"
