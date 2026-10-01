/**
 * Rapor yükle (§6.7, F18; EK-10 klasör izleme).
 *
 *   · Bırak ya da [Rapor yükle] → ince ilerleme "Rapor okunuyor…" (başka hiçbir
 *     kullanıcı beklemez). Sonuç tek satır bildirim; pano aynı anda güncellenir:
 *     "Rapor işlendi · Yeni 12 · Değişen 30 · Kapanan 30 · Yeniden açılan 3 · Aynı 392"
 *     [Ayrıntı] → çıkarılanlar, kontrol gerekenler, süre, alınan yedek.
 *   · Aynı dosya: "Bu dosya 11:38'de zaten yüklenmişti. Hiçbir şey değişmedi."
 *   · 409 onay_gerekli → onay çekmecesi (eksik rapor / eski rapor).
 *   · Klasörden gelip onay bekleyen rapor (EK-10) aynı çekmeceyle gözden geçirilir.
 */

import { useCallback, useRef, useState, type ReactNode } from 'react';
import { aktarimUygula, aktarimVazgec, hataMetni, IsHatasi, raporYukle } from '../../is/api';
import type { AktarimFark, AktarimSonucu, OnayBekleyenRapor } from '../../is/tipler';
import { Panel } from '../../ortak/Panel';
import { useBildirim } from '../../ortak/Bildirim';
import { useIsler } from './depo';
import { saatMetni } from './parcalar';

interface OnayIstegi {
  aktarim_id: number;
  fark: AktarimFark;
  nedenler: Array<'cok_kaybolan' | 'eski_rapor'>;
  acik?: number;
  kaybolan_oran?: number;
  son_rapor_zamani?: string | null;
  mesaj?: string;
  dosya_adi?: string;
  klasorden?: boolean;
}

const sayi = (n: number | null | undefined) => (n ?? 0).toLocaleString('tr-TR');

export function farkCumlesi(f: AktarimFark): string {
  return `Yeni ${sayi(f.yeni)} · Değişen ${sayi(f.degisen)} · Kapanan ${sayi(f.kaybolan)} · Yeniden açılan ${sayi(
    f.yeniden_acilan,
  )} · Aynı ${sayi(f.degismeyen)}`;
}

