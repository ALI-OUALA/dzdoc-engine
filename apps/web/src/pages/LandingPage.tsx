import { ArrowRight, FileText, GithubLogo, ShieldCheck } from "@phosphor-icons/react";
import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

gsap.registerPlugin(ScrollTrigger);

const stages = [
  {
    title: "Trust what is already good.",
    body: "DzDoc inspects native PDF text first and keeps reliable content intact.",
    detail: "Native PDF inspection",
  },
  {
    title: "Read only what needs OCR.",
    body: "Uncertain regions are detected once, routed by script, and fused with numeric checks.",
    detail: "Arabic, French, digits",
  },
  {
    title: "Review the evidence.",
    body: "Every value keeps coordinates, confidence, alternatives, validation, and correction provenance.",
    detail: "Traceable human review",
  },
];

function ScrollStory() {
  const sectionRef = useRef<HTMLElement>(null);
  const stageRefs = useRef<Array<HTMLElement | null>>([]);
  const markerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || !sectionRef.current) return;
    const context = gsap.context(() => {
      const media = gsap.matchMedia();
      media.add("(min-width: 768px)", () => {
        gsap.set(stageRefs.current.slice(1), { autoAlpha: 0, y: 28 });
        const timeline = gsap.timeline({
          scrollTrigger: {
            trigger: sectionRef.current,
            start: "top top",
            end: "+=240%",
            pin: true,
            scrub: 0.7,
          },
        });
        stageRefs.current.forEach((stage, index) => {
          if (!stage) return;
          if (index > 0) timeline.to(stageRefs.current[index - 1], { autoAlpha: 0, y: -24, duration: 0.35 });
          timeline.to(stage, { autoAlpha: 1, y: 0, duration: 0.35 }, index === 0 ? 0 : ">");
          timeline.to(markerRef.current, { xPercent: index * 100, duration: 0.35 }, "<");
        });
      });
      return () => media.revert();
    }, sectionRef);
    return () => context.revert();
  }, []);

  return (
    <section ref={sectionRef} id="how-it-works" className="story-section">
      <div className="story-copy">
        <p className="section-kicker">One document. Three decisions.</p>
        <div className="story-stage-wrap">
          {stages.map((stage, index) => (
            <article
              key={stage.title}
              ref={(element) => { stageRefs.current[index] = element; }}
              className="story-stage"
            >
              <span>{stage.detail}</span>
              <h2>{stage.title}</h2>
              <p>{stage.body}</p>
            </article>
          ))}
        </div>
        <div className="story-track" aria-hidden="true"><div ref={markerRef} /></div>
      </div>
      <div className="document-world" aria-label="Document processing illustration">
        <div className="world-page">
          <div className="world-heading"><b>FACTURE</b><span>فاتورة</span></div>
          <i /><i /><i /><i />
          <div className="world-table"><span /><span /><span /><span /><span /><span /></div>
          <div className="world-box world-box-ar" />
          <div className="world-box world-box-total" />
        </div>
      </div>
    </section>
  );
}

export function LandingPage() {
  return (
    <div className="landing-page">
      <header className="landing-nav">
        <Link to="/" className="wordmark" aria-label="DzDoc home"><span>د</span>DzDoc</Link>
        <nav aria-label="Landing navigation">
          <a href="#how-it-works">Pipeline</a>
          <a href="#deployment">Deployment</a>
          <a href="https://github.com/ALI-OUALA/dzdoc-engine">GitHub</a>
        </nav>
        <Button asChild size="sm"><Link to="/app">Open workspace<ArrowRight data-icon="inline-end" /></Link></Button>
      </header>

      <main>
        <section className="hero-section">
          <div className="hero-copy">
            <p className="section-kicker">Arabic-French document intelligence</p>
            <h1>Documents mixtes.<br />Données fiables.</h1>
            <p>Turn Algerian PDFs and scans into structured, traceable data.</p>
            <div className="hero-actions">
              <Button asChild size="lg"><Link to="/app">Process a document<ArrowRight data-icon="inline-end" /></Link></Button>
              <Button asChild variant="outline" size="lg"><a href="https://github.com/ALI-OUALA/dzdoc-engine"><GithubLogo data-icon="inline-start" />View source</a></Button>
            </div>
          </div>
          <figure className="hero-visual">
            <img src="/media/dzdoc-workspace-concept.png" alt="DzDoc bilingual invoice review workspace" width="1600" height="1000" />
          </figure>
        </section>

        <Separator />
        <ScrollStory />
        <Separator />

        <section className="proof-section">
          <div>
            <h2>Evidence stays attached.</h2>
            <p>Raw output is preserved. Corrections never erase the source. Low confidence remains visible.</p>
          </div>
          <dl>
            <div><dt><FileText weight="regular" />Canonical output</dt><dd>Versioned JSON, text, Markdown, and benchmark predictions.</dd></div>
            <div><dt><ShieldCheck weight="regular" />Private by default</dt><dd>Local, offline, hosted, and on-premise profiles share one engine.</dd></div>
          </dl>
        </section>

        <section id="deployment" className="deployment-section">
          <div>
            <h2>Start on one server.</h2>
            <p>Run the web app, API, worker, PostgreSQL, and local object storage with Docker Compose.</p>
          </div>
          <pre><code>docker compose up --build</code></pre>
          <Button asChild variant="outline"><a href="https://github.com/ALI-OUALA/dzdoc-engine#deployment">Deployment guide<ArrowRight data-icon="inline-end" /></a></Button>
        </section>
      </main>

      <footer className="landing-footer">
        <span>DzDoc Engine</span>
        <span>Independent project by MERATI Ali Ouala Eddine</span>
      </footer>
    </div>
  );
}
