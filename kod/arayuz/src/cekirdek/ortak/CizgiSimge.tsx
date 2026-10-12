/**
 * Boş durumların simgesi: emoji yerine ince çizgi simge (SF Symbols dili).
 *
 * Ekranlar `simge="📦"` gibi emoji vermeye devam edebilir; burada aynı
 * anlamdaki çizgi simgeye çevrilir. Tanınmayan emoji genel bir simgeye düşer;
 * emoji olmayan (SVG/JSX) simge olduğu gibi geçer.
 */

import type { ReactNode } from 'react';

type Cizim = ReactNode;

const kutu = (
  <>
    <path d="M3.5 7.5 12 3l8.5 4.5v9L12 21l-8.5-4.5z" />
    <path d="m3.5 7.5 8.5 4.5 8.5-4.5M12 12v9" />
  </>
);
const harita = (
  <>
    <path d="M9 4 3.5 6v14L9 18l6 2 5.5-2V4L15 6z" />
    <path d="M9 4v14M15 6v14" />
  </>
);
const pusula = (
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="m15.5 8.5-2 5-5 2 2-5z" />
  </>
);
const kisiler = (
  <>
    <circle cx="9" cy="8.5" r="3.2" />
    <path d="M3.5 19c.6-3.2 2.8-5 5.5-5s4.9 1.8 5.5 5" />
    <path d="M15.5 5.6a3 3 0 0 1 0 5.8M17.5 14.3c1.6.7 2.6 2.3 3 4.7" />
  </>
);
const belge = (
  <>
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <path d="M14 3v5h5M9 13h6M9 17h4" />
  </>
);
const tamam = (
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="m8 12.4 2.7 2.6L16 9.6" />
  </>
);
const konum = (
  <>
    <path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11z" />
    <circle cx="12" cy="10" r="2.4" />
  </>
);
const kilit = (
  <>
    <rect x="5" y="10.5" width="14" height="10" rx="2.5" />
    <path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" />
  </>
);
const telefon = (
  <path d="M6.6 3.8 9 3.5l1.6 4-2 1.4a11 11 0 0 0 6.5 6.5l1.4-2 4 1.6-.3 2.4a2 2 0 0 1-2 1.6C10.4 19 5 13.6 5 5.8a2 2 0 0 1 1.6-2z" />
);
const posta = (
  <>
    <path d="M3.5 13.5 6 5.5h12l2.5 8V18a1.5 1.5 0 0 1-1.5 1.5H5A1.5 1.5 0 0 1 3.5 18z" />
    <path d="M3.5 13.5H8l1.5 2.5h5l1.5-2.5h4.5" />
  </>
);
const yildiz = (
  <path d="m12 3.5 2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z" />
);
const uyari = (
  <>
    <path d="M10.3 4.2 2.8 17.5A2 2 0 0 0 4.5 20.5h15a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 0-3.4 0z" />
    <path d="M12 9.5v4.5M12 17.2h.01" />
  </>
);
const yenile = (
  <>
    <path d="M20 11a8 8 0 0 0-14.3-4.9L4 8" />
    <path d="M4 4v4h4M4 13a8 8 0 0 0 14.3 4.9L20 16" />
    <path d="M20 20v-4h-4" />
  </>
);
const pano = (
  <>
    <rect x="5" y="4.5" width="14" height="16.5" rx="2" />
    <path d="M9 4.5V3.5h6v1M9 11h6M9 15h4" />
  </>
);
const bilet = (
  <>
    <path d="M3.5 8a2 2 0 0 0 0 4v0a2 2 0 0 1 0 4V18a1.5 1.5 0 0 0 1.5 1.5h14A1.5 1.5 0 0 0 20.5 18v-2a2 2 0 0 1 0-4 2 2 0 0 0 0-4V6A1.5 1.5 0 0 0 19 4.5H5A1.5 1.5 0 0 0 3.5 6z" />
    <path d="M14.5 5v14" strokeDasharray="2 2.2" />
  </>
);
const bina = (
  <>
    <path d="M4 21V5.5A1.5 1.5 0 0 1 5.5 4h7A1.5 1.5 0 0 1 14 5.5V21M14 10h4.5A1.5 1.5 0 0 1 20 11.5V21M2.5 21h19" />
    <path d="M7.5 8h3M7.5 12h3M7.5 16h3" />
  </>
);
const sinyal = (
  <>
    <path d="M5 18v-2M9.5 18v-5M14 18v-8M18.5 18V6" />
  </>
);
const anahtarAlet = (
  <path d="M14.5 6.5a4 4 0 0 0 5 5L13 18a2.1 2.1 0 0 1-3-3l6.5-6.5a4 4 0 0 1-2-2zM5.5 18.5l2-2" />
);
const genel = (
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M8.5 12h7" />
  </>
);

const TABLO: Record<string, Cizim> = {
  '📦': kutu,
  '🗺️': harita,
  '🗺': harita,
  '🧭': pusula,
  '👥': kisiler,
  '📄': belge,
  '✓': tamam,
  '✅': tamam,
  '📍': konum,
  '🔒': kilit,
  '☎️': telefon,
  '☎': telefon,
  '📭': posta,
  '🎉': yildiz,
  '⚠️': uyari,
  '⚠': uyari,
  '🔁': yenile,
  '📋': pano,
  '🎫': bilet,
  '🏗️': bina,
  '🏗': bina,
  '📶': sinyal,
  '🛠️': anahtarAlet,
  '🛠': anahtarAlet,
};

export function cizgiSimge(simge: ReactNode, boyut = 28): ReactNode {
  if (typeof simge !== 'string') return simge;
  const cizim = TABLO[simge.trim()] ?? genel;
  return (
    <svg
      width={boyut}
      height={boyut}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {cizim}
    </svg>
  );
}
