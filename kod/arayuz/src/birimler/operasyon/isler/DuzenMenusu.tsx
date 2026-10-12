/**
 * TASKS araç çubuğundaki "Düzen ▾": kişinin Excel düzenleri (sunucuda; kişiyi bilgisayardan bilgisayara izler).
 *   · Hazır: "Varsayılan" (fabrika) · "TV ekibi" … · unvanın varsayılanı (Administrator verdiyse).
 *   · Kayıtlı: kişinin adlı düzenleri ("Superbox", "Fiber kurulum" …); seç = uygula, ✕ = sil.
 *   · "Şu anki düzeni kaydet": ad + isteğe bağlı "süzgeçlerle" (uygulanınca ortak süzgeç de gelir).
 *   · Administrator: şu anki düzeni bir unvanın varsayılanı yapar / kaldırır.
 * Durum: tercihDeposu.ts. Kim: Isler.tsx.
 */

import { useCallback, useRef, useState } from 'react';
import { hataMetni } from '../../../cekirdek/is/api';
import { useBildirim } from '../../../cekirdek/ortak/Bildirim';
import { Kapat } from '../../../cekirdek/ortak/Ikon';
import { useDisariKapat, useEkranaSigdir } from './acilir';
import type { SutunDuzeni } from './sutunDuzeni';
import { VARSAYILAN_GORUNEN } from './sutunlar';
import { duzenKaydet, duzenOku, duzenSil, duzenUygula, unvanVarsayilaniYaz, useTercih, type Duzen } from './tercihDeposu';

