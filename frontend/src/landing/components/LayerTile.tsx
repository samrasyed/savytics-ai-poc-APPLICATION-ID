import { AlignLeft, CircleHelp, ListChecks, Target } from "lucide-react";
import { layerMeta } from "../content";
import type { LayerKey } from "../content";

const ICONS = { summary: AlignLeft, keyPoints: Target, actions: ListChecks, questions: CircleHelp };

// Shows a layer's Lucide icon inside its pastel square tile.
export default function LayerTile({ layer, size = 40 }: { layer: LayerKey; size?: number }) {
  const Icon = ICONS[layer];
  return (
    <span className={`sift-tile sift-tone-${layerMeta[layer].tone}`} style={{ width: size, height: size }}>
      <Icon size={size >= 40 ? 20 : 16} strokeWidth={1.5} aria-hidden="true" />
    </span>
  );
}
