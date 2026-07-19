# Strategy classification kernel

This package implements the deterministic policy for SOS-202. It has no dependency on FastAPI,
SQLAlchemy, the scoring implementation, or mutable process state. Persistence and API adapters must
translate to and from these contracts rather than adding rules around them.

## Public contract

`StrategyContext` receives:

- `MarketScores`: demand, competition, price stability, data confidence, and overall opportunity;
- `history_months`: the number of comparable monthly observations available;
- optional complete `EconomicsSignals`: profitability, cash efficiency, and contribution margin;
- optional complete `InventorySignals`: inventory risk, units on hand, and stock-cover days.

Every score is an integer from 0 through 100. Higher demand, competition, price-stability,
confidence, opportunity, profitability, and cash-efficiency values are more favourable. A higher
inventory-risk score is less favourable. Percentage and duration values use `Decimal`; binary
floating point is not accepted.

`MarketScores.from_mapping()` is the narrow adapter boundary for a scoring engine. It accepts the
five canonical keys and ignores additional scores, which lets scoring evolve without making this
module import or depend on its implementation.

`StrategyDecision` contains:

- a stable machine strategy identifier;
- the exact rules version;
- at least two structured evidence objects;
- stable reason codes derived from that evidence; and
- all matching candidates in the order used to resolve conflicts.

The decision and all input/evidence objects are frozen dataclasses. A caller should persist a new
decision per snapshot; it should never mutate previous recommendations.

## Eligibility and precedence

The bundled policy is [`policies/v1.json`](policies/v1.json). It is strict JSON, validated at load
time, and uses strings for decimal thresholds to prevent precision loss.

The classifier applies these controls in order:

1. Confidence below the configured threshold returns `discovery` and blocks action-oriented rules.
2. All eligible rules are evaluated without side effects.
3. The policy's explicit priority list selects the first candidate.
4. `monitor` is the deterministic fallback when no action-oriented rule matches.

| Strategy          | Required evidence beyond market scores                         |
| ----------------- | -------------------------------------------------------------- |
| Discovery         | Limited history, missing economics, or the confidence gate     |
| Test Buy          | None; this is the only positive buy test available import-only |
| Growth            | Complete economics signals                                     |
| Cash Cow          | Complete economics signals and sufficient monthly history      |
| Premium Margin    | Complete economics signals                                     |
| Monitor           | None; fallback when no other rule matches                       |
| Clearance Watch   | Inventory signals and units currently on hand                   |
| Avoid             | None; poor economics are used only when economics exist         |

Protective rules precede opportunity rules. For example, inventory exposed to serious stock risk
is `clearance_watch` even when the same context also matches `cash_cow`, `growth`, and `test_buy`.
This is a recommendation to investigate and intervene, not an instruction to mark down inventory.

An import-only context cannot become `growth`, `cash_cow`, `premium_margin`, or `clearance_watch`.
This enforces the guardrails that profitability cannot be claimed without seller costs and that an
inventory decision cannot be made without inventory evidence.

## Policy versioning

Once a rules version has produced persisted recommendations, treat its JSON file as immutable. To
change thresholds or priority:

1. add a new JSON policy file;
2. increment `rules_version` using `strategy-v<major>.<minor>.<patch>`;
3. validate it with `load_strategy_policy()`;
4. add boundary, strategy, and conflict tests for the new behavior; and
5. create new recommendations rather than rewriting old ones.

The parser rejects unknown keys, missing keys, duplicate or incomplete priority lists, invalid score
ranges, imprecise JSON numbers for decimal thresholds, invalid cross-field ranges, unsupported schema
versions, and unversioned rules. This intentionally makes configuration typos fail closed.

## Integration example

```python
from app.modules.strategies import MarketScores, StrategyClassifier, StrategyContext

context = StrategyContext(
    scores=MarketScores.from_mapping(score_values),
    history_months=history_months,
)
decision = StrategyClassifier().classify(context)
```

The application service that calls this kernel is responsible for organisation scoping, loading the
correct snapshot facts, converting validated decimal values, and persisting the returned rules
version, structured evidence, and reason codes transactionally.

## AI governance boundary

An AI agent may explain a completed decision, compare versioned policies, propose a policy change,
or generate test cases. It must not invent missing signals, bypass the confidence gate, reorder
priority at runtime, mutate historical decisions, or turn a recommendation into an automatic buying,
pricing, reorder, or clearance action. Numerical classification remains deterministic and testable.
