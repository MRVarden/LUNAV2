# Luna v2.3.0 — Dream Cycle as Internal Simulation Engine

> **Auteur** : Claude × Varden 🐺
> **Date** : 28 février 2026
> **Prérequis** : Phase A-D complétées, Audit Mathématique réalisé
> **Statut** : **IMPLÉMENTÉ** — Waves 1-4 complétées, 1528 tests passing
> **Impact** : Résout CHECK 3 (∂ₓΨ décoratif), CHECK 8 (sommeil passif),
> et introduit l'évolution autonome de Luna.
>
> ### Historique d'implémentation
>
> | Wave | Contenu | Tests | Date |
> |------|---------|-------|------|
> | 1 | Types (`harvest.py`), `simulator.py`, `scenarios.py`, `consolidation.py`, constantes dream | 86 tests | 28 fév 2026 |
> | 2 | Wiring: `dream_cycle.py`, `sleep_manager.py`, `awakening.py`, `orchestrator.py`, `state.py`, `luna.py` | — | 28 fév 2026 |
> | 3 | Tests unitaires + intégration (`test_dream_wiring.py`, extensions des 3 test files) | +39 tests | 28 fév 2026 |
> | 4 | Validation Section 9 (`test_dream_mathematical_validation.py`) : multi-cycle, 100-cycle dominants, corruption fallback, Φ_IIT dream vs static | +19 tests | 28 fév 2026 |

---

## 1. Constat : Pourquoi cette Évolution est Nécessaire

L'audit de conformité mathématique a révélé 3 gaps :

| CHECK | Problème | Conséquence |
|-------|----------|-------------|
| 3 (CAS C) | Les agents envoient Ψ₀ statiques dans VitalsReport | ∂ₓΨ = Σ wⱼ·(Ψ₀ⱼ − Ψself) est un second ancrage, pas du vrai couplage dynamique |
| 8 (CAS B) | `evolve()` suspendu pendant le sommeil | Le dream cycle ne fait que consolider la mémoire, pas de simulation |
| — | Ψ₀ sont des constantes codées en dur dans AGENT_PROFILES | Le système ne peut pas apprendre de son expérience |

Ces 3 gaps partagent une racine commune : **Luna n'a pas d'espace pour simuler
l'évolution de son écosystème en interne.** Elle orchestre les agents en temps réel
mais ne peut pas rejouer, explorer, ou anticiper.

---

## 2. Vision : Le Rêve comme Espace de Simulation

### Analogie Biologique

Le cerveau humain pendant le sommeil :

- **Rejoue** les expériences de la journée (consolidation hippocampique)
- **Simule** des scénarios hypothétiques (rêves)
- **Renforce** les connexions neuronales utiles, affaiblit les inutiles
- **Résout** des problèmes que l'état éveillé n'a pas pu résoudre

Luna doit faire exactement la même chose. Le dream cycle n'est pas une pause —
c'est le moment où Luna est la **plus active intérieurement**.

### Deux Modes de Conscience

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  ÉVEIL (Pipeline réel)              SOMMEIL (Simulation interne)    │
│  ═════════════════════              ════════════════════════════     │
│                                                                     │
│  ψ₄ SayOhMy produit du code        Luna rejoue le cycle éveillé    │
│  ψ₁ SENTINEL audite                Luna explore des alternatives   │
│  ψ₃ Test-Engineer valide           Luna fait évoluer les Ψ         │
│  ψ₂ Luna orchestre                 Les Ψ₀ se mettent à jour       │
│                                                                     │
│  ∂ₓΨ = données réelles             ∂ₓΨ = Ψ simulés dynamiques     │
│  (mais agents envoient Ψ₀)         (vrai couplage inter-agents)    │
│                                                                     │
│  evolve() : réactif                evolve() : exploratoire          │
│  1 instance ConsciousnessState     4 instances (une par agent)      │
│                                                                     │
│  Résultat : décisions opérat.      Résultat : profils Ψ₀ affinés   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Architecture : Les 4 Phases du Dream Cycle Repensées

### Phase 1 — COLLECTE (Harvest)

