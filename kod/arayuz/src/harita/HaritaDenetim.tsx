/**
 * Harita denetimleri — iki haritada (yönetici ve satışçı) aynı parçalar:
 *   · Altlık seçici: Harita · Uydu · Sade
 *   · 3B düğmesi
 *   · Mercek seçici (3B'de binaların rengi neyi anlatsın) ve lejantı
 *   · Atıf (karo sağlayıcısının adı; lisans gereği görünür durur)
 */

import type { ReactNode } from 'react';
import type { AltlikDurumu, AltlikKipi } from './altlik';
import { MERCEK_ADLARI, MERCEKLER, type Boyama, type Mercek } from './ikiz';
import './harita.css';

const ALTLIK_ADLARI: Record<AltlikKipi, string> = {
  harita: 'Harita',
  uydu: 'Uydu',
  sade: 'Sade',
};

const ALTLIK_ACIKLAMA: Record<AltlikKipi, string> = {
  harita: 'Sokak haritası (yakınlaştırınca sokak ve bina adları)',
  uydu: 'Uydu görüntüsü',
  sade: 'Yalnız yollar — internet gerektirmez',
};

export function AltlikSecici({
  kip,
  degisti,
  buyuk = false,
}: {
  kip: AltlikKipi;
  degisti: (k: AltlikKipi) => void;
  /** Telefon: parmakla rahat basılacak boy. */
  buyuk?: boolean;
}) {
  return (
    <div className={`hr-segment${buyuk ? ' buyuk' : ''}`} role="group" aria-label="Harita altlığı">
      {(['harita', 'uydu', 'sade'] as AltlikKipi[]).map((k) => (
        <button
          key={k}
          type="button"
          className={kip === k ? 'secili' : undefined}
          aria-pressed={kip === k}
          title={ALTLIK_ACIKLAMA[k]}
          onClick={() => degisti(k)}
        >
          {ALTLIK_ADLARI[k]}
        </button>
      ))}
    </div>
  );
}

function Kup({ boyut = 18 }: { boyut?: number }) {
  return (
    <svg
      width={boyut}
      height={boyut}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M12 2.8 20 7.3v9.4l-8 4.5-8-4.5V7.3z" />
      <path d="M4 7.3 12 12l8-4.7M12 12v9.2" />
    </svg>
  );
}

export function UcBDugmesi({
  acik,
  degisti,
  hazirlaniyor = false,
  devreDisi = false,
  yuvarlak = false,
}: {
  acik: boolean;
  degisti: (acik: boolean) => void;
  hazirlaniyor?: boolean;
  devreDisi?: boolean;
  /** Telefon: 56 px yuvarlak düğme (konum düğmesinin kardeşi). */
  yuvarlak?: boolean;
}) {
  const etiket = acik ? '3B görünümü kapat' : '3B görünüm: binaları katlarıyla göster';
  return (
    <button
      type="button"
      className={`${yuvarlak ? 'hr-uc-yuvarlak' : 'hr-uc'}${acik ? ' acik' : ''}`}
      aria-pressed={acik}
      aria-label={etiket}
      title={devreDisi ? 'Kutu çizerken harita düz kalır' : etiket}
      disabled={devreDisi}
      onClick={() => degisti(!acik)}
    >
      {hazirlaniyor ? <span className="hr-donen" aria-hidden="true" /> : <Kup boyut={yuvarlak ? 22 : 17} />}
      <span>3B</span>
    </button>
  );
}

export function MercekSecici({
  mercek,
  degisti,
  buyuk = false,
}: {
  mercek: Mercek;
  degisti: (m: Mercek) => void;
  buyuk?: boolean;
}) {
  return (
    <div className={`hr-segment mercek${buyuk ? ' buyuk' : ''}`} role="group" aria-label="Binaların rengi">
      {MERCEKLER.map((m) => (
        <button
          key={m}
          type="button"
          className={mercek === m ? 'secili' : undefined}
          aria-pressed={mercek === m}
          onClick={() => degisti(m)}
        >
          {MERCEK_ADLARI[m]}
        </button>
      ))}
    </div>
  );
}

/** Lejantta sınıfların önüne yazılan birim (Durum merceğinde gerekmez). */
const MERCEK_BIRIMI: Record<Mercek, string | null> = {
  durum: null,
  firsat: 'Boş kapı',
  doluluk: 'Doluluk',
  is_emri: 'Açık iş emri',
};

export function MercekLejanti({
  mercek,
  boyama,
  temsili,
  sikisik = false,
  secici,
  yalnizSecici = false,
}: {
  mercek: Mercek;
  boyama: Boyama;
  /** Taban çizgisi olmayan (temsili gövdeyle çizilen) bina sayısı. */
  temsili: number;
  sikisik?: boolean;
  /** Lejantın başına konan mercek seçici (yönetici haritası). */
  secici?: ReactNode;
  /** Yer darken (bina kartı açık) yalnız seçici gösterilir. */
  yalnizSecici?: boolean;
}) {
  const birim = MERCEK_BIRIMI[mercek];
  return (
    <div className={`hr-lejant${sikisik ? ' sikisik' : ''}`}>
      {secici ? (
        <div className="hr-lejant-ust">
          {secici}
          {!yalnizSecici ? <span className="hr-lejant-not">Yükseklik = kat sayısı</span> : null}
        </div>
      ) : null}
      {!yalnizSecici ? (
        <>
          <div className="hr-lejant-siniflar">
            {birim && boyama.siniflar.length ? <span className="hr-birim">{birim}</span> : null}
            {boyama.siniflar.map((s) => (
              <span key={s.etiket} className="hr-sinif">
                <span
                  className="hr-kutu"
                  style={{ background: `rgb(${s.renk[0]},${s.renk[1]},${s.renk[2]})` }}
                />
                {s.etiket}
                <b>{s.adet.toLocaleString('tr-TR')}</b>
              </span>
            ))}
            {!secici ? <span className="hr-lejant-not">Yükseklik = kat</span> : null}
          </div>
          {boyama.not ? <div className="hr-lejant-uyari">{boyama.not}</div> : null}
          {temsili ? (
            <div className="hr-lejant-uyari">
              {temsili.toLocaleString('tr-TR')} binanın taban çizgisi yok; temsili gövdeyle çizildi.
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

/** Sağ alt köşedeki küçük atıf satırı. Karo yoksa sade haritaya düşüldüğünü söyler. */
export function Atif({
  metin,
  durum,
  ortulu = false,
}: {
  metin: string | null;
  durum: AltlikDurumu;
  /** Ekrandaki alan önceden indirilmiş karolarla tam örtülü mü? */
  ortulu?: boolean;
}) {
  const not =
    durum === 'cevrimdisi'
      ? ortulu
        ? 'Çevrimdışı · önceden yüklenen harita'
        : 'Çevrimdışı · sade harita'
      : durum === 'ulasilamiyor'
        ? 'Altlık yüklenemedi · sade harita'
        : null;
  if (!metin && !not) return null;
  return <div className={`hr-atif${not ? ' uyari' : ''}`}>{not ?? metin}</div>;
}
