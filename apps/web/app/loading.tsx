export default function Loading() {
  return (
    <main className="min-h-screen bg-canvas px-6 py-10">
      <div className="mx-auto max-w-[1160px] animate-pulse">
        <div className="h-3 w-24 rounded-full bg-line" />
        <div className="mt-4 h-7 w-56 rounded-control bg-line" />
        <div className="mt-8 grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
          <div className="h-80 rounded-card border border-line bg-surface" />
          <div className="h-80 rounded-card border border-line bg-surface" />
        </div>
      </div>
      <span className="sr-only">正在加载</span>
    </main>
  );
}
