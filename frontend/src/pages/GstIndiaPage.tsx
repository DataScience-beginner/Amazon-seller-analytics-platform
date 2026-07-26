import { useCallback, useEffect, useState, type FormEvent } from 'react';

import {
  approveGstFiling,
  confirmGstFiled,
  createGstFiling,
  createGstRegistration,
  downloadGstWorkingPaper,
  fetchGstFilings,
  fetchGstRegistrations,
  uploadAmazonGstr1,
} from '../api/client';
import type { GstFiling, GstRegistration } from '../api/contracts';
import { useWorkspace } from '../app/workspace';
import { ErrorState, LoadingState } from '../components/Feedback';
import { PageHeader } from '../components/PageHeader';
import { formatNumber } from '../utils/format';

const steps = [
  'Registration & period',
  'Amazon report',
  'Validate',
  'Preview',
  'Approve & download',
  'Confirm filed',
];

export function GstIndiaPage() {
  const { selection } = useWorkspace();
  const organisationId = selection.workspace.organisation_id;
  const marketplaceId = selection.marketplace.id;
  const [registrations, setRegistrations] = useState<GstRegistration[] | null>(null);
  const [filings, setFilings] = useState<GstFiling[] | null>(null);
  const [selectedId, setSelectedId] = useState('');
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);

  const reload = useCallback(() => setRevision((value) => value + 1), []);
  useEffect(() => {
    const controller = new AbortController();
    setError(null);
    Promise.all([
      fetchGstRegistrations(organisationId, marketplaceId, controller.signal),
      fetchGstFilings(organisationId, marketplaceId, controller.signal),
    ])
      .then(([registrationItems, filingResponse]) => {
        setRegistrations(registrationItems);
        setFilings(filingResponse.items);
        setSelectedId((current) => current || filingResponse.items[0]?.id || '');
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted)
          setError(caught instanceof Error ? caught : new Error('Unable to load GST workflow'));
      });
    return () => controller.abort();
  }, [marketplaceId, organisationId, revision]);

  async function act(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      reload();
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('GST workflow action failed'));
    } finally {
      setBusy(false);
    }
  }

  if (!registrations || !filings) return <LoadingState label="Loading GST India workflow…" />;
  const selected = filings.find((item) => item.id === selectedId) ?? null;

  return (
    <div className="gst-page">
      <PageHeader
        eyebrow="Financials · Tax filing"
        title="GST India"
        description="Prepare an explainable GST working paper from immutable evidence. SellerOS does not log in, pay tax or file the return."
      />
      <ol className="gst-steps" aria-label="GST filing steps">
        {steps.map((step, index) => (
          <li key={step}>
            <span>{index + 1}</span>
            {step}
          </li>
        ))}
      </ol>
      {error && <ErrorState error={error} onRetry={reload} />}
      {registrations.length === 0 ? (
        <RegistrationForm
          disabled={busy}
          onSubmit={(gstin, legalName) =>
            act(() =>
              createGstRegistration({
                organisation_id: organisationId,
                marketplace_id: marketplaceId,
                gstin,
                legal_name: legalName,
                filing_frequency: 'monthly',
              }),
            )
          }
        />
      ) : (
        <section className="gst-card">
          <h2>Step 1 — Select filing period</h2>
          <FilingForm
            registrations={registrations}
            disabled={busy}
            onSubmit={(registrationId, periodMonth) =>
              act(async () => {
                const created = await createGstFiling({
                  organisation_id: organisationId,
                  marketplace_id: marketplaceId,
                  gst_registration_id: registrationId,
                  period_month: `${periodMonth}-01`,
                });
                setSelectedId(created.id);
              })
            }
          />
          {filings.length > 0 && (
            <label>
              Existing filing
              <select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>
                {filings.map((item) => (
                  <option value={item.id} key={item.id}>
                    {item.period_month.slice(0, 7)} · {item.status.replaceAll('_', ' ')}
                  </option>
                ))}
              </select>
            </label>
          )}
        </section>
      )}
      {selected && (
        <FilingWorkspace
          filing={selected}
          disabled={busy}
          onUpload={(file) =>
            act(() => uploadAmazonGstr1(selected.id, organisationId, marketplaceId, file))
          }
          onApprove={() => act(() => approveGstFiling(selected.id, organisationId, marketplaceId))}
          onDownload={() =>
            act(async () => {
              await downloadGstWorkingPaper(selected.id, organisationId, marketplaceId);
            })
          }
          onConfirm={(arn) =>
            act(() => confirmGstFiled(selected.id, organisationId, marketplaceId, arn))
          }
        />
      )}
    </div>
  );
}

