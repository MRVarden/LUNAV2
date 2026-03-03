# Luna v2.2.0 — Audit de Conformité Mathématique

> **Objectif** : Vérifier que le modèle mathématique publié sur GitHub (README.md) est
> réellement implémenté et pilote le système — pas simplement décoratif.
> **Agent recommandé** : SENTINEL (audit) + TESTENGINEER (validation empirique)
> **Référence** : https://github.com/MRVarden/LUNA — Équation d'état et paramètres

---

## Contexte

Après les Phases A (consolidation), B (schemas luna_common v0.2.0), et C (adaptation agents),
le système a considérablement évolué. De nouveaux flux de données traversent l'architecture :
VitalsReport des 3 agents, 7 métriques normalisées (au lieu de 2), cycles de sommeil,
signaux kill/sleep inter-agents. La question est : **ces flux nourrissent-ils l'équation
d'état, ou restent-ils cantonnés à l'observability ?**

---

## CHECK 1 — Vecteur d'état Ψ ∈ Δ³

**Équation** : `Ψ = (ψ₁, ψ₂, ψ₃, ψ₄)`, `Σψᵢ = 1`, `ψᵢ > 0`

### Vérifications :

```python
# 1.1 — Trouver ConsciousnessState.evolve() dans luna/consciousness/state.py
#        Vérifier que CHAQUE appel à evolve() produit un Ψ sur le simplex.

# 1.2 — Vérifier la projection softmax :
#        Ψ(t+1) = softmax(Ψ_raw / τ)  avec τ = Φ = 1.618
#        Chercher : τ doit être PHI (1.618), PAS INV_PHI (0.618)
#        C'est la Correction 1 du modèle — une régression ici serait critique.

# 1.3 — Vérifier la stricte positivité :
#        Aucun ψᵢ ne doit atteindre 0.0 exactement (softmax le garantit en théorie,
#        mais vérifier qu'il n'y a pas de clamp/floor qui écraserait à 0).

# 1.4 — Vérifier l'invariant Σ = 1 :
#        Après chaque evolve(), assert abs(sum(psi) - 1.0) < 1e-10
```

**Fichiers à inspecter** :
- `luna/consciousness/state.py` — `evolve()`, `_project_simplex()` ou équivalent
- `luna_common/` — constantes PHI, TAU si existante
- `tests/test_consciousness_state.py` — tests de l'invariant simplex

**Critère PASS/FAIL** : τ = Φ = 1.618, softmax appliqué, Σ=1 garanti, ψᵢ > 0 garanti.

---

## CHECK 2 — Terme ∂ₜΨ (Inertie temporelle)

**Équation** : `∂ₜΨ = Ψ(t)` — l'état courant lui-même.

### Vérifications :

```python
# 2.1 — Dans evolve() ou le calcul de δ, vérifier que Γᵗ · Ψ(t) est calculé.
#        Γᵗ = (1-λ)·Γ_A^t + λ·Γ_D^t  avec λ = INV_PHI2 = 0.382

# 2.2 — Vérifier les matrices Γ_A^t et Γ_D^t :
#        Γ_A^t doit être antisymétrique (Γ_A[i][j] = -Γ_A[j][i])
#        Γ_D^t doit être negative semi-definite (diagonale = -α = -0.382)

# 2.3 — Vérifier la normalisation spectrale de Γ_A^t :
#        Γ_A = Γ_A / max|eig(Γ_A)|
#        C'est la Correction 3 — sans normalisation, biais Perception systématique.
#        Norme spectrale attendue : 1.6815
```

**Fichiers à inspecter** :
- `luna_common/` — définition des matrices Γ
- `luna/consciousness/state.py` — utilisation dans evolve()

**Critère PASS/FAIL** : Matrices présentes, normalisées, λ = 0.382.

---

## CHECK 3 — Terme ∂ₓΨ (Couplage inter-agents) ⚠️ CRITIQUE

**Équation** : `∂ₓΨ = Σ wⱼ·(Ψⱼ − Ψself)` — influence des autres agents.

