import type { ProductSummary } from '../api/contracts';
import { Link } from '../app/router';
import { productScore, productStrategy } from '../features/products/productModel';
import { formatMoney, formatNumber } from '../utils/format';
import { StatusBadge } from './StatusBadge';

export function ProductSummaryRow({
  product,
  risk = false,
}: {
  product: ProductSummary;
  risk?: boolean;
}) {
  const overall = productScore(product, 'overall_opportunity');
  const confidence = productScore(product, 'data_confidence');
  const strategy = productStrategy(product);
  return (
    <article className="product-summary-row">
      <div className="product-summary-row__identity">
        {product.image_url && <img src={product.image_url} alt="" loading="lazy" />}
        <div>
          <Link to={`/products/${encodeURIComponent(product.id)}`}>{product.title}</Link>
          <small>
            {product.brand || 'Unknown brand'} · {product.asin}
          </small>
        </div>
      </div>
      <div className="product-summary-row__facts">
        {strategy ? (
          <StatusBadge value={strategy} prefix="Recommended" />
        ) : (
          <span className="muted">No recommendation</span>
        )}
        <span>
          {risk ? 'Opportunity' : 'Overall'}:{' '}
          <strong>{overall ? `${formatNumber(overall.value)} / 100` : 'Not scored'}</strong>
        </span>
        <span>
          Confidence:{' '}
          <strong>{confidence ? `${formatNumber(confidence.value)} / 100` : 'Not scored'}</strong>
        </span>
        {product.buy_box_price !== undefined && (
          <span>
            Observed price: <strong>{formatMoney(product.buy_box_price)}</strong>
          </span>
        )}
      </div>
    </article>
  );
}
