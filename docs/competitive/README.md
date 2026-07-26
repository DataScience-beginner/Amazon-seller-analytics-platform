# SellerOS competitive reference

This documentation captures public, seller-facing capabilities from Helium 10, Amazon Seller
Central, Jungle Scout and sellerboard and translates the strongest product patterns into a
reference blueprint for SellerOS.

Research date: **2026-07-19**

## Documents

- [Platform walkthroughs](PLATFORM_WALKTHROUGHS.md) describes the products, modules, workflows,
  inputs, outputs and public integration behaviour of each platform.
- [Feature matrix](FEATURE_MATRIX.md) compares the platforms and identifies the appropriate
  SellerOS response and delivery phase.
- [SellerOS reference blueprint](SELLEROS_REFERENCE_BLUEPRINT.md) turns the research into proposed
  backend capabilities, API boundaries, frontend pages and interaction patterns.
- [Source register](SOURCES.md) lists the official public sources used and their scope.

## Evidence rules

The documents use these labels:

- **Verified public capability**: described in a first-party product page, help article or API
  reference available without a private account.
- **Observed UI pattern**: visible in first-party documentation, screenshots or documented steps.
- **Architectural inference**: a likely enabling capability inferred from public behaviour. It is
  not a claim about a competitor's private code, data model, infrastructure or algorithm.
- **SellerOS recommendation**: a design choice proposed for this repository. It is not committed
  scope until added to the product backlog.

## Boundaries

- This is product research, not reverse engineering. It does not reproduce proprietary source
  code, formulas, private APIs, visual assets or confidential workflows.
- Feature availability changes by marketplace, selling plan, brand status and subscription tier.
  The source register should be rechecked before using a plan limit or availability rule in a
  product decision.
- Marketing claims and estimated metrics are recorded as product behaviour, not independently
  validated accuracy claims.
- Logged-in screens may contain additional features not covered by public documentation.
- SellerOS should adopt useful interaction principles without copying another product's trade
  dress, wording or opaque scoring formulas.

## Strategic conclusion

Amazon Seller Central is the operational system of record for listings, inventory, fulfillment,
orders, payments and account status. Helium 10 and Jungle Scout add research, optimization,
monitoring and analytics around Amazon data. sellerboard adds a concentrated profitability,
inventory, cash-flow and operational-control layer. SellerOS should occupy a narrower decision
layer:

> Combine imported market evidence with seller-owned costs, suppliers, inventory and cash
> constraints to recommend what to test, grow, reorder, mark down, clear or avoid—and explain the
> effect on contribution profit and cash conversion.

This positioning avoids trying to clone four mature products and directly supports the SellerOS
product vision.
