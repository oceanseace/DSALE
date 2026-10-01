/**
 * Keşif ikonları — satır içi SVG (ikon kütüphanesi kurulu değil).
 * Hepsi 24×24 kutuda, `currentColor` konturlu; boyut tasarım pikseli cinsindendir.
 */
import type { CSSProperties, ReactNode } from 'react';
import { u } from '../ui/tema';

const YOLLAR: Record<string, ReactNode> = {
  /* 3B küp */
  kup: (
    <>
      <path d="M12 3 20.5 7.5v9L12 21 3.5 16.5v-9Z" />
      <path d="M3.5 7.5 12 12l8.5-4.5M12 12v9" />
    </>
  ),
  /* 2B düz plan */
  duz: (
    <>
      <path d="M3 8.5 12 4l9 4.5-9 4.5Z" />
      <path d="M3 13.5 12 18l9-4.5" />
    </>
  ),
  /* binalar */
  bina: (
    <>
      <path d="M4 21V9.5L10 6v15" />
      <path d="M10 21V11l8-3.5V21" />
      <path d="M2.5 21h19" />
      <path d="M13.5 11.5v2M13.5 16v2M6.8 11.5v2M6.8 16v2" />
    </>
  ),
  /* bölge sınırı */
  sinir: (
    <>
      <path d="M4.5 6.5 10 4l5 2.5L19.5 4v13.5L15 20l-5-2.5-5.5 2.5Z" />
      <path d="M10 4v13.5M15 6.5V20" />
    </>
  ),
  /* ısı sütunları */
  sutun: (
    <>
      <path d="M4 21v-6M9.3 21V9M14.7 21v-9M20 21V5" />
      <path d="M2.5 21h19" />
    </>
  ),
  /* yollar */
  yol: (
    <>
      <path d="M8 3 5 21M16 3l3 18" />
      <path d="M12 4v3M12 10.5v3M12 17v3" />
    </>
  ),
  /* ofis / merkez */
  ofis: (
    <>
      <path d="M12 21s7-6.2 7-11a7 7 0 1 0-14 0c0 4.8 7 11 7 11Z" />
      <circle cx="12" cy="10" r="2.6" />
    </>
  ),
  /* arama */
  ara: (
    <>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="m15.4 15.4 4.6 4.6" />
    </>
  ),
  /* başa dön */
  basaDon: (
    <>
      <circle cx="12" cy="12" r="7.5" />
      <path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3" />
      <circle cx="12" cy="12" r="2" />
    </>
  ),
  /* dosya aç */
  dosya: (
    <>
      <path d="M3.5 19V6.5a1 1 0 0 1 1-1h4.2l2 2.4h8.8a1 1 0 0 1 1 1V19a1 1 0 0 1-1 1h-15a1 1 0 0 1-1-1Z" />
      <path d="M12 16.5v-6M9.2 13l2.8-2.8 2.8 2.8" />
    </>
  ),
  /* tam ekran */
  tamEkran: (
    <>
      <path d="M4 9V4.5h4.5M20 9V4.5h-4.5M4 15v4.5h4.5M20 15v4.5h-4.5" />
    </>
  ),
  /* sunuma dön */
  sunum: (
    <>
      <path d="M3.5 4.5h17v11h-17Z" />
      <path d="M12 15.5V20M8.5 20h7" />
      <path d="m10.3 8 3.9 2.1-3.9 2.1Z" />
    </>
  ),
  kapat: <path d="m6 6 12 12M18 6 6 18" />,
  /* mahalle (arama sonucu türü) */
  mahalle: (
    <>
      <path d="M3.5 20.5h17" />
      <path d="M5.5 20.5V10L12 5.5 18.5 10v10.5" />
      <path d="M10 20.5v-5h4v5" />
    </>
  ),
  site: (
    <>
      <path d="M3.5 20.5h17" />
      <path d="M5 20.5V8l4.5-3v15.5M13 20.5V11l6-2.5v12" />
    </>
  ),
  ok: <path d="m9 5 7 7-7 7" />,
};

export type IkonAdi = keyof typeof YOLLAR;

export interface IkonProps {
  ad: IkonAdi;
  /** tasarım pikseli (varsayılan 24) */
  boyut?: number;
  kalinlik?: number;
  style?: CSSProperties;
}

export function Ikon({ ad, boyut = 24, kalinlik = 1.7, style }: IkonProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={u(boyut)}
      height={u(boyut)}
      fill="none"
      stroke="currentColor"
      strokeWidth={kalinlik}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ flex: '0 0 auto', ...style }}
      aria-hidden
    >
      {YOLLAR[ad]}
    </svg>
  );
}

export default Ikon;
