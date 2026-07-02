import { create } from 'zustand'

// Single source of scroll + pointer truth. Lenis writes `scroll` (0..1,
// normalized over the whole page) on every frame; the background graph reads
// `mouse` for a subtle parallax drift. `loaded` hides the loader.
export const useStore = create((set) => ({
  scroll: 0, // normalized 0..1 scroll progress
  mouse: [0, 0], // -1..1 normalized pointer, for background parallax
  loaded: false, // ready -> hide loader

  setScroll: (scroll) => set({ scroll }),
  setMouse: (mouse) => set({ mouse }),
  setLoaded: (loaded) => set({ loaded }),
}))
