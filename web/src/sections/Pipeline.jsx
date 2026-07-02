// The agent loop as an inline SVG flow diagram.
// Flow:  Request -> Triage -> Recall (<-> Lesson memory) -> Execute (<-> Tools)
//        -> Verify -> Outcome -> Persist ; feedback: Persist --> Lesson memory.
// Palette: white boxes, fine borders, --accent flow, --accent-2 on the
//          result / learned nodes. Mono labels throughout.
export default function Pipeline() {
  return (
    <section className="section section--pipeline" id="pipeline">
      <div className="section__head">
        <span className="mono section__num">[ 04 ]</span>
        <h2 className="section__title">The agent loop</h2>
      </div>

      <p className="prose pipeline__intro">
        Every request flows through the same closed loop — and each verified
        outcome feeds a lesson back into memory, so the loop gets smarter over
        time.
      </p>

      <div className="pipeline__diagram">
        <svg viewBox="0 0 1000 720" role="img" aria-label="Agent loop diagram" preserveAspectRatio="xMidYMin meet">
          <defs>
            <marker id="arrow" markerWidth="9" markerHeight="9" refX="6" refY="3" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L6,3 L0,6 Z" fill="#2f6feb" />
            </marker>
            <marker id="arrowStart" markerWidth="9" markerHeight="9" refX="0" refY="3" orient="auto" markerUnits="strokeWidth">
              <path d="M6,0 L0,3 L6,6 Z" fill="#2f6feb" />
            </marker>
            <marker id="arrowResult" markerWidth="9" markerHeight="9" refX="6" refY="3" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L6,3 L0,6 Z" fill="#0f9d8f" />
            </marker>
          </defs>

          {/* ── Request ─────────────────────────────────────────────── */}
          <g className="node">
            <rect x="270" y="20" width="320" height="54" rx="8" className="box" />
            <text x="430" y="44" className="dlabel dlabel--accent" textAnchor="middle">REQUEST</text>
            <text x="430" y="63" className="ditem" textAnchor="middle">support ticket · question</text>
          </g>
          <line x1="430" y1="74" x2="430" y2="110" className="flow" markerEnd="url(#arrow)" />

          {/* ── Triage ──────────────────────────────────────────────── */}
          <g className="node">
            <rect x="310" y="110" width="240" height="60" rx="8" className="box box--run" />
            <text x="430" y="136" className="dlabel dlabel--accent" textAnchor="middle">TRIAGE</text>
            <text x="430" y="156" className="ditem" textAnchor="middle">intent · objective · criteria</text>
          </g>
          <line x1="430" y1="170" x2="430" y2="206" className="flow" markerEnd="url(#arrow)" />

          {/* ── Recall memory (<-> Lesson memory) ───────────────────── */}
          <g className="node">
            <rect x="310" y="206" width="240" height="60" rx="8" className="box" />
            <text x="430" y="232" className="dlabel" textAnchor="middle">RECALL MEMORY</text>
            <text x="430" y="252" className="ditem" textAnchor="middle">search lessons by meaning</text>
          </g>
          <line x1="550" y1="236" x2="680" y2="236" className="flow" markerStart="url(#arrowStart)" markerEnd="url(#arrow)" />
          <g className="node">
            <rect x="680" y="206" width="230" height="60" rx="8" className="box box--result" />
            <text x="795" y="232" className="dlabel dlabel--result" textAnchor="middle">LESSON MEMORY</text>
            <text x="795" y="252" className="ditem" textAnchor="middle">Qdrant vectors · MCP</text>
          </g>
          <line x1="430" y1="266" x2="430" y2="302" className="flow" markerEnd="url(#arrow)" />

          {/* ── Execute (<-> Tools) ─────────────────────────────────── */}
          <g className="node">
            <rect x="310" y="302" width="240" height="60" rx="8" className="box box--run" />
            <text x="430" y="328" className="dlabel dlabel--accent" textAnchor="middle">EXECUTE</text>
            <text x="430" y="348" className="ditem" textAnchor="middle">act · adapt to results</text>
          </g>
          <line x1="550" y1="332" x2="680" y2="332" className="flow" markerStart="url(#arrowStart)" markerEnd="url(#arrow)" />
          <g className="node">
            <rect x="680" y="302" width="230" height="60" rx="8" className="box box--ghost" />
            <text x="795" y="328" className="dlabel" textAnchor="middle">TOOLS</text>
            <text x="795" y="348" className="ditem ditem--dim" textAnchor="middle">Playwright · Desktop Cmd</text>
          </g>
          <line x1="430" y1="362" x2="430" y2="398" className="flow" markerEnd="url(#arrow)" />

          {/* ── Verify ──────────────────────────────────────────────── */}
          <g className="node">
            <rect x="310" y="398" width="240" height="60" rx="8" className="box" />
            <text x="430" y="424" className="dlabel" textAnchor="middle">VERIFY</text>
            <text x="430" y="444" className="ditem" textAnchor="middle">read-only verifier subagent</text>
          </g>
          <line x1="430" y1="458" x2="430" y2="494" className="flow" markerEnd="url(#arrow)" />

          {/* ── Outcome (result) ────────────────────────────────────── */}
          <g className="node">
            <rect x="310" y="494" width="240" height="60" rx="8" className="box box--result" />
            <text x="430" y="520" className="dlabel dlabel--result" textAnchor="middle">OUTCOME</text>
            <text x="430" y="540" className="ditem" textAnchor="middle">answer · changed state</text>
          </g>
          <line x1="430" y1="554" x2="430" y2="590" className="flow" markerEnd="url(#arrow)" />

          {/* ── Persist (result) ────────────────────────────────────── */}
          <g className="node">
            <rect x="310" y="590" width="240" height="60" rx="8" className="box box--result" />
            <text x="430" y="616" className="dlabel dlabel--result" textAnchor="middle">PERSIST</text>
            <text x="430" y="636" className="ditem" textAnchor="middle">reinforce · fail · new lesson</text>
          </g>

          {/* feedback: Persist -> Lesson memory (learned loop) */}
          <path d="M550,620 H965 V236 H912" className="flow flow--result" markerEnd="url(#arrowResult)" />
          <text x="958" y="430" className="ditem ditem--dim" textAnchor="middle" transform="rotate(90 958 430)">
            learned lesson → memory
          </text>
        </svg>
      </div>
    </section>
  )
}
