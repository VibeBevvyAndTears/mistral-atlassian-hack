"use client";

import { Info } from "@phosphor-icons/react";
import { useEffect, useId, useRef, useState } from "react";

export const AI_PRIORITY_FACTORS =
  "Deadline proximity · overlap with your responsibilities · attached conflict · unanswered questions";

export function AiPriorityInfoButton() {
  const tipId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className="relative inline-flex" ref={rootRef}>
      <button
        type="button"
        className="inline-flex size-7 items-center justify-center rounded-full border border-border text-ask hover:bg-ask/10 hover:text-ask"
        aria-label="Why this priority order"
        aria-expanded={open}
        aria-controls={tipId}
        title="Why this order"
        onClick={() => setOpen((v) => !v)}
      >
        <Info className="size-3.5" weight="bold" />
        <span className="sr-only">AI priority factors</span>
      </button>
      {open ? (
        <div
          id={tipId}
          role="tooltip"
          className="absolute top-[calc(100%+6px)] left-1/2 z-20 w-56 -translate-x-1/2 rounded-xl border border-border bg-popover p-2.5 text-xs shadow-[0_8px_24px_rgba(0,0,0,0.45)]"
        >
          <p className="mb-1 text-[10px] font-medium tracking-wide text-muted-foreground uppercase">
            AI priority
          </p>
          <p className="leading-relaxed text-foreground">{AI_PRIORITY_FACTORS}</p>
        </div>
      ) : null}
    </div>
  );
}
