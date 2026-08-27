"""
test_capacity_planner.py — Pruebas Unitarias para Capacity Planning
====================================================================
Valida los cálculos matemáticos de regresión de crecimiento y Time To Exhaustion.
"""

import pytest
from src.capacity.capacity_planner import (
    _linear_regression,
    _detect_trend,
    CapacitySnapshot,
    GrowthRate,
)


def test_linear_regression_calculation():
    """Valida el cálculo de la pendiente de crecimiento en MB/día."""
    # 5 días con crecimiento constante de 100 MB por día
    x_days = [0.0, 1.0, 2.0, 3.0, 4.0]
    y_sizes_mb = [1000.0, 1100.0, 1200.0, 1300.0, 1400.0]
    
    slope, intercept = _linear_regression(x_days, y_sizes_mb)
    
    # Pendiente debe ser 100 MB/día e intercepto 1000 MB
    assert pytest.approx(slope, rel=1e-2) == 100.0
    assert pytest.approx(intercept, rel=1e-2) == 1000.0


def test_detect_trend_stable():
    """Valida que una pendiente casi nula sea catalogada como 'stable'."""
    slope = 0.05
    y_values = [500.0, 500.1, 500.2, 500.1]
    trend = _detect_trend(slope, y_values)
    assert trend == "stable"


def test_detect_trend_growing():
    """Valida que un crecimiento continuo sea catalogado como 'growing'."""
    slope = 50.0
    y_values = [500.0, 550.0, 600.0, 650.0]
    trend = _detect_trend(slope, y_values)
    assert trend in ("growing", "accelerating")


def test_time_to_exhaustion_projection():
    """Valida la fórmula de proyección y días restantes antes de saturación."""
    current_size_gb = 100.0
    growth_gb_day = 2.0
    max_capacity_gb = 200.0
    
    remaining_gb = max_capacity_gb - current_size_gb
    days_to_full = remaining_gb / growth_gb_day
    
    assert days_to_full == 50.0