export function DuzenMenusu({ duzen }: { duzen: SutunDuzeni }) {
  const t = useTercih();
  const bildirim = useBildirim();
  const [acik, setAcik] = useState(false);
  const [ad, setAd] = useState('');
  const [suzgecle, setSuzgecle] = useState(false);
  const [unvanId, setUnvanId] = useState<number | ''>('');
  const [gidiyor, setGidiyor] = useState(false);
  const kok = useRef<HTMLDivElement>(null);
  const kapat = useCallback(() => setAcik(false), []);
  useDisariKapat(kok, kapat, acik);
  const acilirRef = useRef<HTMLDivElement>(null);
  useEkranaSigdir(acilirRef, acik);

  const uygula = (adi: string | null, d: Duzen) => {
    duzenUygula(adi, { ...d, bilinen: d.bilinen ?? VARSAYILAN_GORUNEN });
    setAcik(false);
  };
  const kaydet = () => {
    const a = ad.trim();
    if (!a) return;
    if (t.fabrika.some((f) => f.ad.toLocaleLowerCase('tr-TR') === a.toLocaleLowerCase('tr-TR'))) {
      bildirim.goster(`“${a}” hazır bir düzenin adı; başka ad verin.`, 'uyari');
      return;
    }
    duzenKaydet(a, suzgecle);
    setAd('');
    bildirim.goster(`“${a}” düzeni kaydedildi.`, 'basari');
  };
  const unvanYaz = async (kaldir: boolean) => {
    if (unvanId === '') return;
    setGidiyor(true);
    try {
      await unvanVarsayilaniYaz(unvanId, kaldir);
      const u = t.unvanlar.find((x) => x.id === unvanId)?.ad ?? 'Unvan';
      bildirim.goster(kaldir ? `${u}: varsayılan düzen kaldırıldı.` : `${u}: şu anki düzen varsayılan yapıldı.`, 'basari');
    } catch (e) {
      bildirim.goster(hataMetni(e), 'uyari');
    } finally {
      setGidiyor(false);
    }
  };

  const unvanDuzeni = duzenOku(t.unvan?.duzen);
  const etiket = duzen.ad ? `Düzen: ${duzen.ad}${duzen.degisti ? ' *' : ''}` : 'Düzen';
  const satir = (anahtar: string, adi: string, d: Duzen, not?: string, sil?: () => void) => (
    <div key={anahtar} className="xg-duzen-satir">
      <button
        type="button"
        className={`xg-menu-satir${duzen.ad === adi && !duzen.degisti ? ' secili' : ''}`}
        title={d.suzgec ? 'Uygulanınca süzgeçler de değişir' : undefined}
        onClick={() => uygula(adi, d)}
      >
        <span className="xg-deger-ad">{adi}</span>
        <span className="xg-sayi">
          {not ? `${not} · ` : ''}
          {d.gorunen.length} sütun{d.suzgec ? ' · süzgeçli' : ''}
        </span>
      </button>
      {sil ? (
        <button type="button" className="xg-duzen-sil" aria-label={`${adi} düzenini sil`} title="Sil" onClick={sil}>
          <Kapat boyut={12} kalinlik={2} />
        </button>
      ) : null}
    </div>
  );

  return (
    <div className="xg-bolunmus" ref={kok}>
      <button
        type="button"
        className={`xg-arac-dugme${duzen.ad ? ' etkin' : ''}`}
        aria-expanded={acik}
        title="Kayıtlı Excel düzenleri: sütunlar, sıra, genişlik, yakınlaştırma (hesabınızla her bilgisayarda)"
        onClick={() => setAcik((a) => !a)}
      >
        {etiket} ▾
      </button>
      {acik ? (
        <div ref={acilirRef} className="xg-acilir xg-ozel xg-duzen" role="dialog" aria-label="Düzenler">
          <div className="xg-menu-etiket">Hazır</div>
          <button type="button" className="xg-menu-satir" onClick={() => { duzen.varsayilan(); setAcik(false); }}>
            <span className="xg-deger-ad">Varsayılana dön</span>
            <span className="xg-sayi">fabrika</span>
          </button>
          {unvanDuzeni ? satir('unvan', `${t.unvan?.ad ?? 'Unvan'} varsayılanı`, unvanDuzeni, 'unvan') : null}
          {t.fabrika.map((f) => satir(`f:${f.ad}`, f.ad, f.duzen, 'hazır'))}
          <hr />
          <div className="xg-menu-etiket">Kayıtlı düzenlerim</div>
          {t.duzenler.map((x) => satir(`k:${x.ad}`, x.ad, x.duzen, undefined, () => duzenSil(x.ad)))}
          {!t.duzenler.length ? <div className="xg-not">Henüz kayıtlı düzen yok.</div> : null}
          <div className="xg-ozel-kaydet">
            <input
              className="o-girdi kucuk"
              value={ad}
              maxLength={60}
              placeholder="Şu anki düzeni kaydet: ad"
              onChange={(o) => setAd(o.target.value)}
              onKeyDown={(o) => o.key === 'Enter' && kaydet()}
            />
            <button type="button" className="o-dugme kucuk vurgu" disabled={!ad.trim()} onClick={kaydet}>
              Kaydet
            </button>
          </div>
          <label className="xg-sutun-sec">
            <input type="checkbox" checked={suzgecle} onChange={(o) => setSuzgecle(o.target.checked)} />
            <span>Süzgeçleri de kaydet</span>
          </label>
          {t.administrator && t.unvanlar.length ? (
            <>
              <hr />
              <div className="xg-menu-etiket">Unvan varsayılanı (Administrator)</div>
              <div className="xg-ozel-kaydet">
                <select
                  className="o-girdi kucuk"
                  value={unvanId}
                  aria-label="Unvan"
                  onChange={(o) => setUnvanId(o.target.value ? Number(o.target.value) : '')}
                >
                  <option value="">Unvan seçin…</option>
                  {t.unvanlar.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.ad}
                      {u.duzen ? ' ✓' : ''}
                    </option>
                  ))}
                </select>
                <button type="button" className="o-dugme kucuk" disabled={unvanId === '' || gidiyor} onClick={() => void unvanYaz(false)}>
                  Şu anki düzeni ata
                </button>
              </div>
              {unvanId !== '' && t.unvanlar.find((u) => u.id === unvanId)?.duzen ? (
                <button type="button" className="xg-menu-satir" disabled={gidiyor} onClick={() => void unvanYaz(true)}>
                  Bu unvanın varsayılanını kaldır
                </button>
              ) : null}
              <div className="xg-not">Kendi düzeni olmayan kişi unvanının varsayılanıyla başlar.</div>
            </>
          ) : null}
          {t.sunucu === 'hata' ? <div className="xg-not">Sunucuya ulaşılamadı; değişiklikler bu bilgisayarda tutuluyor.</div> : null}
        </div>
      ) : null}
    </div>
  );
}