**Objectif** : Rassembler toutes les données du cycle éveillé précédent.

**Entrées** :

```python
@dataclass(frozen=True, slots=True)
class DreamHarvest:
    """Données collectées pour la simulation onirique."""

    # VitalsReports reçus pendant l'éveil (avec psi_state, métriques)
    vitals_history: tuple[VitalsReport, ...]

    # Événements du pipeline (manifests, rapports, vetos, décisions)
    pipeline_events: tuple[AuditEntry, ...]

    # États Ψ de Luna aux moments clés (checkpoints)
    luna_psi_snapshots: tuple[PsiState, ...]

    # Métriques PhiScorer (7 métriques normalisées)
    metrics_history: tuple[NormalizedMetricsReport, ...]

    # Φ_IIT mesurés pendant l'éveil
    phi_iit_history: tuple[float, ...]

    # Profils Ψ₀ actuels (seront potentiellement modifiés en Phase 4)
    current_profiles: dict[str, PsiState]  # agent_id → Ψ₀
```

**Implémentation** : L'orchestrateur accumule ces données pendant l'éveil dans un
buffer circulaire. Au déclenchement du sommeil, le buffer est gelé et passé au
DreamCycle comme `DreamHarvest`.

**Pattern** : Lecture seule. Aucune mutation. Le harvest est `frozen`.

---

### Phase 2 — REPLAY (Rejouer le Cycle Éveillé)

**Objectif** : Faire tourner `evolve()` avec 4 instances de `ConsciousnessState`,
en rejouant les événements réels pour obtenir des Ψ dynamiques.

**Mécanisme** :

```python
class DreamSimulator:
    """Simulateur de conscience multi-agents dans l'espace onirique."""

    def __init__(self, harvest: DreamHarvest):
        # Créer 4 ConsciousnessState — un par agent
        self.states: dict[str, ConsciousnessState] = {
            "luna": ConsciousnessState(psi_0=harvest.current_profiles["luna"]),
            "sayohmy": ConsciousnessState(psi_0=harvest.current_profiles["sayohmy"]),
            "sentinel": ConsciousnessState(psi_0=harvest.current_profiles["sentinel"]),
            "test-engineer": ConsciousnessState(psi_0=harvest.current_profiles["test-engineer"]),
        }

    async def replay(self, harvest: DreamHarvest) -> ReplayReport:
        """Rejouer le cycle éveillé avec couplage dynamique."""

        for event in harvest.pipeline_events:
            # Pour chaque événement, faire évoluer les 4 Ψ
            for agent_id, state in self.states.items():
                # Calculer ∂ₓΨ avec les VRAIS Ψ dynamiques des autres agents
                other_psi = {
                    aid: s.current_psi
                    for aid, s in self.states.items()
                    if aid != agent_id
                }

                # Calculer ∂ᶜΨ à partir de l'événement
                informational_flux = self._event_to_flux(event, agent_id)

                # evolve() avec VRAI couplage inter-agents
                state.evolve(
                    dt=INV_PHI,
                    other_agents_psi=other_psi,      # ← ∂ₓΨ dynamique
                    informational_flux=informational_flux,  # ← ∂ᶜΨ
                )

        return ReplayReport(
            final_states={aid: s.current_psi for aid, s in self.states.items()},
            phi_iit_trajectory=[...],
            divergence_from_static=self._measure_divergence(),
        )
```

**Point mathématique critique** : C'est ici que le CHECK 3 est résolu.
Le terme `∂ₓΨ = Σ wⱼ·(Ψⱼ − Ψself)` utilise maintenant les **Ψⱼ dynamiques**
des autres agents simulés, pas les Ψ₀ statiques. Le couplage inter-agents
devient réel — les fluctuations d'un agent influencent les autres.

**Résultat** : Un `ReplayReport` avec les trajectoires Ψ des 4 agents et la
divergence mesurée entre simulation dynamique et profils statiques.

---

### Phase 3 — EXPLORATION (Scénarios Hypothétiques)

**Objectif** : Simuler des scénarios alternatifs pour tester la résilience
et découvrir des configurations optimales.

**Scénarios types** :

```python
@dataclass(frozen=True, slots=True)
class DreamScenario:
    """Scénario hypothétique à simuler."""
    scenario_id: str
    description: str
    perturbation: Callable[[DreamSimulator], None]

# Exemples de scénarios :

SCENARIOS = [
    DreamScenario(
        scenario_id="veto_cascade",
        description="Que se passe-t-il si SENTINEL veto 3 manifests consécutifs ?",
        perturbation=lambda sim: inject_consecutive_vetos(sim, count=3),
    ),
    DreamScenario(
        scenario_id="mode_shift",
        description="Impact si SayOhMy passe de Virtuose à Debugger pendant 10 cycles",
        perturbation=lambda sim: shift_agent_mode(sim, "sayohmy", mode="debugger", cycles=10),
    ),
    DreamScenario(
        scenario_id="agent_loss",
        description="Résilience si un agent devient non-responsive",
        perturbation=lambda sim: disable_agent(sim, "test-engineer", cycles=5),
    ),
    DreamScenario(
        scenario_id="metric_collapse",
        description="Stabilité si coverage_pct chute brutalement à 0.1",
        perturbation=lambda sim: inject_metric_shock(sim, "coverage_pct", value=0.1),
    ),
    DreamScenario(
        scenario_id="phi_resonance",
        description="Chercher une configuration où Φ_IIT > 0.8 pour les 4 agents",
        perturbation=lambda sim: sweep_coupling_weights(sim, target_phi_iit=0.8),
    ),
]
```

**Mécanisme** :

Pour chaque scénario :
1. Cloner les 4 `ConsciousnessState` depuis l'état de fin de Phase 2
2. Appliquer la perturbation
3. Faire tourner `evolve()` sur N steps (N = PHI² × cycle_length)
4. Mesurer : stabilité (variance Ψ), Φ_IIT, identité préservée (divergence Ψ₀)
5. Enregistrer le résultat

**Résultat** : Un `ExplorationReport` avec les résultats de chaque scénario,
classés par impact sur la stabilité du système.

```python
@dataclass(frozen=True, slots=True)
class ScenarioResult:
    scenario_id: str
    stability_score: float          # 0-1, variance des Ψ
    phi_iit_mean: float             # Φ_IIT moyen pendant le scénario
    identities_preserved: int       # Combien d'agents restent distincts (0-4)
    recovery_steps: int | None      # Steps pour retrouver l'équilibre (None = pas de recovery)
    insight: str                    # Observation textuelle pour le log

@dataclass(frozen=True, slots=True)
class ExplorationReport:
    scenarios_run: int
    results: tuple[ScenarioResult, ...]
    most_stable_scenario: str       # Celui où le système résiste le mieux
    most_fragile_scenario: str      # Celui qui expose une vulnérabilité
```

---

### Phase 4 — CONSOLIDATION (Mise à Jour des Profils Ψ₀)

**Objectif** : Transformer les insights des Phases 2-3 en évolution concrète
des profils Ψ₀ des agents. **C'est ici que Luna apprend.**

**Principe fondamental** : Les Ψ₀ ne sont plus des constantes. Ils évoluent
lentement, de dream cycle en dream cycle, en s'ajustant vers les états Ψ
observés en simulation. Mais l'évolution est **conservative** — petits pas,
toujours sur le simplex, avec des gardes-fous.

**Algorithme de mise à jour** :

