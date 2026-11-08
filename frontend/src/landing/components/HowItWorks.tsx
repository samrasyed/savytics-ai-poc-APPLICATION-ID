import { how } from "../content";

// Renders the three numbered steps from pasting text to acting on the result.
export default function HowItWorks() {
  return (
    <section id="how" className="sift-section" aria-labelledby="how-title">
      <div className="sift-container">
        <div className="sift-section-head" data-reveal>
          <p className="sift-label">{how.eyebrow}</p>
          <h2 id="how-title" className="sift-h2 sift-display">
            {how.title}
          </h2>
        </div>
        <ol className="sift-steps">
          {how.steps.map((s, i) => (
            <li key={s.n} className="sift-step" data-reveal style={{ ["--i" as string]: i }}>
              <span className="sift-step__numeral sift-display" aria-hidden="true">
                {s.n}
              </span>
              <h3 className="sift-h3 sift-display">{s.title}</h3>
              <p className="sift-body-2">{s.text}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