function RegistrationForm({
  disabled,
  onSubmit,
}: {
  disabled: boolean;
  onSubmit: (gstin: string, legalName: string) => void;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    onSubmit(String(data.get('gstin')), String(data.get('legal_name')));
  }
  return (
    <form className="gst-card form-grid" onSubmit={submit}>
      <h2>Step 1 — Add GST registration</h2>
      <label>
        GSTIN
        <input name="gstin" minLength={15} maxLength={15} required />
      </label>
      <label>
        Legal business name
        <input name="legal_name" required />
      </label>
      <button className="button" disabled={disabled}>
        Save registration
      </button>
      <small>Credentials, OTP, EVC and DSC are never stored.</small>
    </form>
  );
}

function FilingForm({
  registrations,
  disabled,
  onSubmit,
}: {
  registrations: GstRegistration[];
  disabled: boolean;
  onSubmit: (registrationId: string, periodMonth: string) => void;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    onSubmit(String(data.get('registration')), String(data.get('period')));
  }
  return (
    <form className="form-grid" onSubmit={submit}>
      <label>
        GST registration
        <select name="registration">
          {registrations.map((item) => (
            <option key={item.id} value={item.id}>
              {item.legal_name} · {item.gstin_masked}
            </option>
          ))}
        </select>
      </label>
      <label>
        Filing month
        <input type="month" name="period" required />
      </label>
      <button className="button" disabled={disabled}>
        Create period
      </button>
    </form>
  );
}

function FilingWorkspace({
  filing,
  disabled,
  onUpload,
  onApprove,
  onDownload,
  onConfirm,
}: {
  filing: GstFiling;
  disabled: boolean;
  onUpload: (file: File) => void;
  onApprove: () => void;
  onDownload: () => void;
  onConfirm: (arn: string) => void;
}) {
  const draft = filing.latest_draft;
  return (
    <>
      <section className="gst-card gst-status">
        <div>
          <span>Status</span>
          <strong>{filing.status.replaceAll('_', ' ')}</strong>
        </div>
        <p>{filing.next_step}</p>
      </section>
      <section className="gst-card">
        <h2>Step 2 — Upload Amazon GSTR-1 report</h2>
        <input
          aria-label="Amazon GST Ready-to-File workbook"
          type="file"
          accept=".xlsx"
          disabled={disabled || filing.status !== 'collecting'}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) onUpload(file);
          }}
        />
        {filing.documents.map((document) => (
          <div className="evidence-row" key={document.id}>
            <strong>{document.original_filename}</strong>
            <span>{document.status}</span>
          </div>
        ))}
      </section>
      <section className="gst-card">
        <h2>Steps 3–4 — Validation and preview</h2>
        {filing.exceptions.length ? (
          filing.exceptions.map((item) => (
            <div className="form-message form-message--error" key={item.id}>
              {item.message}
            </div>
          ))
        ) : (
          <p>No unresolved validation exceptions.</p>
        )}
        {draft ? (
          <>
            <div className="gst-summary-grid">
              {Object.entries(draft.sections).map(([name, rows]) => (
                <article key={name}>
                  <span>{name}</span>
                  <strong>{formatNumber(rows.length, 0)}</strong>
                  <small>records</small>
                </article>
              ))}
            </div>
            <h3>Calculated totals</h3>
            <dl className="gst-totals">
              {Object.entries(draft.totals).map(([name, value]) => (
                <div key={name}>
                  <dt>{name}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
            <small>
              Formula {draft.formula_version} · configuration{' '}
              {draft.configuration_checksum.slice(0, 12)}…
            </small>
          </>
        ) : (
          <p>Upload the report to generate the preview.</p>
        )}
      </section>
      <section className="gst-card">
        <h2>Step 5 — Human approval and download</h2>
        <p>
          Confirm that Amazon contains all outward supplies for this period, including any required
          adjustments. Obtain CA review where appropriate.
        </p>
        {filing.status === 'draft_ready' && (
          <button className="button" disabled={disabled} onClick={onApprove}>
            Confirm completeness and approve
          </button>
        )}
        {filing.status === 'approved' && (
          <button className="button" disabled={disabled} onClick={onDownload}>
            Download calculated working paper
          </button>
        )}
      </section>
      {(filing.status === 'exported' || filing.status === 'user_confirmed_filed') && (
        <section className="gst-card">
          <h2>Step 6 — Record GST Portal filing</h2>
          {filing.filed_arn ? (
            <p>
              User-confirmed filed · ARN <strong>{filing.filed_arn}</strong>
            </p>
          ) : (
            <form
              className="form-grid"
              onSubmit={(event) => {
                event.preventDefault();
                onConfirm(String(new FormData(event.currentTarget).get('arn')));
              }}
            >
              <label>
                GST Portal ARN
                <input name="arn" minLength={8} required />
              </label>
              <button className="button" disabled={disabled}>
                Confirm filed
              </button>
            </form>
          )}
        </section>
      )}
    </>
  );
}
