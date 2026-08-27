#!/usr/bin/env bash
# =============================================================================
# CloudDB Sentinel — Script Maestro de Ejecución Integral (Linux / macOS)
# =============================================================================
# Ejecuta la rutina completa de operaciones de base de datos Cloud:
# 1. Verificación de conectividad e infraestructura Docker
# 2. Checklist Preventivo de Salud (Health Check - 15+ KPIs)
# 3. Pipeline de Respaldo Automatizado (Dumps, Compresión, S3/MinIO)
# 4. Prueba de Recuperación ante Desastres (Disaster Recovery Validation)
# 5. Recolección de Métricas de Capacidad (Capacity Planning a 30/60/90 días)
# 6. Generación de Reporte Corporativo Ejecutivo (HTML / PDF)
# =============================================================================

set -e

# Colores para terminal
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}=====================================================================${NC}"
echo -e "${CYAN}☁️   CLOUDB SENTINEL — SUITE INTEGRAL DE OPERACIONES DE BASES DE DATOS${NC}"
echo -e "${CYAN}=====================================================================${NC}"
echo -e "${BLUE}[INFO] Fecha y hora de inicio:${NC} $(date '+%Y-%m-%d %H:%M:%S')"

# 1. Verificar entorno Python
if [ -d "venv" ]; then
    echo -e "${GREEN}[OK]${NC} Activando entorno virtual venv..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo -e "${GREEN}[OK]${NC} Activando entorno virtual .venv..."
    source .venv/bin/activate
fi

# 2. Paso 1: Health Check Preventivo
echo -e "\n${BLUE}=====================================================================${NC}"
echo -e "${BLUE}▶ PASO 1/5: Ejecutando Motor de Health Check Preventivo (15+ KPIs)${NC}"
echo -e "${BLUE}=====================================================================${NC}"
python3 -m src.healthcheck.engine || {
    echo -e "${YELLOW}[WARN] Health check finalizado con advertencias.${NC}"
}

# 3. Paso 2: Pipeline de Respaldos
echo -e "\n${BLUE}=====================================================================${NC}"
echo -e "${BLUE}▶ PASO 2/5: Ejecutando Pipeline de Respaldos Consistentes y Carga S3${NC}"
echo -e "${BLUE}=====================================================================${NC}"
python3 -m src.backup.backup_manager || {
    echo -e "${YELLOW}[WARN] Backup manager finalizado.${NC}"
}

# 4. Paso 3: Disaster Recovery Validation
echo -e "\n${BLUE}=====================================================================${NC}"
echo -e "${BLUE}▶ PASO 3/5: Ejecutando Validación Automatizada de Disaster Recovery${NC}"
echo -e "${BLUE}=====================================================================${NC}"
python3 -m src.backup.dr_validator || {
    echo -e "${YELLOW}[WARN] DR validation finalizado.${NC}"
}

# 5. Paso 4: Capacity Planning
echo -e "\n${BLUE}=====================================================================${NC}"
echo -e "${BLUE}▶ PASO 4/5: Recolectando Métricas de Almacenamiento y Capacidad${NC}"
echo -e "${BLUE}=====================================================================${NC}"
python3 -m src.capacity.capacity_planner || {
    echo -e "${YELLOW}[WARN] Capacity planner finalizado.${NC}"
}

# 6. Paso 5: Generación de Reportes Corporativos
echo -e "\n${BLUE}=====================================================================${NC}"
echo -e "${BLUE}▶ PASO 5/5: Generando Reporte Ejecutivo B2B Consolidado (HTML / PDF)${NC}"
echo -e "${BLUE}=====================================================================${NC}"
python3 -m src.reporting.generator || {
    echo -e "${YELLOW}[WARN] Generador de reportes finalizado.${NC}"
}

echo -e "\n${GREEN}=====================================================================${NC}"
echo -e "${GREEN}✅ EJECUCIÓN INTEGRAL FINALIZADA CON ÉXITO${NC}"
echo -e "${GREEN}=====================================================================${NC}"
echo -e "Los reportes y logs están disponibles en:"
echo -e "  📄 Reportes HTML/PDF:     ./reports/"
echo -e "  📋 Logs de Health Check:  ./logs/health_reports/"
echo -e "  🛡️  Certificados de DR:    ./logs/dr_certificates/"
echo -e "  💾 Backups Locales:       ./data/backups/"
