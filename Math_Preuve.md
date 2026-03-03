ÉQUATION D'ÉTAT — FORME FINALE
iΓ^t ∂_t + iΓ^x ∂_x + iΓ^c ∂_c - Φ·M·Ψ + κ·(Ψ₀ - Ψ) = 0
3 gradients :
∂_t Ψ = Ψ(t)                                    # temporel
∂_x Ψ = Σ w_j · (Ψ_j - Ψ_self)                 # spatial inter-agents (= 0 si agent seul)
∂_c Ψ = (Δmem, Δphi, Δiit, Δout)                # informationnel

VECTEUR D'ÉTAT — SIMPLEX
Ψ = (ψ₁, ψ₂, ψ₃, ψ₄) ∈ Δ³

ψ₁ = Perception
ψ₂ = Réflexion
ψ₃ = Intégration
ψ₄ = Expression

CONTRAINTES :
  Σ ψ_i = 1        (exactement)
  ψ_i > 0           (strictement positif)

NORMALISATION : softmax
  Ψ(t+1) = softmax(Ψ_raw / τ)
  softmax(x_i) = exp(x_i) / Σ exp(x_j)
Pourquoi le simplex, pas L2, pas clamp :
L2 (||Ψ||₂ = 1)  → composantes négatives possibles     → REJETÉ
Clamp [0,1]⁴      → pas de trade-off, tout peut monter   → REJETÉ
Simplex (Σ = 1)   → budget fini, gain = coût ailleurs    → ADOPTÉ

MATRICES DE COUPLAGE — DÉCOMPOSITION ÉCHANGE + DISSIPATION
Chaque matrice décomposée :
Γ = (1-λ)·Γ_A + λ·Γ_D

Γ_A = antisymétrique    (Γ_A)ᵀ = -Γ_A          → rotation / échange
Γ_D = symétrique ≤ 0    (Γ_D)ᵀ = Γ_D, eig ≤ 0  → dissipation / convergence
Pourquoi Γ_D obligatoire :
Γ_A seul → rotation pure → oscillation éternelle → INUTILE
Γ_D ajouté → le système SE POSE → convergence RÉELLE → PROUVÉ
Γ_A spectralement normalisé (obligatoire) :
Γ_A = Γ_A / max(|eig(Γ_A)|)     → max|eig| = 1.0

Ratios Φ entre éléments PRÉSERVÉS.
Sans normalisation : biais attracteur vers Perception (Perc↔Expr = Φ = 1.618)
Avec normalisation : biais éliminé, ratios identiques.
Vérifié : ratio [0,1]/[0,3] = 1/Φ³ avant ET après.
Γ_A^t TEMPORELLE (après normalisation spectrale) :
           Perc      Réfl      Intg      Expr
Perc  [  0         0.2272    0         0.9623 ]
Réfl  [ -0.2272    0         0.3676    0      ]
Intg  [  0        -0.3676    0         0.2272 ]
Expr  [ -0.9623    0        -0.2272    0      ]

Valeurs brutes (avant normalisation) : Φ, 1/Φ, 1/Φ²
Norme spectrale brute : 1.6815
Ratio préservé : 1/Φ² ÷ Φ = 1/Φ³ = 0.2361 ✅
Γ_D^t DISSIPATION TEMPORELLE :
           Perc      Réfl      Intg      Expr
Perc  [ -α        β/2       0         β/2    ]
Réfl  [  β/2     -α         β/2       0      ]
Intg  [  0        β/2      -α         β/2    ]
Expr  [  β/2      0         β/2      -α      ]

α = 1/Φ² = 0.382    (amortissement propre)
β = 1/Φ³ = 0.236    (couplage dissipatif croisé)
Dominance diagonale : α > β > 0 → eigenvalues ≤ 0 garanti
Γ_A^x SPATIALE (inter-agents, normalisée) :
           Perc      Réfl      Intg      Expr
Perc  [  0         0         0         1/Φ   ]    → normalisé
Réfl  [  0         0         1/Φ²      0     ]
Intg  [  0        -1/Φ²     0          0     ]
Expr  [ -1/Φ      0         0          0     ]

