"""
Scraper pour trouverunlogement.lescrous.fr

Le site est une application JavaScript (SPA) : les résultats de recherche
n'existent pas dans le HTML brut, ils sont injectés après coup par le
navigateur. On utilise donc Playwright (navigateur headless) plutôt que
`requests`.

Stratégie d'extraction : plutôt que de dépendre de noms de classes CSS
précis (qui peuvent changer à tout moment côté CROUS), on repère les liens
<a> dont le texte contient un prix ("xxx €"). Sur ce type de site, chaque
carte de résultat est généralement un lien cliquable qui contient à la fois
le titre, l'adresse/résidence et le prix.

Si l'extraction ne trouve rien, une capture d'écran + le HTML de la page
sont sauvegardés dans debug/ pour permettre d'ajuster les sélecteurs.
"""

import re
from pathlib import Path

from playwright.sync_api import sync_playwright

PRICE_RE = re.compile(r"(\d[\d\s]{1,6})\s?€")
BASE_URL = "https://trouverunlogement.lescrous.fr"
DEBUG_DIR = Path(__file__).parent / "debug"


def _save_debug(page, api_responses):
    DEBUG_DIR.mkdir(exist_ok=True)
    try:
        page.screenshot(path=str(DEBUG_DIR / "page.png"), full_page=True)
        (DEBUG_DIR / "page.html").write_text(page.content(), encoding="utf-8")
        print(f"🔍 Debug sauvegardé dans {DEBUG_DIR}/ (screenshot + html)")
    except Exception as e:
        print(f"Impossible de sauvegarder le debug (screenshot/html) : {e}")

    # Sauvegarde les réponses réseau de type JSON capturées pendant le
    # chargement : ça permet de voir si le site a une API interne qu'on
    # pourrait appeler directement, plus fiable que le scraping du DOM.
    if api_responses:
        api_dir = DEBUG_DIR / "api_responses"
        api_dir.mkdir(exist_ok=True)
        index_lines = []
        for i, (url, body) in enumerate(api_responses):
            fname = f"response_{i}.json"
            try:
                (api_dir / fname).write_text(body, encoding="utf-8")
            except Exception:
                pass
            index_lines.append(f"{fname} <- {url}")
        (DEBUG_DIR / "api_urls.txt").write_text("\n".join(index_lines), encoding="utf-8")
        print(f"🔍 {len(api_responses)} réponse(s) réseau JSON sauvegardée(s) dans {api_dir}/")
    else:
        print("🔍 Aucune réponse réseau JSON détectée pendant le chargement.")


def fetch_listings(search_url: str, headless: bool = True) -> list[dict]:
    """Retourne une liste de dicts : id, title, price, details, link."""
    results: dict[str, dict] = {}
    api_responses: list[tuple[str, str]] = []

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
            try:
                ctype = response.headers.get("content-type", "")
                if "application/json" in ctype and response.request.resource_type in ("xhr", "fetch"):
                    body = response.text()
                    api_responses.append((response.url, body))
            except Exception:
                pass  # certaines réponses ne sont pas lisibles (déjà consommées, etc.)

        page.on("response", on_response)

        # On n'attend PAS "networkidle" : certains sites gardent des connexions
        # ouvertes en permanence (analytics, polling...) et ça ne se termine
        # jamais. On attend juste le chargement du DOM, puis on laisse du
        # temps au JS pour peupler la page.
        try:
            page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            print(f"⚠️ Le chargement de la page a été lent/interrompu ({e}). "
                  "On continue quand même avec ce qui a été chargé.")

        page.wait_for_timeout(6000)

        # Message anti-bot connu du site CROUS
        page_text = page.content().lower()
        if "trop nombreux" in page_text:
            print("⚠️ Le site indique 'Vous êtes trop nombreux' (limite de trafic). "
                  "Réessaie plus tard ou espace davantage les vérifications.")
            _save_debug(page, api_responses)
            browser.close()
            return []

        anchors = page.query_selector_all("a")
        for a in anchors:
            href = a.get_attribute("href")
            text = (a.inner_text() or "").strip()
            if not href or not text:
                continue

            match = PRICE_RE.search(text)
            if not match:
                continue

            full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            title = lines[0] if lines else "Logement CROUS"
            price = match.group(1).replace(" ", "") + " €"

            results[full_url] = {
                "id": full_url,
                "title": title,
                "price": price,
                "details": " | ".join(lines[1:4]),
                "link": full_url,
            }

        if not results:
            _save_debug(page, api_responses)

        browser.close()

    return list(results.values())


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
        print(f"- {item['title']} | {item['price']} | {item['link']}")