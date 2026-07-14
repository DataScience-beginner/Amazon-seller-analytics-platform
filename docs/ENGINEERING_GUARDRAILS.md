# SellerOS Engineering Guardrails

These rules apply to all Codex tasks and pull requests.

## 1. Architecture

- Use a modular monolith for the first year. Do not create microservices prematurely.
- Keep domain/business logic independent from FastAPI routes, React components and database adapters.
- Separate these concerns: ingestion, mapping, product catalogue, snapshots, scoring, profitability, inventory, forecasting and identity.
- Use dependency injection at external boundaries.
- Create adapter interfaces for Keepa Excel, Keepa API and Amazon SP-API.
- Do not put core business calculations in frontend code.
- Do not build all backend logic in a single file.

## 2. Data integrity

- Treat uploaded market snapshots as immutable.
- Never overwrite seller-entered costs or inventory using Keepa imports.
- Preserve the original import metadata and all unknown fields.
- Use database transactions for imports and financial updates.
- Enforce organisation and marketplace scope in unique keys.
- Use timezone-aware UTC timestamps in storage.
- Use Decimal for money and documented rounding rules.
- Use explicit currency codes; never assume currency from the symbol alone.
- Migrations must be reversible where reasonably possible.

## 3. Dynamic Keepa files

- Never assume fixed column positions.
- Map by canonical field definitions and aliases.
- Normalise headers conservatively.
- Never guess when two columns match the same canonical field.
- Missing optional columns must reduce data confidence, not crash an import.
- Missing required identifiers must create a row-level error.
- Unknown fields must be preserved in JSON/raw attributes.
- Repeated file uploads must be idempotent by checksum.
- Do not commit the user's actual Keepa workbook or imported private data.

## 4. Scoring and recommendations

- Scores and strategy rules must be deterministic, versioned and unit-tested.
- Store score inputs, outputs and reason codes.
- Do not hide missing-data assumptions.
- A low-confidence record must not receive an aggressive buy recommendation.
- Do not label a product profitable without a sourcing-cost assumption.
- Avoid unsupported sales estimates. Label proxies and estimates clearly.
- AI may explain calculations but must not replace or silently alter them.
- No autonomous purchase, reorder, repricing or clearance action in the MVP.

## 5. API quality

- Use versioned API routes such as `/api/v1`.
- Validate every request and return stable typed response schemas.
- Use appropriate HTTP status codes and structured error bodies.
- Never expose stack traces, SQL details or secrets to clients.
- Add pagination to collection endpoints.
- Add deterministic sorting and filter validation.
- Prevent unbounded database queries and N+1 loading.
- Document APIs with OpenAPI and useful examples.

## 6. Frontend quality

- Use TypeScript strict mode.
- Build reusable components and avoid giant page components.
- Every page needs loading, empty, success and error states.
- Forms need client and server validation.
- Preserve filters in URL query parameters.
- Meet basic accessibility requirements: labels, keyboard navigation, focus states, semantic HTML and contrast.
- Design mobile-first for 360 px widths and progressively enhance desktop.
- Do not use colour as the only indicator of risk or status.
- Display calculation definitions and confidence indicators near decisions.

## 7. Security and privacy

- Keep secrets in environment variables or an approved secret manager.
- Provide `.env.example` containing placeholders only.
- Validate file extension, MIME type, size and workbook structure.
- Store uploads outside publicly served directories.
- Generate safe server-side filenames; never trust a supplied path.
- Apply authentication and organisation isolation before public SaaS release.
- Avoid logging uploaded row data, supplier prices or personally identifiable information.
- Use secure defaults for cookies, CORS and headers when authentication is added.
- Pin direct dependencies and monitor vulnerabilities.

## 8. Performance and reliability

- Stream or read large workbooks in memory-conscious mode.
- Avoid loading all products into memory for normal list pages.
- Add indexes based on actual query paths.
- Long imports should be designed for a background-job transition.
- Expose health and readiness checks.
- Use structured logs with correlation/import identifiers.
- Errors during one row should be captured without hiding overall import status.
- Backups and restore procedures are required before production use.

## 9. Testing

Minimum test layers:

- unit tests for mapping, scoring, strategy, profitability and forecasting;
- repository/integration tests using a test database;
- API tests for validation, pagination and errors;
- frontend component tests for critical forms and decisions;
- end-to-end smoke test covering upload -> import -> scores -> product detail.

Test requirements:

- tests must be deterministic;
- use synthetic fixtures, not the user's private workbook;
- include missing columns, renamed columns, duplicate uploads, malformed values and partial rows;
- include monetary rounding and zero-cost edge cases;
- every bug fix needs a regression test.

## 10. Code quality and workflow

- Python: type hints, Ruff, formatting, mypy or Pyright-compatible checks and pytest.
- TypeScript: ESLint, Prettier, strict type checking and Vitest.
- Prefer small focused functions and explicit names.
- Remove dead code; do not leave commented-out implementations.
- Add docstrings/comments only where intent is not obvious.
- Do not suppress type or lint errors without a documented reason.
- Use conventional, focused commit messages.
- Do not mix unrelated refactors and feature work in one commit.
- Update documentation with every contract or setup change.

## 11. CI quality gate

A pull request should not be considered ready unless CI verifies:

- backend formatting/linting;
- backend type checks;
- backend tests;
- frontend linting;
- frontend type checks;
- frontend tests;
- production frontend build;
- migration smoke test;
- secret scanning where available.

## 12. Decision safety language

Use these labels consistently:

- **Observed**: directly present in imported or integrated data.
- **Calculated**: deterministic formula based on stored inputs.
- **Estimated**: proxy or configurable assumption.
- **Recommended**: advisory decision based on rules.
- **User confirmed**: an action or lifecycle decision accepted by a user.

The UI must not present estimated or recommended information as a verified fact.