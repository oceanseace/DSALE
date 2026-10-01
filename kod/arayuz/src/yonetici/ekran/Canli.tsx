/**
 * Canlı durum — "bugün kim nerede, kim hâlâ başlamadı".
 *
 * Sayfa kendi kendine 45 saniyede bir tazelenir; yönetici ekranı açık
 * bırakıp gün boyunca bakabilir. En üstte tek bakışta okunan beş sayı,
 * altında her satışçı için bir kart; karta tıklayınca o kişinin bugünkü
 * listesi (hangi binaya gidildi, hangisi kaldı) açılır.
 */

import { useMemo, useState } from 'react';
import { Cekmece } from '../../ortak/Cekmece';
import { useBildirim } from '../../ortak/Bildirim';
import { Onay, Takvim, Yenile } from '../../ortak/Ikon';
import { sayi, saat, tarihUzun, yuzde } from '../../ortak/bicim';
import { bugunMetni, gorev as gorevUcu, gunOzeti, raporIndir } from '../api';
import { useYonetim } from '../depo';
import { bolumeGit } from '../ortak/Kabuk';
import { Icerik, YonUst } from '../ortak/Kabuk';
import {
  BasHarf,
  BosDurumKutusu,
  HataKutusu,
  Iskelet,
  MiniSayi,
  SayiKutusu,
  useVeri,
} from '../ortak/parcalar';
import { Indir } from '../ortak/simgeler';
import { git } from '../../yol/rota';
import { Hikaye, type HikayeTonu } from '../../ortak/Hikaye';
import type { GunOzetiYaniti, SatisciGunu } from '../tipler';

type Hal = 'calisiyor' | 'bitti' | 'baslamadi' | 'listesiz';

const HAL_ETIKET: Record<Hal, { etiket: string; renk: string }> = {
  calisiyor: { etiket: 'Sahada', renk: 'yesil' },
  bitti: { etiket: 'Listeyi bitirdi', renk: 'mavi' },
  baslamadi: { etiket: 'Henüz başlamadı', renk: 'amber' },
  listesiz: { etiket: 'Liste yok', renk: 'kirmizi' },
};

export function hesaplaHal(s: SatisciGunu): Hal {
  if (!s.gorev_id) return 'listesiz';
  if (s.ziyaret === 0) return 'baslamadi';
  if (s.kalan === 0) return 'bitti';
  return 'calisiyor';
}

