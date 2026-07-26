# Bot de notification logements CROUS — Angers

Surveille la page de recherche de logements du CROUS pour Angers et envoie
un email dès qu'un nouveau logement apparaît, avec le prix, les détails et
le lien direct.

## ⚠️ À savoir avant de commencer

- Le site `trouverunlogement.lescrous.fr` est une application JavaScript :
  le scraper utilise donc un vrai navigateur headless (Playwright), pas de
  simple requête HTTP.
- Le site affiche parfois un message **"Vous êtes trop nombreux"** en cas
  de forte affluence. C'est un mécanisme anti-surcharge du site — le script
  le détecte et réessaiera au prochain passage. **Ne mets pas un intervalle
  trop court** (15–30 minutes est raisonnable) pour rester correct vis-à-vis
  du site et éviter d'être bloqué.
- Le HTML du site peut changer sans préavis. Le scraper est volontairement
  écrit de façon "générique" (il repère les liens contenant un prix "xxx €")
  plutôt que de dépendre de classes CSS précises, mais si CROUS refait leur
  site, il faudra l'ajuster. En cas de souci, lance `python scraper.py`
  (voir plus bas) : si rien n'est trouvé, un screenshot + le HTML de la page
  sont sauvegardés dans `debug/` pour comprendre ce qui a changé.

## Installation

```bash
cd crous-angers-bot
python -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium     # télécharge le navigateur headless
```

## Configuration

```bash
cp .env.example .env
```

Puis édite `.env` :

- `SEARCH_URL` : déjà pré-rempli avec ton URL Angers.
- `SMTP_*` / `EMAIL_*` : tes identifiants d'envoi d'email.

### Configurer Gmail comme expéditeur

1. Active la validation en 2 étapes sur ton compte Google.
2. Génère un "mot de passe d'application" ici :
   https://myaccount.google.com/apppasswords
3. Utilise ce mot de passe (pas ton mot de passe Gmail normal) dans
   `SMTP_PASSWORD`.

(Tu peux aussi utiliser n'importe quel autre fournisseur SMTP : Outlook,
OVH, Infomaniak, etc. — change juste `SMTP_HOST` / `SMTP_PORT`.)

## Utilisation

**Une seule vérification** (idéal pour être lancé par une tâche planifiée) :

```bash
python main.py
```

**Mode boucle continue** (le script tourne et vérifie toutes les X minutes) :

```bash
python main.py --loop --interval 20
```

**Mode debug** (affiche le navigateur pour voir ce qu'il se passe) :

```bash
python main.py --show-browser
```

Le fichier `state.json` garde la mémoire des logements déjà notifiés, pour
ne jamais renvoyer deux fois le même email.

## Planifier des vérifications automatiques

### Linux / macOS (cron)

```bash
crontab -e
```

Ajoute (vérification toutes les 20 minutes) :

```
*/20 * * * * cd /chemin/vers/crous-angers-bot && /chemin/vers/venv/bin/python main.py >> log.txt 2>&1
```

### Windows (Planificateur de tâches)

Crée une tâche qui exécute :

```
venv\Scripts\python.exe main.py
```

toutes les 20 minutes, avec comme "Démarrer dans" le dossier du projet.

### Alternative : GitHub Actions (gratuit, pas besoin de laisser un PC allumé)

Le fichier `.github/workflows/check.yml` fait tourner le bot toutes les
30 minutes directement sur les serveurs de GitHub — pas besoin de laisser
ton PC allumé.

**Mise en place :**

1. Crée un nouveau dépôt sur GitHub (public de préférence, voir remarque
   sur les minutes plus bas) et pousse-y tout le contenu de ce dossier
   **sauf `.env`** (ne commit jamais tes identifiants en clair — le
   `.gitignore` ci-dessous s'en charge).

   ```bash
   git init
   echo -e "venv/\n.env\ndebug/\n__pycache__/" > .gitignore
   git add .
   git commit -m "Bot logements CROUS Angers"
   git branch -M main
   git remote add origin https://github.com/TON_PSEUDO/TON_DEPOT.git
   git push -u origin main
   ```

2. Dans le dépôt GitHub : **Settings → Secrets and variables → Actions →
   New repository secret**, ajoute un secret pour chacune de ces clés
   (avec les mêmes valeurs que dans ton `.env`) :

   - `SEARCH_URL`
   - `SMTP_HOST`
   - `SMTP_PORT`
   - `SMTP_USER`
   - `SMTP_PASSWORD`
   - `EMAIL_FROM`
   - `EMAIL_TO`

3. Va dans l'onglet **Actions** du dépôt, tu devrais voir le workflow
   "Vérification logements CROUS". Lance-le une première fois manuellement
   (bouton "Run workflow") pour vérifier que tout fonctionne, puis il
   tournera automatiquement toutes les 30 minutes.

4. À chaque run, `state.json` est automatiquement mis à jour et recommité
   dans le dépôt — c'est comme ça que le bot se souvient des logements déjà
   notifiés d'une exécution à l'autre.

**⚠️ Budget de minutes gratuites :** sur un compte GitHub gratuit, un dépôt
**privé** a droit à 2000 minutes/mois gratuites ; un dépôt **public** a des
minutes illimitées. Comme Chromium doit être installé à chaque run (même
avec le cache activé dans le workflow, il faut installer ses dépendances
système), reste prudent avec l'intervalle si ton dépôt est privé : 30 min
convient bien, 15 min ferait probablement dépasser le quota gratuit. Aucune
donnée sensible n'est exposée si le dépôt est public — seuls les résultats
de la recherche CROUS (déjà publics) et le code sont visibles, jamais tes
identifiants SMTP (stockés en tant que secrets chiffrés).

## Structure du projet

```
crous-angers-bot/
├── main.py         # orchestrateur (scraping + diff + email)
├── scraper.py       # extraction des logements avec Playwright
├── mailer.py         # envoi d'email SMTP
├── state.json         # logements déjà notifiés (créé automatiquement)
├── .env               # ta config (à créer depuis .env.example)
└── debug/             # captures de debug si l'extraction échoue
```