import { Copy, FileVideo, MoreHorizontal, Play, RotateCcw, Trash2, X } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/animate-ui/components/buttons/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/animate-ui/components/radix/alert-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/animate-ui/components/radix/dropdown-menu";
import {
  Tabs,
  TabsContent,
  TabsContents,
  TabsList,
  TabsTrigger,
} from "@/components/animate-ui/components/radix/tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/animate-ui/components/radix/tooltip";
import { Skeleton } from "@/components/ui/skeleton";

import { StatusCell } from "./status-cell";
import type { UploadedVideo } from "./types";

type UploadsTableProps = {
  videos: UploadedVideo[];
  isLoading?: boolean;
  onCancelUpload: (videoId: string) => void;
  onRetryUpload: (videoId: string) => void;
};

export function UploadsTable({
  videos,
  isLoading = false,
  onCancelUpload,
  onRetryUpload,
}: UploadsTableProps) {
  return (
    <section className="rounded-lg border border-border bg-card shadow-sm">
      <div className="flex flex-col justify-between gap-4 border-b border-border p-4 md:flex-row md:items-center">
        <div>
          <h2 className="text-lg font-semibold">My videos</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {videos.length} uploads
          </p>
        </div>
        <Tabs defaultValue="all">
          <TabsList>
            <TabsTrigger value="all">All</TabsTrigger>
            <TabsTrigger value="active">Active</TabsTrigger>
            <TabsTrigger value="failed">Failed</TabsTrigger>
          </TabsList>
          <TabsContents className="hidden">
            <TabsContent value="all" />
            <TabsContent value="active" />
            <TabsContent value="failed" />
          </TabsContents>
        </Tabs>
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
            {isLoading ? (
              Array.from({ length: 4 }).map((_, index) => (
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
              ))
            ) : (
              videos.map((video) => (
              <tr key={video.id} className="group">
                <td className="border-b border-border px-4 py-4">
                  <div className="flex items-center gap-3">
                    <div className="grid size-10 place-items-center rounded-md bg-secondary text-secondary-foreground">
                      <FileVideo className="size-4" />
                    </div>
                    <span className="font-medium">{video.title}</span>
                  </div>
                </td>
                <td className="border-b border-border px-4 py-4 text-sm text-muted-foreground">
                  {video.uploadedAt}
                </td>
                <td className="border-b border-border px-4 py-4">
                  <StatusCell video={video} />
                </td>
                <td className="border-b border-border px-4 py-4 text-sm text-muted-foreground">
                  {video.size}
                </td>
                <td className="border-b border-border px-4 py-4 text-right">
                  {video.canCancel || video.canRetry ? (
                    <div className="flex justify-end gap-1">
                      {video.canRetry ? (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon-sm"
                              onClick={() => onRetryUpload(video.id)}
                            >
                              <RotateCcw className="size-4" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Retry upload</TooltipContent>
                        </Tooltip>
                      ) : null}
                      {video.canCancel ? (
                        <AlertDialog>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <AlertDialogTrigger asChild>
                                <Button type="button" variant="ghost" size="icon-sm">
                                  <X className="size-4" />
                                </Button>
                              </AlertDialogTrigger>
                            </TooltipTrigger>
                            <TooltipContent>Cancel upload</TooltipContent>
                          </Tooltip>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>Cancel this upload?</AlertDialogTitle>
                              <AlertDialogDescription>
                                The multipart upload will be aborted and removed from the
                                table.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Keep uploading</AlertDialogCancel>
                              <AlertDialogAction
                                onClick={() => onCancelUpload(video.id)}
                              >
                                Cancel upload
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      ) : null}
                    </div>
                  ) : (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button type="button" variant="ghost" size="icon-sm">
                          <MoreHorizontal className="size-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onSelect={() =>
                            toast.info("Opening video", {
                              description: video.title,
                            })
                          }
                        >
                          <Play className="size-4" />
                          Open
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onSelect={() =>
                            toast.success("Link copied", {
                              description: video.title,
                            })
                          }
                        >
                          <Copy className="size-4" />
                          Copy link
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          variant="destructive"
                          onSelect={() =>
                            toast.error("Delete is not wired yet", {
                              description: video.title,
                            })
                          }
                        >
                          <Trash2 className="size-4" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  )}
                </td>
              </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
