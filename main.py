import argparse
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from mailer import send_email
from scraper import fetch_listings

load_dotenv()

STATE_FILE = Path(__file__).parent / "state.json"


def load_seen_ids() -> set[str]:
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text(encoding="utf-8")))
    return set()


def save_seen_ids(ids: set[str]) -> None:
    STATE_FILE.write_text(
        json.dumps(sorted(ids), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def build_email_html(new_listings: list[dict]) -> str:
    rows = ""
    for l in new_listings:
        rows += f"""
        <tr>
          <td style="padding:14px;border-bottom:1px solid #e5e5e5;">
            <div style="font-size:16px;font-weight:bold;color:#222;">{l['title']}</div>
            <div style="color:#666;font-size:14px;margin:4px 0;">{l['details']}</div>
            <div style="color:#0a7a2f;font-weight:bold;font-size:15px;">{l['price']}</div>
            <a href="{l['link']}" style="display:inline-block;margin-top:6px;
               color:#fff;background:#1565c0;padding:6px 12px;border-radius:4px;
               text-decoration:none;font-size:14px;">Voir le logement →</a>
          </td>
        </tr>
        """
    return f"""
    <html><body style="font-family:Arial,Helvetica,sans-serif;background:#f7f7f7;padding:20px;">
      <div style="max-width:600px;margin:auto;background:#fff;border-radius:8px;overflow:hidden;">
        <div style="background:#1565c0;color:#fff;padding:16px 20px;">
          <h2 style="margin:0;">🏠 Nouveaux logements CROUS – Angers</h2>
        </div>
        <div style="padding:10px 20px;">
          <p>{len(new_listings)} nouveau(x) logement(s) détecté(s) :</p>
          <table style="width:100%;border-collapse:collapse;">{rows}</table>
        </div>
      </div>
    </body></html>
    """


def run_once(search_url: str) -> None:
    seen = load_seen_ids()
    listings = fetch_listings(search_url)
    print(f"{len(listings)} logement(s) trouvés sur la page de recherche.")

    new_listings = [l for l in listings if l["id"] not in seen]

    if new_listings:
        print(f"➡️  {len(new_listings)} nouveau(x) logement(s) — envoi de l'email...")
        html = build_email_html(new_listings)
        send_email(
            smtp_host=os.environ["SMTP_HOST"],
            smtp_port=int(os.environ["SMTP_PORT"]),
            smtp_user=os.environ["SMTP_USER"],
            smtp_password=os.environ["SMTP_PASSWORD"],
            email_from=os.environ["EMAIL_FROM"],
            email_to=os.environ["EMAIL_TO"],
            subject=f"🏠 {len(new_listings)} nouveau(x) logement(s) CROUS – Angers",
            html_body=html,
        )
        print("📧 Email envoyé.")
    else:
        print("Rien de nouveau cette fois-ci.")

    # On mémorise tous les logements vus (nouveaux + anciens) pour ne plus
    # les renotifier la prochaine fois.
    save_seen_ids(seen | {l["id"] for l in listings})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bot de notification logements CROUS")
    parser.add_argument("--loop", action="store_true", help="Tourner en continu (sinon: une seule vérification, pour cron)")
    parser.add_argument("--interval", type=int, default=int(os.getenv("CHECK_INTERVAL_MINUTES", 15)), help="Minutes entre deux vérifications en mode --loop")
    args = parser.parse_args()

    search_url = os.getenv("SEARCH_URL")
    if not search_url:
        raise SystemExit("❌ SEARCH_URL n'est pas défini. Copie .env.example vers .env et remplis-le.")

    if args.loop:
        print(f"🔁 Mode boucle : vérification toutes les {args.interval} minutes. Ctrl+C pour arrêter.")
        while True:
            try:
                run_once(search_url)
            except Exception as e:
                print(f"⚠️ Erreur pendant la vérification : {e}")
            time.sleep(args.interval * 60)
    else:
        run_once(search_url)