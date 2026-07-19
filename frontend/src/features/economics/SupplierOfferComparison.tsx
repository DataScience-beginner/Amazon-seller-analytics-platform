import type { SupplierOffer, SupplierOfferListResponse } from '../../api/contracts';
import { formatDate, formatUnitMoney } from '../../utils/format';

export function SupplierOfferComparison({
  offers,
  pagination,
  selectionNote,
  onPageChange,
}: {
  offers: SupplierOffer[];
  pagination: SupplierOfferListResponse['pagination'];
  selectionNote: string;
  onPageChange: (page: number) => void;
}) {
  const firstItem =
    pagination.total_items === 0 ? 0 : (pagination.page - 1) * pagination.page_size + 1;
  const lastItem = firstItem === 0 ? 0 : firstItem + offers.length - 1;
  return (
    <section className="panel" aria-labelledby="supplier-offers-heading">
      <div className="section-heading">
        <div>
          <p className="data-label">User confirmed</p>
          <h2 id="supplier-offers-heading">Supplier offer comparison</h2>
        </div>
        <span>{pagination.total_items} recorded</span>
      </div>
      {offers.length === 0 ? (
        <div className="inline-empty">
          <strong>No supplier offers yet</strong>
          <p>Add a quotation below to compare cost, commitment and replenishment time.</p>
        </div>
      ) : (
        <div
          className="table-scroll"
          tabIndex={0}
          aria-label="Scrollable supplier offer comparison"
        >
          <table className="supplier-table">
            <thead>
              <tr>
                <th scope="col">Supplier</th>
                <th scope="col">Unit cost</th>
                <th scope="col">MOQ</th>
                <th scope="col">Lead time</th>
                <th scope="col">Quotation</th>
                <th scope="col">Validity</th>
                <th scope="col">Price tiers</th>
                <th scope="col">Notes</th>
              </tr>
            </thead>
            <tbody>
              {offers.map((offer) => (
                <tr key={offer.id}>
                  <td>
                    <strong>{offer.supplier.name}</strong>
                  </td>
                  <td>
                    {formatUnitMoney({
                      amount: offer.unit_cost,
                      currency_code: offer.currency_code,
                    })}
                  </td>
                  <td>{offer.minimum_order_quantity} units</td>
                  <td>{offer.lead_time_days} days</td>
                  <td>{formatDate(offer.quotation_date)}</td>
                  <td>{offer.valid_until ? formatDate(offer.valid_until) : 'Open-ended'}</td>
                  <td>
                    {offer.price_tiers.length === 0 ? (
                      'None'
                    ) : (
                      <ul className="compact-list">
                        {offer.price_tiers.map((tier) => (
                          <li key={`${offer.id}-${tier.minimum_quantity}`}>
                            {tier.minimum_quantity}+ at{' '}
                            {formatUnitMoney({
                              amount: tier.unit_cost,
                              currency_code: offer.currency_code,
                            })}
                          </li>
                        ))}
                      </ul>
                    )}
                  </td>
                  <td>{offer.notes || 'None'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <nav className="pagination" aria-label="Supplier offer pages">
        <button
          className="button button--secondary"
          type="button"
          disabled={!pagination.has_previous}
          onClick={() => onPageChange(pagination.page - 1)}
        >
          Previous offers
        </button>
        <span>
          Showing {firstItem}–{lastItem} of {pagination.total_items} · Page {pagination.page} of{' '}
          {Math.max(1, pagination.total_pages)}
        </span>
        <button
          className="button button--secondary"
          type="button"
          disabled={!pagination.has_next}
          onClick={() => onPageChange(pagination.page + 1)}
        >
          Next offers
        </button>
      </nav>
      <p className="decision-disclaimer">
        {selectionNote ||
          'Price alone does not determine the best offer. Review MOQ, lead time, validity and price tiers before choosing a scenario.'}
      </p>
    </section>
  );
}
