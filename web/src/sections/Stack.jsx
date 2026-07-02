const TOOLS = [
  {
    sym: 'mem',
    tag: 'MCP · Qdrant',
    name: 'Lesson memory',
    desc: 'Vector store of learned procedures. Add, search, reinforce and retire lessons — the agent’s long-term memory.',
  },
  {
    sym: 'pw',
    tag: 'Browser',
    name: 'Playwright',
    desc: 'Navigate, read and act on real pages. Search first, then open links actually seen — never guessed URLs.',
  },
  {
    sym: 'dc',
    tag: 'Local',
    name: 'Desktop Commander',
    desc: 'Terminal and filesystem access for local inspection, processes and file operations.',
  },
  {
    sym: 'vfy',
    tag: 'Subagent',
    name: 'Verifier',
    desc: 'A grounded, read-only checker that confirms the end-state matches the objective before reporting success.',
  },
  {
    sym: 'inj',
    tag: 'Hook',
    name: 'Lesson auto-inject',
    desc: 'On every prompt, relevant lessons are surfaced automatically so the agent starts from what it knows.',
  },
  {
    sym: '!!',
    tag: 'Hook',
    name: 'Guardrails',
    desc: 'In-code vetoes for guessed URLs and destructive commands — enforced before a tool ever runs.',
  },
]

export default function Stack() {
  return (
    <section className="section section--stack" id="stack">
      <div className="section__head">
        <span className="mono section__num">[ 03 ]</span>
        <h2 className="section__title">The toolkit</h2>
      </div>

      <div className="stack__grid">
        {TOOLS.map((t) => (
          <div className="material" key={t.name}>
            <span className="material__sym">{t.sym}</span>
            <span className="mono material__tag">{t.tag}</span>
            <span className="material__name">{t.name}</span>
            <span className="material__desc">{t.desc}</span>
          </div>
        ))}
      </div>
    </section>
  )
}
