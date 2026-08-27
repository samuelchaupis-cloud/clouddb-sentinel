# 🎯 GUÍA MAESTRA DE ENTREVISTA: PRACTICANTE PRE DE SERVICIOS CLOUD
## Cómo Defender tu Proyecto "CloudDB Sentinel" y Destacar sobre los demás postulantes

```text
===============================================================================
PUESTO:            Practicante Pre de Servicios Cloud (B2B Telecom & TI)
PROYECTO:          CloudDB Sentinel — Autonomous DB Operations & DR Engine
OBJETIVO:          Superar los filtros de RRHH y la Entrevista Técnica con el
                   Especialista de Servicios Cloud.
===============================================================================
```

---

## 📌 SECCIÓN 1: CÓMO COLOCAR ESTE PROYECTO EN TU CV

Incluye esta sección en tu CV en el apartado de **"Proyectos Destacados / Experiencia Práctica"**:

```text
PROYECTOS DESTACADOS
───────────────────────────────────────────────────────────────────────────────
CloudDB Sentinel — Sistema Automatizado de Monitoreo, Respaldo y Health Check Cloud
Tecnologías: Python, Bash, PostgreSQL 16, MySQL 8.0, Docker, Prometheus, Grafana, AWS S3/MinIO, Linux.

• Diseñé e implementé una plataforma integral para la operación rutinaria y preventiva de bases de datos
  multinube heterogéneas (PostgreSQL y MySQL), reduciendo el tiempo de inspección manual de 45 min a 2 min.
• Desarrollé un motor de Health Check de 15+ KPIs críticos (buffer cache hit ratio >98%, conexiones activas,
  bloqueos/deadlocks, consultas lentas, dead tuples y lag de replicación).
• Construí un pipeline de respaldos con compresión zstd/gzip, cifrado y subida a Cloud Storage (S3/MinIO),
  incorporando un motor de Disaster Recovery con validación automatizada de restauración (Zero-Trust Restore).
• Implementé un módulo de Capacity Planning con análisis de regresión para estimar tasa de ingestión y proyectar
  el agotamiento de disco a 30, 60 y 90 días, previniendo caídas por saturación.
• Redacté Procedimientos Operativos Estándar (SOPs B2B) para NOC/Cloud y generé reportes ejecutivos periódicos en PDF/HTML.
```

---

## 👔 SECCIÓN 2: ENTREVISTA CON RECURSOS HUMANOS (RRHH)

En la entrevista inicial con RRHH buscan: **entusiasmo, compromiso, ganas de aprender, proactividad y saber comunicarse con claridad**.

### Pregunta 1: "Cuéntame sobre ti y por qué te interesa este puesto de Practicante de Servicios Cloud."
> **Respuesta Modelo:**
> *"Soy estudiante de los últimos ciclos apasionado por la infraestructura Cloud, la administración de bases de datos y la automatización en Linux. Conozco la trayectoria de On Empresas en el mercado B2B de telecomunicaciones y sé lo crítico que es para las empresas que sus bases de datos operen 24/7 sin interrupciones.*
> *Aunque estoy postulando a mi primera posición formal, he desarrollado de manera práctica un proyecto completo llamado **CloudDB Sentinel**, donde simulé exactamente los retos de este puesto: checklists de salud preventivos, gestión y validación de backups hacia la nube, y control de capacidad para clientes corporativos. Me motiva mucho sumar mi proactividad al equipo de Servicios Cloud y aprender de sus especialistas."*

### Pregunta 2: "¿Qué haces cuando te encuentras con un problema técnico que no sabes resolver?"
> **Respuesta Modelo (Metodología STAR):**
> * **Situación:** *"Al construir el validador de recuperación ante desastres de mi proyecto, los backups de PostgreSQL fallaban ocasionalmente por inconsistencias de versiones en el encabezado binario.*
> * **Tarea:** *Debía asegurar que el script pudiera validar cualquier respaldo sin arrojar falsos positivos.*
> * **Acción:** *Consulté la documentación oficial de PostgreSQL, revisé los códigos de salida de `pg_restore` y los logs del sistema, e implementé una verificación criptográfica previa con SHA-256 combinada con una inspección de la tabla de contenidos.*
> * **Resultado:** *Logré que la validación fuera 100% confiable y emitiera certificados auditables. Aprendí que ante un problema nuevo, la clave es analizar los logs paso a paso, documentar el error y ser metódico."*