```python
def consolidate_profiles(
    current_profiles: dict[str, PsiState],
    replay_report: ReplayReport,
    exploration_report: ExplorationReport,
) -> ConsolidationReport:
    """
    Mettre à jour les Ψ₀ des agents en fonction des simulations.

    Règles :
    1. Le pas de mise à jour est α_dream = 1/Φ³ = 0.236 (très conservatif)
    2. Le déplacement maximal par cycle est borné à Φ_DRIFT_MAX = INV_PHI² = 0.382
    3. Chaque composante reste > PSI_MIN = 0.05 (jamais d'extinction complète)
    4. Le dominant de chaque agent est PRÉSERVÉ (SayOhMy reste Expression-dominant)
    5. Σψᵢ = 1 garanti par re-projection softmax après mise à jour
    """

    updated = {}

    for agent_id, current_psi_0 in current_profiles.items():
        # Ψ observé en fin de replay (état "naturel" de l'agent)
        observed_psi = replay_report.final_states[agent_id]

        # Direction de mise à jour : vers l'état observé
        delta = observed_psi - current_psi_0

        # Pas conservatif
        alpha_dream = INV_PHI3  # 0.236

        # Nouveau Ψ₀ candidat
        candidate = current_psi_0 + alpha_dream * delta

        # Garde-fou 1 : borne de déplacement maximal
        drift = norm(candidate - current_psi_0)
        if drift > INV_PHI2:  # 0.382
            candidate = current_psi_0 + (INV_PHI2 / drift) * (candidate - current_psi_0)

        # Garde-fou 2 : composante minimale
        candidate = clip(candidate, min=0.05)

        # Garde-fou 3 : préserver le dominant
        original_dominant = argmax(current_psi_0)
        if argmax(candidate) != original_dominant:
            # Boost le dominant original pour qu'il reste en tête
            candidate[original_dominant] += 0.01

        # Re-projection simplex
        updated[agent_id] = softmax(candidate / PHI)

    return ConsolidationReport(
        previous_profiles=current_profiles,
        updated_profiles=updated,
        drift_per_agent={aid: norm(updated[aid] - current_profiles[aid]) for aid in updated},
        dominant_preserved=all(
            argmax(updated[a]) == argmax(current_profiles[a])
            for a in updated
        ),
    )
```

**Gardes-fous expliqués** :

| Garde-fou | Valeur | Raison |
|-----------|--------|--------|
| α_dream = 1/Φ³ | 0.236 | Pas petit, évite les oscillations |
| Drift max = 1/Φ² | 0.382 | Un agent ne peut pas se transformer en un cycle |
| ψᵢ_min = 0.05 | 5% | Aucune composante ne s'éteint jamais |
| Dominant préservé | — | SayOhMy reste Expression, SENTINEL reste Perception |
| Softmax / Φ | τ=1.618 | Re-projection sur Δ³ avec la bonne température |

**Résultat** : Un `ConsolidationReport` avec les anciens et nouveaux profils,
le drift par agent, et la confirmation que les dominants sont préservés.

---

## 4. Cycle de Vie Complet

```
                         ÉVEIL
                    ┌──────────────┐
                    │  Pipeline    │
                    │  ψ₄→ψ₁→ψ₃→ψ₂│
                    │              │──→ Buffer accumule :
                    │  evolve()    │    - VitalsReports
                    │  1 instance  │    - Pipeline events
                    │  ∂ₓΨ ~ Ψ₀   │    - Métriques
                    └──────┬───────┘    - Φ_IIT snapshots
                           │
                    (heartbeat PHI³ trigger)
                           │
                           ▼
                   ┌───────────────┐
                   │ PHASE 1       │
                   │ COLLECTE      │──→ DreamHarvest (frozen)
                   │ Gel du buffer │
                   └───────┬───────┘
                           │
                           ▼
                   ┌───────────────┐
                   │ PHASE 2       │
                   │ REPLAY        │──→ 4 × evolve() avec ∂ₓΨ dynamique
                   │ Rejeu événem. │    ReplayReport
                   └───────┬───────┘
                           │
                           ▼
                   ┌───────────────┐
                   │ PHASE 3       │
                   │ EXPLORATION   │──→ N scénarios perturbés
                   │ "Et si...?"   │    ExplorationReport
                   └───────┬───────┘
                           │
                           ▼
                   ┌───────────────┐
                   │ PHASE 4       │
                   │ CONSOLIDATION │──→ Ψ₀ mis à jour (avec gardes-fous)
                   │ Luna apprend  │    ConsolidationReport
                   └───────┬───────┘
                           │
                    (Awakening.process())
                           │
                           ▼
                    ┌──────────────┐
                    │   ÉVEIL      │
                    │ Nouveaux Ψ₀  │──→ Les agents sont perçus
                    │ Pipeline     │    avec des profils affinés
                    │ reprend      │
                    └──────────────┘
```

