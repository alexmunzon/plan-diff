import Link from "next/link";

export default function NotFound() {
  return (
    <section className="space-y-3">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p>This page or plan is not in the demo. Choose a run to see the available plans.</p>
      <p className="flex flex-wrap gap-4">
        <Link className="underline" href="/">Synthetic demo</Link>
        <Link className="underline" href="/texas">Public Texas run</Link>
      </p>
    </section>
  );
}
