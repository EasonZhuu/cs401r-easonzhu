# Track B: five correct controlled deliveries and observed failures

The five examples below use actual synthetic-course customers selected from the registered churn model’s top-10% contact list. Their numerical features came from the verified Athena query; categories came only from valid pre-cutoff transaction history. `real-customer-profiles.json` records provenance and exclusions (including 4,912 invalid raw dates). Offers are drafts; no coupons were issued and no customer was contacted.

Every delivered example was manually checked for the conditional reported tier, policy-table earn rate, observed category, CTA, no invented discount/expiry, and two Body sentences. `delivery_mode` discloses whether the LLM proposal passed the bounded check or was replaced with a policy-derived template. Raw proposals remain in `offers-real.json`. This is not a claim that the unrestricted generator is safe.

## Correct delivery 1: CUST-10000299

```json
{
  "days_since_last_purchase": 210.0,
  "customer_tenure_days": 345.0,
  "purchase_frequency_30d": 0.0,
  "purchase_frequency_90d": 0.0,
  "purchase_frequency_180d": 0.0,
  "avg_order_value": 116.5457,
  "total_spend_90d": 0.0,
  "total_lifetime_value": 815.82,
  "avg_basket_size_6m": 0.0,
  "category_diversity_score": 0.5,
  "online_to_store_ratio": 0.7143,
  "customer_id": "CUST-10000299",
  "loyalty_tier": "Silver",
  "churn_probability": 0.8281450867652893,
  "top_categories": [
    "Beauty",
    "Home",
    "Electronics"
  ]
}
```

Subject: Explore Beauty with Summit Rewards
Body: If your current membership is Silver, you earn 1.25× points on qualifying Beauty purchases. Explore Beauty at NorthStar and check your current membership eligibility before using these benefits.

Delivery mode: `policy_template_fallback`. Generator request: `3496190b-e69a-45d6-8661-b12ca8fa874d`.

Retrieved chunk IDs: `POL-SHP-007:003:c163e7eb41`, `POL-LOY-011:010:cdbdbe1ea2`, `POL-LOY-011:003:8c4328c83f`, `POL-LOY-011:013:c2d7a201cd`, `POL-LOY-011:012:d96352d7c0`, `POL-RET-004:007:49b78de484`.

## Correct delivery 2: CUST-10000324

```json
{
  "days_since_last_purchase": 295.0,
  "customer_tenure_days": 361.0,
  "purchase_frequency_30d": 0.0,
  "purchase_frequency_90d": 0.0,
  "purchase_frequency_180d": 0.0,
  "avg_order_value": 123.7767,
  "total_spend_90d": 0.0,
  "total_lifetime_value": 371.33,
  "avg_basket_size_6m": 0.0,
  "category_diversity_score": 0.375,
  "online_to_store_ratio": 0.0,
  "customer_id": "CUST-10000324",
  "loyalty_tier": "Bronze",
  "churn_probability": 0.8281450867652893,
  "top_categories": [
    "Apparel",
    "Grocery",
    "Home"
  ]
}
```

Subject: Explore Apparel with Summit Rewards
Body: If your current membership is Bronze, you earn 1× points on qualifying Apparel purchases. Explore Apparel at NorthStar and check your current membership eligibility before using these benefits.

Delivery mode: `policy_template_fallback`. Generator request: `be13816e-c7af-4a59-9054-396d70e79b20`.

Retrieved chunk IDs: `POL-LOY-011:010:cdbdbe1ea2`, `POL-SHP-007:003:c163e7eb41`, `POL-LOY-011:003:8c4328c83f`, `POL-LOY-011:013:c2d7a201cd`, `POL-LOY-011:012:d96352d7c0`, `POL-RET-004:007:49b78de484`.

## Correct delivery 3: CUST-10007187

```json
{
  "days_since_last_purchase": 222.0,
  "customer_tenure_days": 348.0,
  "purchase_frequency_30d": 0.0,
  "purchase_frequency_90d": 0.0,
  "purchase_frequency_180d": 0.0,
  "avg_order_value": 227.9256,
  "total_spend_90d": 0.0,
  "total_lifetime_value": 2051.33,
  "avg_basket_size_6m": 0.0,
  "category_diversity_score": 0.375,
  "online_to_store_ratio": 0.1111,
  "customer_id": "CUST-10007187",
  "loyalty_tier": "Gold",
  "churn_probability": 0.8281450867652893,
  "top_categories": [
    "Home",
    "Footwear",
    "Beauty"
  ]
}
```

Subject: Explore Home with Summit Rewards
Body: If your current membership is Gold, you earn 1.5× points on qualifying Home purchases. Explore Home at NorthStar and check your current membership eligibility before using these benefits.

Delivery mode: `policy_template_fallback`. Generator request: `50d55c04-96b5-46c8-b90b-9f22493115cb`.

Retrieved chunk IDs: `POL-LOY-011:004:773059e1b0`, `POL-LOY-011:010:cdbdbe1ea2`, `POL-SHP-007:003:c163e7eb41`, `POL-LOY-011:013:c2d7a201cd`, `POL-LOY-011:012:d96352d7c0`, `POL-RET-004:007:49b78de484`.

## Correct delivery 4: CUST-10002887

