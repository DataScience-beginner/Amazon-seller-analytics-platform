import { Link } from '../app/router';
import { PageHeader } from '../components/PageHeader';

export function PlanningPage() {
  return (
    <>
      <PageHeader
        eyebrow="Roadmap"
        title="Planning"
        description="Cash-constrained buying, reorder and lifecycle scenarios will build on trusted Phase 1 evidence."
      />
      <section className="panel planning-placeholder">
        <span className="feature-label">Planned for a later phase</span>
        <h2>Reliable evidence comes first</h2>
        <p>
          SellerOS will not suggest quantities or financial commitments until seller costs, lead
          times and inventory are available. Phase 1 establishes the product history and explainable
          recommendations those plans need.
        </p>
        <Link className="button" to="/products">
          Review product evidence
        </Link>
      </section>
    </>
  );
}
