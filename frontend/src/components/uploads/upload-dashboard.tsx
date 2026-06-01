"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { Activity, ArrowLeft } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/animate-ui/components/buttons/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/animate-ui/components/radix/tooltip";

import { uploadedVideos } from "./data";
import { StatusBadge } from "./status-badge";
import type { UploadedVideo } from "./types";
import { UploadDropzone } from "./upload-dropzone";
import { UploadsTable } from "./uploads-table";
import { formatBytes } from "./utils";

export function UploadDashboard() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const progress = selectedFile ? 28 : 0;
  const tableVideos: UploadedVideo[] = selectedFile
    ? [
        {
          id: "current-upload",
          title: selectedFile.name,
          uploadedAt: "Now",
          status: "uploading",
          size: formatBytes(selectedFile.size),
          progress,
        },
        ...uploadedVideos,
      ]
    : uploadedVideos;

  function handleFile(file: File | undefined) {
    if (!file) return;
    setSelectedFile(file);
    toast.success("Upload started", {
      description: file.name,
    });
  }

  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-5 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-4 border-b border-border pb-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-3">
            <Button type="button" variant="outline" size="icon" asChild>
              <Link href="/">
                <ArrowLeft className="size-4" />
              </Link>
            </Button>
            <div>
              <p className="text-sm font-medium text-muted-foreground">
                Rendition library
              </p>
              <h1 className="mt-1 text-2xl font-semibold md:text-3xl">
                Uploads
              </h1>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge status="processing" />
            <Tooltip>
              <TooltipTrigger className="inline-flex size-9 items-center justify-center rounded-md border border-border bg-card text-muted-foreground">
                <Activity className="size-4" />
              </TooltipTrigger>
              <TooltipContent>Encoder status</TooltipContent>
            </Tooltip>
          </div>
        </header>

        <section className="flex flex-col gap-5">
          <UploadDropzone
            inputRef={inputRef}
            isDragging={isDragging}
            onDraggingChange={setIsDragging}
            onFileSelected={handleFile}
          />
          <UploadsTable
            videos={tableVideos}
            onCancelUpload={() => setSelectedFile(null)}
          />
        </section>
      </div>
    </main>
  );
}