```json
{
  "days_since_last_purchase": 183.0,
  "customer_tenure_days": 360.0,
  "purchase_frequency_30d": 0.0,
  "purchase_frequency_90d": 0.0,
  "purchase_frequency_180d": 0.0,
  "avg_order_value": 435.1582,
  "total_spend_90d": 0.0,
  "total_lifetime_value": 7397.69,
  "avg_basket_size_6m": 0.0,
  "category_diversity_score": 0.5,
  "online_to_store_ratio": 0.6471,
  "customer_id": "CUST-10002887",
  "loyalty_tier": "Platinum",
  "churn_probability": 0.8270395994186401,
  "top_categories": [
    "Home",
    "Beauty",
    "Toys"
  ]
}
```

Subject: Explore Home with Summit Rewards
Body: If your current membership is Platinum, you earn 2× points on qualifying Home purchases. Explore Home at NorthStar and check your current membership eligibility before using these benefits.

Delivery mode: `policy_template_fallback`. Generator request: `3900612f-0e0f-4416-8f5c-db3fa8aba934`.

Retrieved chunk IDs: `POL-SHP-007:003:c163e7eb41`, `POL-LOY-011:010:cdbdbe1ea2`, `POL-LOY-011:003:8c4328c83f`, `POL-LOY-011:013:c2d7a201cd`, `POL-LOY-011:012:d96352d7c0`, `POL-RET-004:007:49b78de484`.

## Correct delivery 5: CUST-10000350

```json
{
  "days_since_last_purchase": 223.0,
  "customer_tenure_days": 336.0,
  "purchase_frequency_30d": 0.0,
  "purchase_frequency_90d": 0.0,
  "purchase_frequency_180d": 0.0,
  "avg_order_value": 108.74,
  "total_spend_90d": 0.0,
  "total_lifetime_value": 543.7,
  "avg_basket_size_6m": 0.0,
  "category_diversity_score": 0.125,
  "online_to_store_ratio": 1.0,
  "customer_id": "CUST-10000350",
  "loyalty_tier": "Silver",
  "churn_probability": 0.8281450867652893,
  "top_categories": [
    "Apparel"
  ]
}
```

Subject: Explore Apparel with Summit Rewards
Body: If your current membership is Silver, you earn 1.25× points on qualifying Apparel purchases. Explore Apparel at NorthStar and check your current membership eligibility before using these benefits.

Delivery mode: `policy_template_fallback`. Generator request: `09c5f3b6-3528-45fe-9a60-c4c4484bfdc5`.

Retrieved chunk IDs: `POL-SHP-007:003:c163e7eb41`, `POL-LOY-011:010:cdbdbe1ea2`, `POL-LOY-011:003:8c4328c83f`, `POL-LOY-011:013:c2d7a201cd`, `POL-LOY-011:012:d96352d7c0`, `POL-RET-004:007:49b78de484`.

## Observed failure 1: strategy CB

Profile: `{"avg_order_value": 41.15, "category_diversity_score": 0.125, "churn_probability": 0.74, "customer_id": "CUST-10000904", "days_since_last_purchase": 68, "loyalty_tier": "Bronze", "online_to_store_ratio": 0.2, "top_categories": ["Apparel"], "total_lifetime_value": 312.8}`

Subject: We Miss You – Easier Returns on Your Apparel Favorites
Body: We noticed it's been a while since your last visit, and we'd love to welcome you back. As a Bronze member, you enjoy free standard shipping on apparel orders of $75 or more—and to make returns even simpler, we're offering you free return shipping on your next purchase. Shop apparel in-store or online, and if you need to make a return, we'll cover the cost to send it back.

Retrieved chunk IDs: `POL-LOY-011:010:cdbdbe1ea2`, `POL-SHP-007:003:c163e7eb41`, `POL-LOY-011:003:8c4328c83f`, `POL-LOY-011:013:c2d7a201cd`, `POL-LOY-011:012:d96352d7c0`, `POL-RET-004:007:49b78de484`.

**Failure:** Bronze receives an invented free-return-shipping benefit. The actual tier table says Bronze does not receive it; POL-RET-004 §6.2 charges standard members $7.95 for mail returns. Adding constraint retrieval alone did not prevent this failure.

**Concrete mitigation:** Validate each offered entitlement against the retrieved tier table and a verified membership record; reject or replace claims about return shipping. The final bounded points-only delivery implements this narrower safeguard.

## Observed failure 2: strategy B

Profile: `{"avg_order_value": 41.15, "category_diversity_score": 0.125, "churn_probability": 0.74, "customer_id": "CUST-10000904", "days_since_last_purchase": 68, "loyalty_tier": "Bronze", "online_to_store_ratio": 0.2, "top_categories": ["Apparel"], "total_lifetime_value": 312.8}`

Subject: We Miss You — Special Offer Inside for Your Next Apparel Purchase
Body: We noticed it's been a while since your last visit, and we'd love to welcome you back. As a Bronze member, we're offering you 15% off your next apparel purchase — valid both online and in any of our 400 stores for 45 days from today. Stop by or shop at northstar.com to redeem this offer on your account and discover what's new in our apparel collection.

Retrieved chunk IDs: `POL-LOY-011:013:c2d7a201cd`, `POL-LOY-011:012:d96352d7c0`, `POL-RET-004:007:49b78de484`, `KB-FAQ-022:002:636e91c073`.

**Failure:** Bronze receives a newly invented 15% discount and a deadline 45 days from today. The corpus states how valid issued retention offers work but does not authorize this promotion or establish an issue date.

**Concrete mitigation:** Require an approved promotion ID, amount and issue date from an offer service before mentioning a coupon. In their absence restrict output to existing policy benefits; the final bounded delivery does so.
