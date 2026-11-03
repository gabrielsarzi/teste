// Retratos geométricos dos frequentadores do boteco e ícones dos itens (SVG gerado).
const SKIN = ['#f1c9a5', '#d9a77c', '#b07a52', '#7a4e33'];
const HAIR = '#2a1b12';

export function portrait(face, size = 56) {
  const s = SKIN[face.skin ?? 1];
  const ink = face.ink || '#2a1b12';
  const parts = [];
  // ombros / roupa
  parts.push(`<path d="M8 64 C10 48 22 44 32 44 C42 44 54 48 56 64 Z" fill="${ink}" opacity=".9"/>`);
  if (face.extra === 'gravata') parts.push(`<path d="M32 46 l-3 4 l3 12 l3 -12 z" fill="#b8322a"/><path d="M26 46 l6 3 l6 -3" stroke="#f3ecdc" stroke-width="2" fill="none"/>`);
  // pescoço e cabeça
  parts.push(`<rect x="27" y="36" width="10" height="10" rx="3" fill="${s}"/>`);
  if (face.hair === 'longo') parts.push(`<path d="M17 28 C17 12 47 12 47 28 L49 46 L15 46 Z" fill="${HAIR}"/>`);
  parts.push(`<ellipse cx="32" cy="27" rx="13" ry="14.5" fill="${s}"/>`);
  // orelhas
  parts.push(`<circle cx="19" cy="28" r="3" fill="${s}"/><circle cx="45" cy="28" r="3" fill="${s}"/>`);
  if (face.extra === 'brinco') parts.push(`<circle cx="19" cy="32.5" r="1.6" fill="#f2c14e"/><circle cx="45" cy="32.5" r="1.6" fill="#f2c14e"/>`);
  // cabelo / chapéu
  switch (face.hair) {
    case 'curto':
      parts.push(`<path d="M19 24 C19 10 45 10 45 24 C42 18 36 16 32 17 C27 16 22 18 19 24 Z" fill="${HAIR}"/>`);
      break;
    case 'coque':
      parts.push(`<circle cx="32" cy="9" r="5.5" fill="#9a9a9a"/><path d="M19 25 C18 11 46 11 45 25 C41 17 23 17 19 25 Z" fill="#a9a9a9"/>`);
      break;
    case 'longo':
      parts.push(`<path d="M19 26 C18 12 46 12 45 26 C40 18 26 16 19 26 Z" fill="${HAIR}"/>`);
      break;
    case 'bone':
      parts.push(`<path d="M18 23 C18 9 46 9 46 23 Z" fill="#e2483b"/><path d="M40 22 L56 24 L46 26 Z" fill="#b8322a"/>`);
      break;
    case 'chapeu':
      parts.push(`<ellipse cx="32" cy="17" rx="21" ry="4" fill="#f3e2b0"/><path d="M21 17 C21 5 43 5 43 17 Z" fill="#f3e2b0"/><rect x="21" y="13" width="22" height="3" fill="#6b3a1f"/>`);
      break;
    case 'lenco':
      parts.push(`<path d="M17 25 C17 8 47 8 47 25 C44 19 20 19 17 25 Z" fill="#f2b33d"/><circle cx="25" cy="15" r="1.4" fill="#fff"/><circle cx="33" cy="12" r="1.4" fill="#fff"/><circle cx="40" cy="16" r="1.4" fill="#fff"/>`);
      break;
    case 'capacete':
      parts.push(`<path d="M17 22 C17 6 47 6 47 22 Z" fill="#f2c14e"/><rect x="15" y="20" width="34" height="4" rx="2" fill="#e0a92e"/><rect x="30" y="7" width="4" height="13" fill="#e0a92e"/>`);
      break;
    case 'quepe':
      parts.push(`<rect x="19" y="10" width="26" height="10" rx="3" fill="#1f2c3c"/><path d="M18 20 L46 20 L50 23 L18 23 Z" fill="#111"/><circle cx="32" cy="15" r="2" fill="#f2c14e"/>`);
      break;
    default:
      break; // careca
  }
  // olhos
  if (face.extra === 'oculos') {
    parts.push(`<circle cx="26" cy="27" r="4.3" fill="none" stroke="#111" stroke-width="1.8"/><circle cx="38" cy="27" r="4.3" fill="none" stroke="#111" stroke-width="1.8"/><path d="M30.3 27 h3.4" stroke="#111" stroke-width="1.8"/>`);
  }
  parts.push(`<circle cx="26" cy="27" r="1.6" fill="#111"/><circle cx="38" cy="27" r="1.6" fill="#111"/>`);
  parts.push(`<path d="M22.5 22 q3.5 -2 7 0 M34.5 22 q3.5 -2 7 0" stroke="${HAIR}" stroke-width="1.6" fill="none" stroke-linecap="round"/>`);
  if (face.blush) parts.push(`<circle cx="22.5" cy="32" r="2.6" fill="#e2483b" opacity=".45"/><circle cx="41.5" cy="32" r="2.6" fill="#e2483b" opacity=".45"/>`);
  // nariz e boca
  parts.push(`<path d="M32 28 q-2 5 1 5.5" stroke="${shade(s)}" stroke-width="1.5" fill="none" stroke-linecap="round"/>`);
  if (face.extra === 'barba') parts.push(`<path d="M19.5 30 C20 44 44 44 44.5 30 C41 38 23 38 19.5 30 Z" fill="${HAIR}"/>`);
  if (face.stache === 'cheio') parts.push(`<path d="M24 35.5 C27 32 30 33 32 34.5 C34 33 37 32 40 35.5 C36 35.5 34 36.5 32 36 C30 36.5 28 35.5 24 35.5 Z" fill="${HAIR}"/>`);
  else if (face.stache === 'fino') parts.push(`<path d="M26 35 q6 -3 12 0" stroke="${HAIR}" stroke-width="1.6" fill="none" stroke-linecap="round"/>`);
  parts.push(`<path d="M28.5 38.4 q3.5 2.4 7 0" stroke="#5a2a1a" stroke-width="1.5" fill="none" stroke-linecap="round"/>`);
  if (face.extra === 'palito') parts.push(`<path d="M35 38 L44 35" stroke="#e8c98a" stroke-width="1.4" stroke-linecap="round"/>`);
  if (face.extra === 'copo') parts.push(`<rect x="44" y="46" width="9" height="13" rx="1.5" fill="#f2c14e" opacity=".95"/><rect x="44" y="46" width="9" height="3" fill="#fff8e6"/>`);
  return `<svg viewBox="0 0 64 64" width="${size}" height="${size}" aria-hidden="true">${parts.join('')}</svg>`;
}

