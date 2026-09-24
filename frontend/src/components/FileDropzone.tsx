import { useRef, useState, type DragEvent } from "react";

interface FileDropzoneProps {
  index: number;
  title: string;
  description: string;
  files: File[];
  onFilesChange: (files: File[]) => void;
  required?: boolean;
}

function formatFileSize(bytes: number): string {
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function fileExtension(name: string): string {
  const parts = name.split(".");
  return parts.length > 1 ? parts[parts.length - 1].toUpperCase() : "FILE";
}

function CloudUploadIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M7 18a4.5 4.5 0 01-.5-8.97A5.5 5.5 0 0117 8.5a4 4 0 01-.5 7.98" />
      <path d="M12 12v7" />
      <path d="M9 15l3-3 3 3" />
    </svg>
  );
}

function FileIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M6 3.5h8l4 4v13a1 1 0 01-1 1H6a1 1 0 01-1-1v-16a1 1 0 011-1z" />
      <path d="M14 3.5v4h4" />
    </svg>
  );
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M4 6.5h16" />
      <path d="M8.5 6.5V5a1.5 1.5 0 011.5-1.5h4A1.5 1.5 0 0115.5 5v1.5" />
      <path d="M6.5 6.5l1 13.5a1.5 1.5 0 001.5 1.5h6a1.5 1.5 0 001.5-1.5l1-13.5" />
    </svg>
  );
}

// Most dropzones are optional by design — nothing here enforces a minimum file count on them. A
// `required` zone (see DataIngestion.tsx's MANDATORY_CATEGORY_KEYS) is still just a dropzone —
// the caller enforces the actual gating (disabling "Continue") — this component only communicates
// which ones matter via the red asterisk and hint text below.
export default function FileDropzone({ index, title, description, files, onFilesChange, required = false }: FileDropzoneProps) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function addFiles(newFiles: FileList | null) {
    if (!newFiles || newFiles.length === 0) return;
    onFilesChange([...files, ...Array.from(newFiles)]);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    addFiles(e.dataTransfer.files);
  }

  function removeFile(i: number) {
    onFilesChange(files.filter((_, idx) => idx !== i));
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-start gap-3">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-500 text-sm font-semibold text-white">
          {index}
        </span>
        <div>
          <p className="text-sm font-semibold text-slate-800">
            {title}
            {required && <span className="ml-0.5 text-rose-600">*</span>}
          </p>
          <p className="mt-0.5 text-xs text-slate-500">{description}</p>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div
          className={`flex flex-col items-center justify-center rounded-md border-2 border-dashed px-4 py-6 text-center transition-colors ${
            dragOver ? "border-brand-500 bg-brand-50" : "border-slate-300"
          }`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          role="button"
          tabIndex={0}
        >
          <CloudUploadIcon className="h-7 w-7 text-brand-500" />
          <p className="mt-2 text-sm text-slate-600">Drag &amp; drop your file here</p>
          <p className="text-xs font-medium text-brand-600">or click to browse</p>
          <p className="mt-1 text-[11px] text-slate-400">
            Supported formats: PDF, DOC, DOCX, XLSX (Max 10MB){required ? "" : " — optional"}
          </p>
          <input ref={inputRef} type="file" multiple className="hidden" onChange={(e) => addFiles(e.target.files)} />
        </div>

        <div className="flex flex-col gap-2">
          {files.length === 0 ? (
            <div className="flex h-full min-h-[7rem] items-center justify-center rounded-md bg-slate-50 text-xs text-slate-400">
              No files added yet.
            </div>
          ) : (
            files.map((file, i) => (
              <div key={`${file.name}-${i}`} className="flex items-center gap-2 rounded-md bg-slate-50 px-3 py-2">
                <FileIcon className="h-5 w-5 shrink-0 text-brand-500" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-medium text-slate-700">{file.name}</p>
                  <p className="text-[11px] text-slate-400">
                    {formatFileSize(file.size)} • {fileExtension(file.name)}
                  </p>
                </div>
                <button
                  onClick={() => removeFile(i)}
                  className="flex shrink-0 items-center gap-1 text-xs font-medium text-rose-500 hover:text-rose-600"
                >
                  <TrashIcon className="h-4 w-4" />
                  Delete
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