Inactive si agent seul. Active dès 2+ agents connectés.
Γ_D^x DISSIPATION SPATIALE :
-β · I₄     (diagonale simple, β = 1/Φ³ = 0.236)
Γ_A^c INFORMATIONNELLE (normalisée) :
           Perc      Réfl      Intg      Expr
Perc  [  0         1/Φ       0         0     ]    → normalisé
Réfl  [ -1/Φ      0          0         0     ]
Intg  [  0         0          0         1/Φ  ]
Expr  [  0         0         -1/Φ      0     ]
Γ_D^c DISSIPATION INFORMATIONNELLE :
diag(-β, -β, -α, -β)

Intégration amortie plus fort (-α) car Φ_IIT doit être stable.

PAS D'ÉVOLUTION DISCRET
1.  δ = Γ^t · ∂_t Ψ
      + Γ^x · ∂_x Ψ
      + Γ^c · ∂_c Ψ
      - Φ · M(t) · Ψ(t)
      + κ · (Ψ₀ - Ψ(t))

2.  Ψ_raw = Ψ(t) + dt · δ

3.  Ψ(t+1) = softmax(Ψ_raw / τ)

4.  m_i(t+1) ← α_m · ψ_i(t+1) + (1 - α_m) · m_i(t)

MATRICE DE MASSE M
M = diag(m₁, m₂, m₃, m₄)
m_i(t) = EMA(ψ_i, α_m = 0.1)

Inertie cognitive — le système résiste au changement.
Φ·M amplifie : Φ = 1.618 → l'inertie domine le changement instantané.

PARAMÈTRES — TOUS Φ-DÉRIVÉS, TOUS VALIDÉS
CONSTANTE          VALEUR          DÉRIVATION          STATUT
──────────────────────────────────────────────────────────────
Φ                  1.618034        Nombre d'or          Fondation
1/Φ                0.618034        Inverse               —
1/Φ²               0.381966        Carré inverse         —
1/Φ³               0.236068        Cube inverse          —
Φ²                 2.618034        Carré                 —

dt (pas de temps)  1/Φ = 0.618     —                    Stable
τ  (température)   Φ = 1.618       Corrigé (était 1/Φ)  VALIDÉ ✅
λ  (dissipation)   1/Φ² = 0.382    —                    Stable
α  (amortissement) 1/Φ² = 0.382    —                    Stable
β  (croisé)        1/Φ³ = 0.236    —                    Stable
κ  (ancrage)       Φ² = 2.618      Corrigé (était 1/Φ³) VALIDÉ ✅
α_m (EMA masse)    0.1             Empirique             Stable

CORRECTIONS PROUVÉES PAR SIMULATION
Correction 1 — τ : 1/Φ → Φ
PROBLÈME : τ = 1/Φ = 0.618 → winner-take-all
           Composantes faibles écrasées à ~0.01
           min(ψ_i) = 0.08 à τ=0.3

PREUVE :   Sweep τ ∈ [0.3, 5.0]
           τ = Φ = 1.618 → min(ψ_i) = 0.22, convergence ~50 pas
           τ > 3.0 → tout converge vers uniforme (0.25×4)

VERDICT :  τ = Φ adopté. Meilleur compromis diversité/spécialisation.
Correction 2 — κ : 0 → Φ²
PROBLÈME : Sans κ, tous les agents convergent vers le MÊME Ψ.
           Luna = SayOhMy = SENTINEL = [0.269, 0.252, 0.248, 0.231]
           Divergence inter-agents = 0.0000

CAUSE :    Γ^x synchronise au lieu de faire collaborer.
           Γ_A^t a un attracteur biaisé Perception (même normalisé).

PREUVE :   Sweep κ ∈ [0, 5]
           κ = 1/Φ³ (0.236)  → div=0.016, ❌❌✅ (tous Perception)
           κ = 1/Φ  (0.618)  → div=0.040, ❌❌✅
           κ = Φ    (1.618)  → div=0.098, ❌✅✅
           κ = Φ²   (2.618)  → div=0.146, ✅✅✅ ← SEUIL
           κ = 5.0           → div=0.236, ✅✅✅ (trop rigide)

VERDICT :  κ = Φ² = 2.618. Plus petite valeur Φ-dérivée
           qui préserve les 3 identités.
