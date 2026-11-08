import { useCallback, useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { RotateCcw, Sparkles } from "lucide-react";
import { layerMeta, specimen } from "../content";
import { prefersReducedMotion } from "../motion";
import LayerTile from "./LayerTile";

type Phase = "raw" | "sifting" | "done";

const STAGGER = 120;
const LIFT = 600;

// Picks the starting state: finished straight away when motion is reduced.
function initialPhase(): Phase {
  return prefersReducedMotion() ? "done" : "raw";
}

// Renders the framed, taped specimen card that demonstrates a messy note being sifted into four layers.
export default function Specimen() {
  const [phase, setPhase] = useState<Phase>(initialPhase);
  const rootRef = useRef<HTMLDivElement>(null);
  const timers = useRef<number[]>([]);

  const clearTimers = useCallback(() => {
    timers.current.forEach((t) => window.clearTimeout(t));
    timers.current = [];
  }, []);

  const play = useCallback(() => {
    clearTimers();
    if (prefersReducedMotion()) {
      setPhase("done");
      return;
    }
    setPhase("sifting");
    timers.current.push(window.setTimeout(() => setPhase("done"), LIFT));
  }, [clearTimers]);

  const replay = useCallback(() => {
    clearTimers();
    setPhase("raw");
    if (prefersReducedMotion()) return;
    timers.current.push(window.setTimeout(play, 450));
  }, [clearTimers, play]);

  useEffect(() => {
    const el = rootRef.current;
    if (!el || prefersReducedMotion() || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        observer.disconnect();
        timers.current.push(window.setTimeout(play, 1400));
      },
      { threshold: 0.5 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [play]);

  useEffect(() => clearTimers, [clearTimers]);

  let fragIndex = 0;

  return (
    <div className="sift-specimen" ref={rootRef}>
      <div className="sift-specimen-frame">
        <span className="sift-tape" aria-hidden="true" />
        <div className="sift-specimen-inner" data-state={phase}>
          <p className="sift-label">{specimen.label}</p>
          <p className="sift-specimen-title sift-display">{specimen.title}</p>
          <div className="sift-specimen-stage">
            <div className="sift-specimen-raw" aria-hidden={phase === "done"}>
              {specimen.raw.map((line, i) => (
                <p key={i}>
                  {line.map((part, j) => {
                    if (typeof part === "string") {
                      return (
                        <span key={j} className="sift-raw-rest">
                          {part}
                        </span>
                      );
                    }
                    const style = { "--d": `${fragIndex++ * STAGGER}ms` } as CSSProperties;
                    return (
                      <span key={j} className={`sift-frag sift-mark-${layerMeta[part.layer].tone}`} style={style}>
                        {part.text}
                      </span>
                    );
                  })}
                </p>
              ))}
            </div>
            <ul className="sift-specimen-rows" aria-live="polite">
              {specimen.rows.map((row, i) => (
                <li
                  key={row.layer}
                  className="sift-specimen-row"
                  style={{ "--d": `${i * STAGGER}ms` } as CSSProperties}
                  aria-hidden={phase !== "done"}
                >
                  <LayerTile layer={row.layer} size={28} />
                  <span className="sift-specimen-row-text">
                    <span className="sift-row-label">{layerMeta[row.layer].title}</span>
                    <span>{row.text}</span>
                  </span>
                </li>
              ))}
              <li className="sift-sr-only">{phase === "done" ? specimen.announce : ""}</li>
            </ul>
          </div>
        </div>
        <p className="sift-glass-chip">
          <span className="sift-live-dot" aria-hidden="true" />
          {specimen.chip}
        </p>
      </div>
      <div className="sift-specimen-action">
        {phase === "done" ? (
          <button type="button" className="sift-btn sift-btn-primary sift-btn-sm" onClick={replay}>
            <RotateCcw size={16} strokeWidth={1.5} aria-hidden="true" />
            {specimen.replay}
          </button>
        ) : (
          <button
            type="button"
            className="sift-btn sift-btn-primary sift-btn-sm"
            onClick={play}
            disabled={phase === "sifting"}
          >
            <Sparkles size={16} strokeWidth={1.5} aria-hidden="true" />
            {specimen.run}
          </button>
        )}
      </div>
    </div>
  );
}
