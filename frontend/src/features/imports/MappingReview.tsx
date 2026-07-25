import type { FormEvent } from 'react';

import type { ImportColumnMapping } from '../../api/contracts';
import { StatusBadge } from '../../components/StatusBadge';
import { humanize } from '../../utils/format';

function previewValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function needsReview(column: ImportColumnMapping): boolean {
  return column.classification === 'ambiguous' || column.dataset_classification === 'unrecognized';
}

type MappingReviewProps = {
  columns: ImportColumnMapping[];
  canonicalFields: string[];
  mappings: Record<string, string>;
  missingRequired: string[];
  unresolvedAmbiguous: ImportColumnMapping[];
  mappingSaved: boolean;
  saving: boolean;
  onMappingChange: (ordinal: number, canonicalField: string) => void;
  onSave: (event: FormEvent<HTMLFormElement>) => void;
};

export function MappingReview({
  columns,
  canonicalFields,
  mappings,
  missingRequired,
  unresolvedAmbiguous,
  mappingSaved,
  saving,
  onMappingChange,
  onSave,
}: MappingReviewProps) {
  const reviewColumns = columns.filter(needsReview);
  const canonicalColumns = columns.filter((column) => Boolean(column.canonical_field));
  const preservedColumns = columns.filter(
    (column) => column.dataset_classification === 'registered_source' && !column.canonical_field,
  );

  if (columns.length === 0) {
    return (
      <section className="panel" aria-labelledby="mapping-heading">
        <h2 id="mapping-heading">Column handling</h2>
        <div className="form-message form-message--error" role="alert">
          No readable columns were detected in this workbook.
        </div>
      </section>
    );
  }

  return (
    <section className="panel mapping-review" aria-labelledby="mapping-heading">
      <div className="section-heading">
        <div>
          <p className="data-label">Versioned column handling</p>
          <h2 id="mapping-heading">Review only exceptions</h2>
          <p>
            Registered source fields are preserved automatically. Only ambiguous or genuinely new
            headers need attention.
          </p>
        </div>
        <span>{columns.length} source columns</span>
      </div>

      {reviewColumns.length === 0 && missingRequired.length === 0 ? (
        <div className="form-message form-message--success" role="status">
          Every source column is handled by the registered dataset model. No manual mapping is
          required.
        </div>
      ) : (
        <form onSubmit={onSave}>
          <div className="mapping-list">
            {reviewColumns.map((column) => (
              <div className="mapping-row" key={column.ordinal}>
                <div>
                  <strong>{column.header || `Column ${column.ordinal}`}</strong>
                  <span>
                    Source column {column.ordinal} ·{' '}
                    <StatusBadge
                      value={
                        column.classification === 'ambiguous' ? 'ambiguous' : 'new source field'
                      }
                    />
                  </span>
                  {column.samples && column.samples.length > 0 && (
                    <small>
                      Examples: {column.samples.slice(0, 3).map(previewValue).join(', ')}
                    </small>
                  )}
                </div>
                <label className="field">
                  <span>SellerOS handling for {column.header || `column ${column.ordinal}`}</span>
                  <select
                    value={mappings[String(column.ordinal)] ?? ''}
                    onChange={(event) => onMappingChange(column.ordinal, event.target.value)}
                  >
                    <option value="">
                      {column.classification === 'ambiguous'
                        ? 'Choose a SellerOS field'
                        : 'Preserve as a new source field'}
                    </option>
                    {canonicalFields.map((option) => (
                      <option value={option} key={option}>
                        {humanize(option)}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            ))}
          </div>

          {missingRequired.length > 0 && (
            <div className="form-message form-message--error" role="alert">
              Required fields still need a source column: {missingRequired.map(humanize).join(', ')}
              .
            </div>
          )}
          {unresolvedAmbiguous.length > 0 && (
            <div className="form-message form-message--warning" role="status">
              Resolve {unresolvedAmbiguous.length} ambiguous mapping
              {unresolvedAmbiguous.length === 1 ? '' : 's'} before confirming.
            </div>
          )}

          <div className="form-actions">
            <button className="button button--secondary" type="submit" disabled={saving}>
              {saving ? 'Saving mapping choices…' : 'Save mapping choices'}
            </button>
            {mappingSaved && <span className="mapping-saved">Mapping choices saved</span>}
          </div>
        </form>
      )}

      <div className="mapping-details">
        <details>
          <summary>Canonical decision fields ({canonicalColumns.length})</summary>
          <ul className="source-field-list">
            {canonicalColumns.map((column) => (
              <li key={column.ordinal}>
                <span>{column.header}</span>
                <strong>{humanize(column.canonical_field ?? '')}</strong>
              </li>
            ))}
          </ul>
        </details>
        <details>
          <summary>Preserved source fields ({preservedColumns.length})</summary>
          <p className="muted">
            These fields belong to the registered source model. Their values are retained as
            evidence even though SellerOS does not yet use them in calculations.
          </p>
          <ul className="source-field-list source-field-list--compact">
            {preservedColumns.map((column) => (
              <li key={column.ordinal}>
                <span>{column.header}</span>
                <small>Source column {column.ordinal}</small>
              </li>
            ))}
          </ul>
        </details>
      </div>
    </section>
  );
}
