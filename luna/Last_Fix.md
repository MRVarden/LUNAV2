PRIORITÉ 1b — CLIs Agents (Blocker Pipeline)

Le PipelineRunner invoque les agents en sous-processus.

Seul SENTINEL a une CLI. SAYOHMY et TESTENGINEER n'en ont pas.

SENTINEL (référence) :

  ~/SENTINEL/sentinel_cli.py — click, commandes: scan, status, report, serve

  Invocation : python3 ~/SENTINEL/sentinel_cli.py scan --full

SAYOHMY — Créer ~/SAYOHMY/sayohmy_cli.py :

  Commandes nécessaires pour le pipeline :

  - generate --task <path> --output <path>

    → Lit un PipelineTask JSON, produit un SayOhmyManifest JSON

    → Utilise le mode approprié (parmi les 5 modes existants)

  - status → état de l'agent, version, mode actuel

  S'inspirer de sentinel_cli.py pour la structure (click + rich).

  Le manifest de sortie doit contenir : fichiers modifiés, diff, 

  description des changements, mode utilisé.

TESTENGINEER — Créer ~/TESTENGINEER/testengineer_cli.py :

  Commandes nécessaires pour le pipeline :

  - validate --manifest <path> --report <path> --output <path>

    → Lit le manifest SAYOHMY + le report SENTINEL

    → Lance les tests (pytest), mesure coverage, complexité

    → Produit un ValidationResult JSON

  - status → état de l'agent, version, métriques

  Le ValidationResult doit contenir : tests passed/failed, 

  coverage_pct, complexity_score, test_ratio, function_size_score.

  Ce sont les métriques qui nourrissent le PhiScorer.

ADAPTER le PipelineRunner (luna/pipeline/runner.py) :

  Les commandes d'invocation doivent correspondre aux vraies CLIs :

  - SAYOHMY : python3 ~/SAYOHMY/sayohmy_cli.py generate --task ... --output ...

  - SENTINEL : python3 ~/SENTINEL/sentinel_cli.py scan --full --output ...

  - TESTENGINEER : python3 ~/TESTENGINEER/testengineer_cli.py validate ...

  Les chemins sont dans luna.toml [pipeline] :

  sayohmy_path, sentinel_path, testengineer_path

Chaque agent doit avoir un __main__.py qui route vers sa CLI :

~/SAYOHMY/sayohmy/__main__.py :
    from sayohmy_cli import cli
    cli()

~/TESTENGINEER/testengineer/__main__.py :
    from testengineer_cli import cli
    cli()

~/SENTINEL a déjà sentinel_cli.py mais pas de __main__.py.
Créer ~/SENTINEL/sentinel/__main__.py :
    from sentinel_cli import cli
    cli()

Résultat : les 3 agents s'invoquent de manière uniforme :
    python3 -m sayohmy generate --task ... --output ...
    python3 -m sentinel scan --full --output ...
    python3 -m testengineer validate --manifest ... --output ...

Et le PipelineRunner utilise cette convention :
    subprocess: python3 -m {agent_name} {command} {args}

Cohérent avec Luna elle-même : python3 -m luna chat

Comme ça le PipelineRunner a une seule convention d'invocation : python3 -m {agent} {commande}. Propre, uniforme, testable.