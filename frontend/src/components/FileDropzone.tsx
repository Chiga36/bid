import { useRef, useState, type DragEvent } from "react";

interface FileDropzoneProps {
  title: string;
  description: string;
  files: File[];
  onFilesChange: (files: File[]) => void;
}

// Every dropzone is optional by design — nothing here enforces a minimum file count. The caller
// decides what "Execute" does with however many (including zero) files each zone holds.
export default function FileDropzone({ title, description, files, onFilesChange }: FileDropzoneProps) {
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

  function removeFile(index: number) {
    onFilesChange(files.filter((_, i) => i !== index));
  }

  return (
    <div className="flex flex-col rounded-lg border border-slate-200 bg-white p-4">
      <p className="text-sm font-semibold text-slate-800">{title}</p>
      <p className="mt-0.5 text-xs text-slate-500">{description}</p>

      <div
        className={`mt-3 flex flex-col items-center justify-center rounded-md border-2 border-dashed px-4 py-6 text-center transition-colors ${
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
        <p className="text-sm text-slate-500">Drag &amp; drop files here</p>
        <p className="text-xs text-slate-400">or click to browse — optional</p>
        <input
          ref={inputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => addFiles(e.target.files)}
        />
      </div>

      {files.length === 0 ? (
        <p className="mt-2 text-xs text-slate-400">No files added yet.</p>
      ) : (
        <ul className="mt-2 space-y-1">
          {files.map((file, i) => (
            <li key={`${file.name}-${i}`} className="flex items-center justify-between rounded bg-slate-50 px-2 py-1 text-xs text-slate-600">
              <span className="truncate">{file.name}</span>
              <button className="ml-2 shrink-0 text-slate-400 hover:text-rose-600" onClick={() => removeFile(i)}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
