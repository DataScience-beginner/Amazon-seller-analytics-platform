import type { BrandClassification, ProductSummary, ResearchStatus } from '../../api/contracts';
import { formatNumber, humanize } from '../../utils/format';

const statusOrder: ResearchStatus[] = [
  'priority_research',
  'promising',
  'monitor',
  'insufficient_evidence',
  'avoid',
];

export function ResearchStatusLabel({ status }: { status: ResearchStatus }) {
  return <span className={`research-status research-status--${status}`}>{humanize(status)}</span>;
}

export function BrandLabel({ classification }: { classification: BrandClassification }) {
  const label =
    classification === 'declared_brand'
      ? 'Declared brand'
      : classification === 'likely_generic'
        ? 'Likely generic'
        : 'Brand unknown';
  return <span className={`brand-class brand-class--${classification}`}>{label}</span>;
}

function scoreValue(product: ProductSummary, name: string): number | null {
  const score = product.scores?.find((item) => item.name === name)?.value;
  return typeof score === 'number' ? score : null;
}

export function ResearchCharts({ products }: { products: ProductSummary[] }) {
  const plotted = products
    .map((product) => ({
      product,
      demand: scoreValue(product, 'demand'),
      competition: scoreValue(product, 'competition'),
    }))
    .filter(
      (
        item,
      ): item is {
        product: ProductSummary;
        demand: number;
        competition: number;
      } => item.demand !== null && item.competition !== null,
    );
  const counts = new Map<ResearchStatus, number>(
    statusOrder.map((status) => [
      status,
      products.filter((product) => product.research?.status === status).length,
    ]),
  );
  const largestCount = Math.max(1, ...counts.values());

  return (
    <div className="research-charts">
      <section className="panel" aria-labelledby="research-scatter-heading">
        <div className="section-heading">
          <div>
            <p className="data-label">Calculated · current page</p>
            <h2 id="research-scatter-heading">Demand vs seller competition</h2>
          </div>
        </div>
        <p className="chart-help">
          Upper-right products combine stronger demand with a more approachable competition score.
        </p>
        <svg
          className="research-scatter"
          viewBox="0 0 420 240"
          role="img"
          aria-label={`${plotted.length} products plotted by demand and competition scores`}
        >
          <line x1="42" y1="208" x2="405" y2="208" />
          <line x1="42" y1="12" x2="42" y2="208" />
          <text x="215" y="234">
            Competition score →
          </text>
          <text x="8" y="112" transform="rotate(-90 8 112)">
            Demand score →
          </text>
          {plotted.map(({ product, demand, competition }) => (
            <circle
              key={product.id}
              cx={42 + competition * 3.63}
              cy={208 - demand * 1.96}
              r="5"
              className={`research-dot research-dot--${product.research?.status ?? 'monitor'}`}
            >
              <title>
                {product.title}: demand {demand}, competition {competition}
              </title>
            </circle>
          ))}
        </svg>
      </section>

      <section className="panel" aria-labelledby="research-mix-heading">
        <div className="section-heading">
          <div>
            <p className="data-label">Recommended research action · current page</p>
            <h2 id="research-mix-heading">Candidate mix</h2>
          </div>
        </div>
        <div className="research-bars">
          {statusOrder.map((status) => {
            const count = counts.get(status) ?? 0;
            return (
              <div key={status}>
                <span>{humanize(status)}</span>
                <div aria-hidden="true">
                  <i style={{ width: `${(count / largestCount) * 100}%` }} />
                </div>
                <strong>{formatNumber(count, 0)}</strong>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