export function useRaporYukleyici(): {
  sec: () => void;
  yukle: (f: File) => void;
  okunuyor: boolean;
  onayla: (r: OnayBekleyenRapor) => void;
  arayuz: ReactNode;
} {
  const depo = useIsler();
  const bildirim = useBildirim();
  const girdi = useRef<HTMLInputElement>(null);
  const [okunuyor, setOkunuyor] = useState(false);
  const [onay, setOnay] = useState<OnayIstegi | null>(null);
  const [onayBekliyor, setOnayBekliyor] = useState(false);
  const [ayrinti, setAyrinti] = useState<AktarimSonucu | null>(null);

  const bitti = useCallback(
    (s: AktarimSonucu) => {
      void depo.tazele();
      depo.teknikleriTazele();
      if (s.ayni_dosya) {
        bildirim.goster(`Bu dosya ${saatMetni(s.zaman)}’de zaten yüklenmişti. Hiçbir şey değişmedi.`, 'bilgi', { sureMs: 6000 });
        return;
      }
      bildirim.goster(`Rapor işlendi · ${farkCumlesi(s.fark)}`, 'basari', {
        eylem: { etiket: 'Ayrıntı', calistir: () => setAyrinti(s) },
        sureMs: 12000,
      });
    },
    [bildirim, depo],
  );

  const yukle = useCallback(
    async (dosya: File) => {
      if (!/\.xlsx?$/i.test(dosya.name)) {
        bildirim.goster('Bu dosya Excel değil. BOSS’tan Teknik Task Detay Raporu’nu (.xlsx) indirin.', 'uyari');
        return;
      }
      setOkunuyor(true);
      try {
        bitti(await raporYukle(dosya));
      } catch (e) {
        if (e instanceof IsHatasi && e.kod === 'onay_gerekli') {
          const g = e.govde as unknown as OnayIstegi;
          setOnay({ ...g, dosya_adi: dosya.name });
        } else bildirim.goster(hataMetni(e), 'uyari', { sureMs: 8000 });
      } finally {
        setOkunuyor(false);
        if (girdi.current) girdi.current.value = '';
      }
    },
    [bildirim, bitti],
  );

  const uygula = async (mod: 'tam' | 'kismi') => {
    if (!onay) return;
    setOnayBekliyor(true);
    try {
      const s = await aktarimUygula(onay.aktarim_id, mod);
      setOnay(null);
      bitti(s);
    } catch (e) {
      if (e instanceof IsHatasi && e.kod === 'onay_gerekli') {
        // bu arada başka değişiklik oldu: yeni fark
        setOnay({ ...(e.govde as unknown as OnayIstegi), dosya_adi: onay.dosya_adi });
        bildirim.goster('Bu arada veriler değişti; fark yeniden hesaplandı.', 'uyari');
      } else bildirim.goster(hataMetni(e), 'uyari');
    } finally {
      setOnayBekliyor(false);
    }
  };

  const vazgec = async () => {
    if (!onay) return;
    setOnayBekliyor(true);
    try {
      await aktarimVazgec(onay.aktarim_id);
      bildirim.goster('Rapor işlenmedi; hiçbir şey değişmedi.', 'bilgi');
      void depo.simdiYokla();
    } catch (e) {
      bildirim.goster(hataMetni(e), 'uyari');
    } finally {
      setOnayBekliyor(false);
      setOnay(null);
    }
  };

  const eski = onay?.nedenler.includes('eski_rapor') ?? false;
  const eksik = onay?.nedenler.includes('cok_kaybolan') ?? false;
  const oran = onay?.kaybolan_oran !== undefined ? Math.round((onay.kaybolan_oran ?? 0) * 100) : null;

  const arayuz = (
    <>
      <input
        ref={girdi}
        type="file"
        accept=".xlsx,.xls,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        hidden
        onChange={(o) => {
          const f = o.target.files?.[0];
          if (f) void yukle(f);
        }}
      />
      {okunuyor ? (
        <div className="ip-ilerleme" role="status" aria-live="polite">
          <span className="cubuk" aria-hidden="true" />
          <span className="metin">Rapor okunuyor…</span>
        </div>
      ) : null}

      <Panel
        acik={Boolean(onay)}
        kapat={() => void vazgec()}
        kilitli={onayBekliyor}
        baslik={eski ? 'Bu rapor eski görünüyor' : 'Bu rapor eksik olabilir'}
        altBaslik={onay?.dosya_adi ? `${onay.klasorden ? 'Klasörden gelen · ' : ''}${onay.dosya_adi}` : undefined}
        alt={
          <>
            <button type="button" className="o-dugme metin" onClick={() => void vazgec()} disabled={onayBekliyor}>
              Vazgeç
            </button>
            <span className="bosluk" />
            {eksik && !eski ? (
              <button type="button" className="o-dugme" onClick={() => void uygula('tam')} disabled={onayBekliyor}>
                Tam rapor: kapanmış say
              </button>
            ) : null}
            <button type="button" className="o-dugme birincil" onClick={() => void uygula('kismi')} disabled={onayBekliyor}>
              {onayBekliyor ? 'Bekleyin…' : eski ? 'Yine de işle' : 'Kısmi rapor: kapatma'}
            </button>
          </>
        }
      >
        {onay ? (
          <div className="ip-onay-govde">
            {onay.mesaj ? <p>{onay.mesaj}</p> : null}
            {eksik && !onay.mesaj ? (
              <p>
                Bu raporda {sayi(onay.fark.kaybolan)} açık iş yok{oran !== null ? ` (açık işlerin %${oran}’i)` : ''}. Rapor süzgeçli ya
                da tek ilçe indirilmiş olabilir.
              </p>
            ) : null}
            {eski && !onay.mesaj ? (
              <p>
                Bu rapor en son yüklenenden{onay.son_rapor_zamani ? ` (${saatMetni(onay.son_rapor_zamani)})` : ''} eski görünüyor. İşlenirse
                hiçbir iş kapatılmaz, yalnız eklenir ve güncellenir.
              </p>
            ) : null}
            <ul className="ip-fark">
              <li>
                <span>Yeni</span>
                <b>{sayi(onay.fark.yeni)}</b>
              </li>
              <li>
                <span>Değişen</span>
                <b>{sayi(onay.fark.degisen)}</b>
              </li>
              <li>
                <span>Raporda olmayan (kapanacak)</span>
                <b>{sayi(onay.fark.kaybolan)}</b>
              </li>
              <li>
                <span>Yeniden açılan</span>
                <b>{sayi(onay.fark.yeniden_acilan)}</b>
              </li>
              <li>
                <span>Aynı</span>
                <b>{sayi(onay.fark.degismeyen)}</b>
              </li>
            </ul>
            <p className="ip-not-satiri">
              “Kısmi rapor” seçilirse hiçbir iş kapatılmaz; yalnız yeni işler eklenir, değişenler güncellenir.
            </p>
          </div>
        ) : null}
      </Panel>

      <Panel acik={Boolean(ayrinti)} kapat={() => setAyrinti(null)} baslik="Rapor işlendi" altBaslik={ayrinti ? farkCumlesi(ayrinti.fark) : undefined}>
        {ayrinti ? <AktarimAyrintisi s={ayrinti} /> : null}
      </Panel>
    </>
  );

  return {
    sec: () => girdi.current?.click(),
    yukle: (f) => void yukle(f),
    okunuyor,
    onayla: (r) =>
      setOnay({
        aktarim_id: r.aktarim_id,
        fark: r.fark,
        nedenler: r.nedenler,
        mesaj: r.mesaj,
        dosya_adi: r.dosya_adi,
        klasorden: r.yontem === 'klasor',
      }),
    arayuz,
  };
}

