"""
Test isolé de l'envoi d'email, indépendant du scraping.
Permet de vérifier que la config SMTP fonctionne sans dépendre de
l'existence de vrais logements disponibles quelque part.

Usage : python test_email.py
"""

import os

from dotenv import load_dotenv

from mailer import send_email

load_dotenv()

fake_listings_html = """
<html><body style="font-family:Arial,Helvetica,sans-serif;background:#f7f7f7;padding:20px;">
  <div style="max-width:600px;margin:auto;background:#fff;border-radius:8px;overflow:hidden;">
    <div style="background:#1565c0;color:#fff;padding:16px 20px;">
      <h2 style="margin:0;">🏠 TEST — Ceci est un email de test</h2>
    </div>
    <div style="padding:10px 20px;">
      <p>Si tu reçois cet email, ta configuration SMTP fonctionne correctement ✅</p>
      <table style="width:100%;border-collapse:collapse;">
        <tr>
          <td style="padding:14px;border-bottom:1px solid #e5e5e5;">
            <div style="font-size:16px;font-weight:bold;color:#222;">Studio T1 - Résidence Exemple (FICTIF)</div>
            <div style="color:#666;font-size:14px;margin:4px 0;">18m² | Angers centre</div>
            <div style="color:#0a7a2f;font-weight:bold;font-size:15px;">280 €</div>
            <a href="https://trouverunlogement.lescrous.fr" style="display:inline-block;margin-top:6px;
               color:#fff;background:#1565c0;padding:6px 12px;border-radius:4px;
               text-decoration:none;font-size:14px;">Voir le logement →</a>
          </td>
        </tr>
      </table>
    </div>
  </div>
</body></html>
"""

print("Envoi de l'email de test...")
print(f"  De   : {os.environ['EMAIL_FROM']}")
print(f"  Vers : {os.environ['EMAIL_TO']}")
print(f"  SMTP : {os.environ['SMTP_HOST']}:{os.environ['SMTP_PORT']}")

send_email(
    smtp_host=os.environ["SMTP_HOST"],
    smtp_port=int(os.environ["SMTP_PORT"]),
    smtp_user=os.environ["SMTP_USER"],
    smtp_password=os.environ["SMTP_PASSWORD"],
    email_from=os.environ["EMAIL_FROM"],
    email_to=os.environ["EMAIL_TO"],
    subject="🏠 TEST — Bot logements CROUS",
    html_body=fake_listings_html,
)

print("✅ Envoyé sans erreur. Vérifie ta boîte mail (et le dossier spam).")