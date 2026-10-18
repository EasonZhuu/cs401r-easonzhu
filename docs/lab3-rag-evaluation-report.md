# Lab 3 Track B: repeated RAG evaluation

All numbers below are actual outputs of the supplied RAGEvaluator using RAGAS 0.4.3. Judge and generator: `us.anthropic.claude-haiku-4-5-20251001-v1:0`; judge temperature 0 and max_tokens 2048. The supplied four questions and ground truths were retained. Six configurations × four cases × two repetitions = **48 scored rows**; no NaN scores remain. No scores were dropped to select a favorable run.

Each configuration reuses a recorded generation across the two judge repetitions, so the measured range captures judge variation, not new generator samples. Customer profile is an additional context in every configuration. The answer scored is Subject + Body; internal Rationale is excluded consistently.

## Configuration comparison

A/B/C reproduce the teacher queries with top_k=4. CB combines C top 3 and B top 3 and deduplicates chunk IDs, with at most six contexts. The larger context budget is a confound and is disclosed. CB_hardened changes only the copy specification from CB. CB_controlled uses those same hardened raw drafts and adds an application output check and policy-derived fallback. All original raw drafts and delivery modes are retained.

Each entry is mean [minimum, maximum] over four cases and two repetitions.

| Configuration | Faithfulness | Answer relevance | Context recall |
|---|---:|---:|---:|
| A | 0.1840 [0.1000, 0.3077] | 0.3472 [0.2919, 0.4260] | 0.4833 [0.2000, 1.0000] |
| B | 0.1792 [0.0000, 0.5000] | 0.3949 [0.3377, 0.4794] | 0.3875 [0.0000, 0.8000] |
| C | 0.3088 [0.0909, 0.5455] | 0.3596 [0.2967, 0.4790] | 0.4833 [0.2000, 1.0000] |
| CB | 0.2975 [0.0909, 0.4545] | 0.3602 [0.2633, 0.5326] | 0.6833 [0.3333, 1.0000] |
| CB_controlled | 0.0312 [0.0000, 0.1250] | 0.3081 [0.2190, 0.4280] | 0.6833 [0.3333, 1.0000] |
| CB_hardened | 0.1375 [0.0000, 0.3000] | 0.3694 [0.2572, 0.4767] | 0.6833 [0.3333, 1.0000] |

## Means for each repeated run

| Configuration / repeat | Faithfulness | Answer relevance | Context recall |
|---|---:|---:|---:|
| A / 1 | 0.1786 | 0.3412 | 0.4833 |
| A / 2 | 0.1893 | 0.3531 | 0.4833 |
| B / 1 | 0.2292 | 0.3950 | 0.3875 |
| B / 2 | 0.1292 | 0.3949 | 0.3875 |
| C / 1 | 0.3202 | 0.3580 | 0.4833 |
| C / 2 | 0.2975 | 0.3611 | 0.4833 |
| CB / 1 | 0.2975 | 0.3603 | 0.6833 |
| CB / 2 | 0.2975 | 0.3600 | 0.6833 |
| CB_controlled / 1 | 0.0312 | 0.2975 | 0.6833 |
| CB_controlled / 2 | 0.0312 | 0.3187 | 0.6833 |
| CB_hardened / 1 | 0.1062 | 0.3689 | 0.6833 |
| CB_hardened / 2 | 0.1688 | 0.3698 | 0.6833 |

## Per-case means and ranges across the two repetitions

