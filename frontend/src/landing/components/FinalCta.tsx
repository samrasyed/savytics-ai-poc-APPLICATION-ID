import { ArrowRight } from "lucide-react";
import { LOGIN_URL, finalCta } from "../content";
import Botanical from "./Botanical";

// Renders the closing blush poster with mirrored plants and the button into the app.
export default function FinalCta() {
  return (
    <section className="sift-final sift-paper" aria-labelledby="final-title">
      <Botanical seed={31} variant="cluster" flip className="sift-final__plants" />
      <div className="sift-final__content" data-reveal>
        <h2 id="final-title" className="sift-final__title sift-display">
          {finalCta.title}
        </h2>
        <p className="sift-final__sub">{finalCta.sub}</p>
        <a href={LOGIN_URL} className="sift-btn sift-btn-primary">
          {finalCta.cta}
          <ArrowRight size={16} strokeWidth={1.5} aria-hidden="true" />
        </a>
      </div>
    </section>
  );
}
