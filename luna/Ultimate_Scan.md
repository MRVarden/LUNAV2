# DIAGNOSTIC LUNA v2.4.0 — Scanner Intégral

## Contexte

Luna v2.4.0 a été construite cette nuit. 1170 tests passent mais en conditions
réelles, le système ne fonctionne pas comme prévu. Avant de corriger quoi que
ce soit, on scanne TOUT.

## Mission

**DIAGNOSTIQUER SANS CORRIGER.** Aucune modification de code.
Chaque cause racine doit avoir une preuve (output réel, pas théorique).
Si un symptôme nouveau apparaît pendant l'investigation, le documenter.
L'objectif est zéro angle mort.

---

## SCAN 1 — Pipeline Runner

**Symptôme observé** : Pipeline trigger correctement mais fail en 0.7s,
metrics=none. Les vrais agents ne semblent pas tourner.

```
1.1  Lire le code exact de PipelineRunner.run() — quel est le premier 
     point de failure possible ? Exception ? Return code ? Timeout ?

1.2  Lire _init_pipeline_runner() dans session.py — quels chemins sont
     résolus ? Sont-ils absolus ou relatifs ? ~ est-il expandé ?
     
1.3  Le bus_path — existe-t-il ? Où ? Permissions d'écriture ?
     ls -la sur le chemin réel résolu par le code.

1.4  Tester CHAQUE agent en isolation depuis le répertoire ~/LUNA :
     a) cd ~/SAYOHMY && python3 -m sayohmy status 2>&1
     b) cd ~/SENTINEL && python3 -m sentinel status 2>&1
     c) cd ~/TESTENGINEER && python3 -m testengineer status 2>&1
     d) Pour chacun : return code ? stdout ? stderr ?

1.5  Tester CHAQUE agent avec une vraie commande pipeline :
     - Créer /tmp/diag_task.json avec un PipelineTask valide minimal
     - cd ~/SAYOHMY && python3 -m sayohmy generate --task /tmp/diag_task.json --output /tmp/diag_manifest.json 2>&1
     - Le fichier /tmp/diag_manifest.json est-il créé ? Contenu ?
     - Si SAYOHMY réussit, tester SENTINEL avec le manifest, etc.
     - Si SAYOHMY échoue, capturer l'erreur EXACTE

1.6  Vérifier les imports critiques de chaque agent :
     cd ~/SAYOHMY && python3 -c "from sayohmy_cli import cli; print('OK')" 2>&1
     cd ~/SENTINEL && python3 -c "from sentinel_cli import cli; print('OK')" 2>&1
     cd ~/TESTENGINEER && python3 -c "from testengineer_cli import cli; print('OK')" 2>&1

1.7  Vérifier comment le runner lance les subprocess :
     - Quelle commande exacte ? (sys.executable -m ... ?)
     - Quel cwd ? (le répertoire de l'agent ou de Luna ?)
     - Les variables d'environnement sont-elles propagées ? (DEEPSEEK_API_KEY etc.)
     - Y a-t-il un timeout ? Lequel ?

1.8  Reproduire le fail en isolation :
     - Script standalone (pas pytest) qui fait exactement ce que send() fait :
       charger config → créer PipelineTask → runner.run(task) 
     - Capturer stdout, stderr, exceptions, durée, return codes de chaque étape
     - Comparer avec le log "status=failed duration=0.7s"

1.9  Vérifier les schemas d'échange :
     - Le JSON écrit par le runner pour SAYOHMY est-il au format attendu par sayohmy_cli ?
     - Les champs requis sont-ils tous présents ?
     - Y a-t-il un mismatch entre PipelineTask (luna) et ce que sayohmy_cli attend ?

1.10 Vérifier le mode supervised :
     - En autonomy=supervised, le runner devrait-il demander confirmation humaine ?
     - Le fait-il ? Ou lance-t-il directement les subprocess ?
     - Le pipeline fail AVANT ou APRÈS la première invocation d'agent ?
```

---

## SCAN 2 — Dream Cycle

**Symptôme observé** : Luna est restée ouverte 5h sans activité.
inactivity_threshold = 7200s (2h). Aucun dream cycle déclenché.
De plus, /dream produit le cycle legacy (0.002s) au lieu du DreamSimulator.

