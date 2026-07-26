import type { ProductEconomicsResponse, UnitEconomics } from '../../api/contracts';
import { formatDate, formatMoney, formatUtcDate, humanize } from '../../utils/format';

const percentageOutputs = new Set(['margin_percent', 'roi_percent']);
const outputLabels: Record<string, string> = {
  net_revenue: 'Net revenue',
  output_gst: 'Output GST within selling price',
  roi_percent: 'ROI percent',
};

function outputValue(name: string, value: string | null, currencyCode: string): string {
  if (value === null) return 'Unavailable';
  if (percentageOutputs.has(name)) return `${value}%`;
  return formatMoney({ amount: value, currency_code: currencyCode });
}

function inputLabel(name: string, calculation: UnitEconomics): string {
  if (name === 'selling_price') return 'Observed';
  if (
    ['referral_fee_rate_percent', 'fulfilment_fee', 'closing_fee', 'storage_fee'].includes(name)
  ) {
    return calculation.fee_evidence.status
      ? humanize(calculation.fee_evidence.status)
      : 'Estimated / missing';
  }
  return 'User confirmed';
}

export function UnitEconomicsPanel({ economics }: { economics: ProductEconomicsResponse }) {
  const calculation = economics.calculation;
  return (
    <section className="panel economics-panel" aria-labelledby="economics-heading">
      <div className="section-heading">
        <div>
          <p className="data-label">Calculated</p>
          <h2 id="economics-heading">Unit economics</h2>
        </div>
        {calculation && (
          <span className={`evidence-tag evidence-tag--${calculation.status}`}>
            {humanize(calculation.status)}
          </span>
        )}
      </div>

      {economics.observed_price ? (
        <div className="observed-price">
          <span className="evidence-tag evidence-tag--observed">Observed</span>
          <div>
            <strong>
              {formatMoney({
                amount: economics.observed_price.amount,
                currency_code: economics.observed_price.currency_code,
              })}
            </strong>
            <small>
              {economics.observed_price.observed_on
                ? `Observed on ${formatDate(economics.observed_price.observed_on)}`
                : 'Observation date unavailable'}{' '}
              · processed {formatDate(economics.observed_price.source_at)}
            </small>
          </div>
        </div>
      ) : (
        <div className="form-message form-message--warning">
          No observed selling price is available. Price-dependent outputs remain unavailable.
        </div>
      )}

      {calculation &&
        (calculation.selling_price_tax_basis ? (
          <div className="fee-evidence-strip">
            <span className="evidence-tag evidence-tag--user_confirmed">User confirmed</span>
            <div>
              <strong>Observed selling price</strong>
              <small>
                {calculation.selling_price_tax_basis === 'tax_inclusive'
                  ? 'Price includes GST'
                  : 'Price excludes GST'}
              </small>
            </div>
          </div>
        ) : (
          <div className="form-message form-message--warning" role="status">
            <strong>Selling-price tax basis is unknown.</strong> Net revenue, output GST and every
            selling-price-dependent result are blocked until the seller confirms whether the price
            includes GST.
          </div>
        ))}

      {!calculation ? (
        <div className="inline-empty">
          <strong>Economics not calculated</strong>
          <p>Save an explicit cost profile to calculate landed cost and profitability.</p>
        </div>
      ) : (
        <>
          <div className="economics-output-grid">
            {Object.entries(calculation.outputs).map(([name, value]) => (
              <article className="economics-output" key={name}>
                <span
                  className={`evidence-tag evidence-tag--${value === null ? 'partial' : 'calculated'}`}
                >
                  {value === null ? 'Unavailable' : 'Calculated'}
                </span>
                <h3>{outputLabels[name] ?? humanize(name)}</h3>
                <strong>{outputValue(name, value, economics.currency_code)}</strong>
                {value === null && <small>See missing-data reasons below.</small>}
              </article>
            ))}
          </div>

          <div className="fee-evidence-strip">
            <span
              className={`evidence-tag evidence-tag--${calculation.fee_evidence.status ?? 'estimated'}`}
            >
              {calculation.fee_evidence.status
                ? humanize(calculation.fee_evidence.status)
                : 'Estimated / missing'}
            </span>
            <div>
              <strong>Amazon fee evidence</strong>
              <small>
                {calculation.fee_evidence.source || 'No source provided'} ·{' '}
                {calculation.fee_evidence.effective_at
                  ? `${formatUtcDate(calculation.fee_evidence.effective_at)} UTC`
                  : 'no source date'}
              </small>
            </div>
          </div>

          {calculation.reason_codes.length > 0 && (
            <div className="form-message form-message--warning">
              <strong>Calculation limitations</strong>
              <ul className="compact-list">
                {calculation.reason_codes.map((reason) => (
                  <li key={reason}>{humanize(reason)}</li>
                ))}
              </ul>
            </div>
          )}

          <details className="trace-details">
            <summary>Trace formulas and inputs</summary>
            <p className="muted">
              Version {calculation.formula_version} · configuration{' '}
              <span className="checksum">{calculation.configuration_checksum}</span>
            </p>
            <div className="trace-grid">
              <section aria-labelledby="formula-trace-heading">
                <h3 id="formula-trace-heading">Formula trace</h3>
                <dl className="trace-list">
                  {Object.entries(calculation.formulas).map(([name, formula]) => (
                    <div key={name}>
                      <dt>{humanize(name)}</dt>
                      <dd>{formula}</dd>
                    </div>
                  ))}
                </dl>
              </section>
              <section aria-labelledby="input-trace-heading">
                <h3 id="input-trace-heading">Input trace</h3>
                <dl className="trace-list">
                  {Object.entries(calculation.inputs).map(([name, value]) => (
                    <div key={name}>
                      <dt>{humanize(name)}</dt>
                      <dd>
                        {value ?? 'Missing'}
                        <span className="evidence-tag">{inputLabel(name, calculation)}</span>
                      </dd>
                    </div>
                  ))}
                </dl>
              </section>
            </div>
          </details>
        </>
      )}

      {economics.notices.map((notice) => (
        <div className="form-message form-message--warning" key={notice.code}>
          <span className="evidence-tag">{humanize(notice.evidence_label)}</span> {notice.message}
        </div>
      ))}

      {economics.audit_history.length > 0 && (
        <details className="trace-details">
          <summary>Cost profile audit history</summary>
          <ul className="audit-list">
            {economics.audit_history.map((event) => (
              <li key={event.id}>
                <strong>{humanize(event.event_type)}</strong>
                <span>
                  Profile v{event.profile_version} · {formatDate(event.occurred_at)}
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
