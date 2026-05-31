import { FileVideo, Play, RotateCcw, X } from "lucide-react";

import { Button } from "@/components/animate-ui/components/buttons/button";
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

import { StatusCell } from "./status-cell";
import type { UploadedVideo } from "./types";

type UploadsTableProps = {
  videos: UploadedVideo[];
  onCancelUpload: () => void;
};

export function UploadsTable({ videos, onCancelUpload }: UploadsTableProps) {
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
            {videos.map((video) => (
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
                  {video.id === "current-upload" ? (
                    <div className="flex justify-end gap-1">
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button type="button" variant="ghost" size="icon-sm">
                            <RotateCcw className="size-4" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Retry upload</TooltipContent>
                      </Tooltip>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-sm"
                            onClick={onCancelUpload}
                          >
                            <X className="size-4" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Cancel upload</TooltipContent>
                      </Tooltip>
                    </div>
                  ) : (
                    <Button type="button" variant="ghost" size="sm">
                      <Play className="size-4" />
                      Open
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
