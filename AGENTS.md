# SellerOS AI-Agent Operating Contract

This repository is expected to be maintained heavily by AI agents. Optimise for explicit contracts,
replayability and reviewable evidence—not cleverness.

## Required read order

Before changing behaviour, read:

1. `docs/PRODUCT_VISION.md`
2. `docs/IMPLEMENTATION_BACKLOG.md`
3. `docs/ENGINEERING_GUARDRAILS.md`
4. `docs/STATUS.md`
5. `docs/ARCHITECTURE.md`
6. the README inside every affected backend decision kernel

`docs/CODEX_START_PROMPT.md` is historical Phase 0 material and is not a current task instruction.
The root `app.py` is a legacy prototype and is not an application entry point.

## Change protocol

1. Name the backlog story and acceptance criterion being changed.
2. Trace the request through schema → service/kernel → repository/model → response → UI.
3. Preserve organisation and marketplace scope at every persistence/read boundary.
4. Add a new version for any scoring, strategy or alias semantic change. Never mutate a version that
   already has persisted outputs.
5. Add deterministic synthetic tests, including the regression or boundary that motivated the change.
6. Run backend formatting, linting, typing and tests plus frontend linting, formatting, typing, tests
   and production build.
7. Update `docs/STATUS.md` and contract documentation when behaviour or status changes.

## Non-negotiable invariants

- Never overwrite or delete imported snapshot evidence.
- Never let an import overwrite seller-owned costs or inventory.
- Never use binary float for money.
- Never infer a tenant, currency, marketplace, ASIN or missing financial input.
- Never guess an ambiguous Keepa mapping.
- Never return an unbounded product collection.
- Never present Estimated or Recommended output as Observed fact.
- Never add an AI path that can silently modify deterministic calculations or execute purchasing,
  reorder, repricing or clearance actions.

## AI-readable implementation style

- Prefer stable enums, Pydantic schemas, dataclasses and reason codes over prose-only conventions.
- Keep route handlers thin and pure kernels free of FastAPI/SQLAlchemy/React imports.
- Store formula/rules/registry versions and configuration checksums with outputs.
- Use explicit state transitions and structured error codes.
- Record assumptions and limitations next to the contract, not in transient chat history.
- Fail closed when a policy file is malformed, evidence is incomplete or tenant scope is invalid.

An agent may explain evidence, compare versions and propose changes. Human review remains required for
policy releases and any future action-authority expansion.
