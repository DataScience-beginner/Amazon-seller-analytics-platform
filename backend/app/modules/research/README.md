# Product Research Screener kernel

This package implements the deterministic Product Research v1 read policy. It converts persisted
market scores and bounded snapshot facts into a research status, brand classification and structured
explanations. It has no FastAPI, SQLAlchemy, React, financial or AI dependency.

The strongest status is `priority_research`. It means the product passed configured market-evidence
thresholds and should be investigated next. It never means profitable, authorised, safe to source or
approved to buy. Those claims require seller costs, Amazon fees, supplier evidence and brand/category
permission checks.

## Screens

The immutable `resources/v1.json` policy defines reusable Screener.in-style filters:

- Priority research
- Promising
- Low seller competition
- Stable pricing
- Needs evidence
- All products

Screen thresholds use the existing persisted Demand, Competition, Price Stability, Data Confidence
and Overall Opportunity scores plus current offers and Buy Box availability. Higher Competition means
a more approachable seller environment. Current offers are sellers/offers on one ASIN, not the number
of substitute products in a market.

## Brand classification

`declared_brand` means the imported Brand field contains a non-generic value. It does not verify
trademark ownership, ungating or resale permission. `likely_generic` matches only explicit,
version-controlled generic markers. `unknown` means brand evidence is absent. Every classification
keeps a manual authorisation warning.

## Versioning

Changing a threshold, screen meaning, status rule, brand marker or explanation semantics requires a
new policy resource and version. API outputs include the policy version and SHA-256 configuration
checksum so an AI agent or reviewer can replay the decision from immutable source evidence.

## Research Priority Ranking v1

`resources/ranking_v1.json` defines the separate `selleros.research-priority.v1` read-time ranking.
It does not replace or mutate persisted market-opportunity scores. Its weights are demand 30%, price
stability 20%, competition quality 15%, data confidence 15%, sales-rank trend 10% and Buy Box
availability 10%. The loader fails closed unless every component exists and weights sum to 100.

Missing components score zero and are disclosed. Competition quality caps zero- and single-offer
listings because seller concentration can indicate unavailable supply or a controlled listing rather
than easy entry. Each result returns the formula version, configuration checksum, component scores,
weights and reason codes. It ranks what to research first; supplier cost, fees, authorisation and a
human buying decision remain separate gates.
