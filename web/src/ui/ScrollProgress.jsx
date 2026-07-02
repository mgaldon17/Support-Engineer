import { useStore } from '../store'

// Thin vertical progress indicator on the right edge.
export default function ScrollProgress() {
  const scroll = useStore((s) => s.scroll)
  const pct = Math.round(scroll * 100)

  return (
    <div className="scroll-progress">
      <span className="scroll-progress__pct">{String(pct).padStart(2, '0')}</span>
      <div className="scroll-progress__track">
        <div className="scroll-progress__fill" style={{ height: `${pct}%` }} />
      </div>
      <span className="mono scroll-progress__unit">%</span>
    </div>
  )
}
