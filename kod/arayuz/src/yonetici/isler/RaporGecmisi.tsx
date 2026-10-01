/**
 * Veri ▸ Rapor geçmişi (§6.7, EK-10): son 30 aktarım — zaman · yükleyen · dosya ·
 * iş · yeni/değişen/kapanan/yeniden açılan · durum · yedek (kişisel veri yok).
 * Üstte klasör izleme durumu: hangi klasörlere bakılıyor, en son ne alındı;
 * açılıp kapatılabilir. Onay bekleyen rapor buradan da gözden geçirilir.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { aktarimGecmisi, hataMetni, izlemeDurumu, izlemeYaz } from '../../is/api';
import type { AktarimKaydi, IzlemeDurumu } from '../../is/tipler';
import { Icerik, YonUst } from '../ortak/Kabuk';
import { Tablo, type TabloSutunu } from '../../ortak/Tablo';
import { BosDurum, HataKutusu, Iskelet } from '../../ortak/Bos';
import { Hikaye } from '../../ortak/Hikaye';
import { Hap } from '../../ortak/Rozet';
import { useBildirim } from '../../ortak/Bildirim';
import { useOturum } from '../../depo/oturum';
import { IslerSaglayici } from './depo';
import { useRaporYukleyici } from './RaporYukle';
import { saatMetni, tarihSaatMetni } from './parcalar';
import './isler.css';

const DURUM: Record<AktarimKaydi['durum'], { metin: string; renk: 'yesil' | 'amber' | 'kirmizi' | 'gri' | 'mavi' }> = {
  uygulandi: { metin: 'İşlendi', renk: 'yesil' },
  onay_bekliyor: { metin: 'Onay bekliyor', renk: 'amber' },
  isleniyor: { metin: 'İşleniyor', renk: 'mavi' },
  vazgecildi: { metin: 'Vazgeçildi', renk: 'gri' },
  hata: { metin: 'Hata', renk: 'kirmizi' },
};
const YONTEM: Record<AktarimKaydi['yontem'], string> = { surukle: 'Ekrandan', komut: 'Komut satırı', klasor: 'Klasörden' };

export function RaporGecmisi() {
  return (
    <IslerSaglayici>
      <RaporGecmisiEkrani />
    </IslerSaglayici>
  );
}

function RaporGecmisiEkrani() {
  const { izinli } = useOturum();
  const bildirim = useBildirim();
  const rapor = useRaporYukleyici();
  const [liste, setListe] = useState<AktarimKaydi[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [izleme, setIzleme] = useState<IzlemeDurumu | null>(null);

  const yukle = useCallback(() => {
    aktarimGecmisi(30)
      .then((l) => {
        setListe(l);
        setHata(null);
      })
      .catch((e) => setHata(hataMetni(e)));
    izlemeDurumu()
      .then(setIzleme)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    yukle();
    const t = window.setInterval(() => document.visibilityState === 'visible' && yukle(), 30000);
    return () => window.clearInterval(t);
  }, [yukle]);

  useEffect(() => {
    if (!rapor.okunuyor) yukle();
  }, [rapor.okunuyor, yukle]);

  const sutunlar: Array<TabloSutunu<AktarimKaydi>> = useMemo(
    () => [
      { anahtar: 'zaman', baslik: 'Zaman', deger: (r) => r.zaman, goster: (r) => tarihSaatMetni(r.zaman), genislik: 140, kartta: 'baslik', suzgec: false },
      { anahtar: 'durum', baslik: 'Durum', deger: (r) => DURUM[r.durum]?.metin ?? r.durum, goster: (r) => <Hap renk={DURUM[r.durum]?.renk ?? 'gri'}>{DURUM[r.durum]?.metin ?? r.durum}</Hap>, genislik: 128, kartta: 'alt' },
      { anahtar: 'yukleyen', baslik: 'Yükleyen', deger: (r) => r.yukleyen ?? (r.yontem === 'klasor' ? 'Klasör izleme' : ''), genislik: 150 },
      { anahtar: 'yontem', baslik: 'Yol', deger: (r) => YONTEM[r.yontem] ?? r.yontem, genislik: 110 },
      { anahtar: 'dosya', baslik: 'Dosya', deger: (r) => r.dosya_adi, genislik: 240 },
      { anahtar: 'is', baslik: 'İş', deger: (r) => r.is_sayisi, sayi: true, genislik: 72 },
      { anahtar: 'yeni', baslik: 'Yeni', deger: (r) => r.yeni, sayi: true, genislik: 72 },
      { anahtar: 'degisen', baslik: 'Değişen', deger: (r) => r.degisen, sayi: true, genislik: 84 },
      { anahtar: 'kaybolan', baslik: 'Kapanan', deger: (r) => r.kaybolan, sayi: true, genislik: 84 },
      { anahtar: 'yeniden', baslik: 'Yeniden açılan', deger: (r) => r.yeniden_acilan, sayi: true, genislik: 120 },
      { anahtar: 'ayni', baslik: 'Aynı', deger: (r) => r.degismeyen, sayi: true, genislik: 72 },
      { anahtar: 'cikarilan', baslik: 'Çıkarılan satır', deger: (r) => r.cikarilan, sayi: true, genislik: 116 },
      { anahtar: 'kapsam', baslik: 'Kapsam', deger: (r) => (r.durum === 'uygulandi' ? (r.tam_kapsam ? 'Tam' : 'Kısmi') : ''), genislik: 84 },
      { anahtar: 'yedek', baslik: 'Yedek', deger: (r) => (r.yedek ? r.yedek.split(/[\\/]/).pop() ?? '' : ''), genislik: 220, kartta: 'gizli' },
      { anahtar: 'hata', baslik: 'Hata', deger: (r) => r.hata ?? '', genislik: 220, kartta: 'gizli' },
    ],
    [],
  );

  const izlemeDegistir = async (acik: boolean) => {
    try {
      setIzleme(await izlemeYaz(acik));
      bildirim.goster(acik ? 'Klasör izleme açıldı.' : 'Klasör izleme kapatıldı; raporu elle yükleyin.', 'basari');
    } catch (e) {
      bildirim.goster(hataMetni(e), 'uyari');
    }
  };

  const son = liste?.find((r) => r.durum === 'uygulandi');
  const bekleyen = izleme?.onay_bekleyen ?? [];

  return (
    <>
      <YonUst baslik="Rapor geçmişi">
        {izinli('is.yukle') ? (
          <button type="button" className="o-dugme" onClick={rapor.sec} disabled={rapor.okunuyor}>
            {rapor.okunuyor ? 'Rapor okunuyor…' : 'Rapor yükle'}
          </button>
        ) : null}
      </YonUst>
      <Icerik>
        {son ? (
          <Hikaye
            cumle={`Son rapor ${tarihSaatMetni(son.zaman)}’de işlendi: ${son.is_sayisi ?? 0} iş, ${son.yeni ?? 0} yeni, ${son.kaybolan ?? 0} kapanan.`}
            ton="sakin"
          />
        ) : null}
        {izleme ? (
          <section className="rg-izleme">
            <div className="bas">
              <h2>Klasör izleme</h2>
              <Hap renk={izleme.acik ? (izleme.calisiyor === false ? 'amber' : 'yesil') : 'gri'}>
                {izleme.acik ? (izleme.calisiyor === false ? 'Açık · bu sunucuda çalışmıyor' : 'Açık') : 'Kapalı'}
              </Hap>
              <label className="o-onay-kutusu">
                <input type="checkbox" checked={izleme.acik} onChange={(o) => void izlemeDegistir(o.target.checked)} />
                <span>BOSS’tan indirilen raporu kendiliğinden al</span>
              </label>
            </div>
            <p className="ip-not-satiri">
              {izleme.klasorler_varsayilan ? 'İndirilenler ve Masaüstü' : `${izleme.klasorler.length} klasör`} · desen {izleme.desenler.join(', ')}
              {izleme.son_bakis ? ` · son bakış ${saatMetni(izleme.son_bakis)}` : ''}
              {izleme.son_alinan ? ` · son alınan ${izleme.son_alinan.dosya_adi} (${saatMetni(izleme.son_alinan.zaman)})` : ''}
            </p>
            {bekleyen.map((r) => (
              <div key={r.aktarim_id} className="ip-uyari sari">
                <span>
                  Onay bekleyen rapor · {r.dosya_adi} · {saatMetni(r.zaman)} — {r.mesaj}
                </span>
                <button type="button" className="o-dugme kucuk" onClick={() => rapor.onayla(r)}>
                  Gözden geçir
                </button>
              </div>
            ))}
          </section>
        ) : null}
        {hata && !liste ? <HataKutusu mesaj={hata} tekrar={yukle} /> : null}
        {!liste && !hata ? <Iskelet satir={6} yukseklik={40} /> : null}
        {liste ? (
          liste.length ? (
            <Tablo
              satirlar={liste}
              sutunlar={sutunlar}
              anahtar={(r) => r.id}
              excelAdi="Rapor-gecmisi"
              kayitAnahtari="rapor-gecmisi"
              aramaYerTutucu="Dosya, kişi, durum…"
            />
          ) : (
            <BosDurum
              simge="📄"
              baslik="Henüz rapor yüklenmedi."
              aciklama="BOSS’tan Teknik Task Detay Raporu’nu indirip İşler ekranına bırakın."
            />
          )
        ) : null}
      </Icerik>
      {rapor.arayuz}
    </>
  );
}