export function Canli() {
  const bugun = bugunMetni();
  const [tarih, setTarih] = useState(bugun);
  const canliMi = tarih === bugun;
  const { gun, gunYukleniyor, gunHatasi, gunTazele, sonGuncelleme, ekip } = useYonetim();
  const gecmis = useVeri<GunOzetiYaniti>(() => gunOzeti(tarih), [tarih]);

  /* Pasif hesaplar (Ekip'ten pasife alınan ya da bölge planı geri alınınca kapanan
     yer tutucular) o gün hiç ziyaret yazmadıysa "başlamadı" diye görünmesin. */
  const pasifler = useMemo(
    () => new Set((ekip ?? []).filter((k) => !k.aktif).map((k) => k.id)),
    [ekip],
  );
  const veri = useMemo(() => {
    const ham = canliMi ? gun : gecmis.veri;
    if (!ham || !pasifler.size) return ham;
    return {
      ...ham,
      satiscilar: ham.satiscilar.filter((s) => !pasifler.has(s.kullanici_id) || s.ziyaret > 0),
    };
  }, [canliMi, gun, gecmis.veri, pasifler]);
  const yukleniyor = canliMi ? gunYukleniyor : gecmis.yukleniyor;
  const hata = canliMi ? gunHatasi : gecmis.hata;
  const yenile = canliMi ? gunTazele : gecmis.yenile;

  const { goster } = useBildirim();
  const [secili, setSecili] = useState<SatisciGunu | null>(null);
  const [indiriliyor, setIndiriliyor] = useState(false);

  const uyarilar = useMemo(() => {
    const satirlar = veri?.satiscilar ?? [];
    return {
      listesiz: satirlar.filter((s) => hesaplaHal(s) === 'listesiz'),
      baslamadi: satirlar.filter((s) => hesaplaHal(s) === 'baslamadi'),
    };
  }, [veri]);

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

  const toplam = veri?.toplam;

  /* EK-6: ekranın başında durumdan üretilen tek cümle; ayrıntı aşağıda. */
  const hikaye = useMemo((): { cumle: string; ton: HikayeTonu } | null => {
    if (!veri || !toplam) return null;
    const hepsi = veri.satiscilar.length;
    if (!hepsi) return null;
    const sahada = veri.satiscilar.filter((x) => {
      const h = hesaplaHal(x);
      return h === 'calisiyor' || h === 'bitti';
    }).length;
    const gun = canliMi ? 'Bugün' : `${tarihUzun(tarih)} günü`;
    const cumle = !sahada
      ? `${gun} ${sayi(hepsi)} satışçıdan henüz kimse sahaya çıkmadı.`
      : `${gun} ${sayi(hepsi)} satışçıdan ${sayi(sahada)} kişi sahaya çıktı; ` +
        `${sayi(toplam.ziyaret)} bina gezildi, ${sayi(toplam.satis)} binada satış yapıldı.`;
    const ton: HikayeTonu = uyarilar.listesiz.length ? 'dikkat' : sahada === hepsi ? 'iyi' : 'sakin';
    return { cumle, ton };
  }, [veri, toplam, canliMi, tarih, uyarilar]);

  return (
    <>
      <YonUst
        baslik="Canlı durum"
        altYazi={
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            {tarihUzun(tarih)}
            {canliMi && sonGuncelleme ? (
              <span className="durum-pil yesil canli">
                <span className="nokta" />
                Canlı · {saat(sonGuncelleme.toISOString())}
              </span>
            ) : (
              <span className="durum-pil">Geçmiş gün</span>
            )}
          </span>
        }
      >
        <label className="yon-satir" style={{ gap: 6 }}>
          <Takvim boyut={18} />
          <span className="gizli">Tarih</span>
          <input
            type="date"
            className="yon-alan"
            style={{ width: 160 }}
            value={tarih}
            max={bugun}
            onChange={(o) => setTarih(o.target.value || bugun)}
          />
        </label>
        <button className="yd" onClick={yenile} disabled={yukleniyor}>
          <Yenile boyut={18} />
          Yenile
        </button>
        {/* Ekranın tek birincil eylemi "Görev ata"dır (listesi olmayan varsa);
            Excel raporu ikincildir. */}
        <button className="yd" onClick={indir} disabled={indiriliyor}>
          <Indir boyut={18} />
          {indiriliyor ? 'Hazırlanıyor…' : 'Günün Excel raporu'}
        </button>
      </YonUst>

      <Icerik>
        {hikaye ? <Hikaye cumle={hikaye.cumle} ton={hikaye.ton} /> : null}
        {hata ? <HataKutusu mesaj={hata} yenile={yenile} /> : null}

        {uyarilar.listesiz.length ? (
          <div className="yon-uyari kirmizi">
            <span>
              <b>{uyarilar.listesiz.length} satışçının bugün listesi yok:</b>{' '}
              {uyarilar.listesiz.map((s) => s.ad).join(', ')}
            </span>
            <span className="sag">
              <button
                className="yd birincil"
                onClick={() =>
                  uyarilar.listesiz.length === 1
                    ? git(`/yonetici/atama/${uyarilar.listesiz[0].kullanici_id}`)
                    : bolumeGit('atama')
                }
              >
                Görev ata
              </button>
            </span>
          </div>
        ) : null}

        {uyarilar.baslamadi.length ? (
          <div className="yon-uyari">
            <span>
              <b>{uyarilar.baslamadi.length} satışçı henüz başlamadı:</b>{' '}
              {uyarilar.baslamadi.map((s) => s.ad).join(', ')}
            </span>
          </div>
        ) : null}

        {!veri && yukleniyor ? (
          <>
            <Iskelet yukseklik={96} />
            <Iskelet yukseklik={260} />
          </>
        ) : null}

        {toplam ? (
          <div className="yon-sayilar">
            <SayiKutusu
              etiket="Gezilen bina"
              deger={sayi(toplam.ziyaret)}
              ek={`${sayi(toplam.kalan)} bina listede bekliyor`}
              renk="mavi"
            />
            {/* İki farklı "satış" yan yana durmasın: hangisinin bina hangisinin
                abonelik olduğu etikette yazar. */}
            <SayiKutusu
              etiket="Satış yapılan bina"
              deger={sayi(toplam.satis)}
              ek={`${sayi(toplam.satis_adedi)} abonelik satıldı`}
              renk="yesil"
            />
            <SayiKutusu etiket="Randevu" deger={sayi(toplam.randevu)} ek="tekrar gidilecek" />
            <SayiKutusu etiket="İlgilenmedi" deger={sayi(toplam.ret)} ek="bugün alınan ret" />
            <SayiKutusu
              etiket="Dönüşüm"
              deger={yuzde(toplam.donusum, 1)}
              ek="satışla biten bina / gezilen bina"
            />
          </div>
        ) : null}

        {veri && veri.satiscilar.length ? (
          <div className="satisci-izgara">
            {veri.satiscilar.map((s) => (
              <SatisciKarti key={s.kullanici_id} s={s} ac={() => setSecili(s)} />
            ))}
          </div>
        ) : null}

        {veri && !veri.satiscilar.length ? (
          <BosDurumKutusu
            simge="👥"
            baslik="Henüz satışçı yok"
            aciklama="Ekip bölümünden satışçı ekleyin; günlük takip burada görünecek."
          >
            <button className="yd birincil" onClick={() => bolumeGit('ekip')}>
              Ekip bölümüne git
            </button>
          </BosDurumKutusu>
        ) : null}
      </Icerik>

      <SatisciCekmecesi satisci={secili} tarih={tarih} kapat={() => setSecili(null)} />
    </>
  );
}

