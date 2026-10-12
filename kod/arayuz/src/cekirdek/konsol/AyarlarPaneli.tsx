/**
 * Ayarlar paneli (kenar menünün altında, Görünüm'ün yanında "Ayarlar"): kişi başına, sunucuda saklanan tercihler
 * (cekirdek/ortak/kisiAyarlari.ts). MAP: durum sayaç çubuğu, renk lejantı, otomatik tazeleme aralığı; TASKS · MAP
 * süzgeçleri: diğer filtrelerle gizlenen değerleri soluk göster (varsayılan kapalı → değer listesinde yok).
 * Administrator'a ayrıca "Durum renkleri": MAP'te hangi durum hangi renk (herkes için; cekirdek/is/durumRenk.ts)
 * ve "Otomatik planlama" (herkes için; PUT /api/isler/ayarlar): ilişkili işleri dahil et, ticket otomatik askı,
 * çözümde önceki ekibe geri ata + dilimi, varsayılan askı nedeni (bilgi: Abone Kaynaklı > Ulaşılamadı; bütün askılar),
 * BOSS'a eşzamanlı yazma sayısı (boss_yazma_paralel, 1–10).
 * Giriş: <AyarlarPaneli acik kapat />. Kim: Kabuk.tsx.
 */

import { useEffect, useState } from 'react';
import { Panel } from '../ortak/Panel';
import { TAZELEME_SECENEK, ayarYaz, useKisiAyarlari } from '../ortak/kisiAyarlari';
import { durumRenkleriYaz, hataMetni, isAyarlari, otomatikAyarYaz } from '../is/api';
import type { IsAyarlari } from '../is/tipler';
import {
  DURUM_ADI,
  DURUM_RENK_VARSAYILAN,
  RENK_TANIMI,
  durumRenkleri,
  durumRenkleriniKur,
  durumRenkleriOku,
  useDurumRenkSurumu,
  type DurumAnahtari,
  type DurumRengi,
} from '../is/durumRenk';
import { useOturum } from '../yerel/oturum';

/** Administrator: MAP durum → renk eşlemesi (herkes için; sunucuda). Varsayılan cekirdek/is/durumRenk.ts. */
function DurumRenkleri() {
  useDurumRenkSurumu();
  const esleme = durumRenkleri();
  const [hata, setHata] = useState<string | null>(null);
  const [gidiyor, setGidiyor] = useState(false);
  useEffect(() => {
    isAyarlari()
      .then((a) => durumRenkleriniKur(a.durum_renkleri))
      .catch(() => undefined);
  }, []);
  const yaz = async (m: Partial<Record<DurumAnahtari, DurumRengi>>) => {
    setGidiyor(true);
    setHata(null);
    const once = esleme;
    durumRenkleriniKur({ ...esleme, ...m });
    try {
      const a = await durumRenkleriYaz(m as Record<string, string>);
      durumRenkleriniKur(durumRenkleriOku(a.durum_renkleri));
    } catch (h) {
      durumRenkleriniKur(once);
      setHata(hataMetni(h));
    } finally {
      setGidiyor(false);
    }
  };
  const varsayilanMi = DURUM_ADI.every((d) => esleme[d.anahtar] === DURUM_RENK_VARSAYILAN[d.anahtar]);
  return (
    <>
      <h3 className="ayar-bolum">Durum renkleri (MAP · herkes için)</h3>
      <div className="ayar-renkler" role="table" aria-label="Durum renkleri">
        {DURUM_ADI.map((d) => (
          <div key={d.anahtar} className="ayar-renk-satir" role="row">
            <span role="cell">{d.ad}</span>
            <span role="cell" className="ayar-renk-secim">
              {RENK_TANIMI.map((r) => (
                <button
                  key={r.renk}
                  type="button"
                  className={`ayar-renk${esleme[d.anahtar] === r.renk ? ' secili' : ''}`}
                  style={{ ['--r' as string]: `rgb(${r.rgb.join(',')})` }}
                  title={r.ad}
                  aria-label={`${d.ad}: ${r.ad}`}
                  aria-pressed={esleme[d.anahtar] === r.renk}
                  disabled={gidiyor}
                  onClick={() => esleme[d.anahtar] !== r.renk && void yaz({ [d.anahtar]: r.renk })}
                />
              ))}
            </span>
          </div>
        ))}
      </div>
      {hata ? <p className="ayar-hata">{hata}</p> : null}
      <button type="button" className="o-dugme kucuk" disabled={varsayilanMi || gidiyor} onClick={() => void yaz({ ...DURUM_RENK_VARSAYILAN })}>
        Varsayılana dön
      </button>
    </>
  );
}

