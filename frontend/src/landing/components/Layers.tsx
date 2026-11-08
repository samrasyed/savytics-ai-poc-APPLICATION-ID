import { layerMeta, layers } from "../content";
import LayerTile from "./LayerTile";
import Specimen from "./Specimen";

// Renders the layers as an editorial list beside a sticky heading column with a worked example.
export default function Layers() {
  return (
    <section id="layers" className="sift-section" aria-labelledby="layers-title">
      <div className="sift-container sift-layers">
        <div className="sift-layers__intro" data-reveal>
          <p className="sift-label">{layers.eyebrow}</p>
          <h2 id="layers-title" className="sift-h2 sift-display">
            {layers.titleLead}
            <em className="sift-em">{layers.titleItalic}</em>
            {layers.titleEnd}
          </h2>
          <p className="sift-body-2">{layers.sub}</p>
          <div className="sift-layers__specimen">
            <Specimen />
          </div>
        </div>
        <ol className="sift-layers__list">
          {layers.rows.map((row, i) => (
            <li
              key={row.key}
              className={`sift-layer-row sift-tone-${layerMeta[row.key].tone}`}
              tabIndex={0}
              data-reveal
              style={{ ["--i" as string]: i }}
            >
              <span className="sift-numeral sift-display" aria-hidden="true">
                {row.n}
              </span>
              <span className="sift-layer-row__tile">
                <LayerTile layer={row.key} />
              </span>
              <div className="sift-layer-row__body">
                <h3 className="sift-h3 sift-display">{layerMeta[row.key].title}</h3>
                <p className="sift-body-2">{row.body}</p>
                <span className={`sift-chip sift-tone-${layerMeta[row.key].tone}`}>{row.chip}</span>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