function AktarimAyrintisi({ s }: { s: AktarimSonucu }) {
  const c = s.cikarilan;
  const adlar = Object.entries(c.adlar ?? {}).sort((a, b) => b[1] - a[1]);
  const cikan = c.kurulum + c.ikinci_donanim;
  return (
    <div className="ip-onay-govde">
      <dl className="ip-bilgi">
        <dt>Satır</dt>
        <dd>
          {sayi(c.satir)} satırdan {sayi(cikan)}’i kurulum ekibinin: kurulum {sayi(c.kurulum)} · 2. donanım {sayi(c.ikinci_donanim)}
        </dd>
        <dt>İstisna tutulan</dt>
        <dd>{sayi(c.istisna_tutulan)}</dd>
        <dt>Kontrol gereken</dt>
        <dd>{sayi(s.kontrol)}</dd>
        <dt>BOSS’ta atanmış</dt>
        <dd>{sayi(s.boss_atamasi)}</dd>
        <dt>Askı</dt>
        <dd>
          {sayi(s.aski?.acilan)} açıldı · {sayi(s.aski?.kapanan)} kapandı
        </dd>
        <dt>Kapsam</dt>
        <dd>{s.tam_kapsam ? 'Tam rapor' : 'Kısmi rapor (hiçbir iş kapatılmadı)'}</dd>
        <dt>Süre</dt>
        <dd>{s.sure_sn.toLocaleString('tr-TR', { maximumFractionDigits: 1 })} sn</dd>
        <dt>Yedek</dt>
        <dd>{s.yedek ? s.yedek.split(/[\\/]/).pop() : '—'}</dd>
      </dl>
      {adlar.length ? (
        <details className="ip-acilir">
          <summary>Çıkarılan task adları ({adlar.length})</summary>
          <ul className="ip-cikarilan">
            {adlar.map(([ad, n]) => (
              <li key={ad}>
                <span>{ad}</span>
                <b>{sayi(n)}</b>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}
