import { Skeleton } from "@/components/ui/skeleton";

export function VideoGridSkeleton() {
  return (
    <section className="grid gap-x-5 gap-y-8 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {Array.from({ length: 8 }).map((_, index) => (
        <article key={index}>
          <Skeleton className="aspect-video w-full" />
          <div className="mt-3 flex items-start gap-3">
            <Skeleton className="size-9 shrink-0" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-4/5" />
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-3 w-24" />
            </div>
          </div>
        </article>
      ))}
    </section>
  );
}

export function VideoFeedSkeleton() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-7 px-4 py-5 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-4 border-b border-border pb-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-3">
            <Skeleton className="size-10" />
            <div className="grid gap-2">
              <Skeleton className="h-4 w-28" />
              <Skeleton className="h-3 w-20" />
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Skeleton className="h-10 w-64" />
            <Skeleton className="size-10" />
            <Skeleton className="size-10" />
            <Skeleton className="h-10 w-24" />
          </div>
        </header>

        <VideoGridSkeleton />
      </div>
    </main>
  );
}
