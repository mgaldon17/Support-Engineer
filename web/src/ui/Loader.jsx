import { useEffect } from 'react'
import { useStore } from '../store'

// Brief intro loader. There is no heavy asset to wait on, so we just hold it
// for a beat and fade out — enough to avoid a raw content flash.
export default function Loader() {
  const loaded = useStore((s) => s.loaded)
  const setLoaded = useStore((s) => s.setLoaded)

  useEffect(() => {
    const t = setTimeout(() => setLoaded(true), 550)
    return () => clearTimeout(t)
  }, [setLoaded])

  return (
    <div className={`loader ${loaded ? 'loader--hidden' : ''}`}>
      <div className="loader__inner">
        <span className="mono loader__label">◆ initializing agent</span>
        <div className="loader__bar">
          <div className="loader__fill" />
        </div>
      </div>
    </div>
  )
}