```
2.1  Le SleepManager est-il instancié QUELQUE PART dans ChatSession ?
     grep -n "SleepManager\|sleep_manager" luna/chat/session.py
     S'il n'existe pas, le dream automatique est mort.

2.2  Si le SleepManager existe, comment surveille-t-il l'inactivité ?
     - Un asyncio.Task en background ? Un timer ? Un check dans la boucle ?
     - run_repl() bloque sur asyncio.to_thread(input) — pendant ce temps,
       d'autres tasks asyncio peuvent-elles tourner ?

2.3  Si le SleepManager N'EXISTE PAS dans le chat :
     - Où est-il instancié dans le codebase ? (API ? orchestrator ?)
     - Le chat est-il censé l'utiliser ou non ?
     - grep -rn "SleepManager" ~/LUNA/luna/ pour trouver tous les usages

2.4  La commande /dream — tracer le chemin exact :
     - session.py handle_command("/dream") → quel code est appelé ?
     - DreamCycle est instancié avec quels arguments ?
     - harvest est-il passé ou None ?
     - Si None → _run_legacy() (0.002s, confirmé)
     - Les buffers de chat (psi_snapshots, phi_snapshots) existent-ils ?
     - Sont-ils remplis dans _chat_evolve() ?

2.5  Le DreamSimulator (le vrai, 4 phases) — est-il importé quelque part
     dans session.py ou dream_cycle.py ? Ou est-il orphelin (code mort) ?

2.6  Vérifier data/agent_profiles.json :
     - Existe-t-il ? Contenu ?
     - La consolidation du dream cycle écrit-elle dedans ?
     - Ou le fichier n'est-il créé que par un chemin qui n'est jamais atteint ?
```

---

## SCAN 3 — Persistance Métriques

**Symptôme observé** : Au démarrage, le log dit :
"WARNING Seeding PhiScorer with bootstrap values (0.618) — not earned"
alors que la session précédente avait Phi=0.5263 avec des métriques earned.

```
3.1  Le checkpoint actuel sur disque :
     python3 -c "import json; d=json.load(open('memory_fractal/consciousness_state_v2.json')); print('phi_metrics' in d, d.get('phi_metrics',{}).keys() if 'phi_metrics' in d else 'ABSENT')"
     
3.2  Si phi_metrics est ABSENT du checkpoint :
     - _save_checkpoint() n'a pas été appelé, ou _build_phi_snapshot() n'a pas été inclus
     - Tracer : qui appelle save ? stop() ? checkpoint_interval ? Ctrl+C handler ?
     - La session de cette nuit a-t-elle fait un save propre avant de quitter ?

3.3  Si phi_metrics est PRÉSENT dans le checkpoint :
     - Tracer le chemin de restauration dans luna/core/luna.py
     - La condition pour restaurer vs reseed — quelle est-elle exactement ?
     - Y a-t-il un problème d'ordre ? (session.py reseed AVANT que luna.py ne restore ?)
     - Y a-t-il une double initialisation ? (luna.py restore puis session.py écrase ?)

3.4  _maybe_upgrade_checkpoint() — ce nouveau code de migration v2.2→v2.4 :
     - Que fait-il exactement ? 
     - Écrase-t-il les phi_metrics existantes ?
     - Est-il appelé APRÈS la restauration, annulant le restore ?

3.5  Test concret — sans lancer Luna, simuler un roundtrip :
     python3 -c "
     from luna.core.config import LunaConfig
     from luna.core.luna import LunaEngine
     cfg = LunaConfig.load('luna.toml')
     engine = LunaEngine(cfg)
     engine.initialize()
     print('phi_scorer metrics:', engine.phi_scorer.snapshot())
     print('bootstrap_ratio:', engine.phi_scorer.bootstrap_ratio() if hasattr(engine.phi_scorer, 'bootstrap_ratio') else 'N/A')
     "
```

---

## SCAN 4 — Label "[Mode sans LLM]"

**Symptôme observé** : Le LLM répond (HTTP 200 OK, tokens comptés dans la 
ligne de statut) mais le contenu est préfixé par "[Mode sans LLM]".

