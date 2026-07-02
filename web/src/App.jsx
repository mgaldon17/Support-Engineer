import { useEffect, useRef } from 'react'
import Lenis from 'lenis'
import { useStore } from './store'

import Background from './ui/Background'
import Loader from './ui/Loader'
import Grain from './ui/Grain'
import ScrollProgress from './ui/ScrollProgress'

import Hero from './sections/Hero'
import About from './sections/About'
import Flow from './sections/Flow'
import Stack from './sections/Stack'
import Pipeline from './sections/Pipeline'
import Cta from './sections/Cta'
import Footer from './sections/Footer'

export default function App() {
  const setScroll = useStore((s) => s.setScroll)
  const setMouse = useStore((s) => s.setMouse)
  const lenisRef = useRef(null)

  // ── Smooth scroll (Lenis) is the single scroll source ──────────────────
  useEffect(() => {
    const lenis = new Lenis({
      duration: 1.1,
      smoothWheel: true,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
    })
    lenisRef.current = lenis

    lenis.on('scroll', ({ scroll, limit }) => {
      setScroll(limit > 0 ? scroll / limit : 0)
    })

    let raf
    const loop = (time) => {
      lenis.raf(time)
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)

    return () => {
      cancelAnimationFrame(raf)
      lenis.destroy()
    }
  }, [setScroll])

  // ── Pointer parallax target for the background graph ───────────────────
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
      {/* Fixed full-screen agent-graph background — never scrolls */}
      <Background />

      {/* Overlays (all pointer-events: none) */}
      <Loader />
      <Grain />
      <ScrollProgress />

      {/* Scrolling content above the background */}
      <main>
        <Hero />
        <About />
        <Flow />
        <Stack />
        <Pipeline />
        <Cta />
        <Footer />
      </main>
    </>
  )
}
