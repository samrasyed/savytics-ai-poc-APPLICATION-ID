import { useEffect, useState } from "react";
import { ArrowRight } from "lucide-react";
import { LOGIN_URL, nav } from "../content";
import LogoMark from "./LogoMark";

// Renders the navigation, transparent at the top and liquid glass with a spectrum hairline once scrolled.
export default function Nav() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className={`sift-nav${scrolled ? " is-scrolled" : ""}`}>
      <div className="sift-container sift-nav-inner">
        <a href="/" className="sift-brand" aria-label="Sift home">
          <LogoMark size={28} />
          <span className="sift-wordmark sift-display">Sift</span>
        </a>
        <nav className="sift-nav-links" aria-label="Sections">
          {nav.links.map((l) => (
            <a key={l.href} href={l.href}>
              {l.label}
            </a>
          ))}
        </nav>
        <div className="sift-nav-actions">
          <a href={LOGIN_URL} className="sift-nav-login">
            {nav.login}
          </a>
          <a href={LOGIN_URL} className="sift-btn sift-btn-primary sift-btn-sm">
            {nav.cta}
            <ArrowRight size={16} strokeWidth={1.5} aria-hidden="true" />
          </a>
        </div>
      </div>
    </header>
  );
}
