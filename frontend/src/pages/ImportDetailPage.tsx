import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';

import { confirmImport, fetchImport, updateImportMapping } from '../api/client';
import type { ImportBatch, ImportColumnMapping } from '../api/contracts';
import { Link } from '../app/router';
import { useWorkspace } from '../app/workspace';
import { ErrorState, LoadingState } from '../components/Feedback';
import { PageHeader } from '../components/PageHeader';
import { StatusBadge } from '../components/StatusBadge';
import {
  DatasetConfirmationPanel,
  observedOnError,
} from '../features/imports/DatasetConfirmationPanel';
import { MappingReview } from '../features/imports/MappingReview';
import { useAsync } from '../hooks/useAsync';
import { formatDate, formatMonth, formatNumber, formatUtcDateInput } from '../utils/format';

function normalizedStatus(batch: ImportBatch): string {
  return batch.status.toLowerCase().replace(/[_-]+/g, ' ');
}

function mappingsFrom(columns: ImportColumnMapping[]): Record<string, string> {
  return Object.fromEntries(
    columns.map((column) => [String(column.ordinal), column.canonical_field ?? '']),
  );
}

function previewValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export function ImportDetailPage({ importId }: { importId: string }) {
  const { selection } = useWorkspace();
  const organisationId = selection.workspace.organisation_id;
  const marketplaceId = selection.marketplace.id;
  const load = useCallback(
    (signal: AbortSignal) => fetchImport(importId, organisationId, marketplaceId, signal),
    [importId, marketplaceId, organisationId],
  );
  const state = useAsync(load);
  const [batchOverride, setBatchOverride] = useState<ImportBatch | null>(null);
  const loadedBatch = state.status === 'success' ? state.data : null;
  const batch = batchOverride ?? loadedBatch;
  const columns = useMemo(() => batch?.mapping?.columns ?? batch?.columns ?? [], [batch]);
  const canonicalFields = useMemo(
    () =>
      Array.from(
        new Set(
          [
            ...(batch?.mapping?.missing ?? []),
            ...(batch?.mapping?.required ?? []),
            ...(batch?.mapping?.optional ?? []),
            ...columns.flatMap((column) => [
              column.canonical_field,
              ...(column.candidates ?? []),
              ...(column.required_candidates ?? []),
            ]),
          ].filter((field): field is string => Boolean(field)),
        ),
      ).sort(),
    [batch, columns],
  );
  const [mappings, setMappings] = useState<Record<string, string>>({});
  const [mappingSaved, setMappingSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [observedOn, setObservedOn] = useState('');
  const [dateAcknowledged, setDateAcknowledged] = useState(false);
  const today = formatUtcDateInput();

  useEffect(() => {
    if (!loadedBatch) return;
    const loadedColumns = loadedBatch.mapping?.columns ?? loadedBatch.columns ?? [];
    setMappings(mappingsFrom(loadedColumns));
    const status = normalizedStatus(loadedBatch);
    setMappingSaved(status === 'completed' || !loadedBatch.mapping?.requires_confirmation);
    setObservedOn(
      loadedBatch.dataset?.observed_on ?? loadedBatch.dataset?.observed_on_suggestion ?? '',
    );
    setDateAcknowledged(status === 'completed');
  }, [loadedBatch]);

  useEffect(() => {
    setBatchOverride(null);
    setActionError(null);
    setObservedOn('');
    setDateAcknowledged(false);
  }, [importId, marketplaceId, organisationId]);

  const selectedFields = new Set(Object.values(mappings).filter(Boolean));
  const missingRequired = (batch?.mapping?.missing ?? batch?.mapping?.required ?? []).filter(
    (field) => !selectedFields.has(field),
  );
  if (!selectedFields.has('asin') && columns.length > 0 && !missingRequired.includes('asin')) {
    missingRequired.push('asin');
  }
  const unresolvedAmbiguous = columns.filter(
    (column) => column.classification === 'ambiguous' && !mappings[String(column.ordinal)],
  );
  const mappingComplete = missingRequired.length === 0 && unresolvedAmbiguous.length === 0;
  const mappingReady = mappingComplete && mappingSaved;

  async function saveMapping(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setActionError(null);
    try {
      const response = await updateImportMapping(
        importId,
        organisationId,
        marketplaceId,
        Object.fromEntries(
          Object.entries(mappings).map(([ordinal, canonical]) => [ordinal, canonical || null]),
        ),
      );
      setBatchOverride(response);
      setMappingSaved(true);
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : 'Unable to save mapping');
    } finally {
      setSaving(false);
    }
  }

  async function confirm() {
    if (observedOnError(observedOn, today) || !dateAcknowledged || !mappingReady) return;
    setConfirming(true);
    setActionError(null);
    try {
      const response = await confirmImport(importId, organisationId, marketplaceId, observedOn);
      setBatchOverride(response);
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : 'Unable to confirm import');
    } finally {
      setConfirming(false);
    }
  }

  if (state.status === 'loading') return <LoadingState label="Inspecting import evidence…" />;
  if (state.status === 'error') return <ErrorState error={state.error} onRetry={state.retry} />;
  if (!batch) return null;

  const status = normalizedStatus(batch);
  const previewRows = batch.preview_rows ?? [];
  const previewHeaders = Array.from(new Set(previewRows.flatMap((row) => Object.keys(row)))).slice(
    0,
    10,
  );
  const completed = status === 'completed';
  const failed = status === 'failed';
  const legacyUndatedDataset =
    batch.dataset?.date_status === 'legacy_unconfirmed' ||
    (completed && !batch.dataset?.date_status && !batch.dataset?.observed_on);

  return (
    <>
      <Link className="back-link" to="/imports">
        ← Import history
      </Link>
      <PageHeader
        eyebrow="Import inspection"
        title={batch.original_filename ?? batch.filename ?? `Import ${batch.id}`}
        description="Confirm when the market evidence was observed. The upload time remains separate for auditing."
        action={<StatusBadge value={batch.status} />}
      />

      <section className="metadata-strip" aria-label="Import metadata">
        <div>
          <span>Uploaded</span>
          <strong>{formatDate(batch.uploaded_at ?? batch.created_at)}</strong>
        </div>
        <div>
          <span>Observed on</span>
          <strong>
            {batch.dataset?.observed_on
              ? formatDate(batch.dataset.observed_on)
              : 'Observation date unavailable'}
          </strong>
        </div>
        <div>
          <span>Dataset month</span>
          <strong>
            {batch.dataset?.period_month
              ? formatMonth(batch.dataset.period_month)
              : 'Observation date unavailable'}
          </strong>
        </div>
        <div>
          <span>Source model</span>
          <strong>
            {batch.dataset?.schema_id ?? 'Not registered'} ·{' '}
            {batch.dataset?.schema_version ?? 'No version'}
          </strong>
        </div>
        <div>
          <span>Sheet</span>
          <strong>{batch.selected_sheet ?? 'Detected automatically'}</strong>
        </div>
        <div>
          <span>Checksum</span>
          <strong className="checksum">{batch.checksum_sha256 ?? 'Calculated server-side'}</strong>
        </div>
      </section>

      {batch.duplicate && (
        <div className="form-message form-message--warning" role="status">
          This workbook checksum already exists in the selected workspace. SellerOS opened the
          existing import without creating duplicate snapshots.
        </div>
      )}

      {failed && (
        <div className="form-message form-message--error" role="alert">
          <strong>Import failed.</strong>{' '}
          {batch.error_message ?? 'Review the workbook and try again.'}
        </div>
      )}

      {completed && batch.summary && (
        <section className="panel" aria-labelledby="summary-heading">
          <p className="data-label">Immutable monthly evidence</p>
          <h2 id="summary-heading">
            {legacyUndatedDataset
              ? 'Legacy dataset — observation date unavailable'
              : `${formatMonth(batch.dataset?.period_month)} dataset created`}
          </h2>
          <p>
            {legacyUndatedDataset ? (
              <>No observation date was recorded for this historical import. </>
            ) : (
              <>
                Observed on <strong>{formatDate(batch.dataset?.observed_on)}</strong>.{' '}
              </>
            )}
            Uploaded {formatDate(batch.uploaded_at)} · revision{' '}
            {batch.dataset?.revision ?? 'Not available'}
          </p>
          <div className="summary-grid">
            <div>
              <span>New products</span>
              <strong>{formatNumber(batch.summary.created, 0)}</strong>
            </div>
            <div>
              <span>Matched products</span>
              <strong>{formatNumber(batch.summary.matched, 0)}</strong>
            </div>
            <div>
              <span>Skipped rows</span>
              <strong>{formatNumber(batch.summary.skipped, 0)}</strong>
            </div>
            <div>
              <span>Failed rows</span>
              <strong>{formatNumber(batch.summary.failed, 0)}</strong>
            </div>
          </div>
          <p className="form-message form-message--success" role="status">
            Dataset confirmed. Previous monthly snapshots remain unchanged.
          </p>
          <Link className="button" to="/products">
            Review product recommendations
          </Link>
        </section>
      )}

      {!completed && !failed && (
        <>
          {batch.dataset ? (
            <DatasetConfirmationPanel
              dataset={batch.dataset}
              columns={columns}
              observedOn={observedOn}
              today={today}
              acknowledged={dateAcknowledged}
              mappingReady={mappingReady}
              confirming={confirming}
              actionError={actionError}
              onObservedOnChange={(value) => {
                setObservedOn(value);
                setDateAcknowledged(false);
              }}
              onAcknowledgedChange={setDateAcknowledged}
              onConfirm={confirm}
            />
          ) : (
            <div className="form-message form-message--error" role="alert">
              Dataset metadata is unavailable. Do not confirm this import.
            </div>
          )}

          <MappingReview
            columns={columns}
            canonicalFields={canonicalFields}
            mappings={mappings}
            missingRequired={missingRequired}
            unresolvedAmbiguous={unresolvedAmbiguous}
            mappingSaved={mappingSaved}
            saving={saving}
            onMappingChange={(ordinal, canonicalField) => {
              setMappings((current) => ({
                ...current,
                [String(ordinal)]: canonicalField,
              }));
              setMappingSaved(false);
            }}
            onSave={saveMapping}
          />

          <section className="panel" aria-labelledby="preview-heading">
            <div className="section-heading">
              <div>
                <p className="data-label">Observed preview</p>
                <h2 id="preview-heading">Source values</h2>
              </div>
              <span>{previewRows.length} preview rows</span>
            </div>
            {previewRows.length === 0 ? (
              <p className="muted">No data rows were available for preview.</p>
            ) : (
              <div className="table-scroll" tabIndex={0} aria-label="Scrollable workbook preview">
                <table>
                  <thead>
                    <tr>
                      {previewHeaders.map((header) => (
                        <th scope="col" key={header}>
                          {header}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {previewRows.map((row, rowIndex) => (
                      <tr key={rowIndex}>
                        {previewHeaders.map((header) => (
                          <td key={header}>{previewValue(row[header])}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </>
  );
}
