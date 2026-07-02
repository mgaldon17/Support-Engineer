import { useEffect } from 'react'
import { useStore } from './store'
import Background from './ui/Background'
import Loader from './ui/Loader'
import Grain from './ui/Grain'

// Frozen screens reused by the GitHub Actions workflows:
//  - "maintenance" : site is being updated
//  - "unpublished" : site has been taken offline
// Same agent-graph background as the landing — no scroll, no sections.
const STATES = {
  maintenance: {
    eyebrow: '◆ SCHEDULED MAINTENANCE',
    title: 'Under maintenance',
    sub: 'The site is being updated. Back online shortly.',
  },
  unpublished: {
    eyebrow: '◆ OFFLINE',
    title: 'Page unpublished',
    sub: 'This page has been taken offline.',
  },
}

export default function StateScreen({ variant }) {
  const cfg = STATES[variant] || STATES.maintenance
  const setMouse = useStore((s) => s.setMouse)

  // Keep the background parallax — the only interactivity on these pages.
  useEffect(() => {
    const onMove = (e) => {
      const x = (e.clientX / window.innerWidth) * 2 - 1
      const y = (e.clientY / window.innerHeight) * 2 - 1
      setMouse([x, y])
    }
    window.addEventListener('pointermove', onMove)
    return () => window.removeEventListener('pointermove', onMove)
  }, [setMouse])

  return (
    <>
      <Background />
      <Loader />
      <Grain />

      <div className="state-screen">
        <span className="mono eyebrow">{cfg.eyebrow}</span>
        <h1 className="state-screen__title">{cfg.title}</h1>
        <p className="state-screen__sub">{cfg.sub}</p>
      </div>
    </>
  )
}
