import { footer } from "../content";
import LogoMark from "./LogoMark";

// Renders the single quiet footer row with the mark, links and the sign-off.
export default function Footer() {
  return (
    <footer className="sift-footer">
      <div className="sift-container sift-footer-inner">
        <p className="sift-footer-brand">
          <LogoMark size={18} />
          <span className="sift-footer-name">Sift</span>
          <span>{footer.copyright}</span>
        </p>
        <nav aria-label="Footer">
          {footer.links.map((l) => (
            <a key={l.href} href={l.href}>
              {l.label}
            </a>
          ))}
        </nav>
        <p className="sift-footer-sign">
          {footer.signOff} <span aria-hidden="true">🌿</span>
        </p>
      </div>
    </footer>
  );
}
