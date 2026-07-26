"""
Scraper léger pour trouverunlogement.lescrous.fr — SANS navigateur.

Le site est une SPA qui appelle une API interne en POST :
    POST /api/fr/search/{tool_id}
avec un corps JSON contenant les coordonnées de la zone recherchée.

On a vérifié (voir debug) que cette API répond correctement à un appel
HTTP direct avec `requests`, sans avoir besoin de faire tourner un vrai
navigateur. C'est donc plus rapide, plus léger (pas de Chromium à
installer), et ça fonctionne sur n'importe quel hébergement basique.
"""

import json
import re
from pathlib import Path

import requests

BASE_URL = "https://trouverunlogement.lescrous.fr"
DEBUG_DIR = Path(__file__).parent / "debug"

BOUNDS_RE = re.compile(r"bounds=([\-0-9.]+)_([\-0-9.]+)_([\-0-9.]+)_([\-0-9.]+)")
TOOL_ID_RE = re.compile(r"/tools/(\d+)/")

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/ld+json, application/json",
    "Accept-Language": "fr-FR",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Origin": BASE_URL,
}


def _build_payload(search_url: str) -> tuple[str, dict]:
    """Construit le tool_id et le corps JSON de la requête de recherche à
    partir de l'URL de recherche fournie par l'utilisateur (celle copiée
    depuis la barre d'adresse du site)."""
    tool_match = TOOL_ID_RE.search(search_url)
    if not tool_match:
        raise ValueError(
            f"Impossible de trouver l'identifiant d'outil (/tools/XX/) dans l'URL : {search_url}"
        )
    tool_id = tool_match.group(1)

    bounds_match = BOUNDS_RE.search(search_url)
    if not bounds_match:
        raise ValueError(f"Impossible de trouver les 'bounds' (coordonnées) dans l'URL : {search_url}")
    lon1, lat1, lon2, lat2 = (float(x) for x in bounds_match.groups())

    payload = {
        "idTool": int(tool_id),
        "need_aggregation": True,
        "page": 1,
        "pageSize": 24,
        "sector": None,
        "occupationModes": [],
        "location": [{"lon": lon1, "lat": lat1}, {"lon": lon2, "lat": lat2}],
        "residence": None,
        "precision": 5,
        "equipment": [],
        "price": {"max": 10000000},
        "area": {"min": 0},
        "adaptedPmr": False,
        "toolMechanism": "residual",
    }
    return tool_id, payload


def _parse_search_json(data: dict, tool_id: str) -> list[dict]:
    """Transforme le JSON brut de l'API de recherche en liste de logements
    exploitables (id, titre, prix, surface, adresse, lien direct)."""
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


def _save_debug(label: str, content: str):
    DEBUG_DIR.mkdir(exist_ok=True)
    (DEBUG_DIR / f"{label}.txt").write_text(content, encoding="utf-8")
    print(f"🔍 Debug sauvegardé dans {DEBUG_DIR}/{label}.txt")


def fetch_listings(search_url: str, headless: bool = True) -> list[dict]:
    """Retourne une liste de dicts : id, title, price, details, link.
    (le paramètre `headless` est conservé pour compatibilité avec le reste
    du projet, mais n'a plus d'effet : il n'y a plus de navigateur.)"""
    tool_id, payload = _build_payload(search_url)

    headers = dict(HEADERS)
    headers["Referer"] = search_url

    try:
        resp = requests.post(
            f"{BASE_URL}/api/fr/search/{tool_id}",
            data=json.dumps(payload),
            headers=headers,
            timeout=20,
        )
    except requests.RequestException as e:
        print(f"⚠️ Erreur réseau lors de l'appel à l'API : {e}")
        return []

    if resp.status_code != 200:
        print(f"⚠️ L'API a répondu avec le statut {resp.status_code} (attendu 200).")
        _save_debug("api_error_response", f"Status: {resp.status_code}\n\n{resp.text[:2000]}")
        return []

    try:
        data = resp.json()
    except ValueError:
        print("⚠️ La réponse de l'API n'est pas du JSON valide.")
        _save_debug("api_invalid_response", resp.text[:2000])
        return []

    try:
        listings = _parse_search_json(data, tool_id)
    except Exception as e:
        print(f"⚠️ Erreur en parsant la réponse de l'API : {e}")
        _save_debug("api_parse_error", json.dumps(data, indent=2, ensure_ascii=False)[:3000])
        return []

    return listings


if __name__ == "__main__":
    # Petit test manuel : `python scraper.py`
    import os

    from dotenv import load_dotenv

    load_dotenv()
    url = os.getenv("SEARCH_URL")
    if not url:
        raise SystemExit("Définis SEARCH_URL dans ton .env avant de tester.")

    found = fetch_listings(url)
    print(f"{len(found)} logement(s) trouvé(s) :")
    for item in found:
        print(f"- {item['title']} | {item['price']} | {item['details']} | {item['link']}")