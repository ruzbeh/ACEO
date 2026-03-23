import React, { useCallback, useRef, useState } from "react";

interface UploadedFile {
  file: File;
  preview: string | null;
  progress: number;
  status: "pending" | "uploading" | "done" | "error";
}

const ACCEPTED_TYPES = ["image/png", "image/jpeg", "image/webp", "application/pdf"];
const MAX_SIZE_MB = 10;
const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;

export default function FileUploadZone() {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const addFiles = useCallback((incoming: FileList | File[]) => {
    const newFiles: UploadedFile[] = Array.from(incoming)
      .filter((f) => {
        if (!ACCEPTED_TYPES.includes(f.type)) return false;
        if (f.size > MAX_SIZE_BYTES) return false;
        return true;
      })
      .map((file) => ({
        file,
        preview: file.type.startsWith("image/")
          ? URL.createObjectURL(file)
          : null,
        progress: 0,
        status: "pending" as const,
      }));
    setFiles((prev) => [...prev, ...newFiles]);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
    },
    [addFiles]
  );

  const removeFile = (index: number) => {
    setFiles((prev) => {
      const updated = [...prev];
      if (updated[index].preview) URL.revokeObjectURL(updated[index].preview!);
      updated.splice(index, 1);
      return updated;
    });
  };

  const uploadAll = async () => {
    for (let i = 0; i < files.length; i++) {
      if (files[i].status !== "pending") continue;

      setFiles((prev) =>
        prev.map((f, idx) =>
          idx === i ? { ...f, status: "uploading" as const } : f
        )
      );

      // Simulate upload progress — replace with real upload logic
      for (let p = 0; p <= 100; p += 20) {
        await new Promise((r) => setTimeout(r, 150));
        setFiles((prev) =>
          prev.map((f, idx) => (idx === i ? { ...f, progress: p } : f))
        );
      }

      setFiles((prev) =>
        prev.map((f, idx) =>
          idx === i
            ? { ...f, status: "done" as const, progress: 100 }
            : f
        )
      );
    }
  };

  return (
    <div className="w-full max-w-lg mx-auto">
      {/* Drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer rounded-xl border-2 border-dashed p-10 text-center transition-colors ${
          dragging
            ? "border-indigo-500 bg-indigo-50"
            : "border-gray-300 bg-gray-50 hover:border-gray-400"
        }`}
      >
        <svg
          className="mx-auto h-10 w-10 text-gray-400"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.5}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
          />
        </svg>
        <p className="mt-3 text-sm font-medium text-gray-700">
          Drag & drop files here, or click to browse
        </p>
        <p className="mt-1 text-xs text-gray-500">
          PNG, JPG, WebP, PDF up to {MAX_SIZE_MB}MB
        </p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED_TYPES.join(",")}
          className="hidden"
          onChange={(e) => e.target.files && addFiles(e.target.files)}
        />
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div className="mt-6 space-y-3">
          {files.map((f, i) => (
            <div
              key={i}
              className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-3"
            >
              {/* Thumbnail */}
              {f.preview ? (
                <img
                  src={f.preview}
                  alt=""
                  className="h-12 w-12 rounded object-cover"
                />
              ) : (
                <div className="flex h-12 w-12 items-center justify-center rounded bg-gray-100 text-xs text-gray-500">
                  PDF
                </div>
              )}

              {/* Info + progress */}
              <div className="flex-1 min-w-0">
                <p className="truncate text-sm font-medium text-gray-800">
                  {f.file.name}
                </p>
                <p className="text-xs text-gray-500">
                  {(f.file.size / 1024 / 1024).toFixed(1)} MB
                </p>
                {f.status === "uploading" && (
                  <div className="mt-1 h-1.5 w-full rounded-full bg-gray-200 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-indigo-600 transition-all"
                      style={{ width: `${f.progress}%` }}
                    />
                  </div>
                )}
                {f.status === "done" && (
                  <span className="text-xs text-green-600 font-medium">
                    Uploaded
                  </span>
                )}
              </div>

              {/* Remove */}
              <button
                onClick={() => removeFile(i)}
                className="shrink-0 text-gray-400 hover:text-red-500"
              >
                <svg
                  className="h-5 w-5"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={2}
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>
          ))}

          <button
            onClick={uploadAll}
            className="w-full rounded-lg bg-indigo-600 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 transition-colors"
          >
            Upload {files.filter((f) => f.status === "pending").length} file(s)
          </button>
        </div>
      )}
    </div>
  );
}
