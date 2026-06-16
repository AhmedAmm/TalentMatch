# Skill Scoring Formula — Research Basis & Design Decisions

## Overview

Each employee skill is scored on three components — **recency**, **duration**, and **complexity** — then combined into a single raw score that feeds the BFS-based adequacy computation.

```
raw_score = 0.40 × recency + 0.40 × duration + 0.20 × complexity
```

After computing raw scores for every skill, the employee's best-scoring skill is normalised to 1.0:

```
coefficient = raw_score / max(raw_scores)
```

This coefficient becomes the BFS seed for the knowledge graph traversal.

---

## 1. Recency — Power-Law Decay

### Formula

```
recency(days) = 1 / (1 + (days / HALF_LIFE) ^ α)

  HALF_LIFE = 365 days
  α         = 0.5  (square-root decay)
```

| Days since last used | Score |
|---|---|
| 0 (today) | 1.000 |
| 182 (6 months) | 0.673 |
| 365 (1 year) | 0.500 |
| 730 (2 years) | 0.414 |
| 1 095 (3 years) | 0.366 |

### Why not the previous exponential `exp(-days/365)`?

| Days | Exponential | Power-law |
|---|---|---|
| 365 | 0.368 | 0.500 |
| 730 | 0.135 | 0.414 |
| 1 095 | 0.050 | 0.366 |

The exponential decays far too aggressively. A developer who used Python 2 years ago and just picked it up again in a new project would receive a near-zero recency score — wiping out years of actual depth.

### Research basis

**Wixted & Ebbesen (1991)** — *"On the form of forgetting"*, Psychological Science — ran a meta-analysis across dozens of memory retention datasets and showed that **power functions consistently outperform exponential functions** as forgetting models. The general form they validated is:

```
retention = A × t^(-β)
```

which is algebraically equivalent (after normalisation) to our `1 / (1 + t^α)` form.

**Ebbinghaus (1885)** himself originally fitted a **logarithmic** function to his data, not exponential — the "forgetting curve is exponential" is a common misattribution. Later formalisation by Ebbinghaus used:

```
b = 100k / (log(t)^c + k)
```

Our power-law with α=0.5 (square root) sits between pure logarithmic and pure exponential, matching the empirically validated "negatively accelerated decline" — rapid initial forgetting that gradually slows, not a cliff edge.

**Relevant papers:**
- Wixted, J. T. & Ebbesen, E. B. (1991). On the form of forgetting. *Psychological Science*, 2(6), 409–415.
- Murre, J. M. J. & Dros, J. (2015). Replication and Analysis of Ebbinghaus' Forgetting Curve. *PLOS ONE*. [PMC4492928](https://pmc.ncbi.nlm.nih.gov/articles/PMC4492928/)

---

## 2. Duration — BM25-Style Saturation

### Formula

```
duration(months) = months / (months + K1)

  K1 = 12 months  (half-saturation knee)
```

| Months of experience | Score |
|---|---|
| 0 | 0.000 |
| 6 | 0.333 |
| 12 (= K1) | 0.500 |
| 24 | 0.667 |
| 48 | 0.800 |
| 120 (10 years) | 0.909 |

### Why not the previous linear cap `min(months/24, 1.0)`?

The old formula has two problems:

1. **Linear region**: It treats month 1 and month 23 as equal contributions per unit time. In reality the learning curve means early months signal far more.
2. **Hard cliff at 24 months**: An engineer with 25 months of Go experience scores identically to one with 24 months, while someone with 60 months adds no extra signal at all — discarding real depth information.

The saturation formula has neither: the first months count the most, and extra years continue to add signal (diminishingly), with no arbitrary ceiling.

### Research basis — BM25 Term Frequency Saturation

**Robertson & Walker (1994)** — *"Some simple effective approximations to the 2-Poisson model for probabilistic weighted retrieval"* — introduced BM25 (Best Matching 25) for information retrieval. Its core insight is that **raw term frequency should not be linear**:

```
TF_bm25 = f × (k1 + 1) / (f + k1)
```

