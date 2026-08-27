# =============================================================================
# CloudDB Sentinel — Script Maestro de Ejecución Integral (Windows PowerShell)
# =============================================================================
# Ejecuta la rutina completa de operaciones de base de datos Cloud:
# 1. Verificación de entorno y dependencias
# 2. Checklist Preventivo de Salud (Health Check - 15+ KPIs)
# 3. Pipeline de Respaldo Automatizado (Dumps, Compresión, S3/MinIO)
# 4. Prueba de Recuperación ante Desastres (Disaster Recovery Validation)
# 5. Recolección de Métricas de Capacidad (Capacity Planning a 30/60/90 días)
# 6. Generación de Reporte Corporativo Ejecutivo (HTML / PDF)
# =============================================================================

$ErrorActionPreference = "Continue"

Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "☁️   CLOUDB SENTINEL — SUITE INTEGRAL DE OPERACIONES DE BASES DE DATOS" -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "[INFO] Fecha y hora de inicio: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray

# 1. Verificar entorno virtual de Python
if (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "[OK] Activando entorno virtual venv..." -ForegroundColor Green
    & "venv\Scripts\Activate.ps1"
} elseif (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "[OK] Activando entorno virtual .venv..." -ForegroundColor Green
    & ".venv\Scripts\Activate.ps1"
}

# 2. Paso 1: Health Check Preventivo
Write-Host "`n=====================================================================" -ForegroundColor Yellow
Write-Host "▶ PASO 1/5: Ejecutando Motor de Health Check Preventivo (15+ KPIs)" -ForegroundColor Yellow
Write-Host "=====================================================================" -ForegroundColor Yellow
python -m src.healthcheck.engine

# 3. Paso 2: Pipeline de Respaldos
Write-Host "`n=====================================================================" -ForegroundColor Yellow
Write-Host "▶ PASO 2/5: Ejecutando Pipeline de Respaldos Consistentes y Carga S3" -ForegroundColor Yellow
Write-Host "=====================================================================" -ForegroundColor Yellow
python -m src.backup.backup_manager

# 4. Paso 3: Disaster Recovery Validation
Write-Host "`n=====================================================================" -ForegroundColor Yellow
Write-Host "▶ PASO 3/5: Ejecutando Validación Automatizada de Disaster Recovery" -ForegroundColor Yellow
Write-Host "=====================================================================" -ForegroundColor Yellow
python -m src.backup.dr_validator

# 5. Paso 4: Capacity Planning
Write-Host "`n=====================================================================" -ForegroundColor Yellow
Write-Host "▶ PASO 4/5: Recolectando Métricas de Almacenamiento y Capacidad" -ForegroundColor Yellow
Write-Host "=====================================================================" -ForegroundColor Yellow
python -m src.capacity.capacity_planner

# 6. Paso 5: Generación de Reportes Corporativos
Write-Host "`n=====================================================================" -ForegroundColor Yellow
Write-Host "▶ PASO 5/5: Generando Reporte Ejecutivo B2B Consolidado (HTML / PDF)" -ForegroundColor Yellow
Write-Host "=====================================================================" -ForegroundColor Yellow
python -m src.reporting.generator

Write-Host "`n=====================================================================" -ForegroundColor Green
Write-Host "✅ EJECUCIÓN INTEGRAL FINALIZADA CON ÉXITO" -ForegroundColor Green
Write-Host "=====================================================================" -ForegroundColor Green
Write-Host "Los reportes y logs están disponibles en:" -ForegroundColor White
Write-Host "  📄 Reportes HTML/PDF:     ./reports/" -ForegroundColor White
Write-Host "  📋 Logs de Health Check:  ./logs/health_reports/" -ForegroundColor White
Write-Host "  🛡️  Certificados de DR:    ./logs/dr_certificates/" -ForegroundColor White
Write-Host "  💾 Backups Locales:       ./data/backups/" -ForegroundColor White
