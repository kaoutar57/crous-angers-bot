"""
Scraper pour trouverunlogement.lescrous.fr

Le site est une application JavaScript (SPA) qui appelle une API interne
(/api/fr/search/{tool_id}) pour charger les résultats. Plutôt que de parser
le HTML rendu (fragile, dépend du design), on utilise Playwright pour
charger la page normalement, puis on intercepte directement la réponse
JSON de cette API — c'est la donnée brute, fiable et complète (prix,
adresse, surface, équipements...).
"""

import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "https://trouverunlogement.lescrous.fr"
DEBUG_DIR = Path(__file__).parent / "debug"
SEARCH_API_RE = re.compile(r"/api/fr/search/(\d+)")
TOOL_ID_RE = re.compile(r"/tools/(\d+)/")


def _dismiss_cookie_banner(page):
    """Ferme le bandeau de consentement cookies (RGPD) s'il est présent.
    Sur les sites gouv.fr, ce bandeau peut bloquer le reste de la page
    tant qu'on n'a pas cliqué dessus."""
    page.wait_for_timeout(1200)
    selectors = [
        "#tarteaucitronPersonalize2All",
        "#tarteaucitronAllAllowed",
        "button:has-text('Tout accepter')",
        "button:has-text('Accepter tout')",
        "button:has-text('Accepter')",
        "button:has-text(\"J'accepte\")",
    ]
    for sel in selectors:
        try:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                btn.click(timeout=3000)
                print("🍪 Bandeau cookies fermé.")
                page.wait_for_timeout(1500)
                return True
        except Exception:
            continue
    return False


def _save_debug(page, api_responses):
    DEBUG_DIR.mkdir(exist_ok=True)
    try:
        page.screenshot(path=str(DEBUG_DIR / "page.png"), full_page=True)
        (DEBUG_DIR / "page.html").write_text(page.content(), encoding="utf-8")
        print(f"🔍 Debug sauvegardé dans {DEBUG_DIR}/ (screenshot + html)")
    except Exception as e:
        print(f"Impossible de sauvegarder le debug (screenshot/html) : {e}")

    if api_responses:
        api_dir = DEBUG_DIR / "api_responses"
        api_dir.mkdir(exist_ok=True)
        index_lines = []
        for i, (url, body, meta) in enumerate(api_responses):
            fname = f"response_{i}.json"
            meta_fname = f"response_{i}_request.txt"
            try:
                (api_dir / fname).write_text(body, encoding="utf-8")
                (api_dir / meta_fname).write_text(meta, encoding="utf-8")
            except Exception:
                pass
            index_lines.append(f"{fname} <- {url}")
        (DEBUG_DIR / "api_urls.txt").write_text("\n".join(index_lines), encoding="utf-8")
        print(f"🔍 {len(api_responses)} réponse(s) réseau JSON sauvegardée(s) dans {api_dir}/")
    else:
        print("🔍 Aucune réponse réseau JSON détectée pendant le chargement.")


def _parse_search_json(body: str, tool_id: str) -> list[dict]:
    """Transforme le JSON brut de l'API de recherche en liste de logements
    exploitables (id, titre, prix, surface, adresse, lien direct)."""
    data = json.loads(body)
    items = data.get("results", {}).get("items", [])
    listings = []

    for item in items:
        item_id = item.get("id")
        residence = item.get("residence", {})
        residence_label = residence.get("label", "Résidence CROUS")
        address = residence.get("address", "")
        room_label = item.get("label", "")
        area = item.get("area", {})
        area_min, area_max = area.get("min"), area.get("max")
        if area_min and area_max:
            area_str = f"{area_min} m²" if area_min == area_max else f"{area_min}–{area_max} m²"
        else:
            area_str = ""

        # Le loyer est en centimes ; on prend le mode d'occupation "alone"
        # en priorité, sinon le premier disponible.
        occupation_modes = item.get("occupationModes", [])
        rent_cents = None
        for mode in occupation_modes:
            if mode.get("type") == "alone":
                rent_cents = mode.get("rent", {}).get("min")
                break
        if rent_cents is None and occupation_modes:
            rent_cents = occupation_modes[0].get("rent", {}).get("min")

        price_str = f"{rent_cents / 100:.0f} €" if rent_cents is not None else "Prix non précisé"

        equipments = [e.get("label") for e in item.get("equipments", []) if e.get("label")]

        details_parts = [p for p in [address, area_str] if p]
        if equipments:
            details_parts.append(", ".join(equipments))

        link = f"{BASE_URL}/tools/{tool_id}/accommodations/{item_id}"

        listings.append({
            "id": str(item_id),
            "title": f"{residence_label}" + (f" — {room_label}" if room_label else ""),
            "price": price_str,
            "details": " | ".join(details_parts),
            "link": link,
        })

    return listings


def fetch_listings(search_url: str, headless: bool = True) -> list[dict]:
    """Retourne une liste de dicts : id, title, price, details, link."""
    api_responses: list[tuple[str, str, str]] = []
    search_json_body: str | None = None

    tool_id_match = TOOL_ID_RE.search(search_url)
    tool_id = tool_id_match.group(1) if tool_id_match else "47"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            locale="fr-FR",
            viewport={"width": 1366, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        def on_response(response):
            nonlocal search_json_body
            try:
                ctype = response.headers.get("content-type", "")
                if "application/json" in ctype and response.request.resource_type in ("xhr", "fetch"):
                    body = response.text()
                    req = response.request
                    meta = (
                        f"METHOD: {req.method}\n"
                        f"URL: {req.url}\n"
                        f"POST DATA: {req.post_data}\n"
                    )
                    api_responses.append((response.url, body, meta))
                    if SEARCH_API_RE.search(response.url):
                        search_json_body = body
            except Exception:
                pass  # certaines réponses ne sont pas lisibles (déjà consommées, etc.)

        page.on("response", on_response)

        try:
            page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            print(f"⚠️ Le chargement de la page a été lent/interrompu ({e}). "
                  "On continue quand même avec ce qui a été chargé.")

        page.wait_for_timeout(2000)
        _dismiss_cookie_banner(page)

        # Attend activement la réponse de l'API de recherche (jusqu'à 20s)
        elapsed = 0
        while search_json_body is None and elapsed < 20000:
            page.wait_for_timeout(1000)
            elapsed += 1000

        page_text = page.content().lower()
        if "trop nombreux" in page_text:
            print("⚠️ Le site indique 'Vous êtes trop nombreux' (limite de trafic). "
                  "Réessaie plus tard ou espace davantage les vérifications.")
            _save_debug(page, api_responses)
            browser.close()
            return []

        listings = []
        if search_json_body:
            try:
                listings = _parse_search_json(search_json_body, tool_id)
            except Exception as e:
                print(f"⚠️ Erreur en parsant la réponse de l'API de recherche : {e}")

        if not listings:
            _save_debug(page, api_responses)

        browser.close()

    return listings


if __name__ == "__main__":
    # Petit test manuel : `python scraper.py`
    import os

    from dotenv import load_dotenv

    load_dotenv()
    url = os.getenv("SEARCH_URL")
    if not url:
        raise SystemExit("Définis SEARCH_URL dans ton .env avant de tester.")

    found = fetch_listings(url, headless=False)
    print(f"{len(found)} logement(s) trouvé(s) :")
    for item in found:
        print(f"- {item['title']} | {item['price']} | {item['details']} | {item['link']}")