import { ArrowDown, ArrowRight } from "lucide-react";
import { LOGIN_URL, hero } from "../content";

// Renders the hero: the Sift wordmark on the left, the tagline, intro and actions on the right.
export default function Hero() {
  return (
    <section className="sift-hero sift-paper" aria-labelledby="hero-title">
      <div className="sift-hero__grid">
        <p className="sift-hero__brand sift-display" aria-hidden="true">
          Sift
        </p>
        <div className="sift-hero__copy">
          <p className="sift-hero__eyebrow sift-label">
            <span className="sift-live-dot" aria-hidden="true" />
            {hero.eyebrow}
          </p>
          <h1 id="hero-title" className="sift-hero__title sift-display">
            {hero.titleLines.join("")}
            <em className="sift-em">{hero.titleItalic}</em>
          </h1>
          <p className="sift-hero__lede">{hero.lead}</p>
          <div className="sift-hero__actions">
            <a href={LOGIN_URL} className="sift-btn sift-btn-primary">
              {hero.primary}
              <ArrowRight size={16} strokeWidth={1.5} aria-hidden="true" />
            </a>
            <a href="#how" className="sift-textlink">
              {hero.secondary}
              <ArrowDown size={16} strokeWidth={1.5} aria-hidden="true" />
            </a>
          </div>
          <p className="sift-micro">{hero.micro}</p>
        </div>
      </div>
    </section>
  );
}
