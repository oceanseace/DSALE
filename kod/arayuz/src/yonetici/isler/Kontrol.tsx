/**
 * Kontrol gerekli (§6.5, F4, F5): yalnız gerçek sorunlar; her satırda düz
 * Türkçe neden ve o nedene uygun eylemler.
 *
 *   il_disi        "Adres İzmir yazıyor…"      → Öbeğe ata · Mahalleyi seç · Merkeze gönderildi
 *   mahalle_yok    "Adreste mahalle yok."      → Mahalleyi seç · Öbeğe ata
 *   mahalle_benzer "'Taşliman' … 'Taşlimanı'"  → Aynı mahalle · Yeni mahalle · Öbeğe ata
 *   obeksiz        "Mahallesi hiçbir öbekte…"  → Bu mahalleyi bir öbeğe ekle · Yalnız bu işi taşı
 *   altyapi_supheli "Teknisyen altyapı…"       → Ticket'a bağla · Yeniden ata
 *
 * "Öbeğe ata" işe elle öbek yazar (sonraki raporlarda korunur, satırda "elle");
 * "Bu mahalleyi bir öbeğe ekle" mahallenin kendisini ekler: bundan sonra o
 * mahalleden gelen her iş kendiliğinden oraya düşer.
 */

import { useState } from 'react';
import {
  esadEkle,
  hataMetni,
  mahalleAra,
  mahalleEkle,
  mahalleSec,
  obegeAta,
  obekMahalleEkle,
} from '../../is/api';
import type { IsSatir, MahalleKaydi, Obek } from '../../is/tipler';
import { katla } from '../../ortak/ara';
import { Panel } from '../../ortak/Panel';
import { useBildirim } from '../../ortak/Bildirim';
import { BosDurum } from '../../ortak/Bos';
import { SureHapi } from '../../ortak/SureHapi';
import { MahalleSecici } from '../obekler/MahalleSecici';
import { useIsler } from './depo';
import { kalanDk } from './IsSatiri';
import { ObekSecici, yerMetni } from './parcalar';

type Islem =
  | { tur: 'obek-is'; s: IsSatir }
  | { tur: 'obek-mahalle'; s: IsSatir; mahalle: MahalleKaydi }
  | { tur: 'mahalle'; s: IsSatir };

