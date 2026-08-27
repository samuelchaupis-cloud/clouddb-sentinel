# PROCEDIMIENTO OPERATIVO ESTÁNDAR (SOP)
## Código: SOP-DBA-001 | Versión: 1.0

```text
===============================================================================
EMPRESA:           Servicios Cloud & Telecomunicaciones B2B
ÁREA:              Operaciones Cloud / Gestión de Bases de Datos
TÍTULO:            Rutina Preventiva Diaria de Health Check de Bases de Datos
RESPONSABLE:       Practicante Pre de Servicios Cloud / Especialista Cloud
APROBADO POR:      Jefe de Operaciones de Infraestructura Cloud
FECHA VIGENCIA:    2026-08-01
===============================================================================
```

---

## 1. OBJETIVO
Establecer el procedimiento estándar y sistemático para la inspección preventiva diaria del estado de salud (*Health Check*) de las bases de datos contratadas por clientes B2B (PostgreSQL y MySQL), detectando anomalías antes de que impacten la disponibilidad o el rendimiento de los servicios en producción.

---

## 2. ALCANCE
Aplica a todas las instancias de bases de datos relacionales alojadas en nubes públicas (AWS, Azure, GCP), nube privada corporativa o infraestructura híbrida bajo contrato de administración delegada de Servicios Cloud.

---

## 3. HORARIOS Y FRECUENCIA DE EJECUCIÓN
* **Turno Mañana:** 07:30 AM (Verificación de inicio de operaciones comerciales).
* **Turno Tarde:** 06:30 PM (Verificación de cierre y preparación de procesos batch nocturnos).
* **Frecuencia:** Lunes a Domingo (365 días del año).

---

## 4. RESPONSABILIDADES (MATRIZ RACI)
* **Practicante Pre de Servicios Cloud (Responsable / R):** Ejecuta la herramienta `CloudDB Sentinel`, revisa los indicadores, documenta anomalías y genera el reporte del turno.
* **Especialista de Servicios Cloud (Accountable / A):** Valida los hallazgos críticos, aprueba acciones correctivas de emergencia y asesora al practicante.
* **Jefe de Servicios Cloud (Consulted / C):** Es informado de incidentes mayores o degradaciones de SLA.
* **Service Desk / NOC (Informed / I):** Recibe el resumen de estado del turno.

---

## 5. PROCEDIMIENTO PASO A PASO

### Paso 1: Verificación de Conectividad y Acceso
1. Iniciar sesión en la estación de trabajo de operaciones o servidor bastion con credenciales corporativas.
2. Comprobar conectividad VPN con los entornos de los clientes B2B.

### Paso 2: Ejecución del Checklist Automatizado
1. Abrir la terminal de operaciones y posicionarse en el directorio del proyecto:
   ```bash
   cd /opt/clouddb-sentinel   # O ruta local en Windows
   ```
2. Ejecutar el orquestador de Health Check:
   ```bash
   python -m src.healthcheck.engine
   ```

### Paso 3: Revisión de los 15 Indicadores Clave de Salud (KPIs)

| N° | Indicador | Umbral Normal (Verde) | Umbral Alerta (Amarillo) | Acción en caso de Fallo Crítico (Rojo) |
|:---|:---|:---|:---|:---|
| **1** | **Conectividad & Latencia** | < 50 ms | 50 - 200 ms | Si timeout (>500ms), verificar servicio del host y enrutamiento de red. |
| **2** | **Conexiones Activas** | < 70% del máx. | 70% - 85% | Si >90%, consultar `pg_stat_activity` / `PROCESSLIST` por fugas de pool. |
| **3** | **Buffer Cache Hit Ratio** | > 99.0% | 95.0% - 98.9% | Si <95%, escalamiento a Especialista para evaluar incremento de RAM / buffers. |
| **4** | **Bloqueos (Waiting Locks)** | 0 locks en espera | 1 - 2 locks | Si >3 transacciones bloqueadas, identificar la sesión bloqueadora (*PID blocker*). |
| **5** | **Consultas Lentas** | 0 consultas >30s | 1 - 2 consultas | Identificar consulta, notificar al cliente o cancelar si satura CPU al 100%. |
| **6** | **Dead Tuples (PostgreSQL)** | < 1,000 tuplas | 1,000 - 10,000 | Programar `VACUUM ANALYZE` en ventana de bajo tráfico. |
| **7** | **Índices sin Uso** | 0 índices >50MB | 1 - 3 índices | Documentar en informe para propuesta de optimización de disco. |
| **8** | **Espacio en Disco / LUN** | < 75% uso | 75% - 85% | Si >90%, ejecutar purga de WAL/binlogs y solicitar ampliación de volumen. |
| **9** | **Lag de Replicación** | 0 bytes / 0 seg | < 60 segundos | Si >300s, revisar ancho de banda de enlace y estado del servicio de réplica. |
| **10**| **Archivos Temporales** | 0 en disco | < 100 MB | Si >500MB, sugiere `work_mem` insuficiente para ordenamientos. |
| **11**| **Estadísticas de Checkpoint**| Checkpoints programados | Checkpoints forzados | Revisar `max_wal_size` y `checkpoint_completion_target`. |
| **12**| **Estado de Tablas (MySQL)** | 0 tablas corruptas | 0 | Ejecutar `CHECK TABLE` si hay inconsistencias. |
| **13**| **Antigüedad del Backup** | < 24 horas | 24 - 30 horas | Si >30h, ejecutar de inmediato el SOP-DBA-002 de Respaldos. |
| **14**| **Proyección de Capacidad** | > 30 días restantes | 15 - 30 días | Alertar al cliente de necesidad de expansión de storage. |
| **15**| **Logs de Error** | 0 errores FATAL | Errores de sintaxis aislados | Extraer traza y adjuntar al ticket de turno. |

---

### Paso 4: Criterios de Escalamiento Inmediato
Se debe notificar de inmediato vía llamada / Telegram al **Especialista de Servicios Cloud** si:
* La base de datos no responde a la conexión (`CRITICAL: Connection Timeout`).
* El uso de almacenamiento supera el **88%**.
* Existen transacciones bloqueadas por más de **5 minutos**.
* El último backup validado tiene más de **26 horas** de antigüedad.

---

### Paso 5: Generación y Archivado del Reporte de Turno
1. El reporte consolidado se genera automáticamente en `reports/CloudDB_Sentinel_Report_YYYY-MM-DD.html`.
2. Archivar el archivo en el repositorio de documentación del cliente y registrar el resumen en la bitácora de turno del sistema de tickets.