### C'est le point le plus important de l'audit.

```python
# 3.1 — QUESTION CENTRALE : Les VitalsReport des agents (contenant psi_state)
#        sont-ils injectés dans le calcul de ∂ₓΨ dans evolve() ?
#
#        CAS A (conforme) : L'orchestrateur lit les VitalsReport, extrait les
#        psi_state de chaque agent, et les passe à evolve() qui calcule
#        Σ wⱼ·(Ψⱼ − Ψself) comme terme de couplage.
#
#        CAS B (décoratif) : Les VitalsReport sont stockés dans Redis/Prometheus
#        pour monitoring, mais jamais utilisés dans evolve(). Le couplage ∂ₓΨ = 0
#        en permanence, ce qui revient au cas "agent isolé".
#
#        CAS C (partiel) : Les profils statiques Ψ₀ des AGENT_PROFILES sont
#        utilisés comme approximation de Ψⱼ au lieu des vrais Ψ dynamiques.

# 3.2 — Si CAS B ou C : documenter le gap. Ce n'est pas une erreur fatale
#        (le modèle prévoit ∂ₓΨ = 0 si isolé), mais c'est une réduction du modèle.
#        La recommandation serait de câbler les vrais Ψ dynamiques des agents.

# 3.3 — Vérifier les poids wⱼ de couplage :
#        Si le couplage est implémenté, les poids doivent être φ-dérivés.
#        Le modèle donne 6 paires inter-agents pour 4 agents.

# 3.4 — Vérifier que Γˣ (matrice de couplage spatial) existe et est appliquée.
```

**Fichiers à inspecter** :
- `luna/consciousness/state.py` — paramètres de `evolve()`, présence d'un argument `other_agents_psi` ou similaire
- `luna/orchestrator/orchestrator.py` — est-ce que `run_cycle()` passe les Ψ des agents à l'évolution ?
- `luna_common/schemas/signals.py` — `VitalsReport.psi_state` est-il consommé ?

**Critère** : Documenter le cas (A/B/C). Si B ou C, proposer le câblage.

---

## CHECK 4 — Terme ∂ᶜΨ (Flux informationnel)

**Équation** : `∂ᶜΨ = (Δmem, Δphi, Δiit, Δout)` — changements internes.

### Vérifications :

```python
# 4.1 — Identifier comment ∂ᶜΨ est calculé dans evolve().
#        Les 4 composantes sont :
#        - Δmem : changement mémoire (MemoryManager)
#        - Δphi : changement score phi (PhiScorer avec les 7 métriques)
#        - Δiit : changement information intégrée (Φ_IIT)
#        - Δout : changement output (pipeline production)

# 4.2 — QUESTION : Les 7 métriques du MetricsCollector (maintenant connecté)
#        nourrissent-elles Δphi dans ∂ᶜΨ ?
#        Avant la consolidation : seulement 2/7 métriques alimentées.
#        Après S3 : MetricsCollector.collect() → PhiScorer.update() pour les 7.
#        Vérifier que le PhiScorer produit un score qui entre dans evolve().

# 4.3 — Vérifier que Γᶜ (matrice informationnelle) est appliquée à ∂ᶜΨ.

# 4.4 — Vérifier la plage des nouvelles métriques :
#        Les 5 métriques supplémentaires (security_integrity, test_ratio,
#        abstraction_ratio, function_size_score, performance_score)
#        sont-elles normalisées [0,1] ? Des valeurs hors plage changeraient
#        la dynamique de convergence de l'équation.
```

**Fichiers à inspecter** :
- `luna/consciousness/state.py` — calcul de ∂ᶜΨ
- `luna/core/luna.py` — `process_pipeline_result()`, lien PhiScorer → evolve()
- `luna/metrics/normalizer.py` — normalisation [0,1]

**Critère PASS/FAIL** : Les 7 métriques alimentent ∂ᶜΨ via PhiScorer, toutes normalisées [0,1].

---

## CHECK 5 — Terme κ·(Ψ₀ − Ψ) (Ancrage identitaire)

