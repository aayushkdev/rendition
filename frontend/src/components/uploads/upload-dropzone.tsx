import type { DragEvent, RefObject } from "react";
import { FileVideo, FolderOpen, Upload } from "lucide-react";

import { cn } from "@/lib/utils";

type UploadDropzoneProps = {
  inputRef: RefObject<HTMLInputElement | null>;
  isDragging: boolean;
  onDraggingChange: (isDragging: boolean) => void;
  onFileSelected: (file: File | undefined) => void;
};

export function UploadDropzone({
  inputRef,
  isDragging,
  onDraggingChange,
  onFileSelected,
}: UploadDropzoneProps) {
  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    onDraggingChange(false);
    onFileSelected(event.dataTransfer.files[0]);
  }

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        onDraggingChange(true);
      }}
      onDragLeave={() => onDraggingChange(false)}
      onDrop={handleDrop}
      className={cn(
        "relative min-h-[260px] overflow-hidden rounded-lg border border-border bg-card p-5 shadow-sm transition-colors",
        isDragging ? "bg-emerald-50" : "hover:border-primary/60",
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept="video/mp4,video/quicktime,video/x-matroska"
        className="hidden"
        onChange={(event) => onFileSelected(event.target.files?.[0])}
      />

      <div className="grid h-full min-h-[220px] place-items-center">
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className={cn(
            "grid h-full w-full place-items-center rounded-lg border-2 border-dashed p-8 text-center outline-none transition-colors",
            "border-border bg-background/60 hover:border-primary hover:bg-accent/45",
            "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]",
            isDragging && "border-primary bg-emerald-50",
          )}
        >
          <div className="flex max-w-md flex-col items-center">
            <div className="relative grid size-16 place-items-center rounded-lg border border-border bg-card shadow-sm">
              <FileVideo className="size-7 text-foreground" />
              <div className="absolute -bottom-2 -right-2 grid size-8 place-items-center rounded-md bg-primary text-primary-foreground shadow-sm">
                <Upload className="size-4" />
              </div>
            </div>
            <p className="mt-7 text-2xl font-semibold md:text-3xl">
              Drop video to upload
            </p>
            <p className="mt-3 text-sm text-muted-foreground">
              MP4, MOV, or MKV
            </p>
            <span className="mt-5 inline-flex h-9 items-center gap-2 rounded-md border border-border bg-card px-3 text-sm font-medium text-foreground shadow-sm">
              <FolderOpen className="size-4" />
              Choose file
            </span>
          </div>
        </button>
      </div>
    </div>
  );
}