export function KontrolListesi({ isler, ac }: { isler: IsSatir[]; ac: (isNo: string, gorunum?: string) => void }) {
  const depo = useIsler();
  const bildirim = useBildirim();
  const [islem, setIslem] = useState<Islem | null>(null);
  const [bekliyor, setBekliyor] = useState<string | null>(null);

  const kontrol = isler.filter((x) => x.durum === 'triyaj');

  const calistir = async (isNo: string, fn: () => Promise<void>) => {
    setBekliyor(isNo);
    try {
      await fn();
    } catch (e) {
      bildirim.goster(hataMetni(e), 'uyari');
    } finally {
      setBekliyor(null);
    }
  };

  /** Mahallenin sözlük kaydı (birebir ad); yoksa null. */
  const mahalleBul = async (s: IsSatir): Promise<{ tam: MahalleKaydi | null; benzer: { id: number; ad: string } | null }> => {
    const y = await mahalleAra({ q: s.mahalle ?? '', il: s.il ?? undefined, ilce: s.ilce ?? undefined, limit: 20 });
    const tam = y.mahalleler.find((m) => katla(m.ad) === katla(s.mahalle)) ?? null;
    const benzer = y.oneriler[0] ? { id: y.oneriler[0].id, ad: y.oneriler[0].ad } : null;
    return { tam, benzer };
  };

  const ayniMahalle = (s: IsSatir) =>
    calistir(s.is_no, async () => {
      const { benzer } = await mahalleBul(s);
      if (!benzer) {
        bildirim.goster('Benzer mahalle bulunamadı; “Mahalleyi seç” ile seçin.', 'uyari');
        setIslem({ tur: 'mahalle', s });
        return;
      }
      const y = await esadEkle({ il: s.il ?? undefined, ilce: s.ilce ?? undefined, esad: s.mahalle ?? '', mahalle_id: benzer.id });
      bildirim.goster(
        `“${s.mahalle}” artık ${benzer.ad} sayılacak${y.etkilenen_is ? ` · ${y.etkilenen_is} iş öbeğine düştü` : ''}.`,
        'basari',
      );
      void depo.tazele();
    });

  const yeniMahalle = (s: IsSatir) =>
    calistir(s.is_no, async () => {
      if (!s.il || !s.ilce || !s.mahalle) {
        setIslem({ tur: 'mahalle', s });
        return;
      }
      const y = await mahalleEkle({ il: s.il, ilce: s.ilce, ad: s.mahalle, benzerine_ragmen: true });
      bildirim.goster(`${y.mahalle.ad} mahalle listesine eklendi. Şimdi bir öbeğe ekleyin.`, 'basari');
      setIslem({ tur: 'obek-mahalle', s, mahalle: y.mahalle });
      void depo.tazele();
    });

  const mahalleyiObegeEkle = (s: IsSatir) =>
    calistir(s.is_no, async () => {
      const { tam } = await mahalleBul(s);
      if (!tam) {
        if (s.il && s.ilce && s.mahalle) {
          const y = await mahalleEkle({ il: s.il, ilce: s.ilce, ad: s.mahalle, benzerine_ragmen: true }).catch(() => null);
          if (y) {
            setIslem({ tur: 'obek-mahalle', s, mahalle: y.mahalle });
            return;
          }
        }
        bildirim.goster('Mahalle sözlükte bulunamadı; “Yalnız bu işi taşı” kullanın.', 'uyari');
        return;
      }
      setIslem({ tur: 'obek-mahalle', s, mahalle: tam });
    });

  const obekSecildi = async (o: Obek) => {
    if (!islem) return;
    const s = islem.s;
    if (islem.tur === 'obek-is') {
      await calistir(s.is_no, async () => {
        const y = await obegeAta(s.is_no, o.id, s.surum);
        depo.isYaz(y);
        bildirim.goster(`İş ${o.ad} öbeğine alındı (elle; sonraki raporlarda korunur).`, 'basari');
      });
    } else if (islem.tur === 'obek-mahalle') {
      const m = islem.mahalle;
      await calistir(s.is_no, async () => {
        const y = await obekMahalleEkle(o.id, { mahalle_idler: [m.id], tasi: true, surum: depo.obekler?.surum ?? 0 });
        depo.obekleriYaz(y.obekler, y.surum);
        void depo.tazele();
        bildirim.goster(
          `${m.ad} artık ${o.ad} öbeğinde${y.etkilenen_is ? ` · ${y.etkilenen_is} iş oraya düştü` : ''}. Bundan sonra gelen işler de oraya düşer.`,
          'basari',
        );
      });
    }
    setIslem(null);
  };

  if (!kontrol.length) {
    return (
      <BosDurum simge="✓" baslik="Bütün işler öbeğinde." aciklama="Kontrol gereken iş yok. Yeni rapor gelince bakılması gerekenler burada olur." kucuk />
    );
  }

  return (
    <>
      <div className="ip-kontrol" role="list" aria-label="Kontrol gerekli işler">
        {kontrol.map((s) => {
          const n = s.triyaj_nedeni;
          const kilit = bekliyor === s.is_no;
          const d = (etiket: string, fn: () => void, birincil = false) => (
            <button type="button" className={`o-dugme kucuk${birincil ? '' : ' metin'}`} disabled={kilit} onClick={fn}>
              {etiket}
            </button>
          );
          return (
            <div key={s.is_no} className="ip-kontrol-satir" role="listitem">
              <button type="button" className="ip-kontrol-bas" onClick={() => ac(s.is_no)}>
                <SureHapi kalan_dk={kalanDk(s)} renk={s.renk} gecikti={s.gecikti} kucuk />
                <span className="task">{s.task_adi}</span>
                <span className="yer">{[s.musteri_adi, yerMetni(s)].filter(Boolean).join(' · ')}</span>
              </button>
              <p className="neden">{s.triyaj_metni ?? 'Öbeği bulunamadı.'}</p>
              <div className="eylemler">
                {n === 'il_disi' ? (
                  <>
                    {d('Öbeğe ata', () => setIslem({ tur: 'obek-is', s }), true)}
                    {d('Mahalleyi seç', () => setIslem({ tur: 'mahalle', s }))}
                    {d('Merkeze gönderildi', () => ac(s.is_no, 'merkeze'))}
                  </>
                ) : n === 'mahalle_yok' ? (
                  <>
                    {d('Mahalleyi seç', () => setIslem({ tur: 'mahalle', s }), true)}
                    {d('Öbeğe ata', () => setIslem({ tur: 'obek-is', s }))}
                  </>
                ) : n === 'mahalle_benzer' ? (
                  <>
                    {d('Aynı mahalle', () => void ayniMahalle(s), true)}
                    {d('Yeni mahalle', () => void yeniMahalle(s))}
                    {d('Öbeğe ata', () => setIslem({ tur: 'obek-is', s }))}
                  </>
                ) : n === 'obeksiz' ? (
                  <>
                    {d('Bu mahalleyi bir öbeğe ekle', () => void mahalleyiObegeEkle(s), true)}
                    {d('Yalnız bu işi taşı', () => setIslem({ tur: 'obek-is', s }))}
                  </>
                ) : n === 'altyapi_supheli' ? (
                  <>
                    {d('Ticket’a bağla', () => ac(s.is_no, 'ticket'), true)}
                    {d('Yeniden ata', () => ac(s.is_no, 'teknik'))}
                  </>
                ) : (
                  d('Öbeğe ata', () => setIslem({ tur: 'obek-is', s }), true)
                )}
              </div>
            </div>
          );
        })}
      </div>

      <Panel
        acik={Boolean(islem && islem.tur !== 'mahalle')}
        kapat={() => setIslem(null)}
        baslik={islem?.tur === 'obek-mahalle' ? `${islem.mahalle.ad} hangi öbeğe?` : 'Hangi öbeğe?'}
        altBaslik={
          islem?.tur === 'obek-mahalle'
            ? 'Mahalle öbeğe eklenir; bundan sonra oradan gelen işler de oraya düşer.'
            : 'Yalnız bu iş taşınır (elle); mahalle öbeksiz kalır.'
        }
      >
        {islem && islem.tur !== 'mahalle' ? (
          <ObekSecici obekler={depo.obekler?.obekler ?? []} sec={(o) => void obekSecildi(o)} />
        ) : null}
      </Panel>

      <Panel
        acik={islem?.tur === 'mahalle'}
        kapat={() => setIslem(null)}
        baslik="Mahalleyi seçin"
        altBaslik={islem?.tur === 'mahalle' && islem.s.triyaj_metni ? islem.s.triyaj_metni : undefined}
      >
        {islem?.tur === 'mahalle' ? (
          <MahalleSecici
            tek
            baslangicSorgu={islem.s.mahalle ?? ''}
            ilce={islem.s.il && islem.s.ilce ? { il: islem.s.il, ilce: islem.s.ilce } : null}
            tekSec={(m) => {
              const s = islem.s;
              setIslem(null);
              void calistir(s.is_no, async () => {
                const y = await mahalleSec(s.is_no, m.id, s.surum);
                depo.isYaz(y);
                bildirim.goster(
                  y.durum === 'triyaj' ? `Mahalle: ${m.ad}. Bu mahalle henüz bir öbekte değil.` : `Mahalle: ${m.ad} · ${y.obek?.ad ?? ''} öbeğine düştü.`,
                  y.durum === 'triyaj' ? 'uyari' : 'basari',
                );
              });
            }}
          />
        ) : null}
      </Panel>
    </>
  );
}
