#!/usr/bin/env python3
"""
scripts/test_telegram_alert.py — CloudDB Sentinel
===================================================
Script interactivo y CLI para validar la integración de alertas con Telegram Bot API.

Uso:
  python scripts/test_telegram_alert.py --simulate
  python scripts/test_telegram_alert.py --token <BOT_TOKEN> --chat-id <CHAT_ID>
  python scripts/test_telegram_alert.py --level CRITICAL --category BACKUP_FAILURE
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Configurar encoding seguro para terminales Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Cargar variables de entorno del proyecto
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Asegurar que 'src' sea importable
sys.path.insert(0, str(PROJECT_ROOT))

from src.alerting.notifier import AlertManager, Alert


def parse_args():
    parser = argparse.ArgumentParser(
        description="Validador interactivo de alertas de Telegram para CloudDB Sentinel."
    )
    parser.add_argument(
        "--token",
        type=str,
        default=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        help="Token del Bot de Telegram proporcionado por @BotFather",
    )
    parser.add_argument(
        "--chat-id",
        type=str,
        default=os.getenv("TELEGRAM_CHAT_ID", ""),
        help="Chat ID o ID del grupo de Telegram",
    )
    parser.add_argument(
        "--level",
        type=str,
        default="CRITICAL",
        choices=["INFO", "WARNING", "CRITICAL", "OK"],
        help="Nivel de severidad de la alerta de prueba",
    )
    parser.add_argument(
        "--category",
        type=str,
        default="DATABASE_DOWN_P1",
        help="Categoría técnica de la alerta",
    )
    parser.add_argument(
        "--db-id",
        type=str,
        default="cliente-a-pg",
        help="Identificador de base de datos simulada",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Ejecuta una simulación completa sin requerir un token real de Telegram",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 70)
    print("🔔 CLOUDB SENTINEL — TEST DE CANAL DE ALERTAS TELEGRAM BOT")
    print("=" * 70)

    token = args.token.strip()
    chat_id = args.chat_id.strip()

    is_configured = bool(token and chat_id and token != "your_telegram_bot_token_here")

    print(f"[*] Base de Datos:   {args.db_id}")
    print(f"[*] Severidad:       {args.level}")
    print(f"[*] Categoría:       {args.category}")
    print(f"[*] Bot Token:       {token[:6] + '...' + token[-4:] if len(token) > 10 else (token or 'NO CONFIGURADO')}")
    print(f"[*] Chat ID:         {chat_id or 'NO CONFIGURADO'}")
    print(f"[*] Modo Simulado:   {'SÍ' if args.simulate else 'NO'}")
    print("-" * 70)

    # Crear instancia de AlertManager
    config = {
        "telegram_bot_token": token if not args.simulate else "simulated_token",
        "telegram_chat_id": chat_id if not args.simulate else "simulated_chat_id",
        "alert_cooldown_minutes": 0,  # Sin cooldown para el test
        "channels": ["telegram"],
    }
    manager = AlertManager(config=config)

    # Crear alerta de prueba estructurada
    test_alert = Alert(
        db_id=args.db_id,
        level=args.level,
        category=args.category,
        message=(
            f"SIMULACIÓN DE INCIDENTE P1: Conectividad perdida con el cluster {args.db_id} en 127.0.0.1:5432.\n"
            f"• Conexiones activas: 0 / 100\n"
            f"• Tiempo de respuesta: TIMEOUT (>5000 ms)\n"
            f"• Acción requerida: Verificar estado de contenedor Docker y conmutar a réplica."
        ),
        value=5000.0,
        threshold=100.0,
    )

    # 1. Crear ticket ITSM de prueba
    print("\n[+] Paso 1: Generando ticket de soporte ITSM local...")
    ticket = manager.create_itsm_ticket(test_alert)
    print(f"    ✓ Ticket Creado: [{ticket.get('ticket_id')}] - Prioridad: {ticket.get('priority')}")
    print(f"    ✓ Resumen:       {ticket.get('summary')}")

    # 2. Envío o simulación a Telegram
    print("\n[+] Paso 2: Despachando notificación a Telegram...")
    if args.simulate or not is_configured:
        print("    ℹ️  [MODO SIMULACIÓN ACTIVO / CREDENCIALES VACÍAS]")
        print("    Mensaje formateado que se enviaría a Telegram:\n")
        emoji = "🔴" if args.level == "CRITICAL" else "🟡" if args.level == "WARNING" else "🟢"
        print(f"    {emoji} *CloudDB Sentinel* — [{args.level}]")
        print("    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"    *{test_alert.category}* en `{test_alert.db_id}`")
        print(f"    {test_alert.message}")
        print("    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"    🎫 Ticket: `{ticket.get('ticket_id')}` | Prioridad: `{ticket.get('priority')}`")
        print("\n    ✅ Simulación de despacho completada con éxito.")
        if not is_configured:
            print("\n    💡 Para enviar mensajes REALES a tu Telegram:")
            print("       1. Habla con @BotFather en Telegram y crea un bot con /newbot para obtener el TOKEN.")
            print("       2. Habla con @userinfobot en Telegram para obtener tu CHAT_ID.")
            print("       3. Guárdalos en tu archivo .env o ejecuta:")
            print("          python scripts/test_telegram_alert.py --token <TU_TOKEN> --chat-id <TU_CHAT_ID>")
    else:
        try:
            msg_content = (
                f"*{test_alert.category}* en `{test_alert.db_id}`\n\n"
                f"{test_alert.message}\n\n"
                f"🎫 Ticket ITSM: `{ticket.get('ticket_id')}` | Prioridad: `{ticket.get('priority')}`"
            )
            success = manager.send_telegram(msg_content, level=args.level)
            if success:
                print("    ✅ ¡MENSAJE ENVIADO EXITOSAMENTE A TELEGRAM!")
            else:
                print("    ⚠️ No se pudo enviar el mensaje a Telegram. Verifica que el Token y Chat ID sean válidos.")
        except Exception as exc:
            print(f"    ❌ Error al conectar con Telegram API: {exc}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
