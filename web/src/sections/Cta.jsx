import { REPO, README } from './content'

export default function Cta() {
  return (
    <section className="section section--cta" id="cta">
      <div className="section__head" style={{ justifyContent: 'center' }}>
        <span className="mono section__num">[ 05 ]</span>
      </div>

      <h2 className="cta__title">Put it to work</h2>
      <p className="cta__sub">
        Support Engineer is open source — the operating instructions, the lesson
        memory service and the safety hooks are all in the repository.
      </p>

      <div className="cta__actions">
        <a className="btn btn--primary" href={REPO} target="_blank" rel="noreferrer">
          View on GitHub
        </a>
        <a className="btn btn--ghost" href={README} target="_blank" rel="noreferrer">
          Read the docs
        </a>
      </div>
    </section>
  )
}
