import type { FormEvent } from 'react';

import type { ImportColumnMapping, ImportDatasetMetadata } from '../../api/contracts';
import { formatDate, formatMonth, formatNumber, humanize } from '../../utils/format';

type DatasetCounts = {
  canonical: number;
  preserved: number;
  unrecognized: number;
};

export function datasetCounts(columns: ImportColumnMapping[]): DatasetCounts {
  return {
    canonical: columns.filter((column) => Boolean(column.canonical_field)).length,
    preserved: columns.filter(
      (column) => column.dataset_classification === 'registered_source' && !column.canonical_field,
    ).length,
    unrecognized: columns.filter((column) => column.dataset_classification === 'unrecognized')
      .length,
  };
}

export function observedOnError(value: string, today: string): string | null {
  if (!value) return 'Choose the date represented by this workbook.';
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return 'Enter a valid date.';
  const [, year, month, day] = match;
  const date = new Date(Number(year), Number(month) - 1, Number(day));
  if (
    date.getFullYear() !== Number(year) ||
    date.getMonth() !== Number(month) - 1 ||
    date.getDate() !== Number(day)
  ) {
    return 'Enter a valid date.';
  }
  if (value > today) return 'Dataset evidence cannot be dated in the future.';
  return null;
}

type DatasetConfirmationPanelProps = {
  dataset: ImportDatasetMetadata;
  columns: ImportColumnMapping[];
  observedOn: string;
  today: string;
  acknowledged: boolean;
  mappingReady: boolean;
  confirming: boolean;
  actionError: string | null;
  onObservedOnChange: (value: string) => void;
  onAcknowledgedChange: (checked: boolean) => void;
  onConfirm: () => void;
};

export function DatasetConfirmationPanel({
  dataset,
  columns,
  observedOn,
  today,
  acknowledged,
  mappingReady,
  confirming,
  actionError,
  onObservedOnChange,
  onAcknowledgedChange,
  onConfirm,
}: DatasetConfirmationPanelProps) {
  const counts = datasetCounts(columns);
  const dateError = observedOnError(observedOn, today);
  const periodMonth = observedOn ? `${observedOn.slice(0, 7)}-01` : null;
  const canConfirm = mappingReady && !dateError && acknowledged && !confirming;
  const schemaName = dataset.schema_id
    ? humanize(dataset.schema_id.replaceAll('.', '_'))
    : 'Unknown';

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (canConfirm) onConfirm();
  }

  return (
    <section className="panel dataset-confirmation" aria-labelledby="dataset-heading">
      <div className="section-heading">
        <div>
          <p className="data-label">User confirmed dataset evidence</p>
          <h2 id="dataset-heading">Create the monthly dataset</h2>
          <p>
            SellerOS keeps the evidence date separate from the upload time. Review the suggested
            date before any snapshots are created.
          </p>
        </div>
        <span className="dataset-schema">
          {schemaName} · v{dataset.schema_version ?? 'unregistered'}
        </span>
      </div>

      <div className="dataset-counts" aria-label="Dataset column classifications">
        <div>
          <span>Canonical fields</span>
          <strong>{formatNumber(counts.canonical, 0)}</strong>
          <small>Used by SellerOS decisions</small>
        </div>
        <div>
          <span>Preserved source fields</span>
          <strong>{formatNumber(counts.preserved, 0)}</strong>
          <small>Registered in this source model</small>
        </div>
        <div>
          <span>New fields</span>
          <strong>{formatNumber(counts.unrecognized, 0)}</strong>
          <small>Need review when present</small>
        </div>
        <div>
          <span>Dataset month</span>
          <strong>{formatMonth(periodMonth)}</strong>
          <small>
            {dataset.revision
              ? `Revision ${dataset.revision}`
              : 'Revision assigned on confirmation'}
          </small>
        </div>
      </div>

      {!dataset.observed_on_suggestion && dataset.observation_date_candidates.length > 0 && (
        <div className="form-message form-message--warning" role="status">
          Conflicting workbook dates were detected:{' '}
          {dataset.observation_date_candidates
            .map((candidate) => `${formatDate(candidate.date)} (${humanize(candidate.source)})`)
            .join('; ')}
          . Choose the correct evidence date manually.
        </div>
      )}

      <form onSubmit={submit}>
        <div className="dataset-date-grid">
          <div className="field">
            <label htmlFor="dataset-observed-on">Dataset date (observed on)</label>
            <input
              id="dataset-observed-on"
              type="date"
              value={observedOn}
              max={today}
              aria-describedby="dataset-date-help dataset-date-error"
              aria-invalid={Boolean(dateError)}
              onChange={(event) => onObservedOnChange(event.target.value)}
              required
            />
            <small id="dataset-date-help">
              {dataset.observed_on_suggestion
                ? `Suggested from ${humanize(dataset.suggestion_source ?? 'workbook metadata')}. This is only a suggestion.`
                : 'No reliable date was detected. Enter the date represented by the workbook.'}
            </small>
          </div>
          <div className="dataset-date-preview" aria-live="polite">
            <span>Snapshots will be observed on</span>
            <strong>{formatDate(observedOn)}</strong>
            <small>Uploaded separately; historical evidence is never overwritten.</small>
          </div>
        </div>

        {dateError && (
          <p className="field-error" id="dataset-date-error" role="alert">
            {dateError}
          </p>
        )}

        <label className="dataset-acknowledgement">
          <input
            type="checkbox"
            checked={acknowledged}
            onChange={(event) => onAcknowledgedChange(event.target.checked)}
          />
          <span>
            I confirm this workbook contains market evidence observed on{' '}
            <strong>{formatDate(observedOn)}</strong>. Create a separate{' '}
            <strong>{formatMonth(periodMonth)}</strong> dataset without changing previous months.
          </span>
        </label>

        {!mappingReady && (
          <div className="form-message form-message--warning" role="status">
            Resolve and save the mapping items below before creating this dataset.
          </div>
        )}
        {actionError && (
          <div className="form-message form-message--error" role="alert">
            {actionError}
          </div>
        )}

        <div className="dataset-action-bar">
          <div>
            <strong>
              {formatMonth(periodMonth)} · {formatNumber(dataset.source_column_count, 0)} columns
            </strong>
            <small>Confirmation creates immutable product snapshots.</small>
          </div>
          <button className="button" type="submit" disabled={!canConfirm}>
            {confirming
              ? 'Creating monthly dataset…'
              : `Create ${formatMonth(periodMonth)} dataset`}
          </button>
        </div>
      </form>
    </section>
  );
}
