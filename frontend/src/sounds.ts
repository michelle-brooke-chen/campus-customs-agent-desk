// Little synthesized chimes (Web Audio, no sound files).
import type { Role } from './types'

let ctx: AudioContext | null = null

/** Browsers only allow audio after a click, so call this from one. */
export function unlockAudio() {
  ctx ??= new AudioContext()
  if (ctx.state === 'suspended') void ctx.resume()
}

function note(freq: number, start: number, length: number, type: OscillatorType, volume = 0.12) {
  if (!ctx) return
  const t = ctx.currentTime + start
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.type = type
  osc.frequency.value = freq
  gain.gain.setValueAtTime(0.0001, t)
  gain.gain.exponentialRampToValueAtTime(volume, t + 0.015)
  gain.gain.exponentialRampToValueAtTime(0.0001, t + length)
  osc.connect(gain).connect(ctx.destination)
  osc.start(t)
  osc.stop(t + length + 0.02)
}

// Each teammate gets its own pitch, so you can tell who finished by ear.
const PITCH: Record<Role, number> = {
  boss: 523.25,
  inventory: 659.25,
  accounting: 783.99,
  facilities: 587.33,
  customer_service: 880,
}

/** A short rising "bip-boop" when a teammate reports back. */
export function playAgentDone(role: Role) {
  const f = PITCH[role]
  note(f, 0, 0.12, 'triangle')
  note(f * 1.5, 0.09, 0.18, 'triangle')
}

/** The Boss's little fanfare when the whole team is finished. */
export function playBossDone() {
  ;[523.25, 659.25, 783.99].forEach((f, i) => note(f, i * 0.11, 0.16, 'square', 0.06))
  note(1046.5, 0.33, 0.5, 'square', 0.07)
  note(1318.5, 0.33, 0.5, 'triangle', 0.05)
}
