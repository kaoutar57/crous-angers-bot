"""
Test : peut-on appeler l'API du CROUS directement en HTTP (sans Playwright) ?

Ce script relit les fichiers de debug déjà générés par le scraper
(debug/api_responses/response_X_request.txt) pour retrouver la requête
EXACTE que le site fait lui-même (méthode, URL, corps de la requête), et
la rejoue avec `requests` pour voir si ça fonctionne sans navigateur.

Prérequis : avoir déjà lancé `python main.py --show-browser` au moins une
fois avec des résultats trouvés (pour avoir un fichier de debug qui
contient bien la requête vers /api/fr/search/47).

Usage : python test_api_direct.py
"""

import json
import re
from pathlib import Path

import requests

DEBUG_DIR = Path(__file__).parent / "debug" / "api_responses"
SEARCH_API_RE = re.compile(r"/api/fr/search/\d+")


def find_search_request():
    """Retrouve le fichier de requête correspondant à l'API de recherche."""
    if not DEBUG_DIR.exists():
        raise SystemExit(
            "❌ Aucun dossier debug/api_responses trouvé. "
            "Lance d'abord `python main.py --show-browser` avec une URL "
            "qui a des résultats (ex: Corte), pour générer les fichiers de debug."
        )

    for meta_file in sorted(DEBUG_DIR.glob("*_request.txt"), key=lambda f: f.stat().st_mtime, reverse=True):
        content = meta_file.read_text(encoding="utf-8")
        if SEARCH_API_RE.search(content):
            return content

    raise SystemExit(
        "❌ Aucune requête vers /api/fr/search/ trouvée dans debug/api_responses. "
        "Relance le scraper avec une URL qui a des résultats."
    )


def parse_request_meta(content: str):
    method = re.search(r"METHOD: (.+)", content).group(1).strip()
    url = re.search(r"URL: (.+)", content).group(1).strip()
    # Important : pas de re.DOTALL ici. Le corps POST tient sur une seule
    # ligne dans le fichier de debug ; capturer au-delà (avec DOTALL)
    # récupérait aussi le texte qui suit et corrompait le JSON envoyé.
    post_data_match = re.search(r"^POST DATA: (.*)$", content, re.MULTILINE)
    post_data = post_data_match.group(1).strip() if post_data_match else None
    if post_data == "None":
        post_data = None
    return method, url, post_data


def main():
    content = find_search_request()
    method, url, post_data = parse_request_meta(content)

    print(f"Méthode capturée : {method}")
    print(f"URL capturée     : {url}")
    print(f"Corps capturé    : {post_data}\n")

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": "https://trouverunlogement.lescrous.fr/",
        "Origin": "https://trouverunlogement.lescrous.fr",
    }

    print("Envoi de la requête directe (sans navigateur)...")
    if method.upper() == "POST":
        resp = requests.post(url, data=post_data, headers=headers, timeout=20)
    else:
        resp = requests.get(url, headers=headers, timeout=20)

    print(f"\nStatus code : {resp.status_code}")
    try:
        data = resp.json()
        total = data.get("results", {}).get("total", {}).get("value")
        print(f"✅ Réponse JSON valide. Nombre de logements trouvés : {total}")
        print("\nExtrait de la réponse :")
        print(json.dumps(data, indent=2, ensure_ascii=False)[:800])
    except Exception as e:
        print(f"❌ La réponse n'est pas du JSON exploitable : {e}")
        print("Contenu brut (premiers 500 caractères) :")
        print(resp.text[:500])


if __name__ == "__main__":
    main()