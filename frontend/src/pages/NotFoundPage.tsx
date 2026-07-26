import { Link } from '../app/router';
import { EmptyState } from '../components/Feedback';

export function NotFoundPage() {
  return (
    <EmptyState
      title="Page not found"
      action={
        <Link className="button" to="/dashboard">
          Return to dashboard
        </Link>
      }
    >
      <p>The address does not match a SellerOS page.</p>
    </EmptyState>
  );
}
