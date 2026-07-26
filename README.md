# Bot de notification logements CROUS — Angers

Surveille l'API du CROUS pour Angers et envoie un email dès qu'un nouveau
logement apparaît, avec le prix, les détails et le lien direct.

## Comment ça marche

Le site `trouverunlogement.lescrous.fr` est une application JavaScript qui
appelle une API interne (`/api/fr/search/{tool_id}`) pour charger les
résultats. Le bot appelle **directement cette API en HTTP** (via la
librairie `requests`) — pas besoin de navigateur, pas de Playwright, pas
de Chromium à installer. C'est rapide, léger, et ça tourne sur à peu près
n'importe quel hébergement.

## Installation

```bash
cd crous-angers-bot
python -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate

pip install -r requirements.txt
```

C'est tout — pas d'étape `playwright install`, plus besoin.

## Configuration

```bash
cp .env.example .env
```

Puis édite `.env` :

- `SEARCH_URL` : l'URL de recherche copiée depuis la barre d'adresse du
  site (doit contenir `/tools/XX/` et `bounds=...`).
- `SMTP_*` / `EMAIL_*` : tes identifiants d'envoi d'email.

### Configurer Gmail comme expéditeur

1. Active la validation en 2 étapes sur ton compte Google.
2. Génère un "mot de passe d'application" ici :
   https://myaccount.google.com/apppasswords
3. Utilise ce mot de passe (pas ton mot de passe Gmail normal) dans
   `SMTP_PASSWORD`.

## Utilisation

**Une seule vérification** (idéal pour être lancé par une tâche planifiée) :

```bash
python main.py
```

**Mode boucle continue** :

```bash
python main.py --loop --interval 5
```

Le fichier `state.json` garde la mémoire des logements déjà notifiés.

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
minutes illimitées. Maintenant que le bot n'utilise plus Chromium, chaque
run dure environ 5-10 secondes — même avec un intervalle de 5 minutes
(≈ 8600 runs/mois), tu restes largement dans le quota gratuit, y compris
en dépôt privé.

## Alternative : héberger sur Wispbyte

Maintenant que le bot n'a plus besoin de navigateur (juste `requests` +
`python-dotenv`, quelques Mo), un hébergement léger comme
[Wispbyte](https://wispbyte.com) devient tout à fait viable — ce n'était
pas le cas avec la version Playwright, trop lourde pour ce type
d'hébergement gratuit.

**Mise en place (via le panel Wispbyte) :**

1. Crée un serveur avec l'egg **"Python"** (ou "Generic"), en choisissant
   une version Python récente (3.11+).
2. Upload tous les fichiers du projet **sauf** `venv/`, `debug/`,
   `__pycache__/` — via l'onglet fichiers du panel, ou en connectant le
   dépôt Git si l'option est proposée.
3. Configure les variables d'environnement dans l'onglet "Startup" ou
   "Variables" du panel (équivalent de ton `.env`) : `SEARCH_URL`,
   `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM`,
   `EMAIL_TO`.
4. Définis la commande de démarrage ("Startup Command") :
   ```
   pip install -r requirements.txt && python main.py --loop --interval 5
   ```
5. Démarre le serveur — comme c'est un process qui tourne en continu
   (`--loop`), pas besoin de cron ici, contrairement à GitHub Actions.

**Point d'attention :** vérifie les limites du plan gratuit de Wispbyte
(RAM, uptime garanti) au moment de la mise en place — les plans gratuits
évoluent et je n'ai pas un accès direct à leurs specs actuelles.
Contrairement à GitHub Actions, ce n'est pas un service géré par un grand
fournisseur cloud (Microsoft/GitHub) : à toi de juger le niveau de fiabilité
que tu attends pour un usage régulier.

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