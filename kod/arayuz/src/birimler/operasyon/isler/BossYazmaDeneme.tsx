/**
 * BOSS bağlantısı ▸ "BOSS'a deneme yazması" (yalnız Administrator).
 *   1) Task No + eylem (Not / Atama / Askı) → GET /api/isler/{is_no}/boss-yazma-onizleme: gönderilecek gövde.
 *   2) Gönder → POST /api/boss/yazma-dene {is_no, eylem}; ardından 2 sn'de bir GET /api/boss/durum →
 *      yazma.deneme / yazma.son_deneme: gönderiliyor · başarılı (returnCode 0) · hata.
 *   3) Genel yazma anahtarı (PUT /api/boss/yazma-anahtari {acik}); varsayılan kapalı, onay sorulur.
 * Kim: BossBaglantisi.tsx.
 */

import { useEffect, useRef, useState } from 'react';
import {
  bossDurum,
  bossYazmaAnahtari,
  bossYazmaDene,
  bossYazmaOnizleme,
  hataMetni,
  type BossYazmaDenemeKaydi,
  type BossYazmaEylem,
  type BossYazmaOnizlemeKaydi,
  type BossYazmaOzeti,
} from '../../../cekirdek/is/api';
import { useOnay } from '../../../cekirdek/ortak/Onay';
import { Segment } from '../../../cekirdek/ortak/Segment';

const EYLEMLER: Array<{ deger: BossYazmaEylem; etiket: string }> = [
  { deger: 'not', etiket: 'Not' },
  { deger: 'atama', etiket: 'Atama' },
  { deger: 'aski', etiket: 'Askı' },
];
const KAYIT_ADI: Record<BossYazmaEylem, string> = { not: 'not', atama: 'atama', aski: 'askı' };

type Sonuc = { tur: 'bekliyor' | 'tamam' | 'hata'; metin: string };

function sonucMetni(d: BossYazmaDenemeKaydi | null | undefined): Sonuc | null {
  const s = d?.sonuc;
  if (!s) return null;
  const rk = s.return_kodu;
  if (s.durum === 'gonderildi' && (rk === 0 || rk === '0')) {
    return { tur: 'tamam', metin: `Başarılı · returnCode 0${s.http ? ` · HTTP ${s.http}` : ''}` };
  }
  if (s.durum === 'onizleme') return { tur: 'hata', metin: 'Gönderilmedi (yalnız önizleme yapıldı).' };
  const parca = [
    s.return_mesaji || s.hata || (s.durum === 'gonderildi' ? 'BOSS isteği kabul etmedi' : 'Hata'),
    rk !== null && rk !== undefined ? `returnCode ${rk}` : null,
    s.http ? `HTTP ${s.http}` : null,
    s.belirsiz ? 'sonuç gelmedi' : null,
    s.yanit && !s.return_mesaji ? `yanıt: ${s.yanit.slice(0, 300)}` : null,
  ].filter(Boolean);
  return { tur: 'hata', metin: parca.join(' · ') };
}

