# Política de Seguridad — CloudDB Sentinel

## 🛡️ Compromiso de Seguridad

En entornos B2B y de misión crítica, la seguridad de las bases de datos y de sus credenciales es primordial. CloudDB Sentinel implementa las siguientes directrices por diseño:

1. **Sin credenciales embebidas (Zero Hardcoded Secrets):** Todas las credenciales se inyectan exclusivamente a través de variables de entorno (`.env` o secretos en plataformas CI/CD / Kubernetes).
2. **Cifrado de respaldos:** Todos los backups destinados a Cloud Storage (AWS S3 / MinIO) son cifrados en tránsito (HTTPS/TLS) y en reposo (SSE-S3 / SSE-KMS).
3. **Validación Criptográfica:** Integridad de respaldos garantizada mediante sumas de verificación `SHA-256`.
4. **Principio de Menor Privilegio:** Los usuarios de base de datos utilizados por los módulos de Health Check solo requieren permisos de lectura sobre las vistas del catálogo del sistema (`pg_stat_activity`, `information_schema`).

---

## 🚨 Reporte de Vulnerabilidades

Si descubres una vulnerabilidad de seguridad en este proyecto:
1. **NO** abras un Issue público.
2. Envía un correo electrónico privado a la dirección del mantenedor del proyecto.
3. Proporciona una descripción detallada, pasos para reproducir y posible vector de impacto.
4. Se responderá en un plazo máximo de 48 horas con el plan de remediación.
