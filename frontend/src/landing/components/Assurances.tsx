import { FlaskConical, History, ShieldCheck } from "lucide-react";
import { assurances } from "../content";

const ICONS = { shield: ShieldCheck, history: History, flask: FlaskConical };

// Renders the three short promises about validation, history and demo mode.
export default function Assurances() {
  return (
    <section className="sift-section sift-assurances" aria-label="Assurances">
      <div className="sift-container">
        <ul className="sift-assurance-list">
          {assurances.map((a, i) => {
            const Icon = ICONS[a.icon];
            return (
              <li key={a.title} data-reveal style={{ ["--i" as string]: i }}>
                <Icon size={24} strokeWidth={1.5} aria-hidden="true" className="sift-assurance-icon" />
                <p className="sift-assurance-title">{a.title}</p>
                <p className="sift-assurance-text">{a.text}</p>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