export function BossYazmaDeneme({ ozet, tazele }: { ozet: BossYazmaOzeti | undefined; tazele: () => void }) {
  const [isNo, setIsNo] = useState('');
  const [eylem, setEylem] = useState<BossYazmaEylem>('not');
  const [kayit, setKayit] = useState<BossYazmaOnizlemeKaydi | null | undefined>(undefined);
  const [hata, setHata] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);
  const [izlenen, setIzlenen] = useState<number | null>(null);
  const [yazma, setYazma] = useState<BossYazmaOzeti | undefined>(ozet);
  const [onayPenceresi, sor] = useOnay();
  const zamanlayici = useRef<number | null>(null);
  const tazeleRef = useRef(tazele);
  tazeleRef.current = tazele;

  useEffect(() => setYazma(ozet), [ozet]);

  /* Önizleme: Task No ya da eylem değişince (kısa gecikmeyle). */
  useEffect(() => {
    const no = isNo.trim();
    setKayit(undefined);
    setHata(null);
    if (!no) return;
    let iptal = false;
    const t = window.setTimeout(() => {
      bossYazmaOnizleme(no)
        .then((o) => !iptal && setKayit(o.kayitlar.find((k) => k.tur === eylem) ?? null))
        .catch((h) => !iptal && (setKayit(null), setHata(hataMetni(h))));
    }, 350);
    return () => {
      iptal = true;
      window.clearTimeout(t);
    };
  }, [isNo, eylem]);

  /* Gönderimden sonra 2 sn'de bir durum: deneme bitince durur. */
  useEffect(() => {
    if (izlenen === null) return;
    const yokla = async () => {
      try {
        const d = await bossDurum();
        const y = d?.yazma;
        setYazma(y);
        const bitti = !y?.deneme || y.deneme.id !== izlenen;
        if (bitti && y?.son_deneme?.id === izlenen) {
          setIzlenen(null);
          tazeleRef.current();
        }
      } catch {
        /* geçici hata: sonraki yoklamada yeniden denenir */
      }
    };
    void yokla();
    zamanlayici.current = window.setInterval(() => void yokla(), 2000);
    return () => {
      if (zamanlayici.current !== null) window.clearInterval(zamanlayici.current);
    };
  }, [izlenen]);

  const gonder = async () => {
    const no = isNo.trim();
    if (!no || mesgul) return;
    const evet = await sor({
      baslik: `BOSS'a gerçek istek gönderilsin mi?`,
      metin: `${no} · ${EYLEMLER.find((e) => e.deger === eylem)?.etiket}. Eklenti bu isteği BOSS'a bir kez gönderir.`,
      onay: 'Gönder',
    });
    if (!evet) return;
    setMesgul(true);
    setHata(null);
    try {
      const y = await bossYazmaDene(no, eylem);
      setIzlenen(y.kayit_id);
    } catch (h) {
      setHata(hataMetni(h));
    } finally {
      setMesgul(false);
    }
  };

  const anahtarDegistir = async () => {
    const acik = yazma?.ayar !== 'acik';
    const evet = await sor(
      acik
        ? {
            baslik: "BOSS'a yazma açılsın mı?",
            metin: 'Uygulamadaki Ata ve Not kayıtları (yalnız doğrulanmış şablonlar) BOSS’a kendiliğinden gönderilir.',
            onay: 'Aç',
            yikici: true,
          }
        : { baslik: "BOSS'a yazma kapatılsın mı?", metin: 'Hiçbir kayıt BOSS’a gönderilmez.', onay: 'Kapat' },
    );
    if (!evet) return;
    try {
      setYazma(await bossYazmaAnahtari(acik));
      tazele();
    } catch (h) {
      setHata(hataMetni(h));
    }
  };

  const suruyor = izlenen !== null;
  const son = !suruyor ? sonucMetni(yazma?.son_deneme) : null;
  const acik = yazma?.ayar === 'acik';

  return (
    <section className="bb-yazma" aria-label="BOSS'a deneme yazması">
      <header className="bb-yazma-bas">
        <h2>BOSS’a deneme yazması</h2>
        <span className={`bb-yazma-anahtar ${acik ? 'acik' : ''}`}>Genel yazma: {acik ? 'açık' : 'kapalı'}</span>
        <button type="button" className={`o-dugme kucuk${acik ? ' yikici-metin' : ''}`} onClick={() => void anahtarDegistir()}>
          {acik ? 'Kapat' : 'Aç'}
        </button>
      </header>

      <div className="o-arac">
        <input
          className="o-girdi bb-yazma-no"
          placeholder="Task No"
          aria-label="Task No"
          value={isNo}
          onChange={(o) => setIsNo(o.target.value)}
          onKeyDown={(o) => o.key === 'Enter' && void gonder()}
        />
        <Segment<BossYazmaEylem> etiket="Eylem" deger={eylem} degisti={setEylem} secenekler={EYLEMLER} />
        <button
          type="button"
          className="o-dugme vurgu"
          disabled={!isNo.trim() || !kayit || kayit.eksik.length > 0 || mesgul || suruyor}
          onClick={() => void gonder()}
        >
          Gönder
        </button>
      </div>

      {isNo.trim() && kayit === null && !hata ? (
        <p className="bb-yazma-not">Bu işte gönderilecek {KAYIT_ADI[eylem]} kaydı yok. Önce uygulamada bu eylemi yapın.</p>
      ) : null}
      {kayit ? (
        <div className="bb-yazma-onizleme">
          <div className="bb-yazma-satir">
            <span>
              {kayit.yontem} {kayit.yol}
            </span>
            {!kayit.dogrulandi ? <span className="bb-yazma-uyari">Şablon doğrulanmadı</span> : null}
            {kayit.eksik.length ? <span className="bb-yazma-uyari">Eksik: {kayit.eksik.join(', ')}</span> : null}
          </div>
          <pre>{JSON.stringify(kayit.govde, null, 2)}</pre>
        </div>
      ) : null}

      {suruyor ? (
        <p className="bb-yazma-sonuc bekliyor" role="status">
          Gönderiliyor… (kayıt {izlenen}; eklenti BOSS sekmesinden gönderecek)
        </p>
      ) : son ? (
        <p className={`bb-yazma-sonuc ${son.tur}`} role="status">
          Son deneme {yazma?.son_deneme?.is_no} · {yazma?.son_deneme?.tur}: {son.metin}
        </p>
      ) : null}
      {hata ? (
        <p className="bb-yazma-sonuc hata" role="alert">
          {hata}
        </p>
      ) : null}
      {onayPenceresi}
    </section>
  );
}