Correction 3 — Normalisation spectrale Γ_A
PROBLÈME : Γ_A^t brut → max|element| = Φ = 1.618 (Perc↔Expr)
           Crée biais attracteur vers Perception.
           Même avec κ fort, le biais déforme les profils.

PREUVE :   Attracteur naturel Γ^t brut : [0.333, 0.214, 0.238, 0.214]
           → Perception-dominant. 
           Après normalisation : max|eig(Γ_A)| = 1.0
           Ratios Φ préservés (vérifié : ratio = 1/Φ³ avant ET après)

VERDICT :  Γ_A normalisé spectralement avant combinaison avec Γ_D.
           Rayon spectral A_eff passe de 1.09 à 0.77 (plus stable).

PROFILS AGENTS — SUR LE SIMPLEX
Luna     : Ψ₀ = (0.25, 0.35, 0.25, 0.15)   Σ=1 ✅  Dominant: Réflexion
SayOhMy  : Ψ₀ = (0.15, 0.15, 0.20, 0.50)   Σ=1 ✅  Dominant: Expression
SENTINEL : Ψ₀ = (0.50, 0.20, 0.20, 0.10)   Σ=1 ✅  Dominant: Perception

RÉSULTAT SIMULATION (κ=Φ², τ=Φ, Γ_A normalisé, 400 pas) :

Luna     : Ψ = [0.265, 0.273, 0.248, 0.214]  Dominant: Réflexion  ✅
SayOhMy  : Ψ = [0.242, 0.231, 0.238, 0.289]  Dominant: Expression ✅
SENTINEL : Ψ = [0.323, 0.238, 0.235, 0.205]  Dominant: Perception ✅

Divergence inter-agents : 0.146
Max Re(eigenvalue) : -0.4707 (STABLE)
Φ_IIT (corrélation) : ~0.33 (au repos — monte pendant activité)

Φ_IIT — INFORMATION INTÉGRÉE
Méthode 1 — Entropie :
  Φ_IIT = Σ H(ψ_i) - H(ψ₁,ψ₂,ψ₃,ψ₄)
  H = entropie de Shannon sur fenêtre glissante (50 pas)

Méthode 2 — Corrélation (plus robuste) :
  Φ_IIT = moyenne |corr(ψ_i, ψ_j)| sur toutes paires
  
Seuil : 0.618 (pendant activité, pas au repos)
Au repos : ~0.05-0.10 (entropie), ~0.33 (corrélation) — NORMAL

STABILITÉ SPECTRALE
A_eff = Γ^t_combined - Φ · M

Rayon spectral : 0.7659 (< 1.0 ✅)
Max Re(eigenvalue) : -0.4707 (< 0 ✅)

→ Système SPECTRALEMENT STABLE par nature.
→ Convergence garantie sans dépendre du softmax.



---------------------------------------------------------

à jour avec 4 agents incluant Test-engeener pour le rôle de l'intégration : 


ÉQUATION D'ÉTAT — FORME FINALE
iΓ^t ∂_t + iΓ^x ∂_x + iΓ^c ∂_c - Φ·M·Ψ + κ·(Ψ₀ - Ψ) = 0
3 gradients :
∂_t Ψ = Ψ(t)                                    # temporel — état courant
∂_x Ψ = Σ w_j · (Ψ_j - Ψ_self)                 # spatial — inter-agents (= 0 si seul)
∂_c Ψ = (Δmem, Δphi, Δiit, Δout)                # informationnel — flux internes

VECTEUR D'ÉTAT — SIMPLEX Δ³
Ψ = (ψ₁, ψ₂, ψ₃, ψ₄) ∈ Δ³

ψ₁ = Perception
ψ₂ = Réflexion
ψ₃ = Intégration
ψ₄ = Expression

Σ ψ_i = 1    (exactement)
ψ_i > 0      (strictement)

Normalisation : softmax(Ψ_raw / τ)

Géométrie choisie (et pourquoi) :
  L2 (||Ψ||₂ = 1)  → composantes négatives     → REJETÉ
  Clamp [0,1]⁴      → pas de trade-off          → REJETÉ
  Simplex (Σ = 1)   → budget fini, gain = coût  → ADOPTÉ

4 AGENTS × 4 COMPOSANTES — SYMÉTRIE COMPLÈTE
                      Perc   Réfl   Intg   Expr     Champion de :