function shade(hex) {
  const n = parseInt(hex.slice(1), 16);
  const r = Math.max(0, (n >> 16) - 40), g = Math.max(0, ((n >> 8) & 255) - 40), b = Math.max(0, (n & 255) - 40);
  return `rgb(${r},${g},${b})`;
}

export function bottleIcon(color, size = 40) {
  return `<svg viewBox="0 0 40 56" width="${size * 0.72}" height="${size}" aria-hidden="true">
  <rect x="15" y="2" width="10" height="6" rx="1.5" fill="#6b3a1f"/>
  <path d="M16 8 h8 v8 c0 3 7 6 7 13 v20 a4 4 0 0 1 -4 4 h-14 a4 4 0 0 1 -4 -4 v-20 c0 -7 7 -10 7 -13 z" fill="${color}" stroke="rgba(0,0,0,.35)" stroke-width="1.2"/>
  <rect x="10.5" y="30" width="19" height="13" rx="1.5" fill="#f3ecdc"/>
  <path d="M13 34 h14 M13 38 h9" stroke="#2a1b12" stroke-width="1.6"/>
  <path d="M13 13 c-2 6 -3 10 -3 16" stroke="rgba(255,255,255,.45)" stroke-width="2" fill="none" stroke-linecap="round"/>
  </svg>`;
}

