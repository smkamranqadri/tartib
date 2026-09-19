/** A sound when a session ends: bell, kitchen timer, or wood, or none. Per device.
 *
 * The recordings are CC0 (see sounds/SOURCES.md) and go through Vite, so they are served from
 * /assets/ and the service worker keeps them once fetched. iOS plays nothing until a page has made
 * sound inside a tap, so `unlockChime` runs on the Start press -- and loads the chosen sound while
 * the network is surely there. If it still cannot be loaded, a generated two-note chime plays. */
import bell from "./sounds/bell.mp3";
import kitchen from "./sounds/kitchen.mp3";
import wood from "./sounds/wood.mp3";

export type ChimeSound = "bell" | "kitchen" | "wood" | "off";
export const SOUNDS: { value: ChimeSound; label: string }[] = [
  { value: "bell", label: "Bell" },
  { value: "kitchen", label: "Kitchen" },
  { value: "wood", label: "Wood" },
  { value: "off", label: "Off" },
];
const URLS: Record<Exclude<ChimeSound, "off">, string> = { bell, kitchen, wood };

const KEY = "tartib-chime";
let ctx: AudioContext | null = null;
const buffers = new Map<string, Promise<AudioBuffer>>();

export function chimeSound(): ChimeSound {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "off" || v === "bell" || v === "kitchen" || v === "wood") return v;
  } catch {
    /* private mode */
  }
  return "bell"; // unset, or "on" from before there was a choice
}

export function setChimeSound(sound: ChimeSound): void {
  try {
    localStorage.setItem(KEY, sound);
  } catch {
    /* private mode: the choice lasts as long as the page */
  }
}

function context(): AudioContext | null {
  if (ctx) return ctx;
  const Ctor = window.AudioContext ?? (window as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  ctx = new Ctor();
  return ctx;
}

function load(ac: AudioContext, sound: Exclude<ChimeSound, "off">): Promise<AudioBuffer> {
  let p = buffers.get(sound);
  if (!p) {
    p = fetch(URLS[sound])
      .then((r) => {
        if (!r.ok) throw new Error(`sound ${r.status}`);
        return r.arrayBuffer();
      })
      .then((data) => ac.decodeAudioData(data));
    p.catch(() => buffers.delete(sound)); // a failed load is tried again next time
    buffers.set(sound, p);
  }
  return p;
}

/** Call from a tap. A silent blip is what convinces iOS the page may make sound later. */
export function unlockChime(): void {
  const sound = chimeSound();
  if (sound === "off") return;
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
  void load(ac, sound).catch(() => {});
}

/** Play the chosen sound, or `sound` when previewing a choice. */
export async function playChime(sound: ChimeSound = chimeSound()): Promise<void> {
  if (sound === "off") return;
  const ac = context();
  if (!ac) return;
  void ac.resume();
  try {
    const src = ac.createBufferSource();
    src.buffer = await load(ac, sound);
    src.connect(ac.destination);
    src.start();
  } catch {
    fallback(ac);
  }
}

/** Two soft tones a fifth apart, for when the recording cannot be had. */
function fallback(ac: AudioContext): void {
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
