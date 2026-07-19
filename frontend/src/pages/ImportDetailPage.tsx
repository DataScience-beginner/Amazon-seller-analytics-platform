import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';

import { confirmImport, fetchImport, updateImportMapping } from '../api/client';
import type { ImportBatch, ImportColumnMapping } from '../api/contracts';
import { Link } from '../app/router';
import { useWorkspace } from '../app/workspace';
import { ErrorState, LoadingState } from '../components/Feedback';
import { PageHeader } from '../components/PageHeader';
import { StatusBadge } from '../components/StatusBadge';
import { useAsync } from '../hooks/useAsync';
import { formatDate, formatNumber, humanize } from '../utils/format';

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

  useEffect(() => {
    if (!loadedBatch) return;
    const loadedColumns = loadedBatch.mapping?.columns ?? loadedBatch.columns ?? [];
    setMappings(mappingsFrom(loadedColumns));
    const status = normalizedStatus(loadedBatch);
    setMappingSaved(status === 'completed');
  }, [loadedBatch]);

  useEffect(() => {
    setBatchOverride(null);
    setActionError(null);
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
  const canConfirm = missingRequired.length === 0 && unresolvedAmbiguous.length === 0;

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
    setConfirming(true);
    setActionError(null);
    try {
      const response = await confirmImport(importId, organisationId, marketplaceId);
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

  return (
    <>
      <Link className="back-link" to="/imports">
        ← Import history
      </Link>
      <PageHeader
        eyebrow="Import inspection"
        title={batch.original_filename ?? batch.filename ?? `Import ${batch.id}`}
        description="Review how source evidence maps to SellerOS before any product snapshot is created."
        action={<StatusBadge value={batch.status} />}
      />

      <section className="metadata-strip" aria-label="Import metadata">
        <div>
          <span>Uploaded</span>
          <strong>{formatDate(batch.uploaded_at ?? batch.created_at)}</strong>
        </div>
        <div>
          <span>Sheet</span>
          <strong>{batch.selected_sheet ?? 'Detected automatically'}</strong>
        </div>
        <div>
          <span>Header row</span>
          <strong>{formatNumber(batch.header_row, 0)}</strong>
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
          <p className="data-label">Transactional result</p>
          <h2 id="summary-heading">Import summary</h2>
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
            Import confirmed. Previous snapshots remain unchanged.
          </p>
          <Link className="button" to="/products">
            Review product recommendations
          </Link>
        </section>
      )}

      {!completed && !failed && (
        <>
          <section className="panel" aria-labelledby="mapping-heading">
            <div className="section-heading">
              <div>
                <p className="data-label">Versioned mapping</p>
                <h2 id="mapping-heading">Confirm column mapping</h2>
                <p>
                  Registry {batch.mapping?.registry_id ?? 'Keepa'}{' '}
                  {batch.mapping?.registry_version ?? ''}
                </p>
              </div>
            </div>
            {columns.length === 0 ? (
              <div className="form-message form-message--error" role="alert">
                No readable columns were detected in this workbook.
              </div>
            ) : (
              <form onSubmit={saveMapping}>
                <div className="mapping-list">
                  {columns.map((column) => {
                    const candidateOptions = canonicalFields;
                    return (
                      <div className="mapping-row" key={column.ordinal}>
                        <div>
                          <strong>{column.header || `Column ${column.ordinal}`}</strong>
                          <span>
                            Source column {column.ordinal} ·{' '}
                            <StatusBadge value={column.classification} />
                          </span>
                          {column.samples && column.samples.length > 0 && (
                            <small>
                              Examples: {column.samples.slice(0, 3).map(previewValue).join(', ')}
                            </small>
                          )}
                        </div>
                        <label className="field">
                          <span>
                            SellerOS field for {column.header || `column ${column.ordinal}`}
                          </span>
                          <select
                            value={mappings[String(column.ordinal)] ?? ''}
                            onChange={(event) => {
                              setMappings((current) => ({
                                ...current,
                                [String(column.ordinal)]: event.target.value,
                              }));
                              setMappingSaved(false);
                            }}
                          >
                            <option value="">Preserve as an unknown field</option>
                            {candidateOptions.map((option) => (
                              <option value={option} key={option}>
                                {humanize(option)}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>
                    );
                  })}
                </div>
                {missingRequired.length > 0 && (
                  <div className="form-message form-message--error" role="alert">
                    Required fields still need a source column:{' '}
                    {missingRequired.map(humanize).join(', ')}.
                  </div>
                )}
                {unresolvedAmbiguous.length > 0 && (
                  <div className="form-message form-message--warning" role="status">
                    Resolve {unresolvedAmbiguous.length} ambiguous mapping
                    {unresolvedAmbiguous.length === 1 ? '' : 's'} before confirming.
                  </div>
                )}
                {actionError && (
                  <div className="form-message form-message--error" role="alert">
                    {actionError}
                  </div>
                )}
                <div className="form-actions">
                  <button className="button button--secondary" type="submit" disabled={saving}>
                    {saving ? 'Saving mapping…' : 'Save mapping'}
                  </button>
                  <button
                    className="button"
                    type="button"
                    disabled={!canConfirm || !mappingSaved || confirming}
                    onClick={confirm}
                  >
                    {confirming ? 'Importing rows…' : 'Confirm and create snapshots'}
                  </button>
                </div>
                {!mappingSaved && canConfirm && (
                  <p className="muted">Save the mapping before confirming the import.</p>
                )}
              </form>
            )}
          </section>

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
