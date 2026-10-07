import { useMemo } from 'react'
import { HEIGHT, WIDTH, bulldogPixels } from '../sprites'
import type { Role } from '../types'

interface Props {
  role: Role
  size?: number // rendered width in px
  title?: string
  asleep?: boolean
}

export function PixelBulldog({ role, size = 108, title, asleep = false }: Props) {
  const pixels = useMemo(() => bulldogPixels(role, asleep), [role, asleep])
  return (
    <svg
      className="pixel-bulldog"
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      width={size}
      height={(size * HEIGHT) / WIDTH}
      shapeRendering="crispEdges"
      role="img"
      aria-label={title ?? `${role} bulldog`}
    >
      {pixels.map((p) => (
        <rect key={`${p.x},${p.y}`} x={p.x} y={p.y} width={1.02} height={1.02} fill={p.color} />
      ))}
    </svg>
  )
}