/* ------------------------------ Satışçı kartı ------------------------------ */

function SatisciKarti({ s, ac }: { s: SatisciGunu; ac: () => void }) {
  const hal = hesaplaHal(s);
  const { etiket, renk } = HAL_ETIKET[hal];
  // Payda GÖREV LİSTESİNDEN gelir, ziyaret sayısından değil: aynı binaya
  // ikinci kez gidilince "28 / 28 bina" gibi imkânsız sayılar çıkıyordu.
  const hedef = s.gorev_toplam ?? s.ziyaret + s.kalan;
  const gezilen = Math.min(s.gorev_tamam ?? s.ziyaret, hedef);
  const oran = hedef ? gezilen / hedef : 0;

  return (
    <article className={`satisci-kart ${hal}`}>
      <div className="satisci-bas">
        <BasHarf ad={s.ad} anahtar={s.kullanici_id} />
        <div style={{ minWidth: 0, flex: 1 }}>
          <div className="ad" title={s.ad}>
            {s.ad}
          </div>
          <div className="alt">{s.bolge ? `${s.bolge}. bölge` : 'Bölgesiz'}</div>
        </div>
      </div>

      <div className="yon-satir" style={{ justifyContent: 'space-between' }}>
        <span className={`durum-pil ${renk}${hal === 'calisiyor' ? ' canli' : ''}`}>
          <span className="nokta" />
          {etiket}
        </span>
        <span style={{ fontSize: 14, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
          {sayi(gezilen)} / {sayi(hedef)} bina
        </span>
      </div>

      <div className={`ilerleme-yol${hal === 'bitti' ? ' mavi' : ''}`}>
        <span style={{ width: `${Math.round(oran * 100)}%` }} />
      </div>

      <div className="mini-sayilar">
        <MiniSayi deger={s.satis} etiket="Satış binası" yesil />
        <MiniSayi deger={s.randevu} etiket="Randevu" />
        <MiniSayi deger={s.ret} etiket="Ret" />
        <MiniSayi deger={s.kalan} etiket="Kalan" />
      </div>

      {hal === 'listesiz' ? (
        /* §6.14: o satışçı SEÇİLİ olarak Görev atama açılır. */
        <button className="yd genis" onClick={() => git(`/yonetici/atama/${s.kullanici_id}`)}>
          Bugün için görev ata
        </button>
      ) : (
        <button className="yd genis" onClick={ac}>
          Listesini aç
        </button>
      )}
    </article>
  );
}

/* ------------------------------ Gün listesi çekmecesi ------------------------------ */

function SatisciCekmecesi({
  satisci,
  tarih,
  kapat,
}: {
  satisci: SatisciGunu | null;
  tarih: string;
  kapat: () => void;
}) {
  const { veri, yukleniyor, hata } = useVeri(
    () => (satisci ? gorevUcu(satisci.kullanici_id, tarih) : Promise.resolve(null)),
    [satisci?.kullanici_id, tarih],
  );

  if (!satisci) return null;

  const binalar = veri?.binalar ?? [];
  const gidilen = binalar.filter((b) => b.gorev_durum === 'tamam');
  const kalanlar = binalar.filter((b) => b.gorev_durum !== 'tamam');

  return (
    <Cekmece
      acik
      kapat={kapat}
      baslik={satisci.ad}
      altBaslik={`${satisci.bolge}. bölge · ${tarihUzun(tarih)}`}
    >
      {yukleniyor ? <Iskelet yukseklik={180} /> : null}
      {hata ? <HataKutusu mesaj={hata} /> : null}

      {!yukleniyor && !binalar.length ? (
        <BosDurumKutusu
          simge="📭"
          baslik="Bu gün için liste yok"
          aciklama="Görev atama bölümünden bu kişiye bina gönderebilirsiniz."
        >
          <button
            className="yd birincil"
            onClick={() => {
              kapat();
              git(`/yonetici/atama/${satisci.kullanici_id}`);
            }}
          >
            Görev ata
          </button>
        </BosDurumKutusu>
      ) : null}

      {binalar.length ? (
        <>
          <div className="yon-satir" style={{ marginBottom: 12, gap: 8 }}>
            <span className="durum-pil yesil">
              <Onay boyut={14} /> {sayi(gidilen.length)} gidildi
            </span>
            <span className="durum-pil">{sayi(kalanlar.length)} kaldı</span>
            {veri?.toplam_mesafe_m ? (
              <span className="durum-pil">
                {(veri.toplam_mesafe_m / 1000).toLocaleString('tr-TR', {
                  maximumFractionDigits: 1,
                })}{' '}
                km rota
              </span>
            ) : null}
          </div>

          <div className="secim-listesi" style={{ maxHeight: '52vh' }}>
            {binalar.map((b) => {
              const bitti = b.gorev_durum === 'tamam';
              return (
                <div key={b.bina_serial} className="secim-satir">
                  <span
                    className="sira"
                    style={
                      bitti
                        ? { background: 'var(--yesil-yumusak)', color: 'var(--yesil)' }
                        : undefined
                    }
                  >
                    {bitti ? <Onay boyut={14} /> : b.sira}
                  </span>
                  <div className="govde">
                    <div className="ad">{b.baslik}</div>
                    <div className="alt">
                      {b.adres}
                      {b.firsat ? ` · ${sayi(b.firsat)} boş kapı` : ''}
                    </div>
                  </div>
                  <span className={`durum-pil ${bitti ? 'yesil' : ''}`}>
                    {bitti ? (b.son_sonuc ? b.durum_etiket : 'Gidildi') : 'Bekliyor'}
                  </span>
                </div>
              );
            })}
          </div>
        </>
      ) : null}
    </Cekmece>
  );
}
