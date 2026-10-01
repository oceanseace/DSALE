/**
 * Süre hapı: bir işin sözüne ne kaldığı (§7.3).
 *
 * Renk sunucudan gelir (`renk`: yeşil < %50 · amber %50–80 · kırmızı ≥ %80,
 * gecikti). Yalnız renge güvenilmez: gecikmede metin ve simge de değişir
 * (renk körü kullanıcı ve siyah-beyaz çıktı için).
 */

import { kabaSure, sureMetni } from './sure';
import './bilesen.css';

export type SureRengi = 'yesil' | 'amber' | 'kirmizi';

export function SureHapi({
  kalan_dk,
  renk,
  gecikti = false,
  kucuk = false,
  onEk,
}: {
  kalan_dk: number;
  renk: SureRengi;
  gecikti?: boolean;
  kucuk?: boolean;
  /** Metnin önüne ("BTK", "24 s"). */
  onEk?: string;
}) {
  const metin = gecikti ? `Gecikti · ${kabaSure(kalan_dk)}` : sureMetni(kalan_dk);
  return (
    <span
      className={`o-sure ${gecikti ? 'kirmizi gecikti' : renk}${kucuk ? ' kucuk' : ''}`}
      title={gecikti ? `Süre ${sureMetni(kalan_dk)} önce doldu` : `Kalan süre: ${sureMetni(kalan_dk)}`}
    >
      {gecikti ? (
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" aria-hidden="true">
          <path d="M12 7v6M12 17h.01" strokeLinecap="round" />
        </svg>
      ) : (
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden="true">
          <circle cx="12" cy="12" r="8.5" />
          <path d="M12 7.5V12l3 2" strokeLinecap="round" />
        </svg>
      )}
      {onEk ? <span className="on-ek">{onEk}</span> : null}
      <span>{metin}</span>
    </span>
  );
}
