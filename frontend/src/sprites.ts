// Pixel-art bulldogs. One simple shared bulldog, plus one accessory per agent.
// Each character in a grid is one pixel; '.' is transparent.
import type { Role } from './types'

export const WIDTH = 16
export const HEIGHT = 21

const PALETTE: Record<string, string> = {
  // bulldog
  K: '#3a2a20', // outline, mouth, closed eyes
  T: '#d9a066', // tan fur
  B: '#a8653a', // folded ears
  W: '#f5e6cc', // cream muzzle, chest & paws
  E: '#1b1b1b', // eye
  N: '#2b2b2b', // nose
  // accessories
  S: '#2c3e66', // Boss suit (navy)
  X: '#ffffff', // Boss shirt collar
  R: '#c0392b', // Boss tie, headset cups
  h: '#5b6472', // headset band & mic
  V: '#2e9e5b', // Accounting visor band
  v: '#8fd3a6', // Accounting visor brim
  Y: '#f4c430', // Facilities hard hat
  y: '#fff2a8', // hat shine
  b: '#b9814a', // Inventory clipboard
  Z: '#ffffff', // clipboard paper
  g: '#27ae60', // check marks
  l: '#9aa0a6', // ruled lines, clip
}

/** Build a full row from its left half (the right half is the mirror image). */
const mirror = (rows: string[]) => rows.map((half) => half + [...half].reverse().join(''))

// Left half of the bulldog (8 px): folded ears, a small rounded muzzle with a big nose, and a "w" mouth.
const BULLDOG = mirror([
  'KK......',
  'KBK..KKK',
  'KBBKKTTT',
  '.KTTTTTT',
  '.KTEETTT',
  '.KTEETTT',
  '.KTTTWWN',
  'KTTTWWNN',
  'KTTWWWWK',
  'KTTWKKKW',
  'KTWWWWWW',
  '.KKWWWWW',
  '...KKKKK',
  '..KTTTWW',
  '..KTTTWW',
  '..KTTTWW',
  '..KWWKTW',
  '..KKKKKK',
])
// Same dog with its eyes shut.
const SLEEPING = BULLDOG.map((row, i) => (i === 4 ? row.replace(/E/g, 'T') : i === 5 ? row.replace(/E/g, 'K') : row))
const DOG_X = 0
const DOG_Y = 3

interface Layer {
  x: number
  y: number
  rows: string[]
}

const ACCESSORIES: Record<Role, Layer[]> = {
  // Navy suit and a red tie.
  boss: [{ x: 0, y: DOG_Y + 13, rows: mirror(['..KSSSXR', '..KSSSSR', '..KSSSSR', '..KWWKSS']) }],
  // Clipboard checklist held at the chest.
  inventory: [{ x: 5, y: DOG_Y + 12, rows: ['..ll..', 'bZZZZb', 'bgZllb', 'bZZZZb', 'bgZllb', 'bbbbbb'] }],
  // Green accountant's visor.
  accounting: [{ x: 0, y: DOG_Y + 2, rows: mirror(['...VVVVV', '..vvvvvv']) }],
  // Yellow hard hat.
  facilities: [{ x: 0, y: 1, rows: mirror(['.....KKK', '....KYYy', '...KYYYY', '.KYYYYYY', '.KKKKKKK']) }],
  // Headset over the head, with a mic on one side.
  customer_service: [
    { x: 0, y: 2, rows: mirror(['....hhhh', '...h....', '..h.....', '.h......', '.h......', 'RR......', 'RR......', 'RR......']) },
    { x: 1, y: 10, rows: ['h...', '.hhR'] },
  ],
}

export interface Pixel {
  x: number
  y: number
  color: string
}

function paint(grid: Map<string, Pixel>, layer: Layer) {
  layer.rows.forEach((row, dy) => {
    ;[...row].forEach((ch, dx) => {
      if (ch === '.') return
      const x = layer.x + dx
      const y = layer.y + dy
      grid.set(`${x},${y}`, { x, y, color: PALETTE[ch] ?? '#ff00ff' })
    })
  })
}

const cache = new Map<string, Pixel[]>()

export function bulldogPixels(role: Role, asleep = false): Pixel[] {
  const key = `${role}:${asleep}`
  const hit = cache.get(key)
  if (hit) return hit
  const grid = new Map<string, Pixel>()
  paint(grid, { x: DOG_X, y: DOG_Y, rows: asleep ? SLEEPING : BULLDOG })
  ACCESSORIES[role].forEach((layer) => paint(grid, layer))
  const pixels = [...grid.values()]
  cache.set(key, pixels)
  return pixels
}