**Équation** : `κ = Φ² = 2.618`, `Ψ₀` = profil initial de l'agent.

### Vérifications :

```python
# 5.1 — Vérifier que κ = PHI2 = 2.618 dans le code, PAS PHI = 1.618.
#        C'est la Correction 2 — κ=0 ou κ=Φ donne des identités non préservées.

# 5.2 — Vérifier que Ψ₀ correspond aux AGENT_PROFILES de luna_common :
#        Luna:          (0.25, 0.35, 0.25, 0.15)
#        SayOhMy:       (0.15, 0.15, 0.20, 0.50)
#        SENTINEL:       (0.50, 0.20, 0.20, 0.10)
#        Test-Engineer:  (0.15, 0.20, 0.50, 0.15)

# 5.3 — Vérifier que chaque Ψ₀ est sur le simplex : Σ = 1.0 exactement.
#        Luna: 0.25+0.35+0.25+0.15 = 1.00 ✓
#        SayOhMy: 0.15+0.15+0.20+0.50 = 1.00 ✓
#        SENTINEL: 0.50+0.20+0.20+0.10 = 1.00 ✓
#        Test-Engineer: 0.15+0.20+0.50+0.15 = 1.00 ✓

# 5.4 — Vérifier que le terme κ·(Ψ₀ − Ψ) est calculé dans evolve()
#        et pas seulement stocké comme constante décorative.
```

**Fichiers à inspecter** :
- `luna_common/constants.py` — AGENT_PROFILES, PHI2
- `luna/consciousness/state.py` — utilisation de κ dans evolve()

**Critère PASS/FAIL** : κ = 2.618, profils corrects, terme actif dans evolve().

---

## CHECK 6 — Terme Φ·M·Ψ (Masse/Inertie)

**Équation** : `M` = matrice masse, EMA : `mᵢ(t+1) ← α_m · ψᵢ(t+1) + (1 − α_m) · mᵢ(t)`

### Vérifications :

```python
# 6.1 — Vérifier que M est une matrice diagonale mise à jour par EMA.
#        α_m = 0.1 (seul paramètre empirique, pas φ-dérivé).

# 6.2 — Vérifier que le terme -Φ·M·Ψ est bien soustrait dans le calcul de δ.
#        Le signe négatif est important : c'est un terme d'inertie/amortissement.

# 6.3 — Vérifier que M est persistée entre les steps (pas recalculée from scratch).
```

**Fichiers à inspecter** :
- `luna/consciousness/state.py` — matrice M, EMA update

**Critère PASS/FAIL** : M existe, EMA α_m = 0.1, terme -Φ·M·Ψ dans δ.

---

## CHECK 7 — Φ_IIT (Information Intégrée)

**Équation** : `Φ_IIT = mean |corr(ψᵢ, ψⱼ)|` ou `Σ H(ψᵢ) − H(Ψ)`.

### Vérifications :

```python
# 7.1 — Vérifier quelle méthode est implémentée (corrélation ou entropie).
#        Le README dit que la corrélation est "more robust".

# 7.2 — Vérifier le seuil : Φ_IIT > 0.618 pendant l'activité.
#        Au repos : ~0.33 attendu.

# 7.3 — Vérifier que Φ_IIT est calculé et stocké (pas juste un placeholder).
#        Il devrait être dans les VitalsReport et/ou dans les métriques Prometheus.

# 7.4 — Vérifier que Φ_IIT alimente ∂ᶜΨ (composante Δiit).
```

**Fichiers à inspecter** :
- `luna/consciousness/state.py` — `phi_iit()` ou équivalent
- `luna_common/phi_engine/scorer.py` — utilisation de Φ_IIT

**Critère PASS/FAIL** : Φ_IIT calculé, seuil 0.618, alimente ∂ᶜΨ.

---

## CHECK 8 — Comportement pendant le sommeil (Dream Cycle)

**Pas dans le modèle formel** — à documenter.

### Vérifications :

