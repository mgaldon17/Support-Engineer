import { useMemo, useRef, useEffect } from 'react'
import { useStore } from '../store'

// ── Agent "reasoning graph" background ──────────────────────────────────────
// A deterministic node-link constellation that evokes an autonomous agent's
// decision graph (triage → recall → execute → verify → persist). Rendered as a
// fixed, full-viewport SVG behind all content, in light professional tones.
// It drifts a few pixels with the pointer for depth. Kept intentionally low
// contrast so long-form text stays comfortable to read on top of it.

const W = 1440
const H = 900
const N = 46 // node count
const LINK_DIST = 260 // connect nodes closer than this

// Small seeded PRNG (mulberry32) so the layout is stable across reloads/builds.
function mulberry32(seed) {
  return function () {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function buildGraph() {
  const rand = mulberry32(20260702)
  const nodes = []
  for (let i = 0; i < N; i++) {
    nodes.push({
      x: rand() * W,
      y: rand() * H,
      r: 1.6 + rand() * 3.2,
      // ~1 in 6 nodes is an accent "decision" node.
      accent: rand() > 0.83,
      // per-node animation offset so pulses don't sync up.
      delay: (rand() * 6).toFixed(2),
      // parallax depth: closer nodes move more.
      depth: 0.3 + rand() * 1.0,
    })
  }

  const links = []
  for (let i = 0; i < N; i++) {
    for (let j = i + 1; j < N; j++) {
      const dx = nodes[i].x - nodes[j].x
      const dy = nodes[i].y - nodes[j].y
      const d = Math.hypot(dx, dy)
      if (d < LINK_DIST) {
        links.push({ a: i, b: j, o: 1 - d / LINK_DIST })
      }
    }
  }
  return { nodes, links }
}

export default function Background() {
  const { nodes, links } = useMemo(buildGraph, [])
  const svgRef = useRef(null)
  const mouse = useStore((s) => s.mouse)
  const scroll = useStore((s) => s.scroll)

  // Damp the parallax transform toward the pointer/scroll target.
  const target = useRef({ x: 0, y: 0 })
  const current = useRef({ x: 0, y: 0 })

  useEffect(() => {
    target.current.x = mouse[0] * 26
    target.current.y = mouse[1] * 20 + scroll * 40
  }, [mouse, scroll])

  useEffect(() => {
    let raf
    const loop = () => {
      current.current.x += (target.current.x - current.current.x) * 0.06
      current.current.y += (target.current.y - current.current.y) * 0.06
      if (svgRef.current) {
        svgRef.current.style.transform = `translate3d(${current.current.x}px, ${current.current.y}px, 0) scale(1.06)`
      }
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [])

  return (
    <div className="bg" aria-hidden="true">
      <svg
        ref={svgRef}
        className="bg__svg"
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="xMidYMid slice"
      >
        <defs>
          <radialGradient id="bgGlow" cx="28%" cy="18%" r="90%">
            <stop offset="0%" stopColor="#dfe9ff" />
            <stop offset="45%" stopColor="#eef3fb" />
            <stop offset="100%" stopColor="#f6f8fb" />
          </radialGradient>
        </defs>

        {/* soft wash */}
        <rect x="0" y="0" width={W} height={H} fill="url(#bgGlow)" />

        {/* links */}
        <g stroke="#2f6feb">
          {links.map((l, i) => (
            <line
              key={i}
              x1={nodes[l.a].x}
              y1={nodes[l.a].y}
              x2={nodes[l.b].x}
              y2={nodes[l.b].y}
              strokeWidth="1"
              strokeOpacity={0.06 + l.o * 0.12}
            />
          ))}
        </g>

        {/* nodes */}
        <g>
          {nodes.map((n, i) => (
            <circle
              key={i}
              className={n.accent ? 'bg__node bg__node--accent' : 'bg__node'}
              cx={n.x}
              cy={n.y}
              r={n.r}
              style={{ animationDelay: `${n.delay}s` }}
            />
          ))}
        </g>
      </svg>

      {/* readability overlay: brightens edges + top so text always reads */}
      <div className="bg__overlay" />
    </div>
  )
}