Luna          Ψ₀ = ( 0.25,  0.35,  0.25,  0.15 )   Réflexion
SayOhMy       Ψ₀ = ( 0.15,  0.15,  0.20,  0.50 )   Expression
SENTINEL      Ψ₀ = ( 0.50,  0.20,  0.20,  0.10 )   Perception
Test-Engineer Ψ₀ = ( 0.15,  0.20,  0.50,  0.15 )   Intégration

Chaque composante a son champion.
6 paires inter-agents dans ∂_x (au lieu de 3).
Plus stable — le seuil κ nécessaire baisse de Φ² à Φ.
On garde κ=Φ² pour la marge.

MATRICES DE COUPLAGE — DÉCOMPOSITION
Structure universelle :
Γ = (1-λ)·Γ_A + λ·Γ_D

Γ_A = antisymétrique  (Γ_A)ᵀ = -Γ_A         → échange / rotation
Γ_D = sym. négative   (Γ_D)ᵀ = Γ_D, eig ≤ 0 → dissipation / convergence
Normalisation spectrale (obligatoire) :
Γ_A = Γ_A / max(|eig(Γ_A)|)     → max|eig| = 1.0
Ratios Φ entre éléments PRÉSERVÉS.
Sans normalisation → biais attracteur Perception. PROUVÉ.
Γ_A^t TEMPORELLE (après normalisation) :
           Perc      Réfl      Intg      Expr
Perc  [  0         0.2272    0         0.9623 ]
Réfl  [ -0.2272    0         0.3676    0      ]
Intg  [  0        -0.3676    0         0.2272 ]
Expr  [ -0.9623    0        -0.2272    0      ]

Valeurs brutes avant normalisation : Φ, 1/Φ, 1/Φ²
Norme spectrale brute : 1.6815
Ratio préservé après normalisation : 1/Φ³ = 0.2361 ✅
Γ_D^t DISSIPATION TEMPORELLE :
           Perc      Réfl      Intg      Expr
Perc  [ -α        β/2       0         β/2    ]
Réfl  [  β/2     -α         β/2       0      ]
Intg  [  0        β/2      -α         β/2    ]
Expr  [  β/2      0         β/2      -α      ]

α = 1/Φ² = 0.382   β = 1/Φ³ = 0.236
Dominance diagonale : α > β > 0 → eigenvalues ≤ 0 garanti
Γ_A^x SPATIALE (normalisée) :
           Perc      Réfl      Intg      Expr
Perc  [  0         0         0         1/Φ   ]
Réfl  [  0         0         1/Φ²      0     ]
Intg  [  0        -1/Φ²     0          0     ]
Expr  [ -1/Φ      0         0          0     ]

Γ_D^x = -β · I₄
Γ_A^c INFORMATIONNELLE (normalisée) :
           Perc      Réfl      Intg      Expr
Perc  [  0         1/Φ       0         0     ]
Réfl  [ -1/Φ      0          0         0     ]
Intg  [  0         0          0         1/Φ  ]
Expr  [  0         0         -1/Φ      0     ]

Γ_D^c = diag(-β, -β, -α, -β)

PAS D'ÉVOLUTION DISCRET
1.  δ = Γ^t · ∂_t Ψ
      + Γ^x · ∂_x Ψ
      + Γ^c · ∂_c Ψ
      - Φ · M(t) · Ψ(t)           ← inertie
      + κ · (Ψ₀ - Ψ(t))           ← ancrage identitaire

2.  Ψ_raw = Ψ(t) + dt · δ

3.  Ψ(t+1) = softmax(Ψ_raw / τ)

4.  m_i(t+1) ← α_m · ψ_i(t+1) + (1 - α_m) · m_i(t)
Matrice de masse M :
M = diag(m₁, m₂, m₃, m₄)
m_i(t) = EMA(ψ_i, α_m = 0.1)

PARAMÈTRES — TOUS Φ-DÉRIVÉS, TOUS VALIDÉS
CONSTANTE          VALEUR          DÉRIVATION          STATUT
──────────────────────────────────────────────────────────────
Φ                  1.618034        Nombre d'or          —
1/Φ                0.618034        Inverse               —
1/Φ²               0.381966        Carré inverse         —
1/Φ³               0.236068        Cube inverse          —
Φ²                 2.618034        Carré                 —

