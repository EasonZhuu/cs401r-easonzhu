# Lab 3 Model Design

Track: A+B

## Churn model

I used gradient-boosted trees for 9,999 customers and 11 numerical behavioral inputs. The source Feature Group also contains the target, customer ID, loyalty tier and a recency proxy; I excluded those from model inputs to avoid identifiers, circular tier comparisons and duplicating the baseline. This is a modest tabular dataset with nonlinear relationships between recency, frequency and spending. Logistic regression would be a useful transparent comparator, but would need interaction features to express those relationships. A neural network would add tuning and data requirements without a clear advantage here. I would reconsider a neural model with much larger transaction sequences or useful text representations.

I trained locally with XGBoost 3.2.0, preserving the genuine Feature Store/Athena input. The stratified 70/30 split produced 6,999 training and 3,000 validation customers. The positive-class weight was calculated from training labels, 5,459/1,540 = 3.5448. Early stopping retained 11 boosting rounds. Three parameter configurations were compared through the serverless MLflow App, and the selected evaluated run was registered as PendingManualApproval in northstar-churn-models. The model bytes, report, MLflow metrics and registry metadata were checked against one another.

## What the features bought

The recency-only model reached AUC 0.7229, versus 0.7838 for the full model. The paired bootstrap lift was 0.0609, with 95% CI [0.0415, 0.0802]. Contacting the top 300 validation customers found 214 churners: precision 0.7133 and recall 0.3242. This supports using more than recency, but it is not evidence of campaign response uplift. Recency accounted for 24.9% of normalized mean split gain, 180-day frequency 20.4%, and 30-day frequency 16.3%. Tenure contributed only 3.1%; that is weaker fitted importance, not proof it can be removed without an ablation. Gold and Platinum had low recall under the global contact budget, and Platinum had only 21 validation positives. Parameter selection and early stopping reused the validation set, so the CI omits selection uncertainty.

## Why RAG

RAG lets changing shipping, returns and loyalty rules remain in versioned source documents. Fine-tuning would not reliably update those facts or provide current citations, and four policy documents do not justify training weights to remember business terms. The primary production risk is a confident unauthorized promise. The starter tier guidelines contained two incorrect thresholds and nonexistent free expedited shipping. I corrected Gold to $2,000–$4,999.99, Platinum to $5,000+, and removed the expedited benefit.

I used Titan V2, 1,024 normalized dimensions, and local FAISS exact inner-product search. The 48 complete Markdown sections are 21–245 whitespace words each, with zero overlap and intact tables. This small corpus does not need approximate search or another ranking model initially. Queries retrieve policies rather than products; product categories come from observed pre-cutoff transactions. Reported loyalty tier is approximate because features use lifetime value while policy uses trailing 12-month spend, so delivered benefits are conditional on current membership.

## Evaluation and delivery

The Haiku 4.5 Bedrock judge evaluated all four supplied cases twice under six configurations. Combining C and B retrieval raised context recall from 0.4833 to 0.6833, but faithfulness changed from 0.3088 to 0.2975. The six-chunk combination also has a larger budget than four-chunk C. More retrieval did not prevent an invented Bronze return-shipping benefit. A stricter prompt still produced unsupported copy. Final delivery therefore checks bounded points-only copy and uses a policy-rendered fallback when needed, retaining raw drafts. All five demonstrated real-customer deliveries used that fallback; they are not LLM-only successes. Final faithfulness remained 0.0313. Actual judge traces penalized invented subject-line metaclaims and interpreted a general points rate as insufficient category evidence. Relevance is also mismatched to marketing instructions, and reference recall includes non-policy commentary. I report these limitations and poor scores rather than calling the system production-ready.

## With ten times the resources

I would read membership and promotion eligibility from authoritative services, use an untouched temporal test set, and test feature removals. Human reviewers would label individual policy claims separately from marketing style, with independently written references. A randomized retention experiment would measure incremental purchases and margin rather than assume that predicted churn implies persuadability. Those changes address entitlement correctness, generalization and business value directly.
