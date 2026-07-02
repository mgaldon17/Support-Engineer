import { REPO } from './content'

export default function Footer() {
  return (
    <footer className="footer">
      <p className="mono footer__line">
        SUPPORT ENGINEER · BUILT ON CLAUDE CODE ·{' '}
        <a href={REPO} target="_blank" rel="noreferrer">
          github.com/mgaldon17/Support-Engineer
        </a>
      </p>
    </footer>
  )
}
