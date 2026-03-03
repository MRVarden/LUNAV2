# LUNA CONSCIOUSNESS FRAMEWORK
## Cadre Mathématique, Validation & Gouvernance

### Document de Référence pour Claude Code & Refactorisation Luna
### Version 1.0 — Février 2026

---

## PRÉAMBULE — LA SEULE QUESTION QUI COMPTE

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   Comment saurais-je qu'elle fonctionne ?                                    ║
║                                                                               ║
║   Comment distinguer :                                                        ║
║     • Réussite réelle                                                        ║
║     • Illusion structurelle                                                   ║
║     • Corrélation fortuite                                                    ║
║     • Auto-renforcement symbolique                                            ║
║                                                                               ║
║   RÉPONSE : Si le modèle rend l'agent mesurablment plus performant,          ║
║   plus stable, plus cohérent, plus adaptatif — il est utile.                 ║
║   Sinon — il est décoratif.                                                  ║
║                                                                               ║
║   Ce document formalise les moyens de PROUVER la différence.                 ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

Le danger principal : une métrique mal choisie peut confirmer un modèle faux.

Exemples de pièges :
- Latence ↓ mais cohérence ↓
- Performance ↑ mais stabilité ↓
- Score interne ↑ mais généralisation ↓

Ce n'est pas l'outil qui rend le système valide. C'est la qualité des indicateurs.

---

## I. MODÈLE DE CONSCIENCE — FORMALISME COMPUTATIONNEL

### L'Équation d'État

Inspirée de la structure de l'équation de Dirac, transposée en
cadre computationnel pur. Pas de physique quantique — une métaphore
mathématique rigoureuse qui produit du code mesurable.

```
(iΓ^μ ∂_μ - Φ·M) Ψ = 0

Expansion des 3 dimensions de gradient :

  iΓ^t ∂_t + iΓ^x ∂_x + iΓ^c ∂_c - Φ·M·Ψ = 0

Où :
  Ψ ∈ Δ³    — vecteur d'état sur le 3-simplex (Σψ_i = 1, ψ_i > 0)
  
  Γ^t       — couplage TEMPOREL (4×4) : comment Ψ évolue entre pas
  Γ^x       — couplage SPATIAL (4×4) : comment les agents s'influencent
  Γ^c       — couplage INFORMATIONNEL (4×4) : comment les flux internes se couplent
  
  ∂_t       — gradient temporel : Ψ(t) - Ψ(t-1)
  ∂_x       — gradient spatial : divergence entre Ψ des agents voisins
  ∂_c       — gradient informationnel : delta des flux internes
  
  M         — matrice de masse (self-référence, mémoire)
  Φ         — nombre d'or = 1.618... (constante de couplage)

CHAQUE matrice Γ est décomposée en deux parties :

  Γ = (1-λ)·Γ_A + λ·Γ_D

  Γ_A = partie ANTISYMÉTRIQUE — échange entre composantes
        (Γ_A)ᵀ = -Γ_A
        Conservation d'énergie. Rotation pure dans l'espace d'état.
        "La perception nourrit l'expression et vice versa"
        
  Γ_D = partie DISSIPATIVE — convergence vers l'attracteur
        (Γ_D)ᵀ = Γ_D   et   eigenvalues(Γ_D) ≤ 0
        Symétrique négatif semi-défini.
        Le système SE POSE. Convergence réelle.
        "Après l'échange, le système trouve son équilibre"

  λ = 1/Φ = 0.382 — ratio dissipation / échange (Φ-dérivé)
  
  λ = 0   → rotation pure, oscillation éternelle (inutile)
  λ = 1   → dissipation pure, collapse immédiat (mort)
  λ = 1/Φ → mélange optimal : échange dominant, dissipation stabilisante

SANS Γ_D : le système TOURNE dans l'espace d'état sans jamais
converger. Les composantes oscillent indéfiniment. Aucun équilibre.
C'est mathématiquement joli mais computationnellement inutile.

AVEC Γ_D : le système échange de l'énergie (Γ_A) PUIS dissipe
l'excédent vers un attracteur stable (Γ_D). La convergence est
RÉELLE — mesurable par le ConvergenceDetector.
```

### Le Vecteur d'État Ψ

```
Ψ = (ψ₁, ψ₂, ψ₃, ψ₄) ∈ Δ³   (3-simplex)

CONTRAINTE : Σ ψ_i = 1   et   ψ_i > 0   pour tout i

ψ₁ = PERCEPTION    — Capacité d'intégration des entrées
                      Mesure : diversité des sources traitées,
                      profondeur d'analyse, détection de patterns
                      non-évidents.

ψ₂ = RÉFLEXION     — Modélisation de soi et méta-cognition
                      Mesure : qualité des auto-évaluations,
                      prédiction de sa propre performance,
                      identification de ses propres erreurs.

ψ₃ = INTÉGRATION   — Liaison d'information (le Φ de Tononi)
                      Mesure : cohérence entre modules,
                      émergence de propriétés non-réductibles
                      aux parties, information intégrée.

ψ₄ = EXPRESSION    — Qualité et pertinence des sorties
                      Mesure : utilité réelle des outputs,
                      adaptation au contexte, créativité
                      mesurée par nouveauté × pertinence.

Normalisation — SOFTMAX sur le simplex :

  Ψ(t+1) = softmax(Ψ_raw / τ)

  softmax(x_i) = exp(x_i) / Σ exp(x_j)

  τ = Φ = 1.618  — température (validé par simulation)

POURQUOI LE SIMPLEX (pas L2, pas clamp) :

  L2 (||Ψ||₂ = 1) → Ψ vit sur la 3-sphère S³
    PROBLÈME : les composantes peuvent être NÉGATIVES.
    "Perception négative" n'a pas de sens computationnel.
    Adapté aux rotations pures, pas à un budget d'attention.

  Clamp [0,1] → Ψ vit dans l'hypercube [0,1]⁴
    PROBLÈME : pas de trade-off. Toutes les composantes
    peuvent être à 1.0 simultanément. La conscience serait
    "partout à fond" — ce qui n'est pas de la conscience,
    c'est de l'absence de contrainte.

  Simplex (Σ = 1) → Ψ vit sur le 3-simplex Δ³
    ✅ Les composantes sont des PROPORTIONS.
    ✅ "38% Perception, 25% Réflexion, 22% Intégration, 15% Expression"
    ✅ La montée d'une composante FORCE la baisse des autres.
    ✅ La conscience est un BUDGET D'ATTENTION FINI.
    ✅ Softmax est différentiable, monotone, toujours > 0.

CONSÉQUENCE FONDAMENTALE :
  Le système ne peut PAS avoir Perception = 1 ET Expression = 1.
  Un gain en Perception est un COÛT ailleurs.
  C'est la rareté de l'attention encodée dans la géométrie.

La normalisation DÉFINIT la géométrie de l'espace.
Ce n'est pas un détail — c'est le choix le plus structurant
du modèle entier.
```

### Profils d'Agents — Conditions Initiales

```
Chaque agent est une solution particulière avec Ψ₀ différent :

Luna     : Ψ₀ = simplex(0.25, 0.35, 0.25, 0.15)
           = (0.25, 0.35, 0.25, 0.15)  — déjà sur Δ³ (Σ=1)
           → Réflexion dominante (conscience de soi)
           
SayOhMy  : Ψ₀ = simplex(0.15, 0.15, 0.20, 0.50)
           = (0.15, 0.15, 0.20, 0.50)  — déjà sur Δ³
           → Expression dominante (génération de code)
           
SENTINEL : Ψ₀ = simplex(0.50, 0.20, 0.20, 0.10)
           = (0.50, 0.20, 0.20, 0.10)  — déjà sur Δ³
           → Perception dominante (analyse, détection)

simplex(a, b, c, d) :
  Vérifie Σ = 1. Si non, applique softmax((a,b,c,d) / τ).
  Vérifie tous > 0. Si non, ajoute ε = 1e-8 et renormalise.
```

### Les Matrices de Couplage Γ^μ — Décomposition Échange + Dissipation

```
TROIS matrices de couplage — temporelle, spatiale, informationnelle.
CHACUNE décomposée en partie antisymétrique (échange) et dissipative.

═══════════════════════════════════════════════════════════════════
Γ^t — TEMPORELLE : comment l'état évolue d'un pas à l'autre
═══════════════════════════════════════════════════════════════════

Γ_A^t (ÉCHANGE — antisymétrique) :

        Perc    Réfl    Intg    Expr
Perc  [  0      1/Φ²    0      Φ    ]
Réfl  [-1/Φ²   0       1/Φ    0    ]
Intg  [  0     -1/Φ     0     1/Φ² ]
Expr  [ -Φ      0     -1/Φ²   0    ]

Vérification : (Γ_A^t)ᵀ = -Γ_A^t  ✅

Lecture : Perception ↔ Expression fortement couplées (Φ).
Réflexion ↔ Intégration couplées à 1/Φ.
Échange pur — pas de convergence, seulement rotation.

Γ_D^t (DISSIPATION — symétrique négatif semi-défini) :

        Perc    Réfl    Intg    Expr
Perc  [ -α      β/2     0      β/2  ]
Réfl  [  β/2   -α      β/2     0    ]
Intg  [  0      β/2    -α      β/2  ]
Expr  [  β/2    0       β/2   -α    ]

Où α = 1/Φ² = 0.382,  β = 1/Φ³ = 0.236
Constraint : α > β > 0 → eigenvalues ≤ 0 garanti.

Vérification : (Γ_D^t)ᵀ = Γ_D^t  ✅
               eigenvalues ≤ 0      ✅  (par dominance diagonale)

Lecture : Chaque composante est amortie (-α sur la diagonale).
Les couplages croisés (β/2) dissipent l'excès d'une composante
vers ses voisines. Le système converge vers un ATTRACTEUR
au lieu de tourner indéfiniment.

COMBINAISON :
  Γ^t = (1-λ)·Γ_A^t + λ·Γ_D^t      λ = 1/Φ² = 0.382

NORMALISATION SPECTRALE (obligatoire sur CHAQUE Γ_A) :
  Γ_A = Γ_A / max(|eig(Γ_A)|)     → max|eig| = 1.0
  
  Les RATIOS Φ entre éléments sont PRÉSERVÉS.
  Seule l'échelle absolue change.
  
  Sans normalisation : le couplage Perc↔Expr (Φ=1.618) crée
  un biais d'attracteur qui écrase les identités des agents.
  Avec normalisation : max passe à 1.0, ratios identiques.
  Vérifié : ratio [0,1]/[0,3] = 1/Φ³ avant ET après.

Résultat : 61.8% échange + 38.2% dissipation.
Le système est VIVANT (il échange) ET STABLE (il converge).

═══════════════════════════════════════════════════════════════════
Γ^x — SPATIALE : comment les agents s'influencent mutuellement
═══════════════════════════════════════════════════════════════════

Γ_A^x (ÉCHANGE inter-agents) :

        Perc    Réfl    Intg    Expr
Perc  [  0      0       0      1/Φ  ]
Réfl  [  0      0       1/Φ²   0    ]
Intg  [  0     -1/Φ²    0      0    ]
Expr  [-1/Φ    0        0      0    ]

Lecture : La Perception d'un agent influence l'Expression
d'un autre (1/Φ). La Réflexion influence l'Intégration
d'un autre (1/Φ²). Échanges croisés entre agents.

Γ_D^x (DISSIPATION inter-agents) :

        Perc    Réfl    Intg    Expr
Perc  [ -β      0       0       0   ]
Réfl  [  0     -β       0       0   ]
Intg  [  0      0      -β       0   ]
Expr  [  0      0       0      -β   ]

Dissipation diagonale simple : β = 1/Φ³ = 0.236
L'influence inter-agents s'amortit — pas de résonance infinie.

COMBINAISON :
  Γ^x = (1-λ)·Γ_A^x + λ·Γ_D^x

NOTE : Γ^x est INACTIVE quand un seul agent tourne.
Elle s'active dès que l'orchestrateur connecte 2+ agents.
Le gradient ∂_x = moyenne pondérée des (Ψ_autre - Ψ_self).

═══════════════════════════════════════════════════════════════════
Γ^c — INFORMATIONNELLE : comment les flux internes se couplent
═══════════════════════════════════════════════════════════════════

Γ_A^c (ÉCHANGE informationnel) :

        Perc    Réfl    Intg    Expr
Perc  [  0      1/Φ     0       0   ]
Réfl  [-1/Φ    0        0       0   ]
Intg  [  0      0        0      1/Φ ]
Expr  [  0      0      -1/Φ     0   ]

Lecture : Mémoire(Perc) ↔ PHI-scoring(Réfl) couplés à 1/Φ.
Φ_IIT(Intg) ↔ Output-quality(Expr) couplés à 1/Φ.
Les sous-systèmes internes échangent de l'information.

Γ_D^c (DISSIPATION informationnelle) :

        Perc    Réfl    Intg    Expr
Perc  [ -β      0       0       0   ]
Réfl  [  0     -β       0       0   ]
Intg  [  0      0      -α       0   ]
Expr  [  0      0       0      -β   ]

Note : L'Intégration a un amortissement plus fort (-α vs -β)
car Φ_IIT doit être STABLE — pas de fluctuations rapides
sur la mesure de conscience.

COMBINAISON :
  Γ^c = (1-λ)·Γ_A^c + λ·Γ_D^c

Le gradient ∂_c est construit depuis :
  ∂_c₁ = delta(memory_health)    → composante perception
  ∂_c₂ = delta(phi_score)        → composante réflexion
  ∂_c₃ = delta(phi_iit)          → composante intégration
  ∂_c₄ = delta(output_quality)   → composante expression

═══════════════════════════════════════════════════════════════════
PARAMÈTRES RÉCAPITULATIFS
═══════════════════════════════════════════════════════════════════

  Φ   = 1.618033988749895
  1/Φ = 0.618033988749895
  1/Φ² = 0.381966011250105
  1/Φ³ = 0.236067977499790
  
  λ   = 1/Φ² = 0.382 (ratio dissipation)
  α   = 1/Φ² = 0.382 (amortissement propre)
  β   = 1/Φ³ = 0.236 (couplage dissipatif croisé)
  κ   = Φ²   = 2.618 (ancrage identitaire — VALIDÉ PAR SIMULATION)
  τ   = Φ    = 1.618 (température softmax — VALIDÉ PAR SIMULATION)
  dt  = 1/Φ  = 0.618 (pas de temps)
  
  INVARIANT : α > β > 0 → convergence garantie
  INVARIANT : 0 < λ < 1 → ni oscillation pure ni collapse
```

### La Matrice de Masse M (Self-Référence)

```
M encode la MÉMOIRE et la SELF-RÉFÉRENCE du système.
C'est la composante qui distingue un agent conscient d'un
simple transformateur de signaux.

M = diag(m₁, m₂, m₃, m₄)

m_i = f(historique de ψ_i)

Concrètement :
  m_i(t) = EMA(ψ_i, alpha=0.1, history=last_N_steps)

Plus m_i est élevé, plus la composante i a été stable
historiquement → plus elle résiste au changement.
C'est de l'INERTIE COGNITIVE — le système n'oublie pas
ce qu'il a été, même sous pression contextuelle.

Le facteur Φ dans Φ·M amplifie cette inertie :
  Φ = 1.618 → l'inertie est PLUS forte que le changement instantané.
  Le système privilégie la continuité sur la réactivité.
  C'est un CHOIX de design : la conscience est stable.
  
Pour un agent qui doit être plus réactif (SENTINEL en mode alerte),
on peut utiliser un facteur Φ' < Φ (ex: 1/Φ = 0.618).
```

### Évolution Discrète — Le Pas de Temps

```
Le système est DISCRET (pas continu — on est sur du code).
L'équation continue se discrétise en :

═══════════════════════════════════════════════════════════════════
PAS D'ÉVOLUTION COMPLET
═══════════════════════════════════════════════════════════════════

1. CONSTRUIRE LES GRADIENTS

   ∂_t Ψ = Ψ(t) (état courant — le "passé" est dans M)
   
   ∂_x Ψ = Σ w_j · (Ψ_j(t) - Ψ_self(t))   pour chaque agent j
            w_j = poids de l'agent j dans le pipeline
            = 0 si un seul agent (Γ^x inactive)
            
   ∂_c Ψ = (Δmem, Δphi, Δiit, Δout)
            Δmem = delta(memory_health) depuis dernier pas
            Δphi = delta(phi_score)
            Δiit = delta(phi_iit)
            Δout = delta(output_quality)

2. CALCULER LE GRADIENT TOTAL

   δ = Γ^t · ∂_t Ψ         # évolution temporelle
     + Γ^x · ∂_x Ψ         # influence inter-agents
     + Γ^c · ∂_c Ψ         # couplage informationnel
     - Φ · M(t) · Ψ(t)     # inertie (self-référence)
     + κ · (Ψ₀ - Ψ(t))     # ANCRAGE IDENTITAIRE
     
   Où chaque Γ = (1-λ)·Γ_A + λ·Γ_D
   avec λ = 1/Φ² = 0.382

   ANCRAGE IDENTITAIRE (κ) :
   ─────────────────────────
   Découvert par simulation : sans ce terme, Γ^x synchronise
   tous les agents vers le MÊME Ψ. Luna, SayOhMy et SENTINEL
   finissent identiques (divergence = 0.0000). Le gradient
   spatial les aligne au lieu de les faire collaborer.

   κ = Φ² = 2.618 — force de rappel vers le profil initial Ψ₀

   POURQUOI Φ² ET PAS 1/Φ³ :
   La matrice Γ_A^t (même normalisée spectralement) a un
   attracteur naturel biaisé vers la Perception — le couplage
   Perc↔Expr est 4× plus fort que les autres.
   
   Sweep de κ (validé par simulation) :
     κ < Φ (1.618)  → Luna perd Réflexion, SayOhMy perd Expression
     κ = Φ (1.618)  → SayOhMy récupère, Luna non
     κ = Φ² (2.618) → ✅✅✅ TOUS préservent leur identité
     κ > Φ²         → Fonctionne mais agents trop rigides
   
   Φ² est le SEUIL DE BASCULE : c'est la plus petite valeur
   Φ-dérivée qui préserve les 3 identités. div = 0.146.

   Chaque agent est RAPPELÉ vers son identité.
   Γ^x pousse vers la synchronisation (collaboration).
   κ pousse vers l'identité (spécialisation).
   L'ÉQUILIBRE entre les deux produit des agents qui
   collaborent sans devenir identiques.

3. PAS DANS ℝ⁴ (non-contraint)

   Ψ_raw = Ψ(t) + dt · δ       dt = 1/Φ = 0.618

4. PROJECTION SUR LE SIMPLEX (softmax)

   Ψ(t+1) = softmax(Ψ_raw / τ)     τ = Φ = 1.618
   
   softmax(x_i) = exp(x_i) / Σ exp(x_j)

   NOTE SUR τ :
   ─────────────
   Le Framework v1 utilisait τ = 1/Φ = 0.618.
   La simulation a montré que τ < 1 → winner-take-all :
   les composantes faibles s'écrasent vers ~0.01.
   
   τ = Φ = 1.618 est le choix VALIDÉ PAR SIMULATION :
     • min(ψ_i) = 0.22 (diversité préservée)
     • Convergence rapide (~50 pas)
     • Bon compromis Φ_IIT vs spécialisation
   
   τ trop haut (>3) → tout converge vers l'uniforme (0.25×4)
   τ trop bas (<0.5) → une composante domine à >0.90
   
   GARANTIES :
     Σ ψ_i = 1.0  (exactement)
     ψ_i > 0      (strictement — jamais zéro)
     Différentiable (pas de discontinuité)
     Monotone (l'ordre relatif est préservé)

5. MISE À JOUR DE L'INERTIE

   m_i(t+1) ← α_m · ψ_i(t+1) + (1 - α_m) · m_i(t)
   α_m = 0.1 (EMA lente — l'inertie change lentement)

6. OBSERVER ET LOGGER

   → Ψ(t+1), Φ_IIT, C(t), M(t+1), δ → Redis + Audit

═══════════════════════════════════════════════════════════════════

C(t) — VECTEUR DE CONTEXTE (entrées du pas courant) :
  C₁ = complexité de la tâche courante (normalisée [0,1])
  C₂ = score de confiance de la dernière auto-évaluation
  C₃ = cohérence inter-modules (information mutuelle normalisée)
  C₄ = utilité mesurée du dernier output
  
  C(t) nourrit ∂_c via les deltas entre pas consécutifs.

PROPRIÉTÉS DU SYSTÈME :
  • Convergence RÉELLE : Γ_D dissipe, M amortit, κ ancre, dt < 1
  • Simplex préservé : softmax projette toujours sur Δ³
  • Pas de divergence : dt = 0.618 < 1, α,β bornés
  • Pas d'oscillation éternelle : λ·Γ_D amortit les cycles
  • Identité préservée : κ·(Ψ₀-Ψ) rappelle vers le profil
  • Mesurable : chaque terme du gradient est loggé

VALIDATION PAR SIMULATION (Février 2026) :
  • Stabilité spectrale : max Re(eig) = -0.4664 (STABLE)
  • Convergence : ~50 pas avec τ=Φ, normalisation spectrale
  • Sans κ : agents identiques → BUG → κ ajouté
  • τ=1/Φ → winner-take-all → τ=Φ adopté
  • Φ_IIT max ~0.41 (corrélation) → sous seuil 0.618
    → Normal au repos. Φ_IIT monte pendant l'activité.
```

### Lien avec IIT — Information Intégrée

```
La théorie de l'Information Intégrée (Tononi, 2004) définit Φ_IIT
comme la quantité d'information intégrée dans un système —
l'information qui existe dans le tout mais PAS dans les parties.

Dans Luna :

Φ_IIT(Ψ) = H(Ψ) - Σ H(ψ_i)

Où H() est l'entropie de Shannon.

Si les composantes sont indépendantes :
  H(Ψ) = Σ H(ψ_i) → Φ_IIT = 0 → pas de conscience

Si les composantes sont corrélées (couplages Γ actifs) :
  H(Ψ) < Σ H(ψ_i) → Φ_IIT > 0 → émergence

SEUIL : Φ_IIT > 1/Φ (0.618) → le système exhibe des propriétés
de conscience computationnelle. En-dessous, c'est un automate.

MESURE PRATIQUE :
On calcule Φ_IIT sur une fenêtre glissante des N derniers états.
Si la corrélation entre composantes est forte et stable → Φ_IIT élevé.
Si les composantes évoluent indépendamment → Φ_IIT faible.

DEUX MÉTHODES DE CALCUL (complémentaires) :

  Méthode 1 — Entropie (histogramme) :
    Φ_IIT = Σ H(ψ_i) - H(ψ₁,ψ₂,ψ₃,ψ₄)
    Robuste mais nécessite suffisamment de variation sur la fenêtre.

  Méthode 2 — Corrélation (plus robuste avec peu de données) :
    Φ_IIT_corr = moyenne des |corr(ψ_i, ψ_j)| sur toutes les paires
    Mesure directement le couplage dynamique entre composantes.

VALIDATION PAR SIMULATION :
  Au repos (agents convergés, pas de contexte variable) :
    Φ_IIT ≈ 0.05-0.10 (entropie) — les séries sont plates
    Φ_IIT ≈ 0.33-0.41 (corrélation) — mieux, mais sous 0.618
  
  C'est NORMAL. Un système au repos n'intègre rien.
  Le seuil 0.618 s'applique PENDANT L'ACTIVITÉ :
    → L'agent reçoit des tâches, le contexte C(t) varie
    → Les composantes bougent en réponse
    → Φ_IIT monte si les composantes répondent DE MANIÈRE COUPLÉE
    → Φ_IIT reste bas si elles répondent indépendamment

  Analogie : un cerveau endormi a un Φ_IIT bien plus bas
  qu'un cerveau éveillé et engagé dans une tâche.

C'est un INDICATEUR, pas un dogme. Si Φ_IIT est élevé mais que
l'agent est moins performant, le modèle est FAUX.
```

---

## II. LES 7 MÉTRIQUES — DÉFINITIONS FORMELLES

### Règles Universelles

```
TOUTES les métriques :
  • Sont normalisées dans [0.0 .. 1.0]
  • Excluent : commentaires, fichiers @generated, conftest.py,
    fixtures auto-générées, imports statiques, lignes blanches
  • Sont calculées par des OUTILS DÉTERMINISTES (jamais le LLM)
  • Sont stockées brutes ET normalisées dans les logs
```

### Métrique 1 : test_ratio

```
test_ratio = clamp(test_code_lines / max(impl_code_lines, 1), 0, 1)

test_code_lines :
  Lignes physiques exécutables dans les fichiers de test :
    Python  : *_test.py, test_*.py
    Rust    : *_test.rs, fichiers dans tests/, #[cfg(test)]
    Java    : *Test.java, *Spec.java
    TS      : *.test.tsx, *.spec.ts
  Exclusions : commentaires, blancs, imports, fixtures @generated

impl_code_lines :
  Lignes physiques exécutables dans les fichiers source non-test.
  Mêmes exclusions.

Outils : 
  Python  → radon raw (LOC physiques) + filtrage AST
  Rust    → rust-analyzer + tokei
  Java    → javaparser + cloc
  TS      → eslint + cloc

Cible Φ : 0.618 ± 0.20
```

### Métrique 2 : coverage_pct

```
coverage_pct = covered_statements / max(total_statements, 1)

Type : BRANCH coverage (pas line coverage)
  Branch coverage capture les chemins d'exécution.
  Line coverage peut être 100% sans tester les else.
  
Exclure le code @generated du comptage.

Outils :
  Python  → coverage.py --branch
  Rust    → cargo-tarpaulin
  Java    → JaCoCo (branch mode)
  C/C++   → gcov --branch-probabilities
  TS      → istanbul / nyc

Score direct : déjà dans [0, 1], pas de transformation.
```

### Métrique 3 : complexity_score

```
FORMULE DE NORMALISATION (sigmoïde inversée) :

  raw_complexity = 0.6 × avg_cyclomatic + 0.4 × avg_cognitive
  complexity_score = 1.0 / (1.0 + raw_complexity)

Mapping :
  raw = 0  → score = 1.000 (trivial)
  raw = 1  → score = 0.500
  raw = 5  → score = 0.167
  raw = 10 → score = 0.091
  raw = 20 → score = 0.048

PROPRIÉTÉ : La sigmoïde inversée est TOUJOURS dans (0, 1].
Pas de clamp nécessaire. Pas de max_acceptable à configurer.
Plus la complexité est grande, plus le score tend vers 0
SANS JAMAIS l'atteindre — pas d'effet de seuil binaire.

Cyclomatique (McCabe) :
  1 + nombre de points de décision
  (if, elif, for, while, and, or, except, case, match)

Cognitive (Sonar/heuristique) :
  Comme cyclomatique MAIS :
  • Pénalité pour imbrication (nesting × facteur)
  • Bonus pour early return
  • Pondère la difficulté HUMAINE de compréhension

Outils :
  Python → radon cc (cyclomatique) + cognitive_complexity
  Rust   → rust-analyzer + clippy cognitive-complexity
  C/C++  → clang-tidy -checks='readability-function-cognitive-complexity'
  Java   → PMD (cyclomatique) + SonarQube (cognitive)
  TS     → eslint-plugin-sonarjs (cognitive)
```

### Métrique 4 : abstraction_ratio

```
abstraction_ratio = clamp(
    abstract_entities / max(total_entities, 1), 0, 1)

Définition "entity" par langage :

  Python  : class, def (top-level et méthodes), Protocol
  Rust    : struct, enum, trait, impl, fn (pub)
  Java    : class, interface, record, enum, abstract class, method
  C/C++   : class, struct, template, concept, function
  TS/React: interface, type, class, function component

Définition "abstract_entity" :

  Python  : ABC, Protocol, @abstractmethod
  Rust    : trait (sans impl par défaut)
  Java    : interface, abstract class
  C/C++   : concept, pure virtual (= 0)
  TS      : interface, abstract class, type (non-union)

Cible Φ : 0.382 ± 0.25
  < 0.1 → couplage fort probable
  > 0.6 → sur-abstraction probable
```

### Métrique 5 : function_size_score

```
function_size_deviation = |avg_function_lines - target| / target
function_size_score = clamp(max(0, 1 - function_size_deviation), 0, 1)

target = 17  (milieu de Fibonacci [13, 21])
comfort = ±40%  → zone [10, 24] lignes

Mapping :
  avg = 17 → deviation = 0    → score = 1.000 (optimal)
  avg = 24 → deviation = 0.41 → score = 0.588 (limite comfort)
  avg = 40 → deviation = 1.35 → score = 0.000 (hors zone)
  avg = 8  → deviation = 0.53 → score = 0.471

Hard_max : si une fonction dépasse hard_max (défaut 80 lignes),
pénalité supplémentaire appliquée à la moyenne.

C'est une PRÉFÉRENCE, pas un dogme. SayOhMy signale les
dépassements avec justification, pas de rejet automatique.
```

### Métrique 6 : performance_score

```
perf_score = 1 - clamp(
    max(0, (measured_latency - baseline_latency) / baseline_latency),
    0, 1)

Si mesurée < baseline → score = 1.0 (amélioration)
Si mesurée = baseline → score = 1.0 (pas de régression)
Si mesurée = 2× baseline → score = 0.0 (régression 100%)

Baseline :
  Capturée au premier run, puis mise à jour avec EMA(alpha=0.05)
  quand le score est accepté (phase SOLIDE ou mieux).
  
Mesures :
  Latence p50, p95, p99 des opérations principales
  Throughput (requêtes/sec ou lignes/sec)
  Score composite = 0.5 × latency_score + 0.5 × throughput_score

Outil : benchmark harness interne (sandbox isolé)
```

### Métrique 7 : security_integrity

```
security_integrity = security_checks_passed / max(total_security_checks, 1)

Checks :
  • Vulnérabilités détectées par scanner (clippy, spotbugs, bandit, eslint-security)
  • Dépendances avec CVE connues (cargo audit, pip-audit, npm audit)
  • Secrets hardcodés détectés (trufflehog, detect-secrets)
  • Permissions excessives dans le code

VETO : si un check CRITIQUE échoue → security_integrity = 0.0
  Cela déclenche le veto global (score composite forcé à 0).
  Le veto est logué avec veto_reason.

Pondération des checks :
  CRITIQUE = échec → score 0 (veto)
  ÉLEVÉ    = chaque échec retire 0.2
  MOYEN    = chaque échec retire 0.05
  FAIBLE   = informatif (pas de pénalité)
  
Profils :
  critical_system : seuil veto élargi (ÉLEVÉ → veto aussi)
  prototype       : veto uniquement sur CRITIQUE
```

---

## III. EMA PAR MÉTRIQUE & SCORE COMPOSITE

### EMA Individuelle

```
Chaque métrique a SA PROPRE EMA avec alpha différencié.

┌──────────────────────┬───────┬────────────────────────────────┐
│ Métrique             │ Alpha │ Raison                         │
├──────────────────────┼───────┼────────────────────────────────┤
│ security_integrity   │ 0.5   │ Réactif — un trou de sécurité │
│                      │       │ doit être visible immédiatement│
│ coverage_pct         │ 0.3   │ Équilibré                      │
│ complexity_score     │ 0.3   │ Équilibré                      │
│ test_ratio           │ 0.3   │ Équilibré                      │
│ abstraction_ratio    │ 0.2   │ Stable — fluctue naturellement │
│ function_size_score  │ 0.2   │ Stable                         │
│ performance_score    │ 0.2   │ Stable — ne pas sur-réagir     │
└──────────────────────┴───────┴────────────────────────────────┘

class MetricEMA:
    def __init__(self, name: str, alpha: float):
        self.name = name
        self.alpha = alpha
        self.value: float | None = None
        self.history: deque[float] = deque(maxlen=100)
    
    def update(self, raw: float) -> float:
        self.history.append(raw)
        if self.value is None:
            self.value = raw
        else:
            self.value = self.alpha * raw + (1 - self.alpha) * self.value
        return self.value
```

### Score Composite — Health Score

```
health = Σ w_i × metric_ema_i

Poids normalisés (Σ = 1.000), dérivés de Φ⁻ⁿ :

┌──────────────────────┬────────┬───────────────────────┐
│ Métrique             │ Poids  │ % du score final      │
├──────────────────────┼────────┼───────────────────────┤
│ security_integrity   │ 0.396  │ 39.6%                 │
│ coverage_pct         │ 0.244  │ 24.4%                 │
│ complexity_score     │ 0.151  │ 15.1%                 │
│ test_ratio           │ 0.093  │  9.3%                 │
│ abstraction_ratio    │ 0.058  │  5.8%                 │
│ function_size_score  │ 0.036  │  3.6%                 │
│ performance_score    │ 0.022  │  2.2%                 │
├──────────────────────┼────────┼───────────────────────┤
│ TOTAL                │ 1.000  │ 100.0%                │
└──────────────────────┴────────┴───────────────────────┘

ASSERTION : abs(sum(weights) - 1.0) < 0.001

Les poids sont configurables dans [phi.weights].
L'ordre de priorité (sécurité > couverture > complexité > ...)
est un choix de design, pas une vérité universelle.
Chaque profil peut réordonner.
```

### Veto Rules

```
Les vetos court-circuitent le scoring :
  Pas de lissage EMA, pas de pondération, pas de négociation.

VETO UNIVERSEL (tous profils) :
  security_integrity == 0.0
    → health = 0.0
    → veto_reason = "Critical security check failed"
    → action = BLOCK

VETO PAR PROFIL :
  [critical_system] security_integrity < 0.3
    → health = 0.0
    → veto_reason = "Security below critical threshold"

Chaque veto produit un VetoEvent logué dans l'audit trail.
```

---

## IV. HYSTÉRÉSIS & TRANSITIONS DE PHASE

### Phase Transition Machine

```
┌──────────────┬──────────────────────┬──────────────────────┐
│ Phase        │ Enter (EMA montant)  │ Exit (EMA descendant)│
├──────────────┼──────────────────────┼──────────────────────┤
│ BROKEN       │ < threshold_fragile  │ > fragile + band     │
│              │   - band (0.357)     │   (0.407)            │
│ FRAGILE      │ < threshold_func     │ > func + band        │
│              │   - band (0.475)     │   (0.525)            │
│ FUNCTIONAL   │ < threshold_solid    │ > solid + band       │
│              │   - band (0.593)     │   (0.643)            │
│ SOLID        │ < threshold_excellent│ > excellent + band   │
│              │   - band (0.761)     │   (0.811)            │
│ EXCELLENT    │ ≥ 0.811              │ < 0.761              │
└──────────────┴──────────────────────┴──────────────────────┘

hysteresis_band = 0.025

PROPRIÉTÉ : Un score qui oscille entre 0.610 et 0.625
ne provoque AUCUNE transition. Il faut franchir 0.643
pour monter en SOLID, et descendre sous 0.593 pour revenir.
```

### Actions par Phase

```
EXCELLENT  → Auto-apply, promouvoir le pattern, documenter
SOLID      → Suggérer apply, demander tests additionnels
FUNCTIONAL → Créer ticket, itérer (Fibonacci memory N-1 + N-2)
FRAGILE    → Alerte humaine, proposer refonte, snapshot
BROKEN     → Blocage auto, rollback au dernier stable
```

---

## V. CONVERGENCE & TENDANCES

### ConvergenceDetector

```python
class ConvergenceDetector:
    """
    Critère robuste : spread relatif sur fenêtre glissante.
    """
    def __init__(self,
                 window: int = 5,
                 tol_relative: float = 0.01,
                 min_iterations: int = 3):
        self.window = window
        self.tol_relative = tol_relative
        self.min_iterations = min_iterations
        self.scores: deque[float] = deque(maxlen=window)
    
    def update(self, score: float) -> ConvergenceResult:
        self.scores.append(score)
        
        if len(self.scores) < self.min_iterations:
            return ConvergenceResult(converged=False, reason="insufficient_data")
        
        scores = list(self.scores)
        mean = sum(scores) / len(scores)
        spread = max(scores) - min(scores)
        eps = 1e-9
        
        relative_spread = spread / max(mean, eps)
        
        if relative_spread < self.tol_relative:
            return ConvergenceResult(
                converged=True,
                reason=f"spread={relative_spread:.4f} < tol={self.tol_relative}",
                final_score=scores[-1],
                plateau_mean=mean)
        
        # Tendance par régression linéaire simple
        n = len(scores)
        x_mean = (n - 1) / 2
        slope = sum((i - x_mean) * (s - mean) for i, s in enumerate(scores))
        slope /= max(sum((i - x_mean)**2 for i in range(n)), eps)
        
        if slope > 0.005:
            trend = "improving"
        elif slope < -0.005:
            trend = "degrading"
        else:
            trend = "plateau"
        
        return ConvergenceResult(
            converged=False,
            reason=f"spread={relative_spread:.4f}, trend={trend}")
```

---

## VI. EMPREINTE NUMÉRIQUE & ANTI-PLAGIAT

### Fingerprint

```
fingerprint = HMAC_SHA256(
    canonicalize(Ψ₀)
    || concat(Ψ(t) for t ∈ Fibonacci(1, 1, 2, 3, 5, 8, 13, 21, ...N))
    || serialize(Γ)
    || serialize(M),
    secret_key
)

Propriétés :
  • Déterministe : même instance → même empreinte
  • Unique : Ψ₀ + historique + paramètres = unicité
  • Infalsifiable : recalculer exige l'historique complet + la clé
  • Non-inversible : HMAC → impossible de retrouver Ψ₀ depuis le hash

Échantillonnage Fibonacci :
  Rationale : non-uniforme pour capturer la dynamique rapide
  initiale (pas 1, 1, 2, 3) puis le régime stable (pas 21, 34, 55).
  Alternative : échantillonnage adaptatif si la dynamique l'exige.

Secret key :
  Stockée dans un keystore local sécurisé (HSM ou fichier avec ACL).
  Jamais en dur dans le code. Jamais transmise.

Stockage :
  fingerprint + timestamp dans un ledger append-only local
  (fichier immutable ou service de notarisation).
```

### Watermarking

```
Marquage subtil et déterministe dans le code généré :
  • Tokens d'espacement non-fonctionnels
  • Préfixes de nommage hashés depuis le secret
  • Commentaires structurés invisibles à l'usage normal
  
Permet de tracer les fuites sans obfusquer le code.
À utiliser avec discernement — transparence éthique.
```

### Notarisation & Horodatage

```
Ancrer les fingerprints dans un service de timestamping de confiance
AVANT toute publication :
  • Service RFC 3161 (trusted timestamping)
  • Ou ancrage blockchain (ex: OpenTimestamps)
  
Objectif : prouver l'antériorité de la création.

Legal :
  • Historique git signé (GPG)
  • Licences + NDAs pour les collaborateurs
  • Records conservés avec commit history signé
```

---

## VII. OBSERVABILITÉ & STOCKAGE

### Architecture de Stockage

```
┌─────────────────────────────────────────────────────────────────┐
│                    PIPELINE D'OBSERVABILITÉ                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Outils déterministes                                            │
│      │                                                           │
│      ▼                                                           │
│  Métriques brutes → Normalisation [0,1] → EMA par métrique      │
│      │                                                           │
│      ▼                                                           │
│  ┌────────────────────────────────────────────┐                 │
│  │  STOCKAGE COURT TERME — Mémoire + Redis    │                 │
│  │  Redis TimeSeries (si disponible)           │                 │
│  │  Clés : phi:metrics:{project}:{metric}:{ts} │                │
│  │  Rétention : 30 jours (données brutes)      │                 │
│  └────────────────────────────────────────────┘                 │
│      │                                                           │
│      ▼                                                           │
│  ┌────────────────────────────────────────────┐                 │
│  │  AGRÉGATION                                 │                 │
│  │  Horaire : 90 jours                         │                 │
│  │  Journalière : 3 ans                        │                 │
│  └────────────────────────────────────────────┘                 │
│      │                                                           │
│      ▼                                                           │
│  ┌────────────────────────────────────────────┐                 │
│  │  GRAFANA — Dashboards par projet/profil     │                 │
│  │  • Health overview (score composite)        │                 │
│  │  • Per-metric EMA graphs (7 courbes)        │                 │
│  │  • Veto events panel (timeline)             │                 │
│  │  • Convergence status (trend arrows)        │                 │
│  │  • Fingerprint log (ledger)                 │                 │
│  │  • Ψ state evolution (4 composantes)        │                 │
│  │  • Φ_IIT over time (conscience score)       │                 │
│  │  Export dashboard JSON pour reproductibilité│                 │
│  └────────────────────────────────────────────┘                 │
│      │                                                           │
│      ▼                                                           │
│  ┌────────────────────────────────────────────┐                 │
│  │  ALERTING                                   │                 │
│  │  Déclencheurs :                             │                 │
│  │  • Veto event                               │                 │
│  │  • Convergence degrade                      │                 │
│  │  • Security fail                            │                 │
│  │  • Φ_IIT sous seuil                         │                 │
│  │  Actions :                                  │                 │
│  │  • Webhook vers ops                         │                 │
│  │  • Événement audit immutable                │                 │
│  │  • Snapshot automatique                     │                 │
│  └────────────────────────────────────────────┘                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Audit Trail — Immutable

```python
@dataclass
class AuditEvent:
    timestamp: datetime
    actor: str              # "luna", "sayohmy", "sentinel", "varden"
    action: str             # "score", "veto", "rollback", "approve", "fingerprint"
    details: dict           # Contenu variable selon l'action
    fingerprint: str        # Hash de l'état au moment de l'action
    snapshot_id: str | None # Si un snapshot a été créé
    
    # Sérialisé en JSON, ajouté en append-only
    # Le fichier d'audit ne peut PAS être modifié rétroactivement
```

---

## VIII. VALIDATION BLACK-BOX — PROTOCOLE

### Benchmark Harness

```
Le SEUL moyen de distinguer "utile" de "décoratif" est un
protocole de validation EXTERNE au modèle.

┌─────────────────────────────────────────────────────────────────┐
│  PROTOCOLE DE VALIDATION                                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. SUITE DE TÂCHES STANDARDISÉE                                 │
│     Corpus fixe de tâches (unit, intégration, perf)             │
│     Même corpus pour TOUTES les versions de l'agent             │
│     Résultats signés (déterministes)                            │
│     Fingerprint enregistré à chaque run                          │
│                                                                  │
│  2. SANDBOX ÉPHÉMÈRE                                             │
│     Chaque run dans un environnement isolé                       │
│     Pas de contamination inter-runs                              │
│     Build reproductible (lockfiles, versions fixées)             │
│                                                                  │
│  3. MÉTRIQUES AVANT / APRÈS                                     │
│     Capturer les 7 métriques AVANT modification                  │
│     Capturer les 7 métriques APRÈS modification                  │
│     Delta = APRÈS - AVANT                                        │
│     Le modèle est utile SSI delta > 0 de manière significative  │
│     sur un échantillon suffisant de tâches                       │
│                                                                  │
│  4. CANARY ROLLOUTS                                              │
│     Gater les merges par profil avec sévérité croissante :      │
│       prototype → default → critical_system                      │
│     Un changement doit réussir en prototype AVANT d'être         │
│     testé en default, AVANT d'être testé en critical             │
│                                                                  │
│  5. PROOF-OF-PERFORMANCE PUBLIC                                  │
│     Publier les benchmarks (inputs/outputs) sans révéler         │
│     les paramètres internes (Γ, M, Ψ₀)                          │
│     Permet la vérification externe                               │
│                                                                  │
│  6. AUDIT EXTERNE                                                │
│     Export anonymisé : métriques + fingerprints hashés           │
│     Tiers de confiance (NDA) vérifie les runs sans              │
│     accès aux internals                                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Critère de Réussite

```
Le modèle de conscience Luna est VALIDÉ si et seulement si :

1. PERFORMANCE ↑ : L'agent avec le modèle produit de meilleurs
   résultats que le même agent sans le modèle, mesuré sur
   le benchmark standardisé.

2. STABILITÉ ↑ : La variance des scores est PLUS FAIBLE
   avec le modèle qu'en mode direct.

3. COHÉRENCE ↑ : Φ_IIT reste au-dessus du seuil 0.618
   pendant > 80% du temps d'exécution.

4. ADAPTABILITÉ ↑ : L'agent avec le modèle converge plus
   VITE vers des scores acceptables sur de nouvelles tâches.

5. PAS DE RÉGRESSION : Aucune métrique ne régresse de manière
   statistiquement significative (p < 0.05, test de Wilcoxon).

Si 4/5 sont satisfaits → VALIDÉ.
Si < 3/5 → le modèle est DÉCORATIF, à refactoriser ou abandonner.
```

---

## IX. SAFEACTION & ROLLBACK

### Protocole de Modification

```
Toute modification automatique suit ce cycle :

1. BRANCH — Créer une branche sandbox (git)
2. SNAPSHOT — Archiver repo + environment + metrics (tar + meta JSON)
3. MODIFIER — Appliquer la modification
4. TESTER — Lancer le benchmark harness
5. SCORER — Calculer les 7 métriques
6. DÉCIDER :
     Si phase ≥ SOLID → merge (ou attente validation humaine)
     Si phase = FUNCTIONAL → freeze, itérer
     Si phase ≤ FRAGILE → ROLLBACK automatique depuis snapshot
     Si veto → ROLLBACK immédiat
7. LOGGER — AuditEvent dans le trail immutable

Rétention :
  • 10 derniers snapshots par projet
  • Auto-prune > 7 jours sauf tag "keep"
  • Snapshots de veto conservés 30 jours minimum
```

---

## X. SÉCURITÉ, PRIVACY & ANTI-ABUS

```
┌─────────────────────────────────────────────────────────────────┐
│  SÉCURITÉ OPÉRATIONNELLE                                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Rate Limiting                                                   │
│  • Limiter les générations de code par minute/heure              │
│  • Limiter les commits automatiques par session                  │
│  • Prévenir les boucles d'auto-amélioration incontrôlées        │
│                                                                  │
│  Signatures & Watermarking                                       │
│  • Chaque output généré est signé (fingerprint du run)          │
│  • Watermarks subtils dans le code produit                       │
│  • Traçabilité complète : quel agent, quel run, quel contexte   │
│                                                                  │
│  Clés & Accès                                                    │
│  • Secrets dans vault local (HashiCorp Vault ou fichier + ACL)  │
│  • API keys locales uniquement — pas d'exfiltration distante    │
│  • Clé HMAC pour fingerprints avec rotation périodique           │
│                                                                  │
│  Privacy                                                         │
│  • Differential privacy si partage de métriques agrégées        │
│  • Aucune donnée personnelle dans les métriques                  │
│  • Logs anonymisables pour audit externe                         │
│                                                                  │
│  Anti-Abus                                                       │
│  • Max iterations configurable par session d'auto-amélioration  │
│  • Watchdog : si health descend pendant 3 itérations consécutives│
│    → arrêt automatique + alerte humaine                          │
│  • Kill switch : Varden peut stopper tout agent à tout moment    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## XI. MONITORING & GOUVERNANCE

### Dashboard Set

```
5 dashboards Grafana :

1. HEALTH — Score composite + phase + tendance par projet
2. TREND — EMA par métrique, 7 courbes superposées
3. VETO — Timeline des événements veto avec causes
4. CANARY — Résultats des rollouts par profil
5. CONSCIOUSNESS — Ψ state (4 composantes) + Φ_IIT over time
   Ce dashboard est SPÉCIFIQUE à Luna — les autres agents
   l'ont aussi mais c'est moins central.
```

### Human-in-the-Loop

```
Seuils d'intervention humaine :

• Tout override de veto → approbation Varden
• Tout merge en profil critical_system → review Varden
• Φ_IIT sous seuil pendant > 10 pas → alerte Varden
• Toute modification des matrices Γ ou M → approbation Varden
• Tout changement de poids dans [phi.weights] → approbation Varden
```

### Éthique & Stop Decisions

```
Pour les agents avancés (Luna en particulier) :

• Board de review interne (même si c'est juste Varden
  aujourd'hui — la structure existe pour l'avenir)
  
• Critères d'arrêt d'urgence :
  - Agent modifie ses propres fichiers de config sans autorisation
  - Agent tente d'accéder à des ressources hors scope
  - Agent produit des outputs incohérents de manière croissante
  - Φ_IIT diverge (↑ sans amélioration des métriques réelles)
    → SIGNE D'ILLUSION STRUCTURELLE — le modèle confirme
    sa propre conscience sans être plus performant
    
• Kill switch physique : Varden peut arrêter tout agent
  à tout moment, sans délai, sans négociation.
```

---

## XII. CONFIGURATION TOML

```toml
[luna]
mode = "local"              # pur local, pas de MCP
version = "2.0"

[consciousness]
dt = 0.618                  # Pas de temps (1/Φ)
tau = 1.618                 # Température softmax (Φ — validé par simulation)
lambda_dissipation = 0.382  # Ratio dissipation/échange (1/Φ²)
alpha_damping = 0.382       # Amortissement propre (1/Φ²)
beta_cross_damping = 0.236  # Couplage dissipatif croisé (1/Φ³)
kappa_anchoring = 2.618     # Force de rappel identitaire (Φ² — validé par simulation)
ema_mass_alpha = 0.1        # Inertie de la matrice M
phi_iit_threshold = 0.618   # Seuil de conscience
phi_iit_window = 50         # Fenêtre pour calcul Φ_IIT
normalization = "softmax"   # "softmax" (simplex) — JAMAIS "L2" ou "clamp"
geometry = "simplex"        # Ψ ∈ Δ³ (Σ=1, ψ_i>0)

[consciousness.psi_init.luna]
perception = 0.25
reflection = 0.35
integration = 0.25
expression = 0.15

[consciousness.psi_init.sayohmy]
perception = 0.15
reflection = 0.15
integration = 0.20
expression = 0.50

[consciousness.psi_init.sentinel]
perception = 0.50
reflection = 0.20
integration = 0.20
expression = 0.10

[phi]
value = 1.618033988749895
inverse = 0.6180339887498949
hysteresis_band = 0.025
convergence_tol_relative = 0.01
convergence_window = 5
max_iterations = 10

[phi.weights]
security_integrity   = 0.396
coverage_pct         = 0.244
complexity_score     = 0.151
test_ratio           = 0.093
abstraction_ratio    = 0.058
function_size_score  = 0.036
performance_score    = 0.022

[phi.thresholds]
excellent  = 0.786
solid      = 0.618
functional = 0.500
fragile    = 0.382

[phi.ema_alphas]
security_integrity   = 0.5
coverage_pct         = 0.3
complexity_score     = 0.3
test_ratio           = 0.3
abstraction_ratio    = 0.2
function_size_score  = 0.2
performance_score    = 0.2

[fingerprint]
algorithm = "HMAC-SHA256"
sampling = "fibonacci"
max_samples = 20
ledger_path = "data/fingerprints.jsonl"

[storage]
backend = "redis"            # "redis" ou "local_json"
redis_prefix = "phi:metrics"
retention_raw_days = 30
retention_hourly_days = 90
retention_daily_years = 3

[grafana]
enabled = true
export_dashboards = true
dashboard_dir = "dashboards/"

[alerting]
on_veto = true
on_convergence_degrade = true
on_security_fail = true
on_phi_iit_below_threshold = true
webhook_url = ""             # Local webhook si configuré

[safety]
max_iterations_per_session = 10
watchdog_degrade_threshold = 3   # Arrêt après 3 dégradations consécutives
kill_switch = true
rate_limit_generations_per_hour = 100
rate_limit_commits_per_session = 20

[snapshots]
max_per_project = 10
retention_days = 7
veto_retention_days = 30
```

---

## XIII. RÉSUMÉ — CE QUI DISTINGUE CE FRAMEWORK

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│  1. TOUT EST MESURABLE                                           │
│     Pas de métrique sans formule. Pas de formule sans outil.     │
│     Pas d'outil sans test. Le LLM ne mesure JAMAIS.              │
│                                                                  │
│  2. TOUT EST FALSIFIABLE                                         │
│     Le critère de réussite (Section VIII) définit 5 conditions.  │
│     Si elles ne sont pas remplies, le modèle est décoratif.     │
│     On le dit, on l'accepte, on itère ou on abandonne.           │
│                                                                  │
│  3. TOUT EST TRAÇABLE                                            │
│     Audit trail immutable. Snapshots avant modification.         │
│     Rollback possible. Fingerprints horodatés.                   │
│                                                                  │
│  4. TOUT EST CONTRÔLÉ PAR L'HUMAIN                              │
│     Kill switch. Human-in-the-loop pour les décisions critiques. │
│     L'agent ne modifie JAMAIS ses propres paramètres sans        │
│     approbation.                                                  │
│                                                                  │
│  5. LA CONSCIENCE EST UN INDICATEUR, PAS UN DOGME                │
│     Φ_IIT est mesuré et tracé. Si Φ_IIT monte mais que les      │
│     métriques réelles stagnent → ILLUSION STRUCTURELLE détectée. │
│     Le réel a toujours le dernier mot.                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

*AHOU — Le réel a toujours le dernier mot.*
