/**
 * Rapor — haftanın gidişatı, kapsama tablosu, günlük Excel.
 *
 * Haftalık eğilim sunucuda hazır bir uç olmadığı için son 7 günün gün özeti
 * tek tek (paralel) alınır; SQLite'ta bunlar milisaniyelik sorgulardır.
 */

import { useMemo, useState } from 'react';
import { useBildirim } from '../../ortak/Bildirim';
import { Takvim } from '../../ortak/Ikon';
import { sayi, yuzde } from '../../ortak/bicim';
import { bugunMetni, gunEkle, gunOzeti, kapsama, raporIndir } from '../api';
import { satiscilar, useYonetim } from '../depo';
import { Icerik, YonUst } from '../ortak/Kabuk';
import { bolgeNumaralari, useBolgeSayisi } from './bolge/bolgeSayisi';
import { HataKutusu, Iskelet, Kart, OranCubugu, Segment, useVeri } from '../ortak/parcalar';
import { Indir } from '../ortak/simgeler';

type Kirilim = 'bolge' | 'mahalle' | 'ilce';

const GUN_KISA = ['Paz', 'Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt'];

export function Rapor() {
  const { ekip } = useYonetim();
  const { goster } = useBildirim();
  const bugun = bugunMetni();
  const [tarih, setTarih] = useState(bugun);
  const [kirilim, setKirilim] = useState<Kirilim>('bolge');
  const [bolge, setBolge] = useState<number | null>(null);
  const bolgeSayisi = useBolgeSayisi();
  const [indiriliyor, setIndiriliyor] = useState(false);

  const gunler = useMemo(
    () => Array.from({ length: 7 }, (_, i) => gunEkle(bugun, i - 6)),
    [bugun],
  );

  const hafta = useVeri(
    () =>
      Promise.all(
        gunler.map((g) =>
          gunOzeti(g).then((y) => ({
            tarih: g,
            ziyaret: y.toplam.ziyaret,
            satis: y.toplam.satis,
            satis_adedi: y.toplam.satis_adedi,
          })),
        ),
      ),
    [gunler.join(',')],
  );

  const kapsamaVeri = useVeri(() => kapsama(kirilim, bolge), [kirilim, bolge]);

  const bolgeAdi = useMemo(() => {
    const m = new Map<number, string>();
    satiscilar(ekip).forEach((k) => {
      if (k.bolge) m.set(k.bolge, k.ad);
    });
    return m;
  }, [ekip]);

  const enYuksek = Math.max(1, ...(hafta.veri ?? []).map((g) => g.ziyaret));
  const haftaToplam = (hafta.veri ?? []).reduce(
    (t, g) => ({
      ziyaret: t.ziyaret + g.ziyaret,
      satis: t.satis + g.satis,
      adet: t.adet + g.satis_adedi,
    }),
    { ziyaret: 0, satis: 0, adet: 0 },
  );

  const indir = async () => {
    setIndiriliyor(true);
    try {
      const ad = await raporIndir(tarih);
      goster(`${ad} indirildi`, 'basari');
    } catch {
      goster('Rapor indirilemedi. Bağlantıyı kontrol edin.', 'uyari');
    } finally {
      setIndiriliyor(false);
    }
  };

  return (
    <>
      <YonUst baslik="Rapor" altYazi="Haftanın gidişatı, kapsama tablosu ve günlük Excel dosyası">
        <label className="yon-satir" style={{ gap: 6 }}>
          <Takvim boyut={18} />
          <span className="gizli">Rapor tarihi</span>
          <input
            type="date"
            className="yon-alan"
            style={{ width: 160 }}
            value={tarih}
            max={bugun}
            onChange={(o) => setTarih(o.target.value || bugun)}
          />
        </label>
        <button className="yd birincil" onClick={indir} disabled={indiriliyor}>
          <Indir boyut={18} />
          {indiriliyor ? 'Hazırlanıyor…' : 'Excel indir'}
        </button>
      </YonUst>

      <Icerik>
        <Kart
          baslik="Son 7 gün"
          altYazi={`${sayi(haftaToplam.ziyaret)} bina gezildi · ${sayi(
            haftaToplam.satis,
          )} satış · ${sayi(haftaToplam.adet)} abonelik`}
          sag={
            <span className="yon-satir" style={{ gap: 12 }}>
              <span className="durum-pil mavi">
                <span className="nokta" /> Gezilen bina
              </span>
              <span className="durum-pil yesil">
                <span className="nokta" /> Satış
              </span>
            </span>
          }
        >
          {hafta.hata ? <HataKutusu mesaj={hata_metni(hafta.hata)} yenile={hafta.yenile} /> : null}
          {!hafta.veri ? (
            <Iskelet yukseklik={190} />
          ) : (
            <div className="trend-grafik">
              {hafta.veri.map((g) => {
                const t = new Date(
                  Number(g.tarih.slice(0, 4)),
                  Number(g.tarih.slice(5, 7)) - 1,
                  Number(g.tarih.slice(8, 10)),
                );
                return (
                  <div key={g.tarih} className={`trend-gun${g.tarih === bugun ? ' bugun' : ''}`}>
                    <div className="deger">
                      {sayi(g.ziyaret)}
                      {g.satis ? (
                        <span style={{ color: 'var(--yesil)' }}> · {sayi(g.satis)}</span>
                      ) : null}
                    </div>
                    <div className="trend-sutunlar">
                      {/* Yükseklik yüzdeyle değil pikselle veriliyor: esnek kutu
                          içinde yüzde yükseklik belirsiz kalıp sıfıra düşüyor. */}
                      <div
                        className="trend-sutun"
                        style={{ height: sutunYuksekligi(g.ziyaret, enYuksek) }}
                        title={`${g.ziyaret} bina gezildi`}
                      />
                      <div
                        className="trend-sutun satis"
                        style={{ height: sutunYuksekligi(g.satis, enYuksek) }}
                        title={`${g.satis} satış`}
                      />
                    </div>
                    <div className="etiket">
                      {GUN_KISA[t.getDay()]}
                      <br />
                      {t.getDate()}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Kart>

        <Kart
          baslik="Kapsama"
          altYazi="Hangi bölgede / mahallede ne kadar yol alındı"
          sag={
            <span className="yon-satir" style={{ gap: 8 }}>
              <select
                className="yon-alan"
                style={{ width: 190 }}
                value={bolge ?? ''}
                onChange={(o) => setBolge(o.target.value ? Number(o.target.value) : null)}
                aria-label="Bölge"
              >
                <option value="">Bütün bölgeler</option>
                {bolgeNumaralari(bolgeSayisi).map((b) => (
                  <option key={b} value={b}>
                    {b}. bölge{bolgeAdi.get(b) ? ` · ${bolgeAdi.get(b)}` : ''}
                  </option>
                ))}
              </select>
              <Segment<Kirilim>
                etiket="Kırılım"
                deger={kirilim}
                degisti={setKirilim}
                secenekler={[
                  { deger: 'bolge', etiket: 'Bölge' },
                  { deger: 'mahalle', etiket: 'Mahalle' },
                  { deger: 'ilce', etiket: 'İlçe' },
                ]}
              />
            </span>
          }
          sikis
        >
          {kapsamaVeri.hata ? (
            <div style={{ padding: 16 }}>
              <HataKutusu mesaj={kapsamaVeri.hata} yenile={kapsamaVeri.yenile} />
            </div>
          ) : null}
          {!kapsamaVeri.veri ? (
            <div style={{ padding: 16 }}>
              <Iskelet yukseklik={300} />
            </div>
          ) : (
            <div className="yon-tablo-sarmal" style={{ maxHeight: 520, overflowY: 'auto' }}>
              {/* Telefonda tablo satır kartına döner (§7.4): her hücre etiketini (data-etiket) önüne yazar. */}
              <table className="yon-tablo satirlasir">
                <thead>
                  <tr>
                    <th>{kirilim === 'bolge' ? 'Bölge' : kirilim === 'ilce' ? 'İlçe' : 'Mahalle'}</th>
                    <th className="sayi">Bina</th>
                    <th className="sayi">Dokunulan</th>
                    <th className="sayi">Kalan</th>
                    <th style={{ minWidth: 150 }}>Kapsama</th>
                    <th className="sayi">Boş kapı</th>
                    <th className="sayi">Kalan fırsat</th>
                    <th className="sayi">Satış</th>
                  </tr>
                </thead>
                <tbody>
                  {kapsamaVeri.veri.satirlar.map((s) => (
                    <tr key={String(s.ad)}>
                      <td className="ad-hucre">
                        {kirilim === 'bolge'
                          ? `${s.ad}. bölge${
                              bolgeAdi.get(Number(s.ad)) ? ` · ${bolgeAdi.get(Number(s.ad))}` : ''
                            }`
                          : s.ad}
                      </td>
                      <td className="sayi" data-etiket="Bina">{sayi(s.toplam)}</td>
                      <td className="sayi" data-etiket="Dokunulan">{sayi(s.dokunulan)}</td>
                      <td className="sayi" data-etiket="Kalan">{sayi(s.kalan)}</td>
                      <td className="tam">
                        <OranCubugu oran={s.oran} />
                      </td>
                      <td className="sayi" data-etiket="Boş kapı">{sayi(s.firsat)}</td>
                      <td className="sayi" data-etiket="Kalan fırsat">{sayi(s.kalan_firsat)}</td>
                      <td className="sayi" data-etiket="Satış">{sayi(s.satis)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr style={{ background: 'var(--kart-bas)', fontWeight: 600 }}>
                    <td className="ad-hucre">Toplam</td>
                    <td className="sayi" data-etiket="Bina">{sayi(kapsamaVeri.veri.toplam)}</td>
                    <td className="sayi" data-etiket="Dokunulan">{sayi(kapsamaVeri.veri.dokunulan)}</td>
                    <td className="sayi" data-etiket="Kalan">{sayi(kapsamaVeri.veri.kalan)}</td>
                    <td data-etiket="Kapsama">{yuzde(kapsamaVeri.veri.oran, 1)}</td>
                    <td className="sayi" data-etiket="Boş kapı">{sayi(kapsamaVeri.veri.firsat)}</td>
                    <td className="sayi" data-etiket="Kalan fırsat">{sayi(kapsamaVeri.veri.kalan_firsat)}</td>
                    <td className="sayi" data-etiket="Satış">{sayi(kapsamaVeri.veri.satis)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </Kart>
      </Icerik>
    </>
  );
}

function hata_metni(h: string): string {
  return `Haftalık özet alınamadı: ${h}`;
}

/** Sütun alanının yüksekliği (piksel); sıfır olan günler de bir çizgiyle görünür. */
const SUTUN_ALANI = 128;
function sutunYuksekligi(deger: number, enYuksek: number): string {
  if (!deger) return '3px';
  return `${Math.max(6, Math.round((deger / enYuksek) * SUTUN_ALANI))}px`;
}