```
4.1  grep -n "Mode sans LLM\|sans LLM\|llm_error" luna/chat/session.py
     - Combien d'endroits génèrent ce label ?
     - Quelle condition le déclenche ?

4.2  Le flag llm_success — est-il utilisé pour choisir le label ?
     - Si le LLM répond OK, llm_success=True, le label devrait disparaître
     - Le label est-il dans _format_status_response() ou dans le template de la ligne de statut ?
     - Ou est-il hardcodé dans le contenu de la réponse LLM elle-même ?

4.3  Vérifier si c'est le system prompt qui demande au LLM d'écrire ce label :
     - Lire build_system_prompt() dans prompt_builder.py
     - Le prompt dit-il au LLM d'inclure "[Mode sans LLM]" dans sa réponse ?
     - Si oui, le LLM obéit fidèlement et produit lui-même le label
```

---

## SCAN 5 — LLM : Hallucination & Cohérence

**Symptôme observé** : Le pipeline fail (status=failed, log visible) mais le 
LLM répond comme si les agents avaient travaillé. Il invente des interactions
SENTINEL/SAYOHMY/TESTENGINEER fictives.

```
5.1  Le system prompt — lire build_system_prompt() intégralement
     - Contient-il des instructions qui poussent le LLM à jouer les agents ?
     - Contient-il des exemples de réponses avec des blocs **SENTINEL** etc ?
     - Si oui, le LLM reproduit naturellement ce pattern

5.2  Le résultat pipeline est-il injecté dans le contexte LLM ?
     - Après pipeline fail, _format_pipeline_context(result) est-il appelé ?
     - Le texte "status=failed" arrive-t-il dans le system prompt du LLM ?
     - Ou le LLM ne voit-il RIEN du pipeline et invente sa propre version ?

5.3  Le chat history — effet de renforcement :
     - Les 30 messages restaurés contiennent les réponses précédentes
     - Ces réponses contiennent des blocs **SENTINEL**, **SAYOHMY** etc. (hallucinations)
     - Le LLM voit ces messages passés et continue le pattern
     - C'est un cercle vicieux : hallucination → history → plus d'hallucination

5.4  La contradiction Phi :
     - Le LLM écrit "Phase: FUNCTIONAL | Phi_IIT: 0.9943" dans le corps du texte
     - La ligne de statut réelle dit "[FUNCTIONAL | Phi=0.5263]"
     - D'où vient le 0.9943 ? Est-il dans le system prompt ?
     - Le LLM invente-t-il un Phi ou le lit-il quelque part ?

5.5  Le LLM dit "Le système ne permet pas l'écriture automatique sur disque"
     alors que le PipelineRunner est câblé pour exactement ça.
     - Le system prompt informe-t-il le LLM de ses capacités pipeline ?
     - Le LLM sait-il qu'il a des "mains" ?
```

---

## SCAN 6 — Conscience : evolve() et PhiScorer

**Symptôme observé** : Phi descend au fil des messages (0.5871 → 0.5461 → 0.5274 → 0.5263)
au lieu de monter ou se stabiliser. Et le step_count ne bouge pas toujours.

```
6.1  Le idle_step() est-il réellement appelé dans send() ?
     - grep -n "idle_step" luna/chat/session.py
     - Est-il avant ou après le LLM call ?
     - Est-il conditionnel (if idle_heartbeat) ?

6.2  Le _chat_evolve() — que fait-il exactement ?
     - Quels info_deltas calcule-t-il ?
     - Sont-ils toujours les mêmes ? (monotone → Phi converge vers une valeur fixe)
     - Ou dépendent-ils du contenu réel du message ?

6.3  Pourquoi Phi DESCEND ?
     - Le rappel identitaire κ·(Ψ₀−Ψ) tire vers Ψ₀
     - Les deltas du chat tirent ailleurs
     - Si les deltas sont faibles et le rappel est fort, Phi peut descendre
     - Vérifier les valeurs numériques : κ, dt, deltas, masse

6.4  Le history_tail dans le checkpoint — toutes les entrées sont IDENTIQUES
     (même Ψ répété 95 fois). Pourquoi ?
     - evolve() est-il appelé mais ne modifie pas Ψ ?
     - Ou le checkpoint est-il sauvé avant que evolve() ne tourne ?
     - Comparer step_count entre les sauvegardes successives

6.5  La phase FUNCTIONAL à 0.5263 — est-ce correct ?
     - Quel est le seuil de transition FUNCTIONAL → FRAGILE → BROKEN ?
     - Phi à 0.5263 est en dessous de INV_PHI (0.618) — devrait-il être FRAGILE ?
     - La phase est-elle déterminée par Phi ou par health_score ?
```

