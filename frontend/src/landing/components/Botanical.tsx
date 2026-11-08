import { useMemo } from "react";
import type { CSSProperties, ReactElement } from "react";

type Props = { seed: number; variant: "cluster" | "sprig"; flip?: boolean; className?: string };
type Pt = { x: number; y: number };
type Kind = "grass" | "thistle" | "filler";
type Stem = { kind: Kind; layer: "back" | "front"; base: Pt; c1: Pt; c2: Pt; tip: Pt; sway: number; dur: number; delay: number };

const W = 600;
const H = 700;

// Returns a seeded pseudo-random generator (mulberry32) so every render draws the same plants.
function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Evaluates a point on a stem's cubic curve at position t.
function at(s: Stem, t: number): Pt {
  const u = 1 - t;
  const a = u * u * u;
  const b = 3 * u * u * t;
  const c = 3 * u * t * t;
  const d = t * t * t;
  return { x: a * s.base.x + b * s.c1.x + c * s.c2.x + d * s.tip.x, y: a * s.base.y + b * s.c1.y + c * s.c2.y + d * s.tip.y };
}

// Returns the stem's growth direction in degrees at position t.
function angleAt(s: Stem, t: number): number {
  const p = at(s, Math.max(0, t - 0.01));
  const q = at(s, Math.min(1, t + 0.01));
  return (Math.atan2(q.y - p.y, q.x - p.x) * 180) / Math.PI;
}

// Rounds a number to one decimal so the SVG markup stays compact.
function r1(n: number): string {
  return n.toFixed(1);
}

// Draws a stem as short segments whose stroke tapers from about 3px at the base to 1px at the tip.
function drawStem(s: Stem, key: string, from = 3, to = 1): ReactElement[] {
  const segments = 6;
  const out: ReactElement[] = [];
  for (let i = 0; i < segments; i++) {
    const pts: string[] = [];
    for (let j = 0; j <= 6; j++) {
      const p = at(s, (i + j / 6) / segments);
      pts.push(`${r1(p.x)} ${r1(p.y)}`);
    }
    const width = from + ((to - from) * i) / (segments - 1);
    out.push(
      <path
        key={`${key}-s${i}`}
        d={`M${pts.join(" L")}`}
        fill="none"
        stroke="currentColor"
        strokeWidth={width}
        strokeLinecap="round"
      />,
    );
  }
  return out;
}

// Builds a narrow teardrop leaflet pointing along +x with the given length.
function teardrop(len: number): string {
  const w = len * 0.3;
  return `M0 0 C${r1(len * 0.3)} ${r1(-w)} ${r1(len * 0.8)} ${r1(-w * 0.55)} ${r1(len)} 0 C${r1(len * 0.8)} ${r1(w * 0.55)} ${r1(len * 0.3)} ${r1(w)} 0 0 Z`;
}

// Draws the alternating leaflets of a grass ear along the top 35% of a stem.
function drawEar(s: Stem, rand: () => number, key: string): ReactElement[] {
  const count = 14 + Math.floor(rand() * 5);
  const out: ReactElement[] = [];
  for (let i = 0; i < count; i++) {
    const t = 0.65 + (0.35 * i) / (count - 1);
    const p = at(s, Math.min(t, 0.995));
    const side = i % 2 === 0 ? 1 : -1;
    const tilt = 22 + rand() * 6;
    const len = 16 - (10 * i) / (count - 1);
    const angle = angleAt(s, t) + side * tilt;
    out.push(
      <path key={`${key}-l${i}`} d={teardrop(len)} transform={`translate(${r1(p.x)} ${r1(p.y)}) rotate(${r1(angle)})`} fill="currentColor" />,
    );
  }
  return out;
}

// Draws a thistle head: a round body, radiating spikes over its upper 220 degrees and a cup beneath.
function drawThistle(s: Stem, rand: () => number, key: string): ReactElement {
  const r = 10 + rand() * 5;
  const spikes = 16 + Math.floor(rand() * 7);
  const cx = s.tip.x;
  const cy = s.tip.y - r * 0.9;
  const lines: ReactElement[] = [];
  for (let i = 0; i < spikes; i++) {
    const deg = -90 - 110 + (220 * i) / (spikes - 1);
    const rad = (deg * Math.PI) / 180;
    const len = 8 + rand() * 6;
    lines.push(
      <line
        key={`${key}-k${i}`}
        x1={r1(cx + Math.cos(rad) * r * 0.7)}
        y1={r1(cy + Math.sin(rad) * r * 0.7)}
        x2={r1(cx + Math.cos(rad) * (r + len))}
        y2={r1(cy + Math.sin(rad) * (r + len))}
        stroke="currentColor"
        strokeWidth={1.6}
        strokeLinecap="round"
      />,
    );
  }
  const cup = `M${r1(cx - r * 0.85)} ${r1(cy + r * 0.35)} Q${r1(cx)} ${r1(cy + r * 1.9)} ${r1(cx + r * 0.85)} ${r1(cy + r * 0.35)} Z`;
  return (
    <g key={`${key}-head`}>
      {lines}
      <circle cx={r1(cx)} cy={r1(cy)} r={r1(r)} fill="currentColor" />
      <path d={cup} fill="currentColor" />
    </g>
  );
}

