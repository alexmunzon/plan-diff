import Link from "next/link";

export default function NotFound() {
  return (
    <section className="panel recovery-panel space-y-4">
      <h1 className="page-title">Page not found</h1>
      <p>This page or plan is not in the demo. Choose a run to see the available plans.</p>
      <p className="flex flex-wrap gap-4">
        <Link className="action-link" href="/">Synthetic demo</Link>
        <Link className="action-link" href="/texas">Public Texas run</Link>
      </p>
    </section>
  );
}
