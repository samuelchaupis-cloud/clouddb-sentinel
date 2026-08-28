# ☁️ CloudDB Sentinel
### Sistema Integral de Monitoreo, Health Check, Respaldo Automatizado y Reportes de Capacidad para Bases de Datos Cloud B2B

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Database Support](https://img.shields.io/badge/databases-PostgreSQL%2016%20%7C%20MySQL%208.0-336791.svg)](https://www.postgresql.org/)
[![Storage](https://img.shields.io/badge/storage-AWS%20S3%20%7C%20MinIO-FF9900.svg)](https://min.io/)
[![Observability](https://img.shields.io/badge/observability-Prometheus%20%7C%20Grafana%20%7C%20Zabbix-F46800.svg)](https://grafana.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-Production--Ready-brightgreen.svg)]()

```text
  ____ _                 _ ____  ____    ____             _   _            _ 
 / ___| | ___  _   _  __| |  _ \| __ )  / ___|  ___ _ __ | |_(_)_ __   ___| |
| |   | |/ _ \| | | |/ _` | | | |  _ \  \___ \ / _ \ '_ \| __| | '_ \ / _ \ |
| |___| | (_) | |_| | (_| | |_| | |_) |  ___) |  __/ | | | |_| | | | |  __/ |
 \____|_|\___/ \__,_|\__,_|____/|____/  |____/ \___|_| |_|\__|_|_| |_|\___|_|
   Autonomous Cloud Database Operations & Zero-Trust Disaster Recovery Engine
```

---

## 📋 Descripción del Proyecto

**CloudDB Sentinel** es una plataforma integral diseñada para la gestión operativa, preventiva y de continuidad de negocio de bases de datos empresariales en entornos Cloud y On-Premise. 

Desarrollada específicamente bajo los estándares operativos de proveedores líderes de **Servicios Cloud y Telecomunicaciones B2B**, la plataforma resuelve la necesidad crítica de garantizar la salud, los respaldos verificados, la capacidad de almacenamiento y la generación de reportes ejecutivos periódicos para múltiples clientes y bases de datos heterogéneas.

---

## 🏗️ Arquitectura de la Solución

```
+-----------------------------------------------------------------------------------+
|                           CLOUDB SENTINEL ECOSYSTEM                              |
+-----------------------------------------------------------------------------------+
                                        │
        ┌───────────────────────────────┼───────────────────────────────┐
        ▼                               ▼                               ▼
┌───────────────────┐           ┌───────────────────┐           ┌───────────────────┐
│  POSTGRESQL (16)  │           │   MYSQL (8.0)     │           │ HOST METRICS (OS) │
│  (Cliente A Core) │           │ (Cliente B Fact.) │           │ (CPU, RAM, Disco) │
└───────────────────┘           └───────────────────┘           └───────────────────┘
        │                               │                               │
        └───────────────────────────────┼───────────────────────────────┘
                                        │
                                        ▼
                    ┌───────────────────────────────────────┐
                    │      CORE ENGINE (Python / Bash)      │
                    ├───────────────────────────────────────┤
                    │  1. healthcheck.engine (15+ KPIs)     │
                    │  2. backup_manager (S3/MinIO/Zstd)    │
                    │  3. dr_validator (Zero-Trust Restore) │
                    │  4. capacity_planner (30/60/90 días)  │
                    │  5. reporting.generator (HTML/PDF)    │
                    │  6. alerting.notifier (Telegram/ITSM) │
                    └───────────────────────────────────────┘
                                        │
        ┌───────────────────────────────┼───────────────────────────────┐
        ▼                               ▼                               ▼
┌───────────────────┐           ┌───────────────────┐           ┌───────────────────┐
│   OBSERVABILIDAD  │           │   ALMACENAMIENTO  │           │    ITSM & ALERTS  │
│ Prometheus/Grafana│           │  AWS S3 / MinIO   │           │ Telegram Bot /    │
│ Postgres Exporter │           │ SHA-256 & Retención│          │ Webhook Tickets   │
└───────────────────┘           └───────────────────┘           └───────────────────┘
```

---

## 🚀 Módulos del Sistema

| Módulo | Componente | Descripción y Valor Operativo |
|:---|:---|:---|
| 🩺 **Health Check Engine** | `src/healthcheck/` | Inspección preventiva de +15 KPIs (conexiones activas, aciertos de caché >98%, bloqueos/locks, consultas lentas, dead tuples, bloat y replicación). |
| 💾 **Backup Lifecycle Manager** | `src/backup/backup_manager.py` | Pipeline de dumps consistentes con compresión `zstd`/`gzip`, cifrado, subida a MinIO/AWS S3 y purga automática por retención. |
| 🛡️ **Zero-Trust DR Validator** | `src/backup/dr_validator.py` | **Diferenciador clave:** Prueba de restauración automatizada en contenedor efímero, validación de integridad SHA-256 y emisión de Certificado Formal de DR. |
| 📈 **Capacity Planner** | `src/capacity/capacity_planner.py` | Registro histórico en SQLite, cálculo de tasa de crecimiento diaria (MB/día) y estimación de *Time to Exhaustion* (días hasta llenar el disco) a 30, 60 y 90 días. |
| 📊 **Executive Reporter** | `src/reporting/` | Generación de reportes corporativos visuales en HTML y PDF con semáforo de estado (🟢 Saludable, 🟡 Degradado, 🔴 Crítico) y checklist operativo. |
| 🔔 **Multi-Channel Alerting** | `src/alerting/` | Despacho de notificaciones a Telegram y emisión de tickets estructurados compatibles con ServiceNow / Jira Service Management. |

---

## 📁 Estructura del Repositorio

```text
├── docker-compose.yml             # Stack completo: PostgreSQL, MySQL, MinIO, Prometheus, Grafana
├── .env.example                   # Plantilla de variables de entorno seguras
├── requirements.txt               # Dependencias Python fijadas
├── config/
│   ├── databases.yaml             # Catálogo de bases de datos e inventario B2B
│   ├── alert_rules.yaml           # Matriz de umbrales preventivos y críticos
│   └── prometheus.yml             # Scrape configs para métricas de DBs
├── src/
│   ├── healthcheck/
│   │   ├── engine.py              # Orquestador del checklist de salud
│   │   ├── checks_postgres.py     # 15+ KPIs específicos de PostgreSQL
│   │   └── checks_mysql.py        # Métricas específicas de MySQL
│   ├── backup/
│   │   ├── backup_manager.py      # Backups lógicos/físicos y carga S3
│   │   └── dr_validator.py        # Validación de restauración y certificados DR
│   ├── capacity/
│   │   └── capacity_planner.py    # Proyección lineal y análisis de saturación
│   ├── reporting/
│   │   ├── generator.py           # Renderizador HTML/PDF y checklist
│   │   └── template.html          # Plantilla corporativa con diseño profesional
│   └── alerting/
│       └── notifier.py            # Notificador multi-canal y tickets ITSM
├── docs/
│   ├── SOP_HEALTH_CHECK.md        # Procedimiento Operativo Estándar: Rutina Diaria
│   ├── SOP_BACKUP_RESTORE.md      # Procedimiento Operativo Estándar: Gestión de DR
│   ├── CAPACITY_MANAGEMENT.md     # Política de Gestión de Capacidad y SLAs
│   └── INTERVIEW_GUIDE.md         # Guía de Entrevista: Metodología STAR y Guión Técnico
└── scripts/
    ├── setup_demo_data.sql        # Poblador de datos de prueba empresariales B2B
    ├── run_all.sh                 # Ejecutor integral maestro para Linux/macOS
    └── run_all.ps1                # Ejecutor integral maestro para Windows PowerShell
```

---

## ⚡ Guía de Inicio Rápido

### 1. Prerrequisitos
- **Docker & Docker Compose** (opcional pero recomendado para simular todo el stack)
- **Python 3.10 o superior**
- **Git**

### 2. Instalación y Configuración

```bash
# 1. Clonar el repositorio
git clone https://github.com/samuelchaupis-cloud/clouddb-sentinel.git
cd clouddb-sentinel

# 2. Configurar variables de entorno
cp .env.example .env

# 3. Crear entorno virtual e instalar dependencias
python -m venv venv
# En Linux/macOS:
source venv/bin/activate
# En Windows PowerShell:
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt

# 4. Iniciar la infraestructura de prueba con Docker Compose
docker compose up -d
```

### 3. Ejecución de la Suite Completa

**En Linux / macOS:**
```bash
chmod +x scripts/run_all.sh
./scripts/run_all.sh
```

**En Windows PowerShell:**
```powershell
.\scripts\run_all.ps1
```

---

## 🌐 Accesos y Servicios del Ecosistema

Una vez levantada la infraestructura, los servicios se encuentran disponibles en:

| Servicio | URL / Endpoint | Credenciales por Defecto | Propósito |
|:---|:---|:---|:---|
| 📈 **Grafana Dashboard** | `http://localhost:13000` | `admin` / `AdminGrafana2026!` | Observabilidad en tiempo real y métricas de rendimiento (SLA > 98%). |
| 🪣 **MinIO S3 Console** | `http://localhost:9001` | `cloud_backup_admin` / `MinioBackupPass2026!` | Almacenamiento de objetos S3 y explorador de respaldos. |
| 📊 **Prometheus Server** | `http://localhost:9090` | Acceso directo sin autenticación | Recolección de telemetría de PostgreSQL Exporter. |
| 📄 **Portal Ejecutivo HTML** | `reports/CloudDB_Sentinel_Report_YYYY-MM-DD.html` | Archivo estático autocontenido | Portal interactivo SaaS con 27 KPIs, Donut SVG y filtros. |

---

## 💻 Ejecución Modular Independiente

Cada módulo puede ejecutarse de manera desacoplada según la necesidad operativa:

```bash
# 1. Ejecutar únicamente el Health Check preventivo (27 KPIs)
python -m src.healthcheck.engine

# 2. Ejecutar el Pipeline de Respaldos hacia MinIO / AWS S3
python -m src.backup.backup_manager

# 3. Ejecutar la Validación de Restauración Zero-Trust (Disaster Recovery Test)
python -m src.backup.dr_validator

# 4. Recopilar métricas de capacidad y proyectar crecimiento
python -m src.capacity.capacity_planner

# 5. Generar el Reporte Corporativo Ejecutivo HTML / PDF
python -m src.reporting.generator

# 6. Simular despacho de alertas críticas P1 hacia Telegram e ITSM
python scripts/test_telegram_alert.py --simulate --level CRITICAL --category DATABASE_DOWN_P1
```

---

## 📄 Procedimientos Operativos Estándar (SOPs B2B)

El proyecto incluye documentación técnica de nivel corporativo para auditar y operar en centros de operaciones de red (NOC) y centros de operaciones de seguridad (SOC):
- [SOP-DBA-001: Rutina Diaria de Health Check](docs/SOP_HEALTH_CHECK.md)
- [SOP-DBA-002: Gestión de Respaldos y Recuperación ante Desastres](docs/SOP_BACKUP_RESTORE.md)
- [POL-CAP-001: Política de Gestión de Capacidad y SLAs](docs/CAPACITY_MANAGEMENT.md)
- [GUÍA DE ENTREVISTA: Metodología STAR y Respuestas Técnicas](docs/INTERVIEW_GUIDE.md)

---

## 📜 Licencia

Distribuido bajo la Licencia MIT. Consulte `LICENSE` para más información.