/** Administrator: otomatik planlama anahtarları (herkes için; sunucuda). */
function OtomatikPlanlama() {
  const [a, setA] = useState<IsAyarlari | null>(null);
  const [slot, setSlot] = useState('');
  const [paralel, setParalel] = useState('6');
  const [hata, setHata] = useState<string | null>(null);
  const [gidiyor, setGidiyor] = useState(false);
  useEffect(() => {
    isAyarlari()
      .then((y) => {
        setA(y);
        setSlot(y.ticket_cozum_slot ?? '08:00-10:00');
        setParalel(String(y.boss_yazma_paralel ?? 6));
      })
      .catch((h) => setHata(hataMetni(h)));
  }, []);
  const yaz = async (g: Parameters<typeof otomatikAyarYaz>[0]) => {
    setGidiyor(true);
    setHata(null);
    try {
      const y = await otomatikAyarYaz(g);
      setA(y);
      setSlot(y.ticket_cozum_slot ?? '08:00-10:00');
      setParalel(String(y.boss_yazma_paralel ?? 6));
    } catch (h) {
      setHata(hataMetni(h));
    } finally {
      setGidiyor(false);
    }
  };
  if (!a) return hata ? <p className="ayar-hata">{hata}</p> : null;
  const varsayilan = a.varsayilan_aski;
  const paralelYaz = () => {
    const n = Math.round(Number(paralel));
    if (!Number.isFinite(n) || n < 1 || n > 10) {
      setHata('Eşzamanlı BOSS yazma 1 ile 10 arasında olmalı.');
      setParalel(String(a.boss_yazma_paralel ?? 6));
      return;
    }
    if (n !== (a.boss_yazma_paralel ?? 6)) void yaz({ boss_yazma_paralel: n });
  };
  return (
    <>
      <h3 className="ayar-bolum">Otomatik planlama (herkes için)</h3>
      <label className="ayar-satir">
        <input
          type="checkbox"
          checked={a.iliskili_dahil !== false}
          disabled={gidiyor}
          onChange={(o) => void yaz({ iliskili_dahil: o.target.checked })}
        />
        <span>
          İlişkili işleri dahil et
          <small>Ata ve Askıya al’da aynı müşterinin öbür açık işleri varsayılan işaretli (toptan hariç)</small>
        </span>
      </label>
      <label className="ayar-satir">
        <input
          type="checkbox"
          checked={a.ticket_otomatik_aski !== false}
          disabled={gidiyor}
          onChange={(o) => void yaz({ ticket_otomatik_aski: o.target.checked })}
        />
        <span>
          Ticket’ta otomatik askı
          <small>Altyapı ticket’ına bağlanan işler BOSS’ta varsayılan askı nedeniyle 7 gün askıya alınır, süre dolmadan yenilenir</small>
        </span>
      </label>
      <label className="ayar-satir">
        <input
          type="checkbox"
          checked={a.ticket_cozum_yeniden_ata !== false}
          disabled={gidiyor}
          onChange={(o) => void yaz({ ticket_cozum_yeniden_ata: o.target.checked })}
        />
        <span>
          Çözümde yeniden ata
          <small>Ticket çözülünce iş önceki BOSS ekibine, bir sonraki iş günü bu dilimde atanır</small>
        </span>
      </label>
      <label className="ayar-satir dikey">
        <span>Geri atama dilimi</span>
        <input
          className="o-girdi"
          value={slot}
          maxLength={11}
          placeholder="08:00-10:00"
          disabled={gidiyor}
          onChange={(o) => setSlot(o.target.value)}
          onBlur={() => slot.trim() !== (a.ticket_cozum_slot ?? '') && void yaz({ ticket_cozum_slot: slot.trim() })}
        />
      </label>
      <div className="ayar-satir dikey">
        <span>
          Varsayılan askı: {varsayilan ? `${varsayilan.neden_ad} > ${varsayilan.alt_ad}` : 'Abone Kaynaklı > Ulaşılamadı'}{' '}
          · Not: {varsayilan?.aciklama ?? 'Teknik ekibe iletildi'}
        </span>
        <small>
          Bütün askılar (tek iş, toplu, MAP, ticket otomatik askısı) BOSS’a bu nedenle gider; alt neden her işin kendi
          kategorisindeki “Ulaşılamadı”dır. Ticket askısında not ticket metnidir. Askı formunda önceden seçilidir,
          gerekirse orada başka neden seçilir.
        </small>
      </div>
      <label className="ayar-satir dikey">
        <span>BOSS’a eşzamanlı yazma (1–10)</span>
        <input
          className="o-girdi"
          type="number"
          min={1}
          max={10}
          step={1}
          value={paralel}
          disabled={gidiyor}
          onChange={(o) => setParalel(o.target.value)}
          onBlur={paralelYaz}
          aria-label="BOSS’a eşzamanlı yazma sayısı"
        />
        <small>Eklenti askı/not/atama isteklerini aynı anda en çok bu kadar gönderir (varsayılan 6). BOSS hız sınırı için 10’u aşmaz.</small>
      </label>
      {hata ? <p className="ayar-hata">{hata}</p> : null}
    </>
  );
}