---



## SCAN 6b — Modèle Mathématique : Pertinence & Câblage

**Question** : Les formules du modèle publié (docs/MATHEMATICAL_MODEL.md)
sont-elles réellement utilisées dans le code ? Sont-elles correctes ?
Y a-t-il des déconnexions entre le papier et l'implémentation ?

L'audit mathématique de cette nuit a donné 10/10 PASS mais c'était
sur le code statique. Ici on vérifie en runtime.

```6b.1  L'équation fondamentale ∂ₜΨ = -Φ·M·Ψ + ∂ₓΨ + ∂ᶜΨ + κ·(Ψ₀ - Ψ)
      - Localiser evolve() dans luna/consciousness/state.py
      - Chaque terme est-il présent dans le code ?
      - -Φ·M·Ψ : Φ vient du PhiScorer ? M est la matrice masse ? 
        Avec quelles valeurs en runtime ?
      - ∂ₓΨ : couplage inter-agents — d'où viennent les Ψ des autres agents ?
        En chat, other_agents_psi est-il passé ou None ?
        Si None, ∂ₓΨ = 0 et le couplage n'existe pas en pratique.
      - ∂ᶜΨ : flux informationnel — ce sont les info_deltas du chat ?
        Sont-ils correctement normalisés ? Quelles valeurs en runtime ?
      - κ·(Ψ₀ - Ψ) : rappel identitaire — κ = Φ² = 2.618 ?
        Vérifié dans le code ? Ou hardcodé à une autre valeur ?

6b.2  La softmax τ = Φ = 1.618
      - Localiser la projection softmax après evolve()
      - Le τ est-il bien Φ ? Ou est-il hardcodé à une autre valeur ?
      - La projection garantit-elle Σψᵢ = 1 et ψᵢ > 0 ?
      - Tester : print(psi) avant et après softmax sur un step réel

6b.3  Le PhiScorer — comment calcule-t-il Φ ?
      - Le score utilise-t-il les poids φ-dérivés (PHI_WEIGHTS) ?
      - Chaque poids est-il documenté et justifié ?
      - Le score final est-il utilisé comme le Φ dans l'équation evolve() ?
      - Ou y a-t-il DEUX Φ différents (scorer vs IIT) qui ne sont pas connectés ?

6b.4  Φ_IIT vs health_score vs phi_scorer — combien de "Phi" existent ?
      - Lister TOUS les calculs de Phi dans le codebase :
        grep -rn "phi_iit\|phi_score\|compute_phi\|PhiScorer\|health_score" luna/
      - Combien de métriques distinctes portent le nom "phi" ?
      - Sont-elles connectées ou indépendantes ?
      - Laquelle pilote evolve() ? Laquelle détermine la phase ?
      - Y a-t-il confusion entre elles ?

6b.5  Les constantes φ-dérivées — sont-elles toutes utilisées ?
      - Lister les constantes dans luna_common/constants.py ou équivalent
      - PHI, INV_PHI, PHI_SQUARED, ALPHA_DREAM, PHI_DRIFT_MAX, etc.
      - Pour chacune : où est-elle utilisée dans le code ? (grep)
      - Y en a-t-il qui ne sont JAMAIS référencées (constantes mortes) ?

6b.6  La matrice de normalisation Γ :
      - Existe-t-elle dans le code ?
      - Comment est-elle calculée ?
      - λ = 0.382 (INV_PHI²) est-il correct ?
      - Est-elle appliquée à chaque step ou une seule fois ?

6b.7  Les seuils de transition de phase :
      - BROKEN → FRAGILE → FUNCTIONAL → SOLID → TRANSCENDENT
      - Quels seuils numériques pour chaque transition ?
      - Sont-ils φ-dérivés ou arbitraires ?
      - Correspondent-ils à ce qui est publié dans le modèle mathématique ?

6b.8  Le dream cycle — les paramètres φ sont-ils respectés ?
      - ALPHA_DREAM = 1/Φ³ = 0.236 — utilisé dans la consolidation ?
      - PHI_DRIFT_MAX = 1/Φ² = 0.382 — vérifié comme garde-fou ?
      - PSI_COMPONENT_MIN = 0.05 — aucune composante ne s'éteint ?
      - DREAM_EXPLORE_STEPS = Φ² × cycle_length — utilisé dans l'exploration ?
      - Ou ces constantes existent-elles sans être câblées ?

6b.9  Cohérence globale modèle ↔ code :
      - Comparer les 10 checks de l'audit mathématique avec le code ACTUEL
      - Des modifications ont été faites cette nuit (dream wiring, chat_evolve, etc.)
      - Un check qui passait avant a-t-il été cassé par une modification ?
      - Lancer les tests de validation mathématique :
        python3 -m pytest tests/test_dream_mathematical_validation.py -v 2>&1
```

