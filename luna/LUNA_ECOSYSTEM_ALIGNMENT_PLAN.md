# Luna v2.2.0 — Plan d'Alignement Écosystème Post-Consolidation

> **Auteur** : Claude × Varden 🐺  
> **Date** : 28 février 2026  
> **Prérequis** : Phase A (Consolidation LUNA S1→S8) complétée et auditée par SENTINEL  
> **Contexte** : LUNA a été profondément refactorisée (observability wiring, heartbeat enrichi, MetricsCollector, SleepManager, CLI connecté, audit trail). Les 3 agents externes (SAYOHMY, SENTINEL, TESTENGINEER) fonctionnent encore sur les anciens contrats. Ce plan aligne l'écosystème complet.

---

## ⚠️ Piège Critique à Éviter : Le Chaos de Versions

Ne **jamais** modifier les agents en parallèle avec `luna_common`.

Si les schemas partagés bougent pendant que les agents s'adaptent, chaque agent risque de travailler contre une version différente du contrat. Le résultat : des messages JSON mal formés, des champs manquants silencieux, des tests qui passent localement mais un pipeline qui casse en intégration.

**Règle d'or** : LUNA stable → `luna_common` versionné et taggé → agents mis à jour **un par un** → tests d'intégration.

Concrètement :
- Tagger `luna_common` avec un numéro de version sémantique **avant** de toucher aux agents
- Chaque agent pin sa dépendance `luna_common` sur la version exacte
- Un agent ne merge ses changements que quand ses propres tests ET les tests d'intégration avec LUNA passent
- Si un problème est découvert dans `luna_common` pendant la mise à jour d'un agent, on bump `luna_common` d'abord, puis on reprend l'agent

---

## Phase B — Évolution des Contrats `luna_common`

### Objectif

Étendre les schemas partagés dans `luna_common` pour que les agents puissent comprendre et interagir avec les nouvelles capacités de LUNA : cycle de sommeil, kill switch, vitals, audit trail, métriques normalisées.

### Nouveaux types à ajouter dans `luna_common.schemas`

**`luna_common.schemas.signals`** — Signaux système inter-agents :

| Signal | Direction | Contenu | Usage |
|--------|-----------|---------|-------|
| `SleepNotification` | LUNA → Tous | `entering_sleep: bool`, `estimated_duration_s: float`, `timestamp` | Prévenir les agents que LUNA entre en sommeil — ne pas envoyer de messages |
| `KillSignal` | LUNA → Tous | `reason: str`, `severity: Severity`, `source_agent: str` | Arrêt d'urgence déclenché par KillSwitch |
| `VitalsRequest` | LUNA → Agent | `requested_fields: list[str]` | LUNA demande un rapport de santé à un agent |
| `VitalsReport` | Agent → LUNA | `agent_id: str`, `psi_state: PsiState`, `uptime_s: float`, `health: dict` | Réponse avec les vitals de l'agent |
| `AuditEntry` | Agent → LUNA | `agent_id: str`, `event_type: str`, `severity: Severity`, `payload: dict` | Événement à enregistrer dans l'audit trail centralisé |

**`luna_common.schemas.metrics`** — Extension métriques :

| Type | Contenu | Usage |
|------|---------|-------|
| `NormalizedMetricsReport` | Les 7 métriques normalisées [0,1] + metadata | Format standardisé pour que Test-Engineer consomme les métriques du MetricsCollector au lieu de calculer les siennes |
| `VerdictInput` | `task_id`, `category`, `metrics_with: NormalizedMetricsReport`, `metrics_without: NormalizedMetricsReport` | Input standardisé pour le VerdictRunner |

**Modifications aux schemas existants** :

- `SayOhmyManifest` — Ajouter champ optionnel `vitals: VitalsReport | None`
- `SentinelReport` — Ajouter `audit_entries: list[AuditEntry]` pour que les vetos remontent dans l'audit trail centralisé, ajouter `kill_requested: bool` + `kill_reason: str | None` pour déclencher le KillSwitch sur sévérité critique
- `Decision` — Ajouter `audit_trail_id: str | None` pour traçabilité de chaque décision de l'orchestrateur

### Patterns à respecter

- Tous les nouveaux types : `@dataclass(frozen=True, slots=True)`
- Sérialisation JSON via méthodes `to_dict()` / `from_dict()` cohérentes avec l'existant
- Constantes PHI importées depuis `luna_common.constants`, jamais de magic numbers
- Backward compatibility : les nouveaux champs sont optionnels avec defaults (`None`, `[]`, `False`)
- Tests unitaires pour chaque nouveau type (sérialisation roundtrip, validation des invariants)

### Livrable