export function AyarlarPaneli({ acik, kapat }: { acik: boolean; kapat: () => void }) {
  const a = useKisiAyarlari();
  const { administrator } = useOturum();
  return (
    <Panel acik={acik} kapat={kapat} baslik="Ayarlar" altBaslik="Bu hesapta her bilgisayarda geçerli" genislik={380}>
      <div className="ayar-kok">
        <h3 className="ayar-bolum">MAP</h3>
        <label className="ayar-satir">
          <input type="checkbox" checked={a.map_durum_cubugu} onChange={(o) => ayarYaz({ map_durum_cubugu: o.target.checked })} />
          <span>
            Durum çubuğu
            <small>Gri · Sarı · Mavi · Kırmızı · Mor renklerinin sayıları üstte</small>
          </span>
        </label>
        <label className="ayar-satir">
          <input type="checkbox" checked={a.map_lejant} onChange={(o) => ayarYaz({ map_lejant: o.target.checked })} />
          <span>
            Renk lejantı
            <small>Sağ alt köşede; renge basınca o renk gizlenir</small>
          </span>
        </label>
        <label className="ayar-satir dikey">
          <span>Otomatik tazeleme</span>
          <select
            className="o-girdi"
            value={a.map_tazeleme_sn}
            onChange={(o) => ayarYaz({ map_tazeleme_sn: Number(o.target.value) })}
          >
            {TAZELEME_SECENEK.map((x) => (
              <option key={x.sn} value={x.sn}>
                {x.etiket}
              </option>
            ))}
          </select>
        </label>
        <h3 className="ayar-bolum">Süzgeçler (TASKS · MAP)</h3>
        <label className="ayar-satir">
          <input
            type="checkbox"
            checked={a.suzgec_soluk_goster}
            onChange={(o) => ayarYaz({ suzgec_soluk_goster: o.target.checked })}
          />
          <span>
            Diğer filtrelerle gizlenen değerleri soluk göster
            <small>Kapalıyken ▾ değer listesinde yalnız şu an görünen işlerin değerleri çıkar; arama yine hepsini bulur</small>
          </span>
        </label>
        {administrator && acik ? <DurumRenkleri /> : null}
        {administrator && acik ? <OtomatikPlanlama /> : null}
      </div>
    </Panel>
  );
}
