export default function About() {
  return (
    <section className="section section--about" id="about">
      <div className="section__head">
        <span className="mono section__num">[ 01 ]</span>
        <h2 className="section__title">What it is</h2>
      </div>

      <div className="prose">
        <p>
          Support Engineer turns a support request into a{' '}
          <strong>verified outcome</strong>. The reasoning loop, the vision and
          the tool use are native to <strong>Claude Code</strong> — the repo
          itself is mostly <strong>operating instructions</strong> plus a small
          lesson-memory service and a pair of safety hooks.
        </p>
        <p>
          The one piece of real code is a{' '}
          <strong>lesson memory over Qdrant</strong>, exposed as the{' '}
          <code>memory</code> MCP server. Every task the agent resolves and
          verifies can be distilled into a reusable, step-by-step{' '}
          <strong>lesson</strong> — so the same problem is never solved from
          scratch twice.
        </p>
        <p>
          Two hooks keep it honest: one <strong>auto-injects</strong> relevant
          lessons before each task, the other applies{' '}
          <strong>guardrails</strong> in code — vetoing guessed URLs and
          destructive shell commands before they ever run.
        </p>
      </div>

      <ul className="microdata">
        <li className="mono"><span>RUNTIME</span>Claude Code</li>
        <li className="mono"><span>MEMORY</span>Qdrant · MCP</li>
        <li className="mono"><span>TOOLS</span>Playwright · Desktop Commander</li>
      </ul>
    </section>
  )
}
