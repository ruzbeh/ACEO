"use client";

import { useState, useRef } from "react";

interface AIGenerationFormProps {
  onGenerated?: (imageUrls: string[]) => void;
}

const STYLE_OPTIONS = [
  { value: "default", label: "Default" },
  { value: "professional", label: "Professional" },
  { value: "artistic", label: "Artistic" },
  { value: "cinematic", label: "Cinematic" },
  { value: "vintage", label: "Vintage" },
  { value: "minimalist", label: "Minimalist" },
];

export function AIGenerationForm({ onGenerated }: AIGenerationFormProps) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [style, setStyle] = useState("default");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (!selected) return;

    setFile(selected);
    setError(null);

    const reader = new FileReader();
    reader.onload = (ev) => setPreview(ev.target?.result as string);
    reader.readAsDataURL(selected);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Please upload a source image");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("image", file);
      formData.append("style", style);

      const res = await fetch("/api/generate", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Generation failed");
      }

      const data = await res.json();
      onGenerated?.(data.imageUrls);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="mx-auto max-w-lg space-y-6">
      {/* File input */}
      <div>
        <label className="mb-2 block text-sm font-medium text-gray-700">
          Source Image
        </label>
        <div
          onClick={() => inputRef.current?.click()}
          className="flex cursor-pointer flex-col items-center rounded-xl border-2 border-dashed border-gray-300 p-6 transition-colors hover:border-gray-400"
        >
          {preview ? (
            <img
              src={preview}
              alt="Source"
              className="max-h-48 rounded-lg object-contain"
            />
          ) : (
            <p className="text-sm text-gray-500">Click to select an image</p>
          )}
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            onChange={handleFileChange}
            className="hidden"
          />
        </div>
      </div>

      {/* Style selector */}
      <div>
        <label
          htmlFor="style-select"
          className="mb-2 block text-sm font-medium text-gray-700"
        >
          Style
        </label>
        <select
          id="style-select"
          value={style}
          onChange={(e) => setStyle(e.target.value)}
          className="w-full rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-sm text-gray-700 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          {STYLE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Error */}
      {error && <p className="text-sm text-red-500">{error}</p>}

      {/* Submit */}
      <button
        type="submit"
        disabled={loading || !file}
        className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-500 px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-blue-600 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? (
          <>
            <svg
              className="h-4 w-4 animate-spin"
              viewBox="0 0 24 24"
              fill="none"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
            Generating...
          </>
        ) : (
          "Generate"
        )}
      </button>
    </form>
  );
}