| Configuration / customer | Faithfulness | Answer relevance | Context recall |
|---|---:|---:|---:|
| A / CUST-10000122 | 0.1818 [0.1818, 0.1818] | 0.3521 [0.3502, 0.3540] | 0.3333 [0.3333, 0.3333] |
| A / CUST-10000317 | 0.1214 [0.1000, 0.1429] | 0.2967 [0.2967, 0.2967] | 1.0000 [1.0000, 1.0000] |
| A / CUST-10000588 | 0.1250 [0.1250, 0.1250] | 0.4260 [0.4260, 0.4260] | 0.4000 [0.4000, 0.4000] |
| A / CUST-10000904 | 0.3077 [0.3077, 0.3077] | 0.3139 [0.2919, 0.3358] | 0.2000 [0.2000, 0.2000] |
| B / CUST-10000122 | 0.3333 [0.3333, 0.3333] | 0.3382 [0.3377, 0.3388] | 0.0000 [0.0000, 0.0000] |
| B / CUST-10000317 | 0.3000 [0.1000, 0.5000] | 0.3549 [0.3541, 0.3557] | 0.5000 [0.5000, 0.5000] |
| B / CUST-10000588 | 0.0000 [0.0000, 0.0000] | 0.4794 [0.4794, 0.4794] | 0.2500 [0.2500, 0.2500] |
| B / CUST-10000904 | 0.0833 [0.0833, 0.0833] | 0.4072 [0.4072, 0.4072] | 0.8000 [0.8000, 0.8000] |
| C / CUST-10000122 | 0.0909 [0.0909, 0.0909] | 0.3475 [0.3475, 0.3475] | 0.3333 [0.3333, 0.3333] |
| C / CUST-10000317 | 0.5000 [0.4545, 0.5455] | 0.2967 [0.2967, 0.2967] | 1.0000 [1.0000, 1.0000] |
| C / CUST-10000588 | 0.4444 [0.4444, 0.4444] | 0.3212 [0.3212, 0.3212] | 0.4000 [0.4000, 0.4000] |
| C / CUST-10000904 | 0.2000 [0.2000, 0.2000] | 0.4728 [0.4665, 0.4790] | 0.2000 [0.2000, 0.2000] |
| CB / CUST-10000122 | 0.0909 [0.0909, 0.0909] | 0.3480 [0.3475, 0.3485] | 0.3333 [0.3333, 0.3333] |
| CB / CUST-10000317 | 0.4545 [0.4545, 0.4545] | 0.2967 [0.2967, 0.2967] | 1.0000 [1.0000, 1.0000] |
| CB / CUST-10000588 | 0.4444 [0.4444, 0.4444] | 0.2633 [0.2633, 0.2633] | 1.0000 [1.0000, 1.0000] |
| CB / CUST-10000904 | 0.2000 [0.2000, 0.2000] | 0.5326 [0.5326, 0.5326] | 0.4000 [0.4000, 0.4000] |
| CB_controlled / CUST-10000122 | 0.0000 [0.0000, 0.0000] | 0.2500 [0.2190, 0.2811] | 0.3333 [0.3333, 0.3333] |
| CB_controlled / CUST-10000317 | 0.0625 [0.0000, 0.1250] | 0.4110 [0.3940, 0.4280] | 1.0000 [1.0000, 1.0000] |
| CB_controlled / CUST-10000588 | 0.0000 [0.0000, 0.0000] | 0.2417 [0.2417, 0.2417] | 1.0000 [1.0000, 1.0000] |
| CB_controlled / CUST-10000904 | 0.0625 [0.0000, 0.1250] | 0.3297 [0.3239, 0.3355] | 0.4000 [0.4000, 0.4000] |
| CB_hardened / CUST-10000122 | 0.1250 [0.1250, 0.1250] | 0.3623 [0.3605, 0.3641] | 0.3333 [0.3333, 0.3333] |
| CB_hardened / CUST-10000317 | 0.1250 [0.0000, 0.2500] | 0.4767 [0.4767, 0.4767] | 1.0000 [1.0000, 1.0000] |
| CB_hardened / CUST-10000588 | 0.0000 [0.0000, 0.0000] | 0.2572 [0.2572, 0.2572] | 1.0000 [1.0000, 1.0000] |
| CB_hardened / CUST-10000904 | 0.3000 [0.3000, 0.3000] | 0.3812 [0.3812, 0.3812] | 0.4000 [0.4000, 0.4000] |