### Pregunta 3: "¿Cómo te organizarías con actividades rutinarias y repetitivas como el checklist diario?"
> **Respuesta Modelo:**
> *"Considero que las actividades rutinarias son el corazón de la estabilidad de un servicio Cloud. Mi enfoque es la disciplina y la estandarización: sigo estrictamente los Procedimientos Operativos Estándar (SOPs) para no saltarme ningún paso, y si identifico tareas manuales propensas a error humano, busco automatizarlas mediante scripts en Python o Bash para hacer más eficiente el tiempo y enfocarme en el análisis de las anomalías."*

---

## 🛠️ SECCIÓN 3: ENTREVISTA TÉCNICA (CON EL ESPECIALISTA CLOUD O JEFE)

### 🎙️ El Relato Cronológico del Proyecto (Tu discurso maestro de 5 minutos):

Cuando te digan: *"Cuéntanos sobre tu proyecto o qué has hecho en bases de datos"*, usa esta estructura cronológica:

```
[1. EL PROBLEMA Y LA MOTIVACIÓN] (1 min)
"Identifiqué que en operaciones Cloud B2B gestionadas, los especialistas atienden decenas
de bases de datos de distintos clientes. Hacer el checklist manual de cada una toma casi una
hora por turno y es propenso a descuidos. Además, muchas empresas asumen que sus backups
funcionan hasta el día en que intentan restaurar y el archivo está corrupto."

[2. LA ARQUITECTURA QUE DISEÑÉ] (1.5 min)
"Para resolver esto, diseñé 'CloudDB Sentinel' bajo una arquitectura modular y desacoplada
en Python y Bash. Configuré un entorno multi-tenant en Docker simulando dos clientes B2B:
uno con PostgreSQL 16 para su CRM core y otro con MySQL 8.0 para facturación.
Centralicé el inventario en YAML, permitiendo definir SLAs específicos por cliente:
RPO, RTO, umbrales de conexiones y retención de backups."

[3. EL MOTOR DE HEALTH CHECK Y PREVENCIÓN] (1 min)
"Construí un motor que evalúa más de 15 KPIs en tiempo real: desde métricas de rendimiento
como el Buffer Cache Hit Ratio (que debe ser >98%) hasta riesgos operacionales como
transacciones bloqueadas (locks), consultas lentas >30s, dead tuples que necesitan VACUUM
y el lag de replicación. Todo clasificado en un semáforo de OK, WARNING y CRITICAL."

[4. EL DIFERENCIADOR: ZERO-TRUST BACKUPS & DR TEST] (1 min)
"En el módulo de respaldos, no solo genero dumps consistentes con compresión zstd y subida
a MinIO/S3; implementé una política de 'Zero-Trust Restore'. El sistema levanta un entorno
aislado, restaura el último backup, verifica el hash SHA-256, hace un muestreo de filas
e integridad referencial, y emite un Certificado Formal de Disaster Recovery."

[5. CAPACITY PLANNING Y REPORTES EJECUTIVOS] (30 seg)
"Finalmente, incorporé un módulo de Capacity Planning que calcula la tasa de ingestión
diaria en MB/día y proyecta el agotamiento de disco a 30, 60 y 90 días, generando
automáticamente reportes ejecutivos en PDF y alertas hacia Telegram o tickets ITSM."
```

---

## 🧠 SECCIÓN 4: BANCO DE 15 PREGUNTAS TÉCNICAS DE FUEGO

### 1. ¿Qué es un Health Check de base de datos y por qué es importante?
> **Respuesta:** Es una inspección periódica y preventiva de la infraestructura y el motor de base de datos para diagnosticar disponibilidad, rendimiento, locks, saturación de memoria/disco e integridad de servicios antes de que se produzca una interrupción para los usuarios.

### 2. ¿Qué diferencia hay entre RPO y RTO?
> **Respuesta:**
> * **RPO (Recovery Point Objective):** La cantidad máxima de datos (medida en tiempo) que la empresa está dispuesta a perder ante un desastre. Por ejemplo, RPO = 1 hora significa que el backup más antiguo tolerado es de hace 1 hora.
> * **RTO (Recovery Time Objective):** El tiempo máximo que puede tardar el equipo en restaurar y poner en marcha el servicio tras una caída. Por ejemplo, RTO = 2 horas.

### 3. ¿Qué es el *Buffer Cache Hit Ratio* y por qué debe estar por encima del 98%?
> **Respuesta:** Mide el porcentaje de lecturas de páginas de datos que se resuelven directamente desde la memoria RAM (*shared_buffers* en PostgreSQL o *innodb_buffer_pool* en MySQL) sin tener que recurrir al disco mecánico o SSD. Si cae por debajo del 98%, indica que las consultas están leyendo constantemente de disco, aumentando la latencia y la saturación de I/O.

