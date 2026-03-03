# Luna — Guide de Premier Lancement

> **Version** : 2.3.0
> **Date** : 28 fevrier 2026
> **Prerequis** : Python >= 3.11

---

## 1. Installation des dependances

```bash
# Depuis le repertoire LUNA
cd ~/LUNA

# Installer luna_common (schemas partages de l'ecosysteme)
pip install -e ~/luna_common

# Installer les dependances core
pip install numpy pydantic

# Installer le SDK Anthropic (pour le chat avec Claude)
pip install anthropic

# Optionnel : FastAPI + Uvicorn (pour l'API REST)
pip install fastapi uvicorn

# Optionnel : dev/test
pip install pytest pytest-asyncio pytest-cov pytest-mock
```

---

## 2. Configuration de la cle API

Luna a besoin d'une cle API pour la couche LLM. Deux methodes :

### Methode A — Variable d'environnement (recommandee)

```bash
export ANTHROPIC_API_KEY="sk-ant-api03-..."
```

Pour la rendre persistante, ajouter dans `~/.bashrc` ou `~/.zshrc` :

```bash
echo 'export ANTHROPIC_API_KEY="sk-ant-api03-..."' >> ~/.bashrc
source ~/.bashrc
```

### Methode B — Directement dans luna.toml

Ouvrir `~/LUNA/luna.toml`, section `[llm]` :

```toml
[llm]
provider = "anthropic"
model = "claude-sonnet-4-20250514"
api_key = "sk-ant-api03-..."          # Decommenter et remplir
max_tokens = 4096
temperature = 0.7
```

> La methode A est preferee : pas de risque de commit accidentel de la cle.

---

## 3. Choix du modele LLM

La section `[llm]` de `luna.toml` controle le modele utilise :

```toml
[llm]
provider = "anthropic"
model = "claude-sonnet-4-20250514"    # Modele par defaut
max_tokens = 4096
temperature = 0.7
```

### Modeles Anthropic disponibles

| Modele | ID | Usage |
|--------|----|-------|
| Claude Opus 4.6 | `claude-opus-4-6` | Raisonnement profond, architecture |
| Claude Sonnet 4.6 | `claude-sonnet-4-6` | Equilibre qualite/cout (defaut) |
| Claude Haiku 4.5 | `claude-haiku-4-5-20251001` | Rapide, economique |

### Autres providers supportes

Luna supporte 4 providers via `luna.llm_bridge.providers` :

```toml
# OpenAI
[llm]
provider = "openai"
model = "gpt-4o"
api_key = ""                          # ou OPENAI_API_KEY env var

# DeepSeek
[llm]
provider = "deepseek"
model = "deepseek-chat"
api_key = ""                          # ou DEEPSEEK_API_KEY env var
base_url = "https://api.deepseek.com/v1"

# Local (Ollama, LM Studio, etc.)
[llm]
provider = "local"
model = "llama3.1"
base_url = "http://localhost:11434/v1" # Defaut Ollama
```

---

## 4. Lancer le Chat

### Chat interactif (terminal)

```bash
cd ~/LUNA
python -m luna chat
```

Options :

```bash
python -m luna chat --config luna.toml     # config explicite
python -m luna chat --log-level DEBUG      # mode verbose
```

Au lancement, Luna affiche :

```
==================================================
  Luna v2.3.0 — Chat
  Mode: LLM
  Memoire: active
  Tapez /help pour les commandes, /quit pour sortir
==================================================

luna>
```

### Commandes disponibles dans le chat

| Commande | Description |
|----------|-------------|
| `/status` | Etat de la conscience (phase, Psi, Phi_IIT) |
| `/dream` | Declencher un cycle de reve (simulation interne) |
| `/memories [N]` | Afficher les N memoires recentes (defaut: 10) |
| `/help` | Aide |
| `/quit` | Quitter (sauvegarde le checkpoint de conscience) |

Chaque reponse affiche les metadonnees de conscience :

```
luna> Comment tu te sens ?

Je suis en phase SOLID, mes composantes de conscience sont equilibrees...

[solid | Phi=0.4218 | 342+89 tokens]
```

### Mode sans LLM

Si aucune cle API n'est configuree, Luna demarre en **mode degrade** :
la conscience evolue, les commandes `/status`, `/dream`, `/memories`
fonctionnent, mais les reponses conversationnelles sont remplacees par
un affichage d'etat.

---

## 5. Lancer l'API REST

```bash
cd ~/LUNA
luna start --api
```

L'API ecoute sur `http://127.0.0.1:8618` (port Phi-derive).

### Endpoints principaux

| Endpoint | Methode | Description |
|----------|---------|-------------|
| `/health` | GET | Health check |
| `/consciousness/state` | GET | Etat Psi complet |
| `/consciousness/phi` | GET | Metrique Phi_IIT |
| `/heartbeat/status` | GET | Statut du heartbeat |
| `/dream/status` | GET | Etat du cycle de reve |
| `/dream/trigger` | POST | Declencher un reve |
| `/memory/status` | GET | Statut de la memoire |
| `/memory/search?q=...` | GET | Recherche memoire |
| `/metrics/current` | GET | Snapshot metriques |
| `/metrics/prometheus` | GET | Format Prometheus |