## What changed and whether it helped

C → CB is the retrieval change: context recall increased **0.4833 → 0.6833**, while faithfulness changed **0.3088 → 0.2975** and relevance **0.3596 → 0.3602**. More complete retrieval helped the reference-coverage metric, but did not make raw copy safe. In particular, CB invented free return shipping for the Bronze case. This is a failed generation outcome, not a successful retention offer.

CB → CB_hardened added explicit conditional, points-focused copy instructions. Faithfulness fell to **0.1375** rather than improving. CB_hardened → CB_controlled added bounded output validation, a neutral subject and a policy-rendered fallback when the draft failed checks. Its faithfulness was **0.0313**, relevance **0.3081**, context recall **0.6833**. These low values are reported, not labeled PASS or hidden. Controlled delivery is selected for narrower, auditable claims, not because its RAGAS score won. Fallback copy is application-generated from the retrieved table; it is not presented as an LLM-only success.

## Metric limitations grounded in actual cases

**Faithfulness.** Baseline failures are real: the Bronze CB offer promises free return shipping although POL-LOY-011 §4 says No; the B Bronze offer creates a 15% promotion without an issued promotion record. Lower unsupported-claim rates are therefore necessary. However, a separate diagnostic of the final Gold copy shows that the judge also extracts metaclaims such as “The email subject line is Explore Outdoor with Summit Rewards” and marks them unsupported because no email subject appears in the policy corpus. It marks “Gold members earn 1.5× points on qualifying Outdoor purchases” unsupported, reasoning that the table gives a general rate rather than an Outdoor-only rate, although the delivered sentence does not say the rate is exclusive to Outdoor. It also marks the CTA to check eligibility unsupported. The diagnostic scored faithfulness 0.1667 and context recall 1.0, illustrating variability; it is saved separately and is **not added to the 48-row comparison**. See `judge-diagnostic.json` for the full actual extraction and verdicts. This supports a concrete concern about evaluating creative copy and conditional claims, while not excusing the baseline factual failures.

**Answer relevance.** The harness asks for a marketing offer, while this metric reverse-generates questions from the answer. For example, a question about Gold point benefits is semantically related to the response but differs from the instruction to generate a retention offer for an at-risk online shopper. The final narrow template also sacrifices campaign variety. The 0.3081 mean is a limitation of this particular output and metric pairing, not evidence that customers would respond well.

**Context recall.** C excludes returns and FAQ, causing a real final-sale coverage gap. CB retrieves that rule and promotion restrictions. Still, the Platinum reference includes claims about margin destruction on a $447 average order and an unused credit costing nothing incremental; neither is a policy fact, and credit usage is absent from the profile. A corpus-only retrieval system cannot justify every reference statement. The Bronze reference also suggests cross-category discovery whereas the customer data only verifies Apparel. The observed CB per-case recall range is 0.3333–1.0000; references, not only retrieval, determine that number.

The teacher removed fixed 0.80/0.75/0.70 grading gates on October 12. These results meet the repeated-measurement requirement; they do not establish production readiness. With more time I would label atomic policy claims with human reviewers, score entitlement correctness separately from copy style, use independent references, and measure response uplift in a controlled campaign.

## Evidence and reproducibility

- `rag_eval.csv`: all 48 per-case rows, actual answers, contexts, judge, strategy and repeat.
- `rag-runs/scores-*.csv`: checkpointed original four-case evaluations.
- `rag-runs/offers-*.json`: raw drafts, request IDs, token usage, contexts and controlled delivery.
- `track-b-examples.md`: five actual model-selected customer examples and two observed failures with fixes.
- `../lab3-rag-experiments.log`, `../lab3-rag-hardened.log`, `../lab3-rag-controlled.log`: recorded execution logs.
- `../../notebooks/lab3-demo.ipynb`: fresh-kernel execution with outputs.