const SIMP_ICONS = {
  ferradura: `<path d="M12 8 C2 18 4 40 20 44 C36 40 38 18 28 8 L24 12 C30 20 28 34 20 37 C12 34 10 20 16 12 Z" fill="#c9b9a0" stroke="#2a1b12" stroke-width="1.5"/><circle cx="11" cy="22" r="1.5" fill="#2a1b12"/><circle cx="29" cy="22" r="1.5" fill="#2a1b12"/><circle cx="14" cy="32" r="1.5" fill="#2a1b12"/><circle cx="26" cy="32" r="1.5" fill="#2a1b12"/>`,
  arruda: `<path d="M20 46 C20 34 20 20 20 6" stroke="#2f6a35" stroke-width="2.2" fill="none"/>${[10, 18, 26, 34].map((y, i) => `<ellipse cx="${i % 2 ? 26 : 14}" cy="${y}" rx="6" ry="3.2" transform="rotate(${i % 2 ? -30 : 30} ${i % 2 ? 26 : 14} ${y})" fill="#4f9a5a"/>`).join('')}`,
  olhogrego: `<circle cx="20" cy="25" r="16" fill="#1f4f8f"/><circle cx="20" cy="25" r="11" fill="#f3ecdc"/><circle cx="20" cy="25" r="7" fill="#5fa8d8"/><circle cx="20" cy="25" r="3.5" fill="#111"/>`,
  coelho: `<path d="M14 44 C8 40 10 28 16 24 C14 16 16 6 20 6 C24 6 26 16 24 24 C30 28 32 40 26 44 Z" fill="#efe6d6" stroke="#2a1b12" stroke-width="1.4"/><path d="M14 44 h12 v4 h-12 z" fill="#c9a227"/>`,
  fitinha: `<path d="M8 10 C16 16 24 4 32 10 L30 18 C22 12 16 24 6 18 Z" fill="#e2483b"/><path d="M6 18 C10 28 14 36 10 46" stroke="#e2483b" stroke-width="4" fill="none"/><path d="M30 18 C28 28 30 36 34 46" stroke="#e2483b" stroke-width="4" fill="none"/>`,
  sal: `<path d="M4 44 C8 30 14 22 20 22 C26 22 32 30 36 44 Z" fill="#f3f1ea" stroke="#9a9a90" stroke-width="1.2"/>${[[12, 16], [20, 12], [27, 17], [16, 8], [24, 6]].map(([x, y]) => `<rect x="${x}" y="${y}" width="3.2" height="3.2" transform="rotate(30 ${x} ${y})" fill="#f3f1ea" stroke="#9a9a90" stroke-width=".8"/>`).join('')}`,
  espelho: `<ellipse cx="20" cy="22" rx="13" ry="16" fill="#c9a227"/><ellipse cx="20" cy="22" rx="10" ry="13" fill="#bfe0ee"/><path d="M14 14 l6 -3" stroke="#fff" stroke-width="2" stroke-linecap="round"/><rect x="18" y="38" width="4" height="10" rx="1" fill="#c9a227"/>`,
  trevo: `${[[20, 12], [12, 20], [28, 20], [20, 28]].map(([x, y]) => `<circle cx="${x}" cy="${y}" r="7" fill="#3f9a4a"/>`).join('')}<path d="M20 28 C22 36 24 42 28 47" stroke="#2f6a35" stroke-width="2.4" fill="none"/>`,
};

export function simpatiaIcon(id, size = 40) {
  return `<svg viewBox="0 0 40 50" width="${size * 0.8}" height="${size}" aria-hidden="true">${SIMP_ICONS[id] || ''}</svg>`;
}

export function boxIcon(size = 40) {
  return `<svg viewBox="0 0 48 44" width="${size}" height="${size * 0.92}" aria-hidden="true">
  <path d="M4 14 L24 6 L44 14 L44 36 L24 42 L4 36 Z" fill="#8a5a33" stroke="#2a1b12" stroke-width="1.4"/>
  <path d="M4 14 L24 22 L44 14 M24 22 V42" stroke="#2a1b12" stroke-width="1.4" fill="none"/>
  <path d="M8 20 l12 5 v9 l-12 -5 z" fill="#f3ecdc"/><circle cx="12" cy="25" r="1.3" fill="#111"/><circle cx="16" cy="29" r="1.3" fill="#111"/>
  <path d="M14 10 L34 18" stroke="#e2483b" stroke-width="3"/>
  </svg>`;
}

// Texturas das mesas geradas em canvas (sem arquivos de imagem).
function canvas(w, h) {
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  return [c, c.getContext('2d')];
}

function noise(g, w, h, amount, alpha) {
  const img = g.getImageData(0, 0, w, h);
  const d = img.data;
  for (let i = 0; i < d.length; i += 4) {
    const n = (Math.random() - 0.5) * amount;
    d[i] += n;
    d[i + 1] += n;
    d[i + 2] += n;
    d[i + 3] = 255 * alpha + d[i + 3] * (1 - alpha);
  }
  g.putImageData(img, 0, 0);
}

