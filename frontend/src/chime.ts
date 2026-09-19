/** A short chime when a session ends, made with Web Audio -- no sound file to ship or cache.
 *
 * iOS plays nothing until a page has made sound inside a tap, so `unlockChime` runs on the Start
 * press and the chime at the end reuses that context. Per device, on unless switched off. */

const KEY = "tartib-chime";
let ctx: AudioContext | null = null;

export function chimeEnabled(): boolean {
  try {
    return localStorage.getItem(KEY) !== "off";
  } catch {
    return true;
  }
}

export function setChimeEnabled(on: boolean): void {
  try {
    localStorage.setItem(KEY, on ? "on" : "off");
  } catch {
    /* private mode: the switch lasts as long as the page */
  }
}

function context(): AudioContext | null {
  if (ctx) return ctx;
  const Ctor = window.AudioContext ?? (window as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  ctx = new Ctor();
  return ctx;
}

/** Call from a tap. A silent blip is what convinces iOS the page may make sound later. */
export function unlockChime(): void {
  if (!chimeEnabled()) return;
  const ac = context();
  if (!ac) return;
  void ac.resume();
  const silent = ac.createGain();
  silent.gain.value = 0;
  silent.connect(ac.destination);
  const osc = ac.createOscillator();
  osc.connect(silent);
  osc.start();
  osc.stop(ac.currentTime + 0.01);
}

/** Two soft bell tones, a fifth apart, each fading out. */
export function playChime(): void {
  if (!chimeEnabled()) return;
  const ac = context();
  if (!ac) return;
  void ac.resume();
  const t0 = ac.currentTime;
  [
    [880, 0],
    [1318.5, 0.18],
  ].forEach(([freq, delay]) => {
    const osc = ac.createOscillator();
    const gain = ac.createGain();
    osc.type = "sine";
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.0001, t0 + delay);
    gain.gain.exponentialRampToValueAtTime(0.25, t0 + delay + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + delay + 1.2);
    osc.connect(gain).connect(ac.destination);
    osc.start(t0 + delay);
    osc.stop(t0 + delay + 1.25);
  });
}