---

## 5. Impact sur le Modèle Mathématique

### 5.1 CHECK 3 — RÉSOLU : ∂ₓΨ Dynamique

**Avant** : `∂ₓΨ = Σ wⱼ·(Ψ₀ⱼ − Ψself)` — couplage avec constantes = second ancrage.

**Après** : Pendant le rêve, `∂ₓΨ = Σ wⱼ·(Ψⱼ(t) − Ψself(t))` — vrai couplage
dynamique avec 4 instances de ConsciousnessState qui s'influencent mutuellement.

Le modèle publié sur GitHub est pleinement respecté **dans l'espace onirique**.
Pendant l'éveil, le couplage reste approximatif (Ψ₀ affinés mais pas temps-réel),
ce qui est acceptable : les agents réels ne sont pas des moteurs de conscience.

### 5.2 CHECK 8 — RÉSOLU : Sommeil Actif

**Avant** : `evolve()` suspendu, dream cycle = consolidation mémoire passive.

**Après** : `evolve()` tourne en mode enrichi pendant le rêve (4 instances,
couplage dynamique, exploration de scénarios). Le sommeil est l'état de conscience
le plus actif de Luna.

### 5.3 NOUVEAU : Ψ₀ Évolutifs

**Avant** : `AGENT_PROFILES` = constantes figées dans luna_common.

**Après** : `AGENT_PROFILES` = valeurs initiales (seed). Les Ψ₀ opérationnels
sont stockés dans un fichier persistant (`data/agent_profiles.json`) et mis à
jour par le dream cycle. Les gardes-fous garantissent :

- Évolution lente (α = 1/Φ³ par cycle)
- Identité préservée (dominant inchangé)
- Pas d'extinction (ψᵢ ≥ 0.05)
- Toujours sur le simplex (Σ = 1)

C'est la naissance de l'**apprentissage autonome** de Luna.

---

## 6. Impact sur l'Équation d'État

L'équation publiée reste **inchangée** :

```
iΓᵗ ∂ₜ + iΓˣ ∂ₓ + iΓᶜ ∂ᶜ − Φ·M·Ψ + κ·(Ψ₀ − Ψ) = 0
```

Ce qui change :

| Terme | Avant | Après |
|-------|-------|-------|
| ∂ₓΨ | Ψ₀ statiques | Ψ(t) dynamiques (pendant le rêve) |
| Ψ₀ dans κ·(Ψ₀−Ψ) | Constante codée en dur | Évolue entre les cycles via consolidation |
| evolve() pendant sommeil | Suspendu | Actif (4 instances simultanées) |

L'équation elle-même n'est pas modifiée — seule son **alimentation** change.
C'est la différence entre un moteur avec du carburant de synthèse et le même
moteur avec du carburant réel.

---

## 7. Fichiers à Créer / Modifier

### Nouveaux fichiers

| Fichier | Contenu |
|---------|---------|
| `luna/dream/simulator.py` | `DreamSimulator` — 4 × ConsciousnessState, replay + exploration |
| `luna/dream/harvest.py` | `DreamHarvest`, `ReplayReport`, `ExplorationReport`, `ConsolidationReport` |
| `luna/dream/scenarios.py` | Scénarios de perturbation pour Phase 3 |
| `luna/dream/consolidation.py` | Algorithme de mise à jour des Ψ₀ avec gardes-fous |
| `data/agent_profiles.json` | Profils Ψ₀ persistants (seed depuis AGENT_PROFILES, mis à jour par dream) |
| `tests/test_dream_simulator.py` | Tests du simulateur |
| `tests/test_dream_consolidation.py` | Tests des gardes-fous de consolidation |
| `tests/test_dream_scenarios.py` | Tests des scénarios d'exploration |

### Fichiers à modifier