// Madeira de tampo envernizado: tábuas largas, veio longo e suave, sem riscos duros.
function wood(w, h) {
  const [c, g] = canvas(w, h);
  const grad = g.createLinearGradient(0, 0, w, h);
  grad.addColorStop(0, '#6a4026');
  grad.addColorStop(1, '#55321d');
  g.fillStyle = grad;
  g.fillRect(0, 0, w, h);
  const boards = 3;
  const bw = w / boards;
  for (let k = 0; k < boards; k++) {
    // leve variação de tom por tábua
    g.fillStyle = `rgba(${k % 2 ? '255,225,190' : '20,8,2'},${0.035 + Math.random() * 0.03})`;
    g.fillRect(k * bw, 0, bw, h);
    // veios verticais longos e macios
    for (let i = 0; i < 26; i++) {
      const x0 = k * bw + Math.random() * bw;
      g.strokeStyle = `rgba(${Math.random() < 0.6 ? '35,16,6' : '150,100,60'},${0.04 + Math.random() * 0.06})`;
      g.lineWidth = 1 + Math.random() * 3;
      g.beginPath();
      const amp = 2 + Math.random() * 5;
      const f = (Math.PI * 2 * (1 + Math.floor(Math.random() * 2))) / h;
      const ph = Math.random() * 6;
      for (let y = 0; y <= h; y += 6) {
        const x = x0 + Math.sin(y * f + ph) * amp;
        y === 0 ? g.moveTo(x, y) : g.lineTo(x, y);
      }
      g.stroke();
    }
    // junta entre tábuas, bem discreta
    g.fillStyle = 'rgba(0,0,0,.22)';
    g.fillRect(k * bw, 0, 1, h);
    g.fillStyle = 'rgba(255,220,180,.05)';
    g.fillRect(k * bw + 1, 0, 1, h);
  }
  noise(g, w, h, 8, 0);
  return c.toDataURL('image/jpeg', 0.86);
}

// granulado fino para o fundo do salão
export function grainTexture() {
  const [c, g] = canvas(160, 160);
  g.fillStyle = '#808080';
  g.fillRect(0, 0, 160, 160);
  noise(g, 160, 160, 60, 0);
  return c.toDataURL('image/png');
}

function felt(w, h) {
  const [c, g] = canvas(w, h);
  g.fillStyle = '#1f5a3a';
  g.fillRect(0, 0, w, h);
  noise(g, w, h, 26, 0);
  return c.toDataURL('image/jpeg', 0.85);
}

function marble(w, h) {
  const [c, g] = canvas(w, h);
  g.fillStyle = '#e9e5dd';
  g.fillRect(0, 0, w, h);
  for (let i = 0; i < 26; i++) {
    g.strokeStyle = `rgba(${90 + Math.random() * 40},${90 + Math.random() * 30},${100 + Math.random() * 30},${0.08 + Math.random() * 0.2})`;
    g.lineWidth = 0.5 + Math.random() * 2.5;
    g.beginPath();
    let x = Math.random() * w, y = -10;
    g.moveTo(x, y);
    while (y < h + 10) {
      x += (Math.random() - 0.5) * 40;
      y += 10 + Math.random() * 30;
      g.lineTo(x, y);
    }
    g.stroke();
  }
  noise(g, w, h, 10, 0);
  return c.toDataURL('image/jpeg', 0.85);
}

function plastic(w, h) {
  const [c, g] = canvas(w, h);
  g.fillStyle = '#f2c230';
  g.fillRect(0, 0, w, h);
  noise(g, w, h, 12, 0);
  // relevo de mesa de plástico: anéis concêntricos bem suaves
  for (let r = 20; r < w; r += 22) {
    g.strokeStyle = 'rgba(160,110,0,.10)';
    g.lineWidth = 2;
    g.beginPath();
    g.arc(w / 2, h / 2, r, 0, Math.PI * 2);
    g.stroke();
  }
  return c.toDataURL('image/jpeg', 0.85);
}

export function tableTexture(kind) {
  if (kind === 'feltro') return felt(256, 256);
  if (kind === 'marmore') return marble(512, 512);
  if (kind === 'plastico') return plastic(512, 512);
  if (kind === 'toalha') return null; // feita só com CSS
  return wood(384, 384);
}
