// Peças de dominó (duplo-seis: 28 pedras).
let uidSeq = 1;
export const newUid = () => uidSeq++;

export function fullSet() {
  const out = [];
  for (let a = 0; a <= 6; a++) for (let b = a; b <= 6; b++) out.push(makeTile(a, b));
  return out;
}

export function makeTile(a, b, extra = {}) {
  return { uid: newUid(), a: Math.min(a, b), b: Math.max(a, b), mod: null, bonus: 0, ...extra };
}

export const isDouble = (t) => t.a === t.b;
export const pipSum = (t) => t.a + t.b;
export const hasNum = (t, n) => t.a === n || t.b === n;
export const tileName = (t) => `${t.a}·${t.b}`;

// Nomes populares dos números no dominó brasileiro.
export const NUM_NAMES = ['branco', 'ás', 'duque', 'terno', 'quadra', 'quina', 'sena'];
export const BUCHA_NAMES = [
  'bucha de branco', 'bucha de ás', 'bucha de duque', 'bucha de terno',
  'bucha de quadra', 'bucha de quina', 'bucha de sena',
];

// RNG com semente (mulberry32), para partidas reproduzíveis.
export function makeRng(seed = (Math.random() * 2 ** 32) >>> 0) {
  let s = seed >>> 0;
  const rng = () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  rng.seed = seed;
  rng.int = (n) => Math.floor(rng() * n);
  rng.pick = (arr) => arr[Math.floor(rng() * arr.length)];
  rng.shuffle = (arr) => {
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  };
  return rng;
}

// Depois de carregar um save, garante que novas pedras não repitam uid.
export function bumpUid(min) {
  if (min >= uidSeq) uidSeq = min + 1;
}
