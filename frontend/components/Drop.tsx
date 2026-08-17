"use client";
import { useId, useState } from "react";

/** File drop zone with click-to-browse.
 *
 * Extracted because three views each had their own copy and they had already drifted:
 * one handled dragleave, one did not, so a zone could stay stuck in its hover state
 * after a cancelled drag. One implementation means one behaviour. */
export function Drop({ label, accept = ".tif,.tiff,.png,.jpg,.jpeg", file, onFile, disabled }: {
  label: string;
  accept?: string;
  file?: File | null;
  onFile: (f: File) => void;
  disabled?: boolean;
}) {
  const id = useId();
  const [over, setOver] = useState(false);

  return (
    <>
      <div
        className={`drop ${over ? "over" : ""} ${disabled ? "dis" : ""}`}
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-label={label}
        onClick={() => !disabled && document.getElementById(id)?.click()}
        onKeyDown={(e) => {
          if (!disabled && (e.key === "Enter" || e.key === " ")) {
            e.preventDefault();
            document.getElementById(id)?.click();
          }
        }}
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          if (disabled) return;
          const f = e.dataTransfer.files[0];
          if (f) onFile(f);
        }}
      >
        {file ? file.name : label}
      </div>
      <input id={id} type="file" accept={accept} hidden disabled={disabled}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
          e.target.value = "";        // re-picking the same file must still fire
        }} />
    </>
  );
}