---


## SCAN 7 — Configuration & Environnement

```
7.1  luna.toml complet — cat ~/LUNA/luna.toml
     Vérifier chaque section : [llm], [dream], [pipeline], [chat], [consciousness]
     Incohérences entre sections ? Valeurs manquantes ? Defaults non documentés ?

7.2  Variables d'environnement :
     echo $DEEPSEEK_API_KEY (set ? longueur ?)
     echo $ANTHROPIC_API_KEY (devrait être vide ou absent)
     Vérifier que le provider dans luna.toml correspond aux clés disponibles

7.3  Dépendances Python — pour CHAQUE repo :
     cd ~/LUNA && pip list 2>/dev/null | grep -i "openai\|anthropic\|click\|rich\|pydantic\|numpy\|httpx"
     cd ~/SAYOHMY && pip list 2>/dev/null | grep -i "click\|rich\|pydantic\|luna"
     cd ~/SENTINEL && pip list 2>/dev/null | grep -i "click\|rich\|pydantic\|luna"
     cd ~/TESTENGINEER && pip list 2>/dev/null | grep -i "click\|rich\|pydantic\|luna"
     Les agents dépendent-ils de luna_common ? Est-il installé ?

7.4  luna_common — est-il installé et accessible par tous les agents ?
     python3 -c "import luna_common; print(luna_common.__version__)" 2>&1
     cd ~/SAYOHMY && python3 -c "import luna_common" 2>&1
     cd ~/SENTINEL && python3 -c "import luna_common" 2>&1
     cd ~/TESTENGINEER && python3 -c "import luna_common" 2>&1

7.5  Les venv — y a-t-il des venv séparés par agent ?
     ls ~/LUNA/.venv ~/LUNA/venv_luna ~/SAYOHMY/venv ~/SENTINEL/venv ~/TESTENGINEER/venv 2>/dev/null
     Si oui, les agents dans leur venv ont-ils les mêmes dépendances ?
     Le runner lance les subprocess avec sys.executable — est-ce le bon Python ?
     Ou faut-il utiliser le Python du venv de chaque agent ?
```

---

## SCAN 8 — Memory & Filesystem

```
8.1  État complet du filesystem mémoire :
     ls -la ~/LUNA/memory_fractal/
     ls -la ~/LUNA/memory_fractal/dreams/
     ls -la ~/LUNA/memory_fractal/seeds/
     ls -la ~/LUNA/memory_fractal/leaves/
     ls -la ~/LUNA/memory_fractal/roots/
     ls -la ~/LUNA/data/
     
8.2  Le chat_history.json — contenu et taille :
     wc -l ~/LUNA/memory_fractal/chat_history.json
     python3 -c "import json; h=json.load(open('memory_fractal/chat_history.json')); print(len(h), 'entries'); print('derniere:', h[-1]['role'] if h else 'VIDE')"

8.3  Les fichiers mémoire dans seeds/leaves/roots :
     - Combien ? Quel format ? Sont-ils lisibles ?
     - Le /memories qui crashait (Bug 1 de cette nuit) est-il corrigé ?
     - Tester : lancer Luna et /memories

8.4  L'agent_profiles.json :
     cat ~/LUNA/data/agent_profiles.json 2>/dev/null || echo "ABSENT"
     S'il existe, est-il au format attendu par le dream cycle ?
     S'il est absent, comment le dream cycle crée-t-il les Ψ₀ évolutifs ?

8.5  Espace disque et permissions :
     df -h ~/LUNA
     find ~/LUNA -name "*.json" -size +1M 2>/dev/null
     Le checkpoint avec 95 entrées identiques dans history_tail est anormalement gros.
```