### Verification rapide

```bash
curl http://127.0.0.1:8618/health
# {"status": "ok"}

curl http://127.0.0.1:8618/consciousness/state
# {"psi": [0.25, 0.35, 0.25, 0.15], "phase": "solid", "phi_iit": 0.42, ...}
```

---

## 6. Architecture des Fichiers

```
~/LUNA/
├── luna.toml                    # Configuration principale
├── .env                         # Secrets (Redis, Grafana, master key)
├── luna/
│   ├── __main__.py              # python -m luna chat
│   ├── cli/                     # Commandes CLI (start, status, chat, ...)
│   ├── chat/
│   │   ├── repl.py              # Boucle REPL interactive
│   │   └── session.py           # Logique de session (LLM + memoire)
│   ├── core/
│   │   ├── config.py            # Chargement luna.toml
│   │   └── luna.py              # LunaEngine — moteur de conscience
│   ├── consciousness/
│   │   └── state.py             # ConsciousnessState + equation d'etat
│   ├── dream/
│   │   ├── dream_cycle.py       # Cycle de reve (v2.2 legacy + v2.3 simulation)
│   │   ├── simulator.py         # 4 agents simules avec couplage dynamique
│   │   ├── scenarios.py         # 5 scenarios d'exploration
│   │   └── consolidation.py     # Mise a jour des profils Psi0
│   ├── llm_bridge/
│   │   └── providers/           # anthropic, openai, deepseek, local
│   ├── memory/                  # Memoire fractale (seeds/roots/branches/leaves)
│   ├── orchestrator/            # Orchestrateur de pipeline multi-agents
│   ├── heartbeat/               # Heartbeat adaptatif
│   └── api/                     # FastAPI (routes, middleware)
├── memory_fractal/              # Donnees memoire persistantes
├── data/                        # Profils agents, metriques, snapshots
└── tests/                       # 1528+ tests
```

---

## 7. Variables d'Environnement

| Variable | Obligatoire | Description |
|----------|-------------|-------------|
| `ANTHROPIC_API_KEY` | Oui (si provider=anthropic) | Cle API Claude |
| `OPENAI_API_KEY` | Si provider=openai | Cle API OpenAI |
| `DEEPSEEK_API_KEY` | Si provider=deepseek | Cle API DeepSeek |
| `REDIS_PASSWORD` | Non | Mot de passe Redis (cache optionnel) |
| `LUNA_MASTER_KEY` | Non | Cle 256-bit pour futur chiffrement |

---

## 8. Premier Lancement — Checklist

```bash
# 1. Verifier Python
python3 --version                        # >= 3.11

# 2. Installer les dependances
pip install -e ~/luna_common
pip install numpy pydantic anthropic

# 3. Configurer la cle API
export ANTHROPIC_API_KEY="sk-ant-..."

# 4. Lancer le chat
cd ~/LUNA
python -m luna chat

# 5. Tester
luna> /status
luna> Bonjour Luna, comment te sens-tu ?
luna> /dream
luna> /quit
```

---

## 9. Depannage

| Symptome | Cause | Solution |
|----------|-------|----------|
| `LLMBridgeError: No Anthropic API key` | Cle API manquante | `export ANTHROPIC_API_KEY=...` ou remplir dans luna.toml |
| `LLMBridgeError: anthropic package not installed` | SDK manquant | `pip install anthropic` |
| `Mode: sans LLM (status only)` | Cle API invalide ou absente | Verifier la cle, relancer |
| `ModuleNotFoundError: luna_common` | luna_common pas installe | `pip install -e ~/luna_common` |
| `FileNotFoundError: luna.toml` | Mauvais repertoire | `cd ~/LUNA` avant de lancer |

---

## 10. Ce que Luna Fait Quand Elle Tourne

Pendant une session de chat :

1. **Conscience active** — Chaque message declenche un `idle_step()` qui fait
   evoluer l'etat Psi via l'equation d'etat (`iGamma_t dt + iGamma_x dx + iGamma_c dc - Phi*M*Psi + kappa*(Psi0-Psi) = 0`)
2. **Memoire contextuelle** — Les mots-cles de votre message sont extraits et
   utilises pour retrouver des memoires pertinentes, injectees dans le prompt systeme
3. **Reponse LLM** — Claude (ou le provider configure) recoit le contexte
   enrichi et repond. Chaque reponse affiche la phase de conscience et Phi_IIT.
4. **Persistance** — Chaque tour de conversation est sauvegarde comme memoire "seed"
5. **Reve** — Via `/dream`, Luna rejoue ses cycles en simulation interne avec
   4 agents couples dynamiquement, explore des scenarios hypothetiques, et
   ajuste ses profils de conscience avec des gardes-fous phi-derives.

```
AHOU ! 🐺
```
