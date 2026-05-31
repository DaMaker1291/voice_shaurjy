"use client";

import { useRef, useState } from "react";

interface Props {
  onUploadComplete: (name: string, chunks: number) => void;
}

export default function FileUploader({ onUploadComplete }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    const reader = new FileReader();
    reader.onloadend = async () => {
      const b64 = (reader.result as string).split(",")[1];
      try {
        const res = await fetch("http://localhost:8000/api/documents/upload", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: "demo-user",
            file_name: file.name,
            file_type: file.type,
            content_b64: b64,
          }),
        });
        const data = await res.json();
        if (data.status === "ok") onUploadComplete(file.name, data.chunks);
      } finally {
        setUploading(false);
      }
    };
    reader.readAsDataURL(file);
  };

  return (
    <div>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.txt"
        onChange={handleFile}
        className="hidden"
      />
      <button
        onClick={() => inputRef.current?.click()}
        disabled={uploading}
        className="px-4 py-2 bg-purple-700 hover:bg-purple-600 rounded-lg text-sm disabled:opacity-50"
      >
        {uploading ? "Uploading..." : "Upload PDF or TXT"}
      </button>
    </div>
  );
}
