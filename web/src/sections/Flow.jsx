const STEPS = [
  {
    n: '1',
    title: 'Triage',
    desc: 'Derive intent (answer vs. change) and turn it into a concrete objective with the fewest observable success criteria.',
  },
  {
    n: '2',
    title: 'Recall',
    desc: 'Search the lesson memory and judge candidates by meaning — reuse the learned procedure if one already fits.',
  },
  {
    n: '3',
    title: 'Execute',
    desc: 'Follow the lesson step by step or resolve from scratch, adapting to what each tool actually returns.',
  },
  {
    n: '4',
    title: 'Verify',
    desc: 'A read-only verifier subagent designs checks, runs them, and returns a graded verdict before success is claimed.',
  },
  {
    n: '5',
    title: 'Persist',
    desc: 'Reinforce a lesson that worked, flag one that failed, or store a new verified procedure for next time.',
  },
]

export default function Flow() {
  return (
    <section className="section section--flow" id="flow">
      <div className="section__head">
        <span className="mono section__num">[ 02 ]</span>
        <h2 className="section__title">How it thinks</h2>
      </div>

      <p className="prose flow__intro">
        A single loop runs every request — from a raw ticket to a checked,
        remembered outcome.
      </p>

      <ol className="flow__grid">
        {STEPS.map((s) => (
          <li className="step" key={s.n}>
            <span className="mono step__num">0{s.n}</span>
            <h3 className="step__title">{s.title}</h3>
            <p className="step__desc">{s.desc}</p>
          </li>
        ))}
      </ol>
    </section>
  )
}
