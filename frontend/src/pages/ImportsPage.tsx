import { useCallback, useState, type FormEvent } from 'react';

import { fetchImports, uploadImport } from '../api/client';
import { Link, useNavigate } from '../app/router';
import { useWorkspace } from '../app/workspace';
import { EmptyState, ErrorState, LoadingState } from '../components/Feedback';
import { PageHeader } from '../components/PageHeader';
import { StatusBadge } from '../components/StatusBadge';
import { useAsync } from '../hooks/useAsync';
import { formatDate, formatMonth, formatNumber } from '../utils/format';

export function ImportsPage() {
  const { selection } = useWorkspace();
  const navigate = useNavigate();
  const organisationId = selection.workspace.organisation_id;
  const marketplaceId = selection.marketplace.id;
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const load = useCallback(
    (signal: AbortSignal) => fetchImports(organisationId, marketplaceId, signal),
    [organisationId, marketplaceId],
  );
  const state = useAsync(load);

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setUploadError(null);
    if (!file) {
      setUploadError('Choose a Keepa .xlsx file.');
      return;
    }
    if (!file.name.toLowerCase().endsWith('.xlsx')) {
      setUploadError('Only .xlsx workbooks are supported.');
      return;
    }
    if (file.size === 0) {
      setUploadError('The selected workbook is empty.');
      return;
    }

    setUploading(true);
    try {
      const batch = await uploadImport({ file, organisationId, marketplaceId });
      navigate(`/imports/${encodeURIComponent(batch.id)}`);
    } catch (caught) {
      setUploadError(caught instanceof Error ? caught.message : 'Unable to upload workbook');
    } finally {
      setUploading(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Observed evidence"
        title="Keepa imports"
        description="Create one immutable, explicitly dated market dataset for each monthly Keepa workbook."
      />
      <div className="import-layout">
        <section className="panel" aria-labelledby="upload-heading">
          <h2 id="upload-heading">Upload a workbook</h2>
          <form onSubmit={upload}>
            <label className="upload-field">
              <span>Keepa Excel file</span>
              <input
                type="file"
                accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                aria-describedby="file-help"
              />
              <small id="file-help">
                Use a Keepa Product Finder .xlsx export. The original file is never executed.
              </small>
            </label>
            {file && (
              <p className="selected-file" role="status">
                Selected: <strong>{file.name}</strong> ({formatNumber(file.size / 1024, 0)} KB)
              </p>
            )}
            {uploadError && (
              <div className="form-message form-message--error" role="alert">
                {uploadError}
              </div>
            )}
            <button className="button" type="submit" disabled={uploading}>
              {uploading ? 'Inspecting workbook…' : 'Upload and inspect'}
            </button>
          </form>
        </section>
        <aside className="panel import-safety" aria-labelledby="safe-import-heading">
          <p className="data-label">Import safety</p>
          <h2 id="safe-import-heading">Nothing changes before confirmation</h2>
          <ul>
            <li>The workbook date is suggested, but you must confirm it.</li>
            <li>Registered source fields are preserved without manual mapping.</li>
            <li>Only ambiguous or genuinely new fields need review.</li>
            <li>Duplicate checksums do not create duplicate snapshots.</li>
          </ul>
        </aside>
      </div>

      <section className="panel import-history" aria-labelledby="history-heading">
        <div className="section-heading">
          <div>
            <p className="data-label">Audit trail</p>
            <h2 id="history-heading">Import history</h2>
          </div>
        </div>
        {state.status === 'loading' && <LoadingState label="Loading import history…" />}
        {state.status === 'error' && <ErrorState error={state.error} onRetry={state.retry} />}
        {state.status === 'success' && state.data.items.length === 0 && (
          <EmptyState title="No imports yet">
            <p>Your uploaded workbooks and their final row summaries will appear here.</p>
          </EmptyState>
        )}
        {state.status === 'success' && state.data.items.length > 0 && (
          <div className="table-scroll" tabIndex={0} aria-label="Scrollable import history">
            <table>
              <thead>
                <tr>
                  <th scope="col">File</th>
                  <th scope="col">Status</th>
                  <th scope="col">Rows</th>
                  <th scope="col">Dataset month</th>
                  <th scope="col">Observed on</th>
                  <th scope="col">Revision</th>
                  <th scope="col">Uploaded</th>
                </tr>
              </thead>
              <tbody>
                {state.data.items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <Link to={`/imports/${encodeURIComponent(item.id)}`}>
                        {item.original_filename ?? item.filename ?? `Import ${item.id}`}
                      </Link>
                    </td>
                    <td>
                      <StatusBadge value={item.status} />
                    </td>
                    <td>{formatNumber(item.row_count, 0)}</td>
                    <td>
                      {item.period_month
                        ? formatMonth(item.period_month)
                        : 'Observation date unavailable'}
                    </td>
                    <td>
                      {item.observed_on
                        ? formatDate(item.observed_on)
                        : 'Observation date unavailable'}
                    </td>
                    <td>{item.revision ?? 'Not available'}</td>
                    <td>{formatDate(item.uploaded_at ?? item.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
