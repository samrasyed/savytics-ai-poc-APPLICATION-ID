import { useEffect, useRef, useState } from "react";
import "./landing.css";
import Assurances from "./components/Assurances";
import FinalCta from "./components/FinalCta";
import Footer from "./components/Footer";
import Hero from "./components/Hero";
import HowItWorks from "./components/HowItWorks";
import Layers from "./components/Layers";
import Nav from "./components/Nav";
import { fontWarning } from "./content";
import { hasDisplayItalic, verifyDisplayFont } from "./fontGuard";
import { useReveal } from "./motion";

// Assembles the static Sift landing page, checks the display font and shows a dev-only warning if it failed.
export default function LandingPage() {
  const root = useRef<HTMLDivElement>(null);
  const [fontOk, setFontOk] = useState(true);
  const [italic, setItalic] = useState(false);
  useReveal(root);

  useEffect(() => {
    let alive = true;
    verifyDisplayFont().then((ok) => {
      if (!alive) return;
      setFontOk(ok);
      setItalic(hasDisplayItalic());
    });
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="sift-landing" ref={root} data-italic={italic ? "real" : "fallback"}>
      <a href="#main" className="sift-skip">
        Skip to content
      </a>
      <Nav />
      <main id="main" tabIndex={-1}>
        <Hero />
        <Layers />
        <HowItWorks />
        <Assurances />
        <FinalCta />
      </main>
      <Footer />
      {!fontOk && import.meta.env.DEV && (
        <p className="sift-font-warning" role="status">
          {fontWarning}
        </p>
      )}
    </div>
  );
}
