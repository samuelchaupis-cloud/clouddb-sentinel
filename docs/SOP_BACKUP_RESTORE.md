# PROCEDIMIENTO OPERATIVO ESTÁNDAR (SOP)
## Código: SOP-DBA-002 | Versión: 1.0

```text
===============================================================================
EMPRESA:           Servicios Cloud & Telecomunicaciones B2B
ÁREA:              Operaciones Cloud / Continuidad del Negocio (DRP)
TÍTULO:            Gestión de Respaldos y Recuperación ante Desastres (DR)
RESPONSABLE:       Practicante Pre de Servicios Cloud / Especialista Cloud
APROBADO POR:      Jefe de Infraestructura & Seguridad de la Información
FECHA VIGENCIA:    2026-08-01
===============================================================================
```

---

## 1. OBJETIVO
Definir las directrices para la ejecución, compresión, cifrado, almacenamiento en la nube y **validación obligatoria de restauración** (*Zero-Trust Restore*) de los respaldos de bases de datos para garantizar el cumplimiento de los acuerdos de nivel de servicio (**RPO** y **RTO**).

---

## 2. POLÍTICA DE RESPALDOS B2B (REGLA 3-2-1)
* **3 Copias de datos:** 1 en producción + 1 copia local de contingencia rápida + 1 copia en Cloud Storage (AWS S3 / MinIO).
* **2 Medios diferentes:** Almacenamiento SSD en host local y almacenamiento de objetos distribuido.
* **1 Copia fuera del sitio:** Bucket S3 en región secundaria con inmutabilidad (*Object Lock* contra ransomware).

---

## 3. OBJETIVOS DE RECUPERACIÓN POR TIER DE CLIENTE

| Nivel de Servicio | RPO (Punto Máximo de Pérdida de Datos) | RTO (Tiempo Máximo de Restauración) | Frecuencia de Respaldo | Prueba DR Obligatoria |
|:---|:---|:---|:---|:---|
| **Tier-1 (Mission Critical)** | $\le$ 1 hora | $\le$ 2 horas | Diario Full + WAL/Binlogs continuo | Semanal automatizada |
| **Tier-2 (Business Critical)** | $\le$ 4 horas | $\le$ 4 horas | Diario Full | Quincenal automatizada |
| **Tier-3 (Standard)** | $\le$ 24 horas | $\le$ 8 horas | Diario Full | Mensual automatizada |

---

## 4. PROCEDIMIENTO DE EJECUCIÓN DE RESPALDOS

### 4.1. Ejecución Automatizada Diaria
Los respaldos se ejecutan automáticamente a las **01:00 AM UTC-5** mediante el scheduler:
```bash
python -m src.backup.backup_manager
```

### 4.2. Parámetros Técnicos por Motor
* **PostgreSQL:**
  - Formato Custom binario (`pg_dump -Fc -Z9`).
  - Compresión con algoritmo `zstandard` (alta tasa y velocidad ultra-rápida).
  - Cálculo de hash `SHA-256` inmediato y subida a MinIO/AWS S3.
* **MySQL:**
  - Dump transaccional consistente: `mysqldump --single-transaction --flush-logs --routines --triggers --events`.
  - Compresión `gzip`.

---

## 5. PROCEDIMIENTO DE VALIDACIÓN DE DISASTER RECOVERY (DR TEST)
> **Principio de Zero-Trust:** *"Un backup no existe hasta que ha sido restaurado y verificado con éxito."*

1. Ejecutar el motor de validación:
   ```bash
   python -m src.backup.dr_validator
   ```
2. **Ciclo de Validación Automatizado:**
   - Comprobación de integridad criptográfica (SHA-256 Checksum).
   - Levantamiento de instancia efímera de pruebas aislada.
   - Restauración física del backup en el entorno aislado.
   - Ejecución de consultas de validación de consistencia lógica:
     * Comprobación de catálogo de esquemas y tablas.
     * Conteo y muestreo de registros en tablas principales.
     * Verificación de claves primarias e integridad referencial.
   - Destrucción del entorno de pruebas.
   - Emisión del **Certificado Formal de Validación DR** en `logs/dr_certificates/`.

---

## 6. PROCEDIMIENTO DE RESTAURACIÓN DE EMERGENCIA ANTE DESASTRE

En caso de contingencia real o solicitud de restauración del cliente B2B:

```
[INCIDENTE REPORTADO]
        │
        ▼
1. Identificar el último Backup ID Validado en:
   data/backup_registry.db (status='SUCCESS', dr_validated=1)
        │
        ▼
2. Notificar al Especialista Cloud y al Cliente B2B el inicio de maniobra de DR.
        │
        ▼
3. Descargar el archivo cifrado desde el bucket S3:
   aws s3 cp s3://clouddb-backups-b2b/... /tmp/restore/
        │
        ▼
4. Validar el Checksum SHA-256 localmente antes de inyectar a producción.
        │
        ▼
5. Restaurar sobre la base de datos destino:
   PostgreSQL: pg_restore -h [HOST] -U [USER] -d [DB] --clean --if-exists [FILE]
   MySQL:      mysql -h [HOST] -u [USER] -p [DB] < [FILE]
        │
        ▼
6. Ejecutar el Health Check Preventivo (SOP-DBA-001) para certificar la salud post-restauración.
        │
        ▼
7. Registrar el tiempo total RTO alcanzado y cerrar ticket de soporte.
```
