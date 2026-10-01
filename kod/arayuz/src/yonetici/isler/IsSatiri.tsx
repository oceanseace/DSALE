/**
 * İş satırı (§6.1 "Liste"): 72 px, üç bilgi satırı ve EN ÇOK BİR eylem.
 *
 *   1. Kalan süre hapı (renk + yazı) · BTK · task adı
 *   2. Müşteri (yetkiye göre) · mahalle · kısa adres (◌ konum yaklaşıksa)
 *   3. Durum (nötr, nokta) · "geleli N dk" · randevu (teyitliyse ✓) · teknisyen · rozetler
 *
 * Eylem: Kontrol → [Öbeğe ata] · önerisi olan atanmamış → [Onayla] · önerisiz
 * atanmamış → [Ata] · diğerleri → yok (satır tıklanır).
 */

import { memo, type KeyboardEvent } from 'react';
import type { IsSatir } from '../../is/tipler';
import { DURUM_ETIKET } from '../../is/tipler';
import { SureHapi } from '../../ortak/SureHapi';
import { Rozet, Hap, type RozetTuru } from '../../ortak/Rozet';
import { DurumYazisi, type NoktaRengi } from '../../ortak/Durum';
import { Kbd } from '../../ortak/Kbd';
import { beklemeRengi, dilimMetni, kisaAd, yerMetni } from './parcalar';

export type SatirEylemi = 'obege_ata' | 'onayla' | 'ata';

export function satirEylemi(s: IsSatir): SatirEylemi | null {
  if (s.durum === 'triyaj') return 'obege_ata';
  if (s.kova !== 'atanmadi') return null;
  if (s.oneri) return 'onayla';
  return 'ata';
}

const DURUM_RENGI: Partial<Record<IsSatir['durum'], NoktaRengi>> = {
  triyaj: 'amber',
  bekliyor: 'gri',
  randevulu: 'mor',
  atandi: 'mavi',
  yolda: 'mavi',
  sahada: 'mavi',
  ulasilamadi: 'amber',
  askida: 'gri',
  altyapi: 'amber',
  merkeze: 'gri',
  cozuldu: 'yesil',
  kapandi: 'yesil',
};

/** BTK işinde kalan süre BTK hedefinden (askıda durmuş saat dahil); diğerlerinde 24 saat. */
export function kalanDk(s: IsSatir): number {
  return s.serit === 'BTK' && s.btk_kalan_dk !== null && s.btk_kalan_dk !== undefined ? s.btk_kalan_dk : s.kalan_dk;
}

const GORUNUR_ROZET: RozetTuru[] = ['ticket', 'tekrar', 'bayi', 'global', 'boss_islenecek', 'boss_acik', 'yeniden', 'elle'];

function IsSatiriIc({
  s,
  secili,
  imlecte,
  ac,
  eylem,
  eylemKapali = false,
  kbd = false,
}: {
  s: IsSatir;
  secili: boolean;
  imlecte: boolean;
  ac: (isNo: string) => void;
  eylem: (s: IsSatir, e: SatirEylemi) => void;
  eylemKapali?: boolean;
  kbd?: boolean;
}) {
  const e = satirEylemi(s);
  const bekleme = beklemeRengi(s.bekleme_dk);
  const dilim = s.randevu ? dilimMetni(s.randevu.bas, s.randevu.bit) : '';
  const tus = (o: KeyboardEvent<HTMLDivElement>) => {
    if (o.key === 'Enter' && o.target === o.currentTarget) {
      o.preventDefault();
      ac(s.is_no);
    }
  };
  return (
    <div
      role="listitem"
      className={`ip-satir${secili ? ' secili' : ''}${imlecte ? ' imlec' : ''}${s.kotu_gecmis ? ' gri' : ''}`}
      data-is={s.is_no}
      tabIndex={-1}
      onClick={() => ac(s.is_no)}
      onKeyDown={tus}
      aria-current={secili ? 'true' : undefined}
    >
      <div className="ip-satir-govde">
        <div className="ip-satir-1">
          <SureHapi kalan_dk={kalanDk(s)} renk={s.renk} gecikti={s.gecikti} kucuk />
          {s.serit === 'BTK' ? <Rozet tur="btk" /> : null}
          {s.oncelik ? <Hap renk="kirmizi" baslik={s.oncelik}>Önce bu</Hap> : null}
          <span className="task">{s.task_adi}</span>
          {s.btk_durdu ? <span className="ip-durdu" title="Abone kaynaklı askıda BTK saati durur">saat durdu</span> : null}
        </div>
        <div className="ip-satir-2">
          {s.musteri_adi ? <span className="musteri">{s.musteri_adi}</span> : null}
          <span className="yer">
            {s.konum_yaklasik ? (
              <span className="ip-yaklasik" title="Konum yaklaşık: bina değil, mahalle/ilçe merkezi" aria-label="Konum yaklaşık">
                ◌{' '}
              </span>
            ) : null}
            {yerMetni(s)}
          </span>
        </div>
        <div className="ip-satir-3">
          <DurumYazisi etiket={DURUM_ETIKET[s.durum]} renk={DURUM_RENGI[s.durum]} />
          {s.bekleme_dk !== null && s.bekleme_dk !== undefined ? (
            <span className={`ip-bekleme${bekleme ? ` ${bekleme}` : ''}`}>
              {bekleme === 'kirmizi' ? '⏱ ' : ''}geleli {s.bekleme_dk.toLocaleString('tr-TR')} dk
            </span>
          ) : null}
          {dilim ? (
            <span className="ip-dilim" title={s.randevu?.kaynak === 'boss' ? 'BOSS’taki randevu' : 'Randevu'}>
              {s.randevu?.kaynak === 'boss' ? 'BOSS ' : ''}
              {dilim}
              {s.randevu?.teyitli ? ' ✓' : ''}
            </span>
          ) : null}
          {s.atanan ? <span className="ip-kisi">{kisaAd(s.atanan.ad)}</span> : null}
          {!s.atanan && s.oneri ? (
            <span className="ip-oneri" title={s.oneri.neden}>
              Öneri {kisaAd(s.oneri.teknik.ad)}
              {s.oneri.bas ? ` ${dilimMetni(s.oneri.bas, s.oneri.bit)}` : ''}
            </span>
          ) : null}
          {!s.atanan && !s.oneri && s.boss_ekip ? <span className="ip-boss-ekip">BOSS ekibi: {s.boss_ekip}</span> : null}
          {s.rozetler
            .filter((r) => GORUNUR_ROZET.includes(r as RozetTuru))
            .map((r) => (
              <Rozet key={r} tur={r as RozetTuru} />
            ))}
        </div>
      </div>
      {e ? (
        <div className="ip-satir-eylem">
          <button
            type="button"
            className="o-dugme kucuk"
            disabled={eylemKapali}
            onClick={(o) => {
              o.stopPropagation();
              eylem(s, e);
            }}
          >
            {e === 'obege_ata' ? 'Öbeğe ata' : e === 'onayla' ? 'Onayla' : 'Ata'}
            {e === 'onayla' && kbd ? <Kbd>O</Kbd> : null}
          </button>
        </div>
      ) : null}
    </div>
  );
}

export const IsSatiri = memo(IsSatiriIc);
