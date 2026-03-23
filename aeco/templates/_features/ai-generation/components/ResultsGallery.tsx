"use client";

interface ResultsGalleryProps {
  imageUrls: string[];
  onGenerateMore?: () => void;
}

export function ResultsGallery({ imageUrls, onGenerateMore }: ResultsGalleryProps) {
  const handleDownload = async (url: string, index: number) => {
    try {
      const res = await fetch(url);
      const blob = await res.blob();
      const blobUrl = URL.createObjectURL(blob);

      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = `generated-${index + 1}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(blobUrl);
    } catch (err) {
      console.error("Download failed:", err);
    }
  };

  if (imageUrls.length === 0) {
    return null;
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {imageUrls.map((url, i) => (
          <div key={i} className="group relative overflow-hidden rounded-xl">
            <img
              src={url}
              alt={`Generated ${i + 1}`}
              className="aspect-square w-full object-cover transition-transform group-hover:scale-105"
            />
            <div className="absolute inset-0 flex items-end justify-center bg-gradient-to-t from-black/50 to-transparent opacity-0 transition-opacity group-hover:opacity-100">
              <button
                onClick={() => handleDownload(url, i)}
                className="mb-4 rounded-lg bg-white px-4 py-2 text-sm font-medium text-gray-900 shadow-md transition-colors hover:bg-gray-100"
              >
                Download
              </button>
            </div>
          </div>
        ))}
      </div>

      {onGenerateMore && (
        <div className="flex justify-center">
          <button
            onClick={onGenerateMore}
            className="rounded-lg border border-blue-500 px-6 py-2.5 text-sm font-semibold text-blue-500 transition-colors hover:bg-blue-50"
          >
            Generate More
          </button>
        </div>
      )}
    </div>
  );
}
