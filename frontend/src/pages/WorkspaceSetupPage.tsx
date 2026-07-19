import { useState, type FormEvent } from 'react';

import { createWorkspace } from '../api/client';
import type { Workspace, WorkspaceCreateRequest } from '../api/contracts';
import { useNavigate } from '../app/router';
import { useWorkspace } from '../app/workspace';
import { PageHeader } from '../components/PageHeader';

const defaults: WorkspaceCreateRequest = {
  organisation_name: '',
  marketplace_code: 'IN',
  marketplace_name: 'Amazon India',
  currency_code: 'INR',
};

export function WorkspaceSetupPage({
  onCreated,
  firstUse = false,
}: {
  onCreated?: (workspace: Workspace) => void;
  firstUse?: boolean;
}) {
  if (onCreated) return <WorkspaceSetupForm onCreated={onCreated} firstUse={firstUse} />;
  return <ConnectedWorkspaceSetup firstUse={firstUse} />;
}

function ConnectedWorkspaceSetup({ firstUse }: { firstUse: boolean }) {
  const context = useWorkspace();
  return <WorkspaceSetupForm onCreated={context.addWorkspace} firstUse={firstUse} />;
}

function WorkspaceSetupForm({
  onCreated,
  firstUse,
}: {
  onCreated: (workspace: Workspace) => void;
  firstUse: boolean;
}) {
  const navigate = useNavigate();
  const [values, setValues] = useState(defaults);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const workspace = await createWorkspace({
        ...values,
        organisation_name: values.organisation_name.trim(),
        marketplace_code: values.marketplace_code.trim().toUpperCase(),
        marketplace_name: values.marketplace_name.trim(),
        currency_code: values.currency_code.trim().toUpperCase(),
      });
      onCreated(workspace);
      navigate('/dashboard', { replace: true });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to create workspace');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="setup-card" aria-labelledby="workspace-title">
      <PageHeader
        eyebrow={firstUse ? 'Welcome to SellerOS' : 'Workspace settings'}
        title="Create a seller workspace"
        description="A workspace keeps every product, import and recommendation isolated by organisation and marketplace."
      />
      <form className="form-grid" onSubmit={submit}>
        <label className="field field--wide">
          <span>Organisation name</span>
          <input
            required
            maxLength={255}
            autoComplete="organization"
            value={values.organisation_name}
            onChange={(event) =>
              setValues((current) => ({ ...current, organisation_name: event.target.value }))
            }
          />
        </label>
        <label className="field">
          <span>Marketplace code</span>
          <input
            required
            minLength={2}
            maxLength={32}
            pattern="[A-Za-z0-9_-]+"
            value={values.marketplace_code}
            onChange={(event) =>
              setValues((current) => ({ ...current, marketplace_code: event.target.value }))
            }
          />
        </label>
        <label className="field">
          <span>Marketplace name</span>
          <input
            required
            maxLength={255}
            value={values.marketplace_name}
            onChange={(event) =>
              setValues((current) => ({ ...current, marketplace_name: event.target.value }))
            }
          />
        </label>
        <label className="field">
          <span>Currency code</span>
          <input
            required
            minLength={3}
            maxLength={3}
            pattern="[A-Za-z]{3}"
            value={values.currency_code}
            onChange={(event) =>
              setValues((current) => ({ ...current, currency_code: event.target.value }))
            }
          />
          <small>Three-letter ISO code, for example INR or USD.</small>
        </label>
        {error && (
          <div className="form-message form-message--error field--wide" role="alert">
            {error}
          </div>
        )}
        <div className="form-actions field--wide">
          <button className="button" type="submit" disabled={submitting}>
            {submitting ? 'Creating workspace…' : 'Create workspace'}
          </button>
        </div>
      </form>
    </section>
  );
}
