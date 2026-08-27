"""
notifier.py - Módulo de Alertas Multi-Canal para CloudDB Sentinel v1.0
=======================================================================
Gestiona el envío de alertas a múltiples canales (Telegram, Webhooks ITSM)
y mantiene un registro local de tickets en SQLite con control de cooldown
para prevenir spam de notificaciones.

Canales soportados:
  - Telegram Bot API (mensajes formateados con emojis según severidad)
  - Webhook HTTP (compatible con Jira/ServiceNow)
  - SQLite local (auditoría y trazabilidad de tickets)

Autor: CloudDB Sentinel - Equipo de Ingeniería de Plataformas
Fecha: 2026
"""

import sqlite3
import json
import logging
import os
import time
import hashlib
import requests
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional

# ---------------------------------------------------------------------------
# Logging estructurado
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

# ---------------------------------------------------------------------------
# Rutas de datos
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TICKETS_DB_PATH = os.path.join(BASE_DIR, "data", "tickets.db")

# ---------------------------------------------------------------------------
# Dataclasses de dominio (reutilizable del módulo de capacity si se necesita)
# ---------------------------------------------------------------------------

@dataclass
class Alert:
    """
    Representa una alerta emitida por cualquier módulo del sistema.
    Compatible con el formato usado en capacity_planner.py y checker.py.
    """
    db_id: str
    level: str          # 'INFO' | 'WARNING' | 'CRITICAL'
    category: str       # 'BACKUP_FAILURE' | 'HEALTH_CRITICAL' | 'CAPACITY_ALERT' | 'DR_VALIDATION_FAILURE'
    message: str
    value: float = 0.0
    threshold: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ISTMTicket:
    """Representa un ticket de soporte generado por el sistema."""
    ticket_id: str          # Número correlativo local: CDT-YYYYMMDD-NNNN
    db_id: str
    category: str
    priority: str           # 'P1' | 'P2' | 'P3' | 'P4'
    summary: str
    description: str
    status: str             # 'OPEN' | 'IN_PROGRESS' | 'RESOLVED' | 'CLOSED'
    created_at: str
    resolved_at: Optional[str] = None
    itsm_ref: Optional[str] = None  # Referencia en Jira/ServiceNow si aplica


# ---------------------------------------------------------------------------
# Inicialización de la base de datos SQLite de tickets
# ---------------------------------------------------------------------------

