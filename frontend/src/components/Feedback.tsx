import { ApiError } from '../api/client';

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="state-panel" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <p>{label}</p>
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  const requestId = error instanceof ApiError ? error.requestId : undefined;
  return (
    <div className="state-panel state-panel--error" role="alert">
      <strong>We couldn’t load this information.</strong>
      <p>{error.message}</p>
      {requestId && <p className="support-reference">Support reference: {requestId}</p>}
      {onRetry && (
        <button className="button button--secondary" type="button" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  children,
  action,
}: {
  title: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="state-panel state-panel--empty">
      <strong>{title}</strong>
      <div>{children}</div>
      {action && <div className="state-action">{action}</div>}
    </div>
  );
}