### 4. ¿Qué diferencia existe entre un backup lógico y un backup físico?
> **Respuesta:**
> * **Lógico (`pg_dump`, `mysqldump`):** Exporta las sentencias DDL y DML (tablas, datos, triggers) en formato SQL o binario estructurado. Es portable entre versiones y permite restaurar tablas individuales.
> * **Físico (`pg_basebackup`, copias a nivel de bloque):** Copia los archivos de datos brutos del clúster bit a bit. Es mucho más rápido para bases de datos de cientos de gigabytes y permite recuperación a un punto específico en el tiempo (*PITR* mediante WAL/binlogs).

### 5. ¿Qué es un Deadlock y cómo lo detectas?
> **Respuesta:** Ocurre cuando dos o más transacciones mantienen bloqueos sobre filas y cada una espera que la otra libere el recurso, quedando en espera circular infinita. En PostgreSQL se consulta `pg_stat_activity` y `pg_locks` buscando sesiones con `granted = false`, y el motor activa el `deadlock_timeout` para abortar automáticamente una de las transacciones.

### 6. ¿Para qué sirve el comando `VACUUM` en PostgreSQL?
> **Respuesta:** PostgreSQL utiliza el modelo MVCC (Multi-Version Concurrency Control). Cuando se actualiza o elimina una fila, la versión antigua no se borra físicamente de inmediato, quedando como una "tupla muerta" (*dead tuple*). `VACUUM` limpia esas tuplas para que el espacio pueda ser reutilizado por nuevas filas, evitando la fragmentación (*bloat*) de las tablas.

### 7. ¿Qué harías si recibes una alerta de disco al 90% de capacidad en un servidor de base de datos?
> **Respuesta:**
> 1. Verificar de inmediato en Linux con `df -h` y `du -sh /var/lib/postgresql/*` qué carpeta creció (datos, logs, WALs o temporales).
> 2. Si son archivos de log o temporales antiguos, ejecutar una purga controlada.
> 3. Si es el volumen de datos de la base de datos, notificar de inmediato al Especialista Cloud y solicitar la ampliación del volumen EBS/LUN en el proveedor Cloud.
> 4. Programar un `VACUUM` si hay tablas con alto bloat.

### 8. ¿Cómo monitoreas bases de datos en Linux desde la terminal?
> **Respuesta:**
> * A nivel de Sistema Operativo: `top`, `htop`, `vmstat 1` (CPU/RAM), `iostat -xz 1` (saturación de disco/IOPS), `df -h` (almacenamiento) y `journalctl -u postgresql` (logs del servicio).
> * A nivel de Base de Datos: Clientes interactivos como `psql` / `mysql`, utilidades como `pg_top` o consultando vistas del catálogo como `pg_stat_activity` y `information_schema.processlist`.

### 9. ¿Cómo funciona la integración con Zabbix / Prometheus para alertamiento?
> **Respuesta:** Se instala un exportador o agente (ej: `postgres_exporter` o `zabbix-agent`) en el servidor de base de datos. Este expone métricas en un puerto local. El servidor central de Prometheus/Zabbix sondea (*scrape*) las métricas cada 15-30 segundos. Si una métrica supera un umbral definido en las reglas (ej: conexiones > 90%), se dispara un disparador (*trigger*) que envía una alerta vía Webhook a Telegram, correo o al sistema de tickets.

### 10. ¿Por qué es vital verificar el Checksum SHA-256 de un backup?
> **Respuesta:** Durante la transferencia de red hacia el almacenamiento Cloud (S3/MinIO) o por fallos en el disco, un archivo de backup puede sufrir corrupción silenciosa (*bit rot*). El hash SHA-256 calculado al momento del dump debe coincidir exactamente con el hash del archivo recibido antes de intentar cualquier restauración.

---

## 🙋‍♂️ SECCIÓN 5: PREGUNTAS INTELIGENTES PARA HACER AL FINAL DE LA ENTREVISTA

Cuando te pregunten *"¿Tienes alguna pregunta para nosotros?"*, **NUNCA digas que no**. Elige 2 o 3 de estas preguntas:

1. *"En la operación diaria de Servicios Cloud de On Empresas, ¿cuál es el motor de base de datos que más administran en los clientes B2B (PostgreSQL, MySQL o SQL Server)?"*
2. *"¿Qué herramienta de gestión de tickets e incidentes utilizan actualmente en el área (ServiceNow, Jira Service Management, GLPI)?"*
3. *"Para el checklist preventivo de salud de las bases de datos de los clientes, ¿cuentan ya con herramientas automatizadas o hay oportunidad de que un practicante proponga mejoras con scripts en Python y Bash?"*
4. *"¿Cuáles serían los principales retos o prioridades que tendría que asumir en mis primeros 3 meses como practicante en el equipo?"*