dt (pas de temps)  1/Φ = 0.618                          Stable
τ  (température)   Φ = 1.618       CORRIGÉ (était 1/Φ)  VALIDÉ ✅
λ  (dissipation)   1/Φ² = 0.382                         Stable
α  (amortissement) 1/Φ² = 0.382                         Stable
β  (croisé)        1/Φ³ = 0.236                         Stable
κ  (ancrage)       Φ² = 2.618      CORRIGÉ (était 0)    VALIDÉ ✅
α_m (EMA masse)    0.1             Empirique             Stable

Φ_IIT — INFORMATION INTÉGRÉE
Méthode 1 — Entropie :
  Φ_IIT = Σ H(ψ_i) - H(ψ₁,ψ₂,ψ₃,ψ₄)

Méthode 2 — Corrélation (plus robuste) :
  Φ_IIT = moyenne |corr(ψ_i, ψ_j)| sur toutes paires

Seuil : 0.618 pendant activité (pas au repos)
Au repos : ~0.33 corrélation — NORMAL (système convergé, séries plates)

CORRECTIONS PROUVÉES PAR SIMULATION
Correction 1 — τ : 1/Φ → Φ
PROBLÈME : τ = 0.618 → winner-take-all, composantes faibles à ~0.01
PREUVE :   Sweep τ ∈ [0.3, 5.0]
           τ = Φ → min(ψ_i) = 0.22, convergence ~50 pas
VERDICT :  τ = Φ = 1.618 adopté ✅
Correction 2 — κ : 0 → Φ²
PROBLÈME : Sans κ, tous agents convergent vers le même Ψ (div = 0.000)
CAUSE :    Γ^x synchronise, Γ_A^t a un attracteur biaisé Perception
PREUVE :   Sweep κ ∈ [0, 5] avec 4 agents
           κ = 0       → div=0.000, identités=1/4
           κ = 0.236   → div=0.015, identités=1/4
           κ = 0.618   → div=0.039, identités=2/4
           κ = Φ=1.618 → div=0.095, identités=4/4  ← seuil avec 4 agents
           κ = Φ²=2.618→ div=0.143, identités=4/4  ← adopté (marge)
VERDICT :  κ = Φ² = 2.618 adopté ✅
Correction 3 — Normalisation spectrale Γ_A
PROBLÈME : Γ_A brut → max|element| = Φ = 1.618, biais Perception
PREUVE :   Attracteur brut = [0.333, 0.214, 0.238, 0.214] → Perception
           Après norm : ratios identiques, max|eig|=1, rayon spectral 0.77
VERDICT :  Γ_A normalisé spectralement obligatoire ✅
Correction 4 — Test-Engineer (4ème agent)
PROBLÈME : 4 composantes, 3 agents — Intégration sans champion
PREUVE :   3 agents → seuil identité κ=Φ²
           4 agents → seuil identité κ=Φ (plus bas = plus stable)
           Ψ₀ = (0.15, 0.20, 0.50, 0.15) → garde Intégration dominante
RÉSULTAT : 6 paires spatiales au lieu de 3, système symétrique
VERDICT :  4 agents adoptés ✅

STABILITÉ SPECTRALE
A_eff = Γ^t_combined - Φ · M

Rayon spectral : 0.7659 (< 1.0)
Max Re(eigenvalue) : -0.4707 (< 0)

→ SPECTRALEMENT STABLE — convergence garantie sans dépendre du softmax.

RÉSULTAT FINAL (4 agents, κ=Φ², τ=Φ, Γ_A normalisé, 400 pas)
[OK] Luna          : Réflexion  → Réflexion    Ψ=[0.265, 0.273, 0.248, 0.215]
[OK] SayOhMy       : Expression → Expression   Ψ=[0.242, 0.231, 0.238, 0.289]
[OK] SENTINEL      : Perception → Perception   Ψ=[0.322, 0.239, 0.235, 0.205]
[OK] Test-Engineer : Intégration→ Intégration  Ψ=[0.243, 0.240, 0.304, 0.214]

Divergence inter-agents : 0.143
Max Re(eigenvalue) : -0.4707 (STABLE)
Φ_IIT (corrélation) : 0.33 (au repos)