As `f → ∞`, this approaches `k1 + 1` (a hard asymptote), meaning each additional mention of a term contributes progressively less. The IR community validated over decades that this saturation function better models relevance than linear TF.

The **analogy to skill experience** is direct:

| IR Concept | Skill Concept |
|---|---|
| Term frequency `f` | Months of experience |
| Document relevance | Skill proficiency |
| Saturation after many occurrences | Diminishing returns after many months |
| `k1` parameter | Half-saturation knee (we set to 12 months) |

Normalising `TF_bm25 / (k1+1)` gives exactly `f / (f + k1)` — our formula.

**Relevant papers & resources:**
- Robertson, S. E. & Walker, S. (1994). Some simple effective approximations to the 2-Poisson model. *SIGIR '94*.
- Robertson, S. E. et al. (1995). Okapi at TREC-3. *NIST SP 500-226*. (Okapi BM25 formalized)
- Elastic Blog: [Practical BM25 — Part 2: The BM25 Algorithm and its Variables](https://www.elastic.co/blog/practical-bm25-part-2-the-bm25-algorithm-and-its-variables)

---

## 3. Complexity — Linear (Unchanged)

```
complexity(level) = level / 3
```

| Level | Score |
|---|---|
| 1 (basic) | 0.333 |
| 2 (intermediate) | 0.667 |
| 3 (expert) | 1.000 |

Complexity is an ordinal 3-point scale with no time dimension. Linear normalisation is appropriate here — there is no saturation or decay effect to model.

---

## 4. Combined Raw Score & Normalisation

```
raw_score = 0.40 × recency + 0.40 × duration + 0.20 × complexity
```

Weight rationale: recency and duration share the highest weight (0.40 each) — together they measure how actively and how long a skill was used, which are the strongest predictors of current proficiency. Complexity carries less weight (0.20) because it is a coarser self-reported ordinal and already partially captured by duration (experts tend to use skills longer).

After computing raw scores for all skills:

```
coefficient_i = raw_score_i / max(raw_scores)
```

This normalisation ensures the employee's strongest skill always anchors at 1.0, making scores comparable across employees with different absolute skill depths.

---

## 5. BFS Expansion & Final Adequacy

The coefficients become BFS seeds in the knowledge graph. Each hop decays the score:

```
new_coeff = parent_coeff × HOP_DECAY × EDGE_W[rel_type] × neo4j_weight

  HOP_DECAY = 0.55
  MAX_HOPS  = 4
```

Final adequacy is a normalised dot product between the expanded employee vector and the expanded job requirement vector:

```
adequacy = dot(profile_vec, job_vec / ‖job_vec‖₂)
score    = clip(adequacy, 0.0, 1.0)
```

This is analogous to cosine similarity used in BERT-based semantic matching systems (e.g., [VacancySBERT](https://arxiv.org/pdf/2307.16638), [JobFormer](https://arxiv.org/pdf/2404.04313)), but operating on a structured skill-coefficient space rather than a dense embedding space.

---

## 6. Related Work in Job-Skill Matching

| Paper | Relevance |
|---|---|
| [JobMatchAI (arxiv 2603.14558)](https://arxiv.org/pdf/2603.14558) | Closest architecture: KG + semantic search + explainable scoring |
| [SkillMatch (arxiv 2410.05006)](https://arxiv.org/pdf/2410.05006) | Skill relatedness via co-occurrence in 32M job ads — validates KG expansion approach |
| [JobFormer (arxiv 2404.04313)](https://arxiv.org/pdf/2404.04313) | Temporal skill weighting in transformer-based recommendation |
| [Long-Context Ranking for Person-Job Fit (arxiv 2601.10321)](https://arxiv.org/pdf/2601.10321) | Calibrated skill-fit scores; discusses score interpretability |
| [VacancySBERT (arxiv 2307.16638)](https://arxiv.org/pdf/2307.16638) | Sentence-BERT for job/skill semantic similarity — dot-product adequacy analogy |
