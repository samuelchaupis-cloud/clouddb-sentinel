# POLÍTICA CORPORATIVA DE GESTIÓN DE CAPACIDAD (CAPACITY PLANNING)
## Código: POL-CAP-001 | Versión: 1.0

```text
===============================================================================
EMPRESA:           Servicios Cloud & Telecomunicaciones B2B
ÁREA:              Ingeniería de Infraestructura & Arquitectura Cloud
TÍTULO:            Control de Capacidades y Planificación de Infraestructura B2B
RESPONSABLE:       Practicante Pre de Servicios Cloud / Especialista Cloud
APROBADO POR:      Gerencia de Operaciones y Servicios Gestionados
FECHA VIGENCIA:    2026-08-01
===============================================================================
```

---

## 1. PROPÓSITO Y OBJETIVO
Garantizar que la infraestructura de bases de datos cuente permanentemente con la capacidad adecuada de cómputo, memoria y almacenamiento para soportar las operaciones actuales y el crecimiento futuro de los clientes B2B, evitando caídas por saturación de disco y optimizando los costos de aprovisionamiento en la nube.

---

## 2. MÉTRICAS CLAVE DE CAPACIDAD

1. **Volumen Total Utilizado por Base de Datos:** Crecimiento en megabytes/gigabytes a lo largo del tiempo.
2. **Espacio Disponible en Disco / Filesystem:** Porcentaje libre en la partición `/var/lib/postgresql/data` o `/var/lib/mysql`.
3. **Tasa de Crecimiento Diario ($MB/\text{día}$):** Promedio móvil de ingestión de datos en los últimos 30 días.
4. **Time to Exhaustion (TTE - Días Restantes):** Cálculo proyectado de días antes de alcanzar el umbral de bloqueo ($88\%$ de capacidad).
5. **Top 10 Tablas de Mayor Crecimiento:** Identificación de tablas con mayor volumen e impacto en índices.

---

## 3. MATRIZ DE UMBRALES Y TIEMPOS DE ACCIÓN

| Nivel de Alerta | % Uso de Almacenamiento | TTE Proyectado | Acción Operativa Inmediata |
|:---|:---|:---|:---|
| 🟢 **NORMAL** | $< 75\%$ | $> 60$ días | Operación rutinaria sin intervención requerida. |
| 🟡 **ADVERTENCIA** | $75\% - 84\%$ | $30 - 60$ días | Incluir en el reporte mensual de capacidad; notificar al cliente B2B necesidad de expansión. |
| 🟠 **ALTO RIESGO** | $85\% - 89\%$ | $10 - 29$ días | Abrir ticket de ingeniería para ampliación de volumen Cloud LUN/EBS en un plazo no mayor a 72h. |
| 🔴 **CRÍTICO** | $\ge 90\%$ | $< 10$ días | Escalamiento de emergencia; purga de logs antiguos y ampliación inmediata de storage. |

---

## 4. MODELO MATEMÁTICO DE PROYECCIÓN DE CRECIMIENTO

El módulo `src/capacity/capacity_planner.py` emplea una regresión lineal sobre el histórico de snapshots almacenados en `data/capacity_history.db`:

$$\text{Tasa de Crecimiento Diario } (m) = \frac{\sum (t_i - \bar{t})(S_i - \bar{S})}{\sum (t_i - \bar{t})^2}$$

Donde:
* $t_i$ es el timestamp de cada snapshot.
* $S_i$ es el tamaño de la base de datos en megabytes.

### Proyección a 30, 60 y 90 Días:
$$\text{Tamaño Proyectado}(D) = S_{\text{actual}} + (m \times D)$$

### Días hasta Saturación ($TTE$):
$$TTE = \frac{\text{Capacidad Máxima Permitida (MB)} - S_{\text{actual}}}{m}$$

---

## 5. FORMATO DE INFORME MENSUAL DE CAPACIDAD PARA CLIENTES B2B

```text
+-------------------------------------------------------------------------------+
|                      INFORME MENSUAL DE CAPACIDAD CLOUD                       |
| Cliente: Cliente A Telecom Core          Período: Agosto 2026                 |
+-------------------------------------------------------------------------------+
| Espacio Asignado Total:                  500.00 GB                            |
| Espacio Actual en Uso:                   215.40 GB (43.08%)                   |
| Tasa de Ingestión Promedio:              0.85 GB / día                        |
| Proyección a 30 Días:                    240.90 GB (48.18%)                   |
| Proyección a 60 Días:                    266.40 GB (53.28%)                   |
| Proyección a 90 Días:                    291.90 GB (58.38%)                   |
| Días Estimados hasta Límite del 85%:     247 días                             |
| Estado de Salud de Almacenamiento:       🟢 SALUDABLE (Sin riesgo a corto plazo)|
+-------------------------------------------------------------------------------+
| Recomendación del Especialista:                                               |
| No se requiere ampliación de infraestructura en el trimestre actual.          |
+-------------------------------------------------------------------------------+
```