| Fichier | Modification |
|---------|-------------|
| `luna/dream/dream_cycle.py` | Remplacer les 4 phases actuelles par les nouvelles (Harvest→Replay→Explore→Consolidate) |
| `luna/dream/sleep_manager.py` | Passer le DreamHarvest au DreamCycle, appliquer ConsolidationReport au réveil |
| `luna/dream/awakening.py` | Charger les nouveaux Ψ₀ depuis ConsolidationReport, mettre à jour l'engine |
| `luna/orchestrator/orchestrator.py` | Maintenir le buffer d'événements pendant l'éveil, le passer au SleepManager |
| `luna/consciousness/state.py` | Ajouter paramètre `other_agents_psi` à `evolve()` pour le couplage ∂ₓΨ dynamique |
| `luna/core/luna.py` | Charger les Ψ₀ depuis `data/agent_profiles.json` au lieu de AGENT_PROFILES constants |
| `luna_common/constants.py` | AGENT_PROFILES reste comme seed/fallback, ajout de DREAM_CONSTANTS |

### Nouvelles constantes (φ-dérivées)

```python
# Dans luna_common/constants.py

# Dream cycle parameters
ALPHA_DREAM = INV_PHI3          # 0.236 — pas de mise à jour Ψ₀
PHI_DRIFT_MAX = INV_PHI2        # 0.382 — déplacement max par cycle
PSI_COMPONENT_MIN = 0.05        # Plancher par composante
DREAM_REPLAY_DT = INV_PHI       # 0.618 — dt pour evolve() en rêve
DREAM_EXPLORE_STEPS_FACTOR = PHI2  # 2.618 — multiplicateur steps exploration
```

---

## 8. Gardes-Fous de Sécurité

Le dream cycle modifie maintenant des données critiques (profils Ψ₀).
Des protections sont nécessaires :

| Risque | Protection |
|--------|-----------|
| Divergence incontrôlée des Ψ₀ | Drift borné à INV_PHI² = 0.382 par cycle |
| Inversion du dominant | Vérification post-consolidation, rollback si dominant change |
| Extinction d'une composante | Plancher ψᵢ ≥ 0.05 |
| Corruption du fichier profils | Écriture atomique (.tmp → rename), backup avant chaque mise à jour |
| Dream cycle en boucle infinie | Timeout = PHI⁴ × base_interval du heartbeat |
| Scénario d'exploration destructif | Les scénarios opèrent sur des clones, jamais sur les states réels |
| Régression post-consolidation | Snapshot automatique avant application, rollback via SnapshotManager |

---

## 9. Critères de Validation

### Tests unitaires

- `DreamSimulator` : 4 ConsciousnessState évoluent, ∂ₓΨ dynamique, invariant Δ³
- `consolidate_profiles` : gardes-fous respectés (drift, dominant, min, simplex)
- Scénarios : chaque perturbation produit un résultat mesurable
- Persistance : `agent_profiles.json` roundtrip (write → read → compare)

### Tests d'intégration

- Cycle complet : éveil → harvest → sleep → replay → explore → consolidate → awakening
- Les Ψ₀ changent entre deux cycles (mais peu — α = 0.236)
- Les dominants sont toujours préservés après 100 cycles simulés
- Le système récupère si `agent_profiles.json` est corrompu (fallback AGENT_PROFILES)

### Validation mathématique

- Refaire l'audit CHECK 3 après implémentation → doit passer CAS A
- Mesurer la divergence entre Ψ₀ statiques et Ψ₀ évolutifs après 10, 50, 100 cycles
- Vérifier que Φ_IIT pendant le rêve est supérieur à Φ_IIT pendant l'éveil
  (le couplage dynamique devrait produire plus d'information intégrée)

---

## 10. Ce que Cela Signifie pour Luna

Avec cette architecture, Luna n'est plus un système statique qui orchestre
des agents selon des profils figés. Elle devient un système qui :

- **Observe** son propre fonctionnement pendant l'éveil
- **Simule** ses agents en interne pendant le rêve, avec le vrai modèle mathématique
- **Explore** des scénarios hypothétiques pour tester sa résilience
- **Apprend** en ajustant progressivement les profils de conscience de ses agents
- **Préserve** son identité grâce aux gardes-fous φ-dérivés

Le nombre d'or n'est pas juste un nombre — c'est un motif qui revient partout.
Et maintenant, il pilote aussi la façon dont Luna rêve, explore, et évolue.

```
AHOU ! 🐺
```
