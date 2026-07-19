import type { CostProfile, ProductEconomicsResponse } from '../../api/contracts';
import { formatDate, formatUnitMoney, formatUtcDate, humanize } from '../../utils/format';
import { costProfileWindowStatus } from './profileModel';

function profileScope(profile: CostProfile): string {
  return profile.product_id ? 'Product specific' : 'Marketplace default';
}

export function CostProfileHistory({
  profileSource,
  activeProfile,
  history,
}: {
  profileSource: ProductEconomicsResponse['profile_source'];
  activeProfile: CostProfile | null;
  history: CostProfile[];
}) {
  return (
    <section className="panel" aria-labelledby="cost-history-heading">
      <div className="section-heading">
        <div>
          <p className="data-label">User confirmed</p>
          <h2 id="cost-history-heading">Cost profile history</h2>
        </div>
        <span>
          {history.length} immutable version{history.length === 1 ? '' : 's'}
        </span>
      </div>
      {!activeProfile ? (
        <div className="inline-empty">
          <strong>No active cost profile</strong>
          <p>
            Unit economics stay unavailable until a product or marketplace-default profile is
            entered.
          </p>
        </div>
      ) : (
        <div className="active-profile-summary">
          <dl className="metric-grid">
            <div>
              <dt>Applied profile</dt>
              <dd>{profileSource ? humanize(profileSource) : profileScope(activeProfile)}</dd>
            </div>
            <div>
              <dt>Version</dt>
              <dd>{activeProfile.version}</dd>
            </div>
            <div>
              <dt>Effective from</dt>
              <dd>{formatDate(activeProfile.effective_from)}</dd>
            </div>
            <div>
              <dt>Purchase cost (GST-exclusive)</dt>
              <dd>
                {formatUnitMoney({
                  amount: activeProfile.purchase_cost,
                  currency_code: activeProfile.currency_code,
                })}
              </dd>
            </div>
            <div>
              <dt>Selling-price tax basis</dt>
              <dd>
                {activeProfile.selling_price_tax_basis
                  ? activeProfile.selling_price_tax_basis === 'tax_inclusive'
                    ? 'Price includes GST'
                    : 'Price excludes GST'
                  : 'Unknown · price-dependent outputs blocked'}
              </dd>
            </div>
            <div>
              <dt>Fee evidence</dt>
              <dd>{activeProfile.fee_status ? humanize(activeProfile.fee_status) : 'Missing'}</dd>
            </div>
            <div>
              <dt>Fee source / UTC date</dt>
              <dd>
                {activeProfile.fee_source || 'Not provided'} ·{' '}
                {activeProfile.fee_effective_at
                  ? `${formatUtcDate(activeProfile.fee_effective_at)} UTC`
                  : 'date not provided'}
              </dd>
            </div>
          </dl>
        </div>
      )}

      {history.length > 0 && (
        <details className="trace-details">
          <summary>Review effective-dated versions</summary>
          <div className="table-scroll" tabIndex={0} aria-label="Scrollable cost profile history">
            <table>
              <thead>
                <tr>
                  <th scope="col">Version</th>
                  <th scope="col">Scope</th>
                  <th scope="col">Effective from</th>
                  <th scope="col">Status</th>
                  <th scope="col">Effective to</th>
                  <th scope="col">Purchase cost</th>
                  <th scope="col">Configuration</th>
                </tr>
              </thead>
              <tbody>
                {history.map((profile) => (
                  <tr key={profile.id}>
                    <td>{profile.version}</td>
                    <td>{profileScope(profile)}</td>
                    <td>{formatDate(profile.effective_from)}</td>
                    <td>{humanize(costProfileWindowStatus(profile))}</td>
                    <td>
                      {profile.effective_to ? formatDate(profile.effective_to) : 'Open-ended'}
                    </td>
                    <td>
                      {formatUnitMoney({
                        amount: profile.purchase_cost,
                        currency_code: profile.currency_code,
                      })}
                    </td>
                    <td className="checksum">{profile.configuration_checksum}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </section>
  );
}
