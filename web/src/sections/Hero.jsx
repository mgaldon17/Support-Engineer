import { REPO, README } from './content'

export default function Hero() {
  return (
    <section className="section section--hero" id="hero">
      <div className="hero__content">
        <span className="mono eyebrow">◆ SUPPORT ENGINEER · AUTONOMOUS AGENT · CLAUDE CODE</span>

        <h1 className="hero__title">
          The support engineer that <span className="accent">learns</span> from
          every ticket
        </h1>

        <p className="hero__subtitle">
          An enterprise-support automation agent running on Claude Code. It
          triages intent, recalls what it has already learned, executes with
          browser and shell tools, verifies the outcome — and remembers the
          lesson for next time.
        </p>

        <div className="hero__actions">
          <a className="btn btn--primary" href={REPO} target="_blank" rel="noreferrer">
            View on GitHub
          </a>
          <a className="btn btn--ghost" href={README} target="_blank" rel="noreferrer">
            Read the docs
          </a>
        </div>
      </div>

      <span className="mono hero__scroll-hint">scroll to explore ↓</span>
    </section>
  )
}