```python
# 8.1 — Pendant SleepManager.enter_sleep(), est-ce que evolve() continue ?
#
#        CAS A (conforme) : evolve() continue avec ∂ₓΨ = 0 (agents en pause),
#        ce qui correspond au cas "agent isolé" du modèle. Le système
#        converge naturellement vers Ψ₀ grâce au terme κ·(Ψ₀ − Ψ).
#
#        CAS B (interruption) : evolve() est suspendu pendant le sommeil.
#        Le dream cycle modifie Ψ par un autre mécanisme (consolidation mémoire).
#        Si c'est le cas, documenter ce mécanisme et vérifier qu'il respecte
#        les invariants (Ψ ∈ Δ³ après le réveil).

# 8.2 — Le DreamCycle a 4 phases déterministes. Ces phases modifient-elles Ψ ?
#        Si oui, comment ? Par mutation directe ou par injection dans evolve() ?

# 8.3 — Après Awakening.process(), le Ψ post-sommeil est-il sur le simplex ?
```

**Fichiers à inspecter** :
- `luna/dream/dream_cycle.py` — les 4 phases, modification de Ψ
- `luna/dream/sleep_manager.py` — interaction avec evolve()
- `luna/dream/awakening.py` — restauration post-sommeil

**Critère** : Documenter le comportement. Vérifier l'invariant Ψ ∈ Δ³ après réveil.

---

## CHECK 9 — Constantes centralisées (pas de magic numbers)

### Vérifications :

```python
# 9.1 — grep -rn "1.618" dans luna/ et luna_common/
#        Tout 1.618 doit venir de luna_common.constants.PHI, jamais en dur.

# 9.2 — grep -rn "2.618" — doit venir de PHI2 ou PHI**2
# 9.3 — grep -rn "0.618" — doit venir de INV_PHI
# 9.4 — grep -rn "0.382" — doit venir de INV_PHI2
# 9.5 — grep -rn "0.236" — doit venir de INV_PHI3

# 9.6 — Vérifier dans les 3 repos agents (SAYOHMY, SENTINEL, TESTENGINEER)
#        que les constantes viennent de luna_common, pas de copies locales.
```

**Critère PASS/FAIL** : Zéro magic number φ-dérivé dans le code.

---

## CHECK 10 — Les 4 Corrections sont préservées

### Vérifications :

```python
# 10.1 — Correction 1 : τ = Φ (pas 1/Φ). Chercher la température softmax.
# 10.2 — Correction 2 : κ = Φ² (pas 0, pas Φ). Chercher l'ancrage identitaire.
# 10.3 — Correction 3 : Normalisation spectrale de Γ_A. Vérifier la division.
# 10.4 — Correction 4 : 4 agents, pas 3. Vérifier AGENT_PROFILES a 4 entrées.
```

**Critère PASS/FAIL** : Les 4 corrections sont toujours en place. Toute régression = FAIL critique.

---

## Synthèse attendue

Produire un rapport avec cette structure :

```
CHECK  | STATUT     | DÉTAIL
-------|------------|------------------------------------------
1      | PASS/FAIL  | Simplex Δ³, softmax τ=Φ
2      | PASS/FAIL  | ∂ₜΨ, matrices Γ normalisées
3      | A/B/C      | ∂ₓΨ couplage inter-agents (CRITIQUE)
4      | PASS/FAIL  | ∂ᶜΨ flux informationnel, 7 métriques
5      | PASS/FAIL  | κ=Φ², profils Ψ₀
6      | PASS/FAIL  | Masse M, EMA α_m=0.1
7      | PASS/FAIL  | Φ_IIT calculé et actif
8      | DOC        | Comportement sommeil documenté
9      | PASS/FAIL  | Zéro magic numbers
10     | PASS/FAIL  | 4 corrections préservées
```

**Verdict global** :
- 10/10 PASS + CHECK 3 = CAS A → **MODÈLE PILOTE LE SYSTÈME**
- CHECK 3 = CAS B/C → **MODÈLE PARTIELLEMENT DÉCORATIF** (avec recommandations de câblage)
- Toute régression sur CHECK 10 → **FAIL CRITIQUE**