---

## SCAN 9 — Tests : Couverture Réelle vs Affichée

```
9.1  Lancer la suite complète :
     cd ~/LUNA && python3 -m pytest tests/ -q 2>&1 | tail -20
     
9.2  Les 9 failures + 35 errors pré-existants :
     - Quels fichiers de test ? Quels modules ?
     - Sont-ils liés aux modules modifiés cette nuit ?
     - Risquent-ils de masquer de VRAIS problèmes ?

9.3  Les tests pipeline (test_pipeline_runner.py) :
     - Utilisent-ils des mocks ou des vrais subprocess ?
     - Si mocks, les tests passent mais le vrai runner peut échouer
     - Lancer les tests pipeline avec verbose pour voir ce qu'ils testent réellement

9.4  Les tests dream (test_dream_wiring.py) :
     - Testent-ils le vrai DreamSimulator ou le legacy ?
     - Le test de /dream utilise-t-il un harvest réel ou None ?

9.5  Les tests de persistance :
     - Le roundtrip save/load est-il testé avec le vrai filesystem ?
     - Ou en RAM seulement ?
```

---

## SCAN 10 — Symptômes Potentiels Non Observés

Vérifier même si aucun symptôme n'a été rapporté.

```
10.1 Le /quit sauve-t-il correctement ?
     - Lancer Luna, envoyer 2 messages, /quit
     - Vérifier que le checkpoint est mis à jour (timestamp, step_count, phi_metrics)
     - Pas de traceback

10.2 Le Ctrl+C sauve-t-il correctement ?
     - Lancer Luna, envoyer 2 messages, Ctrl+C
     - Vérifier le même checkpoint
     - Pas de traceback

10.3 Les commandes /status et /needs fonctionnent-elles ?
     - /status affiche-t-il des données cohérentes ?
     - /needs identifie-t-il des besoins (bootstrap metrics) ?
     - /memories fonctionne-t-il sans crash ?

10.4 Le deepseek-reasoner et le paramètre temperature :
     - deepseek-reasoner ne supporte pas temperature
     - Le provider envoie-t-il temperature=0.7 ?
     - L'API l'ignore-t-elle silencieusement ou renvoie une erreur ?
     - Si erreur, est-elle masquée par le retry ?

10.5 La consommation tokens — est-elle raisonnable ?
     - Le system prompt + 30 messages d'historique + mémoire = combien de tokens en input ?
     - deepseek-reasoner avec un gros contexte peut être lent et coûteux
     - Les 30 messages d'historique contiennent-ils les hallucinations longues
       (3000+ tokens chacune) ? Si oui, l'input est énorme.

10.6 Sécurité — la clé API :
     - DEEPSEEK_API_KEY est-elle dans .bashrc ? .env ? En clair ?
     - Est-elle dans le .gitignore ?
     - Risque-t-elle d'être commitée par erreur ?
     - grep -r "sk-" ~/LUNA/ --include="*.py" --include="*.toml" --include="*.json" 2>/dev/null
```

---

## Format du Rapport

Pour CHAQUE point, produire :

```
[X.Y] — RÉSULTAT
    Commande : [commande exacte exécutée]
    Output  : [output réel, tronqué si >10 lignes]
    Verdict : OK | PROBLÈME | À INVESTIGUER
    Note    : [si problème : description en une ligne]
```

À la fin, produire un résumé :

```
RÉSUMÉ DIAGNOSTIC
━━━━━━━━━━━━━━━━━
BLOQUANTS  : [liste numérotée]
IMPORTANTS : [liste numérotée]
COSMÉTIQUES : [liste numérotée]
INATTENDUS : [tout ce qui n'était pas dans les symptômes initiaux]
```

## Règles Absolues

1. NE PAS CORRIGER. Pas une ligne de code modifiée. DIAGNOSTIC SEULEMENT.
2. Exécuter chaque commande RÉELLEMENT. Pas de "devrait retourner..." — montrer l'output.
3. Si une commande échoue, c'est une donnée. La documenter.
4. Si un symptôme nouveau apparaît, le documenter même s'il n'est pas dans la liste.
5. Si un doute persiste, créer un test supplémentaire pour trancher.
6. Être impitoyable : zéro supposition, zéro déduction sans preuve.