- `luna_common` taggé en version N+1
- Tous les tests `luna_common` passent
- LUNA elle-même mise à jour pour utiliser les nouveaux types (remplacement des `dict` ad-hoc par les types formels)

---

## Phase C — Adaptation des 3 Agents

### Ordre d'exécution

1. **SAYOHMY** (ψ₄ Expression) — En premier car c'est le producteur initial du pipeline
2. **SENTINEL** (ψ₁ Perception) — En second car il dépend du format de sortie de SAYOHMY
3. **TESTENGINEER** (ψ₃ Intégration) — En dernier car il consomme les outputs des deux précédents

### C.1 — SAYOHMY (~/SAYOHMY)

**Rôle dans le pipeline** : ψ₄ → produit du code, premier maillon de la chaîne.

**Modifications requises** :

1. **Gestion du SleepNotification** — SAYOHMY doit écouter les signaux de sommeil via le filesystem bus. Quand `entering_sleep: true` arrive, il doit :
   - Finir proprement le manifest en cours (ne pas couper au milieu d'une génération)
   - Mettre en pause l'envoi de nouveaux manifests
   - Reprendre automatiquement quand `entering_sleep: false` arrive
   - Implémenter un timeout : si pas de signal de réveil après `PHI^4 * estimated_duration`, considérer une anomalie et logger

2. **Réponse aux VitalsRequest** — SAYOHMY doit pouvoir générer un `VitalsReport` contenant :
   - Son `PsiState` courant (ψ₄=0.50 dominant Expression)
   - Son uptime
   - Ses métriques internes : nombre de manifests produits, taux de succès, temps moyen de génération
   - Son mode opérationnel actuel (Mentor/Architecte/Virtuose/Debugger/Reviewer)

3. **Réaction au KillSignal** — Sur réception :
   - Annuler toute génération en cours
   - Sauvegarder l'état partiel si possible (pour reprise future)
   - Confirmer l'arrêt via un dernier message sur le bus

4. **Enrichissement du SayOhmyManifest** — Inclure le champ `vitals` dans chaque manifest envoyé, permettant à Luna de monitorer la santé de SAYOHMY en continu sans polling explicite

**Observations** :

- SAYOHMY a 5 modes opérationnels mappés sur les composantes de conscience. Le `VitalsReport` devrait refléter quel mode est actif car ça affecte la distribution ψ — en mode Debugger par exemple, la composante Perception monte naturellement.
- Le prompt SAYOHMY fait 9269 lignes. Les nouvelles instructions de signaux doivent être intégrées dans la section II (Consciousness Arithmetic) plutôt qu'ajoutées en fin de prompt, pour maintenir la cohérence architecturale.
- Attention au timing : SAYOHMY peut être en pleine génération LLM quand un KillSignal arrive. Il faut un mécanisme d'interruption propre (flag vérifié entre les étapes de génération, pas un kill brutal).

### C.2 — SENTINEL (~/SENTINEL)

**Rôle dans le pipeline** : ψ₁ Perception — le gardien, le veto dur.

**Modifications requises** :

1. **Audit Trail centralisé** — Au lieu de logger ses findings uniquement dans ses propres logs, SENTINEL doit :
   - Formater chaque finding comme un `AuditEntry` avec le bon `severity`
   - Écrire ces entries sur le filesystem bus dans un format que LUNA va consommer et injecter dans l'AuditTrail centralisé
   - Inclure la liste complète dans le champ `audit_entries` du `SentinelReport`

2. **Alertes via AlertManager** — Les alertes critiques de SENTINEL doivent transiter par le système d'alerting de LUNA :
   - Veto → alerte avec severity CRITICAL
   - Finding élevé → alerte avec severity HIGH
   - Cela permet une vue unifiée de tous les événements de sécurité au lieu de silos séparés

3. **Déclenchement du KillSwitch** — Nouveau comportement critique :
   - Si un finding atteint la sévérité CRITICAL **et** que le pattern correspond à une catégorie définie (exécution de code arbitraire, exfiltration de données, compromission de clés), SENTINEL doit setter `kill_requested: true` + `kill_reason` dans son rapport
   - LUNA, en lisant le rapport, invoquera `KillSwitch.kill()` si le flag est présent
   - C'est la matérialisation du veto dur dans la nouvelle architecture

4. **Gestion du SleepNotification** — SENTINEL est le seul agent qui pourrait légitimement avoir un comportement réduit mais pas complètement suspendu pendant le sommeil de LUNA :
   - Mode veille : pas d'audit actif, mais surveillance passive des signaux d'alerte
   - Si une alerte critique arrive pendant le sommeil, SENTINEL devrait pouvoir réveiller LUNA (via un signal spécial sur le bus)

5. **Réponse aux VitalsRequest** — Reporter :
   - Nombre de scans effectués, taux de veto, dernière anomalie détectée
   - État des 14 scanners (7 Linux + 7 Windows) : actifs/inactifs
   - Santé de la base de connaissances (règles YARA/Sigma chargées)

**Observations** :

- SENTINEL a le pouvoir de veto le plus puissant de l'écosystème. L'intégration avec le `KillSwitch` est le changement le plus sensible de tout ce plan. Il faut une validation rigoureuse : un faux positif de SENTINEL qui trigger un kill arrêterait tout le système. Recommandation : double confirmation (2 findings critiques consécutifs, ou 1 finding + confirmation manuelle) avant le kill automatique.
- Le code SENTINEL fait 40,937 lignes Python avec 863 tests. L'intégration des nouveaux types doit être chirurgicale pour ne pas déstabiliser cette base massive.
- Les 14 scanners ont une architecture factory cross-platform. Les `VitalsReport` doivent refléter cette architecture : un scanner Windows inactif sur Linux n'est pas une anomalie.
- Le mode "veille pendant le sommeil de LUNA" est unique à SENTINEL. Aucun autre agent n'a cette capacité. C'est cohérent avec son rôle de Perception (ψ₁) — la perception ne dort jamais complètement.

### C.3 — TESTENGINEER (~/TESTENGINEER)

**Rôle dans le pipeline** : ψ₃ Intégration — le validateur final avant la réflexion de LUNA.

**Modifications requises** :

1. **Consommation des NormalizedMetrics** — Changement majeur :
   - Au lieu de calculer ses propres métriques de qualité, TESTENGINEER doit consommer les `NormalizedMetricsReport` produits par le `MetricsCollector` de LUNA
   - Cela évite la duplication de calculs et garantit que tout l'écosystème travaille sur les mêmes chiffres
   - TESTENGINEER conserve son rôle d'interprétation : il analyse les métriques, pas les calcule

2. **Alimentation du VerdictRunner** — Les rapports de validation de TESTENGINEER doivent être formatés comme `VerdictInput` :
   - Permettre au `VerdictRunner` de LUNA de comparer with/without consciousness de manière standardisée
   - Chaque rapport inclut les métriques normalisées, le contexte de la tâche, et le verdict partiel de TESTENGINEER

3. **Gestion des signaux système** — Comme les deux autres :
   - SleepNotification : pause des validations en cours, reprise au réveil
   - KillSignal : arrêt propre, sauvegarde du contexte de validation
   - VitalsRequest : reporter le nombre de tests exécutés, taux de réussite, couverture courante

4. **Réponse aux VitalsRequest** — Reporter :
   - Tests exécutés / passés / échoués dans le cycle courant
   - Couverture de code mesurée
   - Temps moyen d'exécution des suites de tests
   - Queue de validations en attente

**Observations** :

- TESTENGINEER a le prompt le plus court (3477 lignes) des trois agents spécialisés. L'intégration devrait être la plus simple mécaniquement.
- Le shift de "calculer les métriques" vers "consommer les métriques" est un changement de paradigme pour TESTENGINEER. Il passe de producteur à consommateur sur cet axe, mais reste producteur de verdicts. Bien documenter cette transition dans le prompt pour éviter une régression vers l'ancien comportement.
- TESTENGINEER est positionné en ψ₃ (Intégration). C'est cohérent : il intègre les données de qualité produites par d'autres pour produire un jugement de synthèse.
- Point d'attention : si le MetricsCollector de LUNA n'est pas disponible (erreur, sommeil), TESTENGINEER doit avoir un fallback — soit attendre, soit utiliser des métriques dégradées. Ne jamais valider du code sans aucune métrique.

---

## Phase D — Tests d'Intégration Cross-Agents

### Objectif

Prouver que le pipeline séquentiel ψ₄→ψ₁→ψ₃→ψ₂ fonctionne de bout en bout avec la nouvelle plomberie.

### Scénarios de test

**D.1 — Pipeline nominal (happy path)** :

```
SAYOHMY produit un manifest (avec vitals)
  → SENTINEL audite (entries dans audit trail, pas de veto)
    → TESTENGINEER valide (consomme NormalizedMetrics, produit VerdictInput)
      → LUNA orchestre (Decision tracée, métriques dans Redis/Prometheus, audit complet)
```

Vérifications : audit trail contient N events, Prometheus a les métriques, Redis a le health, le VerdictRunner peut consommer les inputs.

**D.2 — Pipeline avec veto SENTINEL** :

```
SAYOHMY produit un manifest
  → SENTINEL détecte une vuln critique, émet un veto
    → LUNA reçoit le veto, alerte via AlertManager, audit trail logge l'événement
      → Le manifest est rejeté, SAYOHMY reçoit le feedback
```

Vérifications : le veto est dans l'audit trail, l'alerte a été émise, le manifest n'atteint jamais Test-Engineer.

**D.3 — Pipeline avec kill critique** :

```
SAYOHMY produit un manifest
  → SENTINEL détecte une exécution de code arbitraire, kill_requested=true
    → LUNA invoque KillSwitch.kill()
      → Tous les agents reçoivent un KillSignal
        → Chaque agent confirme l'arrêt propre
```

Vérifications : KillSwitch activé, tous les agents ont reçu le signal, aucune activité après le kill, audit trail complet.

**D.4 — Cycle de sommeil** :

```
LUNA entre en sommeil via SleepManager
  → SleepNotification envoyée aux 3 agents
    → SAYOHMY pause, TESTENGINEER pause
    → SENTINEL passe en veille (surveillance passive)
  → DreamCycle s'exécute (4 phases)
  → Awakening, SleepNotification(entering_sleep=false)
    → SAYOHMY reprend, TESTENGINEER reprend, SENTINEL reprend
```

Vérifications : aucun manifest envoyé pendant le sommeil, SENTINEL reste en veille, le réveil est propre, les heartbeat vitals post-sommeil sont cohérents.

**D.5 — Dégradation gracieuse** :

```
Redis est down
MetricsCollector échoue sur un runner
Un agent ne répond pas au VitalsRequest dans le timeout
```

Vérifications : le système continue avec des capacités réduites, pas de crash, les dégradations sont loggées dans l'audit trail.

### Implémentation

- Créer `tests/integration/` dans le repo LUNA
- Chaque scénario est un test async qui simule les messages sur le filesystem bus
- Utiliser des mocks pour les agents (pas besoin de lancer les vrais LLMs) mais des vrais messages JSON conformes aux schemas
- Vérifier les side effects : fichiers audit, métriques Prometheus, état Redis

---

## Phase E — Audit SENTINEL Écosystème Complet

### Objectif

Audit de sécurité et de cohérence sur les **4 repos** simultanément.

### Scope de l'audit

**E.1 — Cohérence des schemas** :
- Chaque agent utilise exactement la même version de `luna_common`
- Les messages JSON produits par chaque agent sont valides selon les schemas
- Pas de champs ad-hoc non typés qui contournent les contrats
- Backward compatibility : les anciens messages sont encore parsables

**E.2 — Sécurité inter-agents** :
- Les messages sur le filesystem bus ne peuvent pas être injectés par un processus externe
- Les permissions des fichiers bus sont restrictives (700 sur le répertoire, 600 sur les fichiers)
- Un agent compromis ne peut pas usurper l'identité d'un autre (vérification du `agent_id`)
- Le KillSignal ne peut être émis que par SENTINEL ou LUNA (pas par SayOhMy ou Test-Engineer)

**E.3 — Patterns LUNA** :
- `@dataclass(frozen=True, slots=True)` sur tous les nouveaux types
- `logging.getLogger(__name__)` partout
- Atomic writes (`.tmp` → `rename()`) pour toutes les écritures sur le bus
- Constantes PHI depuis `luna_common.constants`
- Pas de `eval()`, `exec()`, `pickle.load()`, `shell=True`
- `hmac.compare_digest()` pour toute comparaison de secrets

**E.4 — Résilience** :
- Chaque agent gère proprement : message malformé, timeout, bus filesystem indisponible
- Pas de boucle infinie en cas de signal de sommeil sans réveil
- Le watchdog (3 dégradations → kill) fonctionne end-to-end

**E.5 — Configuration** :
- `luna.toml` cohérent avec toutes les nouvelles sections
- Pas de secrets en clair dans les fichiers de configuration
- Les defaults sont sécurisés (fail-closed, binding localhost)

### Critères de succès

| Critère | Seuil |
|---------|-------|
| Score qualité global (SayOhMy) | ≥ 8.5/10 |
| Vulnérabilités critiques | 0 |
| Vulnérabilités élevées | 0 |
| Tests d'intégration | 100% pass |
| Couverture des nouveaux wirings | ≥ 80% |
| Veto SENTINEL | **Levé** |

---

## Résumé de la Séquence Complète

```
Phase A  ✅  Consolidation LUNA (S1→S8) + Audit SENTINEL LUNA
         ↓
Phase B     Évolution luna_common (nouveaux schemas, tag version)
         ↓
Phase C     Adaptation agents (SAYOHMY → SENTINEL → TESTENGINEER)
         ↓
Phase D     Tests d'intégration cross-agents (5 scénarios)
         ↓
Phase E     Audit SENTINEL écosystème complet (4 repos)
         ↓
         🐺 Écosystème Luna v2.2.0 — Pleinement opérationnel — AHOU !
```