// Draws a few small oval buds near the tip of a filler stem.
function drawBuds(s: Stem, rand: () => number, key: string): ReactElement[] {
  const count = 3 + Math.floor(rand() * 3);
  const out: ReactElement[] = [];
  for (let i = 0; i < count; i++) {
    const t = 0.78 + (0.22 * i) / Math.max(1, count - 1);
    const p = at(s, Math.min(t, 0.995));
    const side = i % 2 === 0 ? 1 : -1;
    const angle = angleAt(s, t) + side * 35;
    out.push(
      <ellipse
        key={`${key}-b${i}`}
        cx={0}
        cy={0}
        rx={4.2}
        ry={2.1}
        transform={`translate(${r1(p.x)} ${r1(p.y)}) rotate(${r1(angle)}) translate(4 0)`}
        fill="currentColor"
      />,
    );
  }
  return out;
}

// Plans the stems of a cluster or sprig: bases biased right, curving gently left.
function planStems(seed: number, variant: Props["variant"]): { stems: Stem[]; rand: () => number } {
  const rand = mulberry32(seed);
  const kinds: Kind[] =
    variant === "cluster"
      ? ["grass", "grass", "grass", "grass", "grass", "thistle", "thistle", "filler", "filler"]
      : ["grass", "filler", "grass"];
  for (let i = kinds.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [kinds[i], kinds[j]] = [kinds[j], kinds[i]];
  }
  const stems = kinds.map((kind, i): Stem => {
    const spread = variant === "cluster" ? 430 : 220;
    const x0 = W - 30 - spread * rand() * rand();
    const h = 0.4 + rand() * 0.55;
    const rise = H * h;
    const lean = (60 + rand() * 230) * h;
    const base = { x: x0, y: H };
    const tip = { x: x0 - lean, y: H - rise };
    return {
      kind,
      layer: i % 2 === 0 ? "back" : "front",
      base,
      c1: { x: x0 - rand() * 12, y: H - rise * 0.38 },
      c2: { x: tip.x + 20 + rand() * 30, y: tip.y + rise * 0.3 },
      tip,
      sway: 0.6 + rand() * 0.6,
      dur: 8 + rand() * 3,
      delay: -rand() * 8,
    };
  });
  return { stems, rand };
}

// Draws original pink botanical silhouettes (grass ears, thistles and buds) from a seed.
export default function Botanical({ seed, variant, flip = false, className }: Props) {
  const layers = useMemo(() => {
    const { stems, rand } = planStems(seed, variant);
    const byLayer: Record<"back" | "front", ReactElement[]> = { back: [], front: [] };
    stems.forEach((s, i) => {
      const key = `st${i}`;
      const parts: ReactElement[] = drawStem(s, key, s.kind === "filler" ? 1.6 : 3, 1);
      if (s.kind === "grass") parts.push(...drawEar(s, rand, key));
      if (s.kind === "thistle") parts.push(drawThistle(s, rand, key));
      if (s.kind === "filler") parts.push(...drawBuds(s, rand, key));
      const style = {
        transformOrigin: `${r1(s.base.x)}px ${H}px`,
        animationDuration: `${r1(s.dur)}s`,
        animationDelay: `${r1(s.delay)}s`,
        "--sway": `${s.sway.toFixed(2)}deg`,
      } as CSSProperties;
      byLayer[s.layer].push(
        <g key={key} className="sift-stem" style={style}>
          {parts}
        </g>,
      );
    });
    return byLayer;
  }, [seed, variant]);

  return (
    <svg
      className={`sift-botanical${flip ? " is-flipped" : ""}${className ? ` ${className}` : ""}`}
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="xMaxYMax meet"
      aria-hidden="true"
      focusable="false"
    >
      <g className="sift-plant-back">{layers.back}</g>
      <g className="sift-plant-front">{layers.front}</g>
    </svg>
  );
}