def _init_tickets_db() -> None:
    """
    Crea la base de datos SQLite de tickets y tablas auxiliares si no existen.
    Invocado automáticamente antes de cualquier operación de escritura.
    """
    os.makedirs(os.path.dirname(TICKETS_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(TICKETS_DB_PATH)
    try:
        # Tabla principal de tickets
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id    TEXT    UNIQUE NOT NULL,
                db_id        TEXT    NOT NULL,
                category     TEXT    NOT NULL,
                priority     TEXT    NOT NULL,
                summary      TEXT    NOT NULL,
                description  TEXT,
                status       TEXT    NOT NULL DEFAULT 'OPEN',
                created_at   TEXT    NOT NULL,
                resolved_at  TEXT,
                itsm_ref     TEXT
            )
        """)
        # Tabla de historial de envíos (para cooldown)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alert_dispatch_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_hash   TEXT    NOT NULL,
                channel      TEXT    NOT NULL,
                dispatched_at TEXT   NOT NULL,
                success      INTEGER NOT NULL DEFAULT 1
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_alert_hash ON alert_dispatch_log(alert_hash, dispatched_at)"
        )
        # Contador de tickets para números correlativos
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ticket_counter (
                date_key    TEXT PRIMARY KEY,
                counter     INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()
        logger.debug("Base de datos SQLite de tickets inicializada.")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Clase principal: AlertManager
# ---------------------------------------------------------------------------

class AlertManager:
    """
    Gestiona el ciclo de vida completo de alertas: creación, deduplicación,
    enrutamiento a canales y registro de auditoría.

    Atributos de configuración (desde environment o dict de configuración):
        TELEGRAM_BOT_TOKEN: Token del bot de Telegram.
        TELEGRAM_CHAT_ID:   ID del chat/grupo de Telegram destino.
        WEBHOOK_URL:        URL del webhook ITSM (Jira/ServiceNow).
        ALERT_COOLDOWN_MINUTES: Minutos mínimos entre alertas duplicadas.
        CHANNELS:           Lista de canales habilitados: ['telegram', 'webhook']
    """

    def __init__(self, config: Optional[dict] = None):
        """
        Inicializa el AlertManager con la configuración proporcionada.
        Si config es None, intenta leer desde variables de entorno.

        Args:
            config: Diccionario de configuración con las claves:
                - telegram_bot_token (str)
                - telegram_chat_id (str)
                - webhook_url (str)
                - alert_cooldown_minutes (int): Default 15
                - channels (list): Default ['telegram']
        """
        if config is None:
            config = {}

        self.telegram_bot_token = config.get(
            "telegram_bot_token",
            os.getenv("TELEGRAM_BOT_TOKEN", ""),
        )
        self.telegram_chat_id = config.get(
            "telegram_chat_id",
            os.getenv("TELEGRAM_CHAT_ID", ""),
        )
        self.webhook_url = config.get(
            "webhook_url",
            os.getenv("ITSM_WEBHOOK_URL", ""),
        )
        self.cooldown_minutes = int(config.get(
            "alert_cooldown_minutes",
            os.getenv("ALERT_COOLDOWN_MINUTES", "15"),
        ))
        self.channels = config.get(
            "channels",
            os.getenv("ALERT_CHANNELS", "telegram").split(","),
        )
        # Inicializar DB de tickets
        _init_tickets_db()
        logger.info(
            "AlertManager inicializado | canales=%s | cooldown=%d min",
            self.channels, self.cooldown_minutes,
        )

    # -----------------------------------------------------------------------
    # CANAL: Telegram
    # -----------------------------------------------------------------------

    def send_telegram(self, message: str, level: str = "INFO") -> bool:
        """
        Envía un mensaje formateado a Telegram usando la Bot API.
        Formatea el mensaje con emojis y Markdown según el nivel de severidad.
        Respeta el cooldown configurado para evitar spam.

        Args:
            message: Texto del mensaje a enviar.
            level:   Nivel de severidad: 'INFO' | 'WARNING' | 'CRITICAL' | 'OK'

        Returns:
            True si el mensaje fue enviado exitosamente, False en caso contrario.
        """
        if not self.telegram_bot_token or not self.telegram_chat_id:
            logger.warning(
                "Telegram no configurado. Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID."
            )
            return False

        # Mapeo de nivel a emoji
        level_emoji = {
            "OK":       "🟢",
            "INFO":     "🔵",
            "WARNING":  "🟡",
            "CRITICAL": "🔴",
        }.get(level.upper(), "⚪")

        # Encabezado del mensaje formateado
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        formatted_message = (
            f"{level_emoji} *CloudDB Sentinel* — [{level.upper()}]\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"{message}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🕐 `{timestamp}`"
        )

        api_url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": formatted_message,
            "parse_mode": "Markdown",
            "disable_notification": level not in ("WARNING", "CRITICAL"),
        }

        try:
            response = requests.post(api_url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info("Mensaje Telegram enviado exitosamente | level=%s", level)
            return True
        except requests.exceptions.Timeout:
            logger.error("Timeout al enviar mensaje a Telegram.")
            return False
        except requests.exceptions.HTTPError as exc:
            logger.error("Error HTTP al enviar a Telegram: %s | Response: %s", exc, response.text)
            return False
        except Exception as exc:
            logger.error("Error inesperado al enviar a Telegram: %s", exc)
            return False

    # -----------------------------------------------------------------------
    # CANAL: Webhook ITSM
    # -----------------------------------------------------------------------

    def send_webhook(self, payload: dict, url: str = "") -> bool:
        """
        Envía un payload JSON via POST a un webhook URL.
        El payload es compatible con Jira/ServiceNow para creación automática de tickets.

        Estructura del payload compatible con Jira:
        {
            "summary": "...",
            "description": "...",
            "priority": {"name": "High"},
            "labels": ["clouddb-sentinel", "automated"],
            "customfield_10001": "db_id",  // custom field para BD
            "category": "...",
            "db_id": "...",
            "timestamp": "...",
            "source": "CloudDB Sentinel v1.0"
        }

        Args:
            payload: Diccionario con los datos del ticket/alerta.
            url:     URL del webhook. Si está vacío, usa self.webhook_url.

        Returns:
            True si la petición fue exitosa (HTTP 2xx), False en caso contrario.
        """
        target_url = url or self.webhook_url
        if not target_url:
            logger.warning("Webhook URL no configurada. Mensaje no enviado.")
            return False

        # Asegurar campos requeridos para compatibilidad ITSM
        payload.setdefault("source", "CloudDB Sentinel v1.0")
        payload.setdefault("timestamp", datetime.utcnow().isoformat())

        headers = {
            "Content-Type": "application/json",
            "X-Source": "CloudDB-Sentinel",
            "X-Version": "1.0",
        }

        try:
            response = requests.post(
                target_url,
                json=payload,
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()
            logger.info(
                "Webhook enviado exitosamente | url=%s | status=%d",
                target_url, response.status_code,
            )
            return True
        except requests.exceptions.ConnectionError:
            logger.error("No se pudo conectar al webhook: %s", target_url)
            return False
        except requests.exceptions.Timeout:
            logger.error("Timeout al enviar webhook a: %s", target_url)
            return False
        except requests.exceptions.HTTPError as exc:
            logger.error(
                "Error HTTP en webhook | url=%s | status=%d | response=%s",
                target_url, response.status_code, response.text[:200],
            )
            return False
        except Exception as exc:
            logger.error("Error inesperado al enviar webhook: %s", exc)
            return False

    # -----------------------------------------------------------------------
    # Creación de tickets ITSM locales
    # -----------------------------------------------------------------------

    def create_itsm_ticket(self, alert: Alert) -> dict:
        """
        Formatea una alerta como ticket de soporte y lo registra en SQLite local.
        Genera un número correlativo único por fecha en formato CDT-YYYYMMDD-NNNN.

        Categorías soportadas:
            - BACKUP_FAILURE: Fallos en proceso de respaldo
            - HEALTH_CRITICAL: Health check en estado CRITICAL
            - CAPACITY_ALERT: Alertas de capacidad de disco o BD
            - DR_VALIDATION_FAILURE: Fallos en validación DR

        Args:
            alert: Objeto Alert con los datos de la alerta.

        Returns:
            Diccionario con los datos del ticket creado.
        """
        _init_tickets_db()

        # Mapeo de categoría a prioridad ITSM
        priority_map = {
            "BACKUP_FAILURE":         "P2",
            "HEALTH_CRITICAL":        "P1",
            "CAPACITY_ALERT":         "P2",
            "DR_VALIDATION_FAILURE":  "P1",
            "DISK_ALERT":             "P2",
            "DB_SIZE_ALERT":          "P3",
            "COLLECTION_ERROR":       "P3",
        }
        # Escalar a P1 si el nivel es CRITICAL
        base_priority = priority_map.get(alert.category, "P3")
        priority = "P1" if alert.level == "CRITICAL" and base_priority != "P1" else base_priority

        # Generar número correlativo
        date_key = datetime.utcnow().strftime("%Y%m%d")
        conn = sqlite3.connect(TICKETS_DB_PATH)
        try:
            # Incrementar contador atómicamente
            conn.execute("""
                INSERT INTO ticket_counter (date_key, counter) VALUES (?, 1)
                ON CONFLICT(date_key) DO UPDATE SET counter = counter + 1
            """, (date_key,))
            counter_row = conn.execute(
                "SELECT counter FROM ticket_counter WHERE date_key = ?", (date_key,)
            ).fetchone()
            ticket_number = counter_row[0] if counter_row else 1
        finally:
            conn.close()

        ticket_id = f"CDT-{date_key}-{ticket_number:04d}"

        # Descripción detallada del ticket
        description = (
            f"**Ticket generado automáticamente por CloudDB Sentinel v1.0**\n\n"
            f"**Base de Datos:** {alert.db_id}\n"
            f"**Categoría:** {alert.category}\n"
            f"**Nivel de Severidad:** {alert.level}\n"
            f"**Valor Detectado:** {alert.value}\n"
            f"**Umbral Configurado:** {alert.threshold}\n\n"
            f"**Descripción del Problema:**\n{alert.message}\n\n"
            f"**Timestamp de Detección:** {alert.timestamp}\n\n"
            f"**Acciones Recomendadas:**\n"
            f"1. Verificar el estado actual de la base de datos {alert.db_id}\n"
            f"2. Consultar el dashboard de CloudDB Sentinel para contexto adicional\n"
            f"3. Revisar logs del sistema en /var/log/clouddb-sentinel/\n"
            f"4. Escalar al equipo de DBA si el problema persiste > 30 minutos\n"
        )

        ticket = ISTMTicket(
            ticket_id=ticket_id,
            db_id=alert.db_id,
            category=alert.category,
            priority=priority,
            summary=f"[CloudDB Sentinel] {alert.category} en {alert.db_id}: {alert.message[:120]}",
            description=description,
            status="OPEN",
            created_at=datetime.utcnow().isoformat(),
        )

        # Persistir en SQLite
        conn = sqlite3.connect(TICKETS_DB_PATH)
        try:
            conn.execute("""
                INSERT OR IGNORE INTO tickets
                    (ticket_id, db_id, category, priority, summary, description,
                     status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticket.ticket_id, ticket.db_id, ticket.category, ticket.priority,
                ticket.summary, ticket.description, ticket.status, ticket.created_at,
            ))
            conn.commit()
        finally:
            conn.close()

        ticket_dict = asdict(ticket)
        logger.info(
            "Ticket ITSM creado | ticket_id=%s | db_id=%s | priority=%s | category=%s",
            ticket_id, alert.db_id, priority, alert.category,
        )
        return ticket_dict

    # -----------------------------------------------------------------------
    # Control de cooldown (anti-spam)
    # -----------------------------------------------------------------------

    def _compute_alert_hash(self, alert: Alert) -> str:
        """
        Calcula un hash único por combinación db_id + category + level para
        identificar alertas duplicadas en el período de cooldown.

        Args:
            alert: La alerta a identificar.

        Returns:
            String hexadecimal del hash MD5.
        """
        key = f"{alert.db_id}|{alert.category}|{alert.level}"
        return hashlib.md5(key.encode()).hexdigest()

    def _is_in_cooldown(self, alert_hash: str, channel: str) -> bool:
        """
        Verifica si una alerta está en período de cooldown para un canal dado.

        Args:
            alert_hash: Hash único de la alerta.
            channel:    Canal de notificación ('telegram', 'webhook', etc.)

        Returns:
            True si está en cooldown (no se debe re-enviar), False si se puede enviar.
        """
        _init_tickets_db()
        since = (datetime.utcnow() - timedelta(minutes=self.cooldown_minutes)).isoformat()
        conn = sqlite3.connect(TICKETS_DB_PATH)
        try:
            row = conn.execute("""
                SELECT COUNT(*) FROM alert_dispatch_log
                WHERE alert_hash = ? AND channel = ? AND dispatched_at >= ? AND success = 1
            """, (alert_hash, channel, since)).fetchone()
            return row[0] > 0
        finally:
            conn.close()

    def _log_dispatch(self, alert_hash: str, channel: str, success: bool) -> None:
        """
        Registra el intento de envío de una alerta en el log de despacho.

        Args:
            alert_hash: Hash de la alerta.
            channel:    Canal usado.
            success:    True si el envío fue exitoso.
        """
        _init_tickets_db()
        conn = sqlite3.connect(TICKETS_DB_PATH)
        try:
            conn.execute("""
                INSERT INTO alert_dispatch_log (alert_hash, channel, dispatched_at, success)
                VALUES (?, ?, ?, ?)
            """, (alert_hash, channel, datetime.utcnow().isoformat(), 1 if success else 0))
            conn.commit()
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # Método principal: dispatch_alerts
    # -----------------------------------------------------------------------

    def dispatch_alerts(self, alerts: list) -> dict:
        """
        Método principal de despacho. Para cada alerta:
          1. Calcula el hash para deduplicación.
          2. Verifica cooldown por canal.
          3. Crea ticket ITSM local.
          4. Envía a los canales habilitados (Telegram, Webhook).
          5. Registra el envío en el log de auditoría.

        Args:
            alerts: Lista de objetos Alert o dicts compatibles.

        Returns:
            Diccionario con estadísticas del despacho:
            {
                'dispatched': int,
                'skipped_cooldown': int,
                'failed': int,
                'tickets_created': list[str],
            }
        """
        stats = {
            "dispatched": 0,
            "skipped_cooldown": 0,
            "failed": 0,
            "tickets_created": [],
        }

        if not alerts:
            logger.info("No hay alertas para despachar.")
            return stats

        logger.info("Iniciando despacho de alertas | total=%d", len(alerts))

        for raw_alert in alerts:
            # Normalizar: si es dict, convertir a Alert
            if isinstance(raw_alert, dict):
                alert = Alert(
                    db_id=raw_alert.get("db_id", "unknown"),
                    level=raw_alert.get("level", "INFO"),
                    category=raw_alert.get("category", "GENERAL"),
                    message=raw_alert.get("message", "Sin descripción"),
                    value=float(raw_alert.get("value", 0.0)),
                    threshold=float(raw_alert.get("threshold", 0.0)),
                    timestamp=raw_alert.get("timestamp", datetime.utcnow().isoformat()),
                )
            else:
                alert = raw_alert

            alert_hash = self._compute_alert_hash(alert)

            # Crear ticket ITSM (siempre, sin cooldown para trazabilidad completa)
            try:
                ticket = self.create_itsm_ticket(alert)
                stats["tickets_created"].append(ticket["ticket_id"])
            except Exception as exc:
                logger.error("Error al crear ticket ITSM para alerta | db_id=%s | error=%s", alert.db_id, exc)

            # Despachar a cada canal habilitado
            for channel in self.channels:
                channel = channel.strip().lower()
                if self._is_in_cooldown(alert_hash, channel):
                    logger.debug(
                        "Alerta en cooldown | hash=%s | channel=%s | cooldown=%d min",
                        alert_hash, channel, self.cooldown_minutes,
                    )
                    stats["skipped_cooldown"] += 1
                    continue

                success = False
                try:
                    if channel == "telegram":
                        msg = f"*{alert.category}* en `{alert.db_id}`\n{alert.message}"
                        success = self.send_telegram(msg, level=alert.level)
                    elif channel == "webhook":
                        webhook_payload = self._build_itsm_payload(alert)
                        success = self.send_webhook(webhook_payload)
                    else:
                        logger.warning("Canal desconocido: '%s'. Ignorando.", channel)
                        continue
                except Exception as exc:
                    logger.error(
                        "Excepción al despachar alerta | channel=%s | db_id=%s | error=%s",
                        channel, alert.db_id, exc,
                    )
                    success = False

                self._log_dispatch(alert_hash, channel, success)

                if success:
                    stats["dispatched"] += 1
                    logger.info(
                        "Alerta despachada | channel=%s | db_id=%s | level=%s | category=%s",
                        channel, alert.db_id, alert.level, alert.category,
                    )
                else:
                    stats["failed"] += 1

        logger.info(
            "Despacho completado | enviadas=%d | cooldown=%d | fallidas=%d | tickets=%d",
            stats["dispatched"], stats["skipped_cooldown"],
            stats["failed"], len(stats["tickets_created"]),
        )
        return stats

    def _build_itsm_payload(self, alert: Alert) -> dict:
        """
        Construye el payload del ticket para enviarlo al webhook ITSM.
        Estructura compatible con Jira Service Management y ServiceNow.

        Args:
            alert: La alerta a convertir en payload.

        Returns:
            Diccionario con el payload ITSM.
        """
        # Mapeo de nivel a prioridad Jira
        jira_priority_map = {
            "CRITICAL": "Highest",
            "WARNING":  "High",
            "INFO":     "Medium",
        }
        priority_name = jira_priority_map.get(alert.level.upper(), "Medium")

        return {
            # Campos estándar Jira
            "summary": f"[CloudDB Sentinel] {alert.category} en {alert.db_id}",
            "description": (
                f"*Alerta automática generada por CloudDB Sentinel v1.0*\n\n"
                f"*Base de Datos:* {alert.db_id}\n"
                f"*Categoría:* {alert.category}\n"
                f"*Nivel:* {alert.level}\n"
                f"*Mensaje:* {alert.message}\n"
                f"*Valor:* {alert.value}\n"
                f"*Umbral:* {alert.threshold}\n"
                f"*Timestamp:* {alert.timestamp}"
            ),
            "priority": {"name": priority_name},
            "labels": ["clouddb-sentinel", "automated", alert.category.lower()],
            # Campos personalizados
            "category": alert.category,
            "db_id": alert.db_id,
            "level": alert.level,
            "value": alert.value,
            "threshold": alert.threshold,
            "timestamp": alert.timestamp,
            "source": "CloudDB Sentinel v1.0",
            # Campos ServiceNow equivalentes
            "short_description": f"[CloudDB Sentinel] {alert.category} en {alert.db_id}",
            "urgency": "1" if alert.level == "CRITICAL" else "2",
            "impact": "2",
            "category_sn": "Database",
            "subcategory": alert.category,
        }

    # -----------------------------------------------------------------------
    # Consulta de tickets abiertos
    # -----------------------------------------------------------------------

    def get_open_tickets(self) -> list:
        """
        Lista todos los tickets con estado 'OPEN' o 'IN_PROGRESS' desde SQLite.

        Returns:
            Lista de diccionarios con los datos de cada ticket abierto.
            Ordenados por prioridad (P1 primero) y luego por fecha de creación.
        """
        _init_tickets_db()
        conn = sqlite3.connect(TICKETS_DB_PATH)
        try:
            cursor = conn.execute("""
                SELECT ticket_id, db_id, category, priority, summary,
                       status, created_at, itsm_ref
                FROM tickets
                WHERE status IN ('OPEN', 'IN_PROGRESS')
                ORDER BY
                    CASE priority
                        WHEN 'P1' THEN 1
                        WHEN 'P2' THEN 2
                        WHEN 'P3' THEN 3
                        WHEN 'P4' THEN 4
                        ELSE 5
                    END ASC,
                    created_at ASC
            """)
            columns = ["ticket_id", "db_id", "category", "priority",
                       "summary", "status", "created_at", "itsm_ref"]
            tickets = [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            conn.close()

        logger.info("Tickets abiertos consultados | total=%d", len(tickets))
        return tickets

    def resolve_ticket(self, ticket_id: str, itsm_ref: str = "") -> bool:
        """
        Marca un ticket como RESOLVED en la base de datos local.

        Args:
            ticket_id: Identificador del ticket (ej. 'CDT-20260101-0001').
            itsm_ref:  Referencia opcional en el ITSM externo (ej. JRA-1234).

        Returns:
            True si el ticket fue actualizado, False si no se encontró.
        """
        _init_tickets_db()
        conn = sqlite3.connect(TICKETS_DB_PATH)
        try:
            cursor = conn.execute("""
                UPDATE tickets
                SET status = 'RESOLVED',
                    resolved_at = ?,
                    itsm_ref = COALESCE(NULLIF(?, ''), itsm_ref)
                WHERE ticket_id = ? AND status NOT IN ('RESOLVED', 'CLOSED')
            """, (datetime.utcnow().isoformat(), itsm_ref, ticket_id))
            conn.commit()
            updated = cursor.rowcount > 0
        finally:
            conn.close()

        if updated:
            logger.info("Ticket resuelto | ticket_id=%s | itsm_ref=%s", ticket_id, itsm_ref)
        else:
            logger.warning("Ticket no encontrado o ya estaba resuelto | ticket_id=%s", ticket_id)
        return updated


# ---------------------------------------------------------------------------
# Punto de entrada para pruebas directas
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    """
    Demostración del AlertManager. Crea alertas de prueba y las despacha.
    """
    print("=== CloudDB Sentinel - AlertManager Demo ===")

    # Configurar manager con valores de prueba (sin canales reales)
    manager = AlertManager(config={
        "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
        "alert_cooldown_minutes": 0,  # Sin cooldown para la demo
        "channels": ["webhook"] if os.getenv("ITSM_WEBHOOK_URL") else [],
    })

    # Crear alertas de prueba
    test_alerts = [
        Alert(
            db_id="crm-prod-pg01",
            level="CRITICAL",
            category="HEALTH_CRITICAL",
            message="Conexión rechazada: demasiadas conexiones activas (max_connections alcanzado)",
            value=100.0,
            threshold=80.0,
        ),
        Alert(
            db_id="telecom-prod-pg02",
            level="WARNING",
            category="CAPACITY_ALERT",
            message="Uso de disco al 78%. Proyección de agotamiento en 45 días.",
            value=78.0,
            threshold=75.0,
        ),
        Alert(
            db_id="crm-prod-pg01",
            level="CRITICAL",
            category="BACKUP_FAILURE",
            message="El backup nocturno falló: error de conexión a S3",
            value=0.0,
            threshold=1.0,
        ),
    ]

    # Despachar alertas
    result = manager.dispatch_alerts(test_alerts)
    print(f"\nResultados del despacho:")
    print(f"  Enviadas:  {result['dispatched']}")
    print(f"  Cooldown:  {result['skipped_cooldown']}")
    print(f"  Fallidas:  {result['failed']}")
    print(f"  Tickets:   {result['tickets_created']}")

    # Mostrar tickets abiertos
    tickets = manager.get_open_tickets()
    print(f"\nTickets abiertos ({len(tickets)}):")
    for t in tickets:
        print(f"  [{t['priority']}] {t['ticket_id']} | {t['db_id']} | {t['category']} | {t['status']}")
