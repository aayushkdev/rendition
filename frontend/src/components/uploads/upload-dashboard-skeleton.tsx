import { Skeleton } from "@/components/ui/skeleton";

export function UploadDashboardSkeleton() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-5 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-4 border-b border-border pb-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-3">
            <Skeleton className="size-9" />
            <div className="grid gap-2">
              <Skeleton className="h-3 w-28" />
              <Skeleton className="h-7 w-24" />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Skeleton className="h-7 w-24" />
            <Skeleton className="size-9" />
          </div>
        </header>

        <section className="flex flex-col gap-5">
          <Skeleton className="h-[260px] w-full rounded-lg" />

          <section className="rounded-lg border border-border bg-card shadow-sm">
            <div className="flex flex-col justify-between gap-4 border-b border-border p-4 md:flex-row md:items-center">
              <div className="grid gap-2">
                <Skeleton className="h-5 w-24" />
                <Skeleton className="h-4 w-20" />
              </div>
              <Skeleton className="h-9 w-40" />
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] border-separate border-spacing-0">
                <thead>
                  <tr className="text-left text-xs font-medium uppercase text-muted-foreground">
                    <th className="border-b border-border px-4 py-3">Video</th>
                    <th className="border-b border-border px-4 py-3">Uploaded</th>
                    <th className="border-b border-border px-4 py-3">Status</th>
                    <th className="border-b border-border px-4 py-3">Size</th>
                    <th className="border-b border-border px-4 py-3 text-right">
                      Action
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {Array.from({ length: 4 }).map((_, index) => (
                    <tr key={index}>
                      <td className="border-b border-border px-4 py-4">
                        <div className="flex items-center gap-3">
                          <Skeleton className="size-10" />
                          <Skeleton className="h-4 w-44" />
                        </div>
                      </td>
                      <td className="border-b border-border px-4 py-4">
                        <Skeleton className="h-4 w-20" />
                      </td>
                      <td className="border-b border-border px-4 py-4">
                        <Skeleton className="h-8 w-44" />
                      </td>
                      <td className="border-b border-border px-4 py-4">
                        <Skeleton className="h-4 w-16" />
                      </td>
                      <td className="border-b border-border px-4 py-4">
                        <div className="flex justify-end">
                          <Skeleton className="size-8" />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </section>
      </div>
    </main>
  );
}
