/**
 * RUT (Operasyon menüsü, MAP'ten sonra) — kurulum ekiplerinin günlük rotası; ekiplere gönderilen Excel'in yerine.
 * Rota kendiliğinden kurulur: o gün randevusu olan işler (BOSS randevusu / uygulama ataması), ekip başına bir sayfa
 * (Excel sekmeleri gibi, altta) + "Özet". Satırlar randevu saatine göre. GİRİŞ, ÇIKIŞ, YARDIMCI, CİHAZ, SWITCH ID,
 * DURUM hücreleri yerinde yazılır (Enter: aşağı, Esc: vazgeç) ve sunucuda saklanır; gri yazı öneridir (teknisyenin
 * uygulamadaki saati, iş durumu). "Excel'e aktar" aynı çok sayfalı biçimi üretir. Sunucu: kod/operasyon/v2/rut.py.
 */

import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { Icerik, YonUst } from '../../../cekirdek/konsol/Kabuk';
import { HataKutusu, Iskelet } from '../../../cekirdek/ortak/Bos';
import { useBildirim } from '../../../cekirdek/ortak/Bildirim';
import { Dugme, SimgeDugme } from '../../../cekirdek/ortak/Ilkel';
import { Geri, Ileri } from '../../../cekirdek/ortak/Ikon';
import { rutGetir, rutHucreYaz, rutMesaiYaz, type RutAlan, type RutGun, type RutSatir } from './api';
import { rutExcel } from './excel';
import '../isler/tablo.css';
import './rut.css';

const OZET = '__ozet__';
const TAZELEME_MS = 120_000;

function bugun(): string {
  const d = new Date();
  const iki = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${iki(d.getMonth() + 1)}-${iki(d.getDate())}`;
}

function gunKaydir(tarih: string, fark: number): string {
  const [y, a, g] = tarih.split('-').map(Number);
  const d = new Date(y, a - 1, g + fark);
  const iki = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${iki(d.getMonth() + 1)}-${iki(d.getDate())}`;
}

function tarihMetni(tarih: string): string {
  const [y, a, g] = tarih.split('-').map(Number);
  return new Date(y, a - 1, g).toLocaleDateString('tr-TR', { weekday: 'long', day: 'numeric', month: 'long' });
}

function sade(s: unknown): string {
  return String(s ?? '')
    .toLocaleUpperCase('tr-TR')
    .replace(/Ç/g, 'C')
    .replace(/Ğ/g, 'G')
    .replace(/İ/g, 'I')
    .replace(/Ö/g, 'O')
    .replace(/Ş/g, 'S')
    .replace(/Ü/g, 'U');
}

/** DURUM hücresinin rengi (Excel'deki dolgu gibi). */
function durumSinifi(d: unknown): string {
  const s = sade(d);
  if (!s) return '';
  if (s.startsWith('KURUL') || s.startsWith('TAMAM')) return 'rut-d-tamam';
  if (s.includes('IPTAL')) return 'rut-d-iptal';
  if (s.includes('ERTELE')) return 'rut-d-ertele';
  return 'rut-d-diger';
}

const SAAT_ALANI = new Set(['giris', 'cikis']);

/* ================================================================== düzenlenir hücre */

function DuzenHucre({
  satir,
  alan,
  sira,
  kaydet,
}: {
  satir: RutSatir;
  alan: RutAlan;
  sira: number;
  kaydet: (s: RutSatir, alan: RutAlan, deger: string) => Promise<boolean>;
}) {
  const elle = satir.elle.includes(alan) ? String(satir[alan] ?? '') : '';
  const [deger, setDeger] = useState(elle);
  const vazgecildi = useRef(false);
  const oneri = satir.oneri[alan] ?? '';

  const bitir = async () => {
    if (vazgecildi.current) {
      vazgecildi.current = false;
      setDeger(elle);
      return;
    }
    if (deger.trim() === elle.trim()) return;
    const tamam = await kaydet(satir, alan, deger.trim());
    if (!tamam) setDeger(elle);
  };

  const tus = (e: KeyboardEvent<HTMLInputElement>) => {
    const ileri = e.key === 'Enter' || e.key === 'ArrowDown';
    const geri = e.key === 'ArrowUp';
    if (e.key === 'Escape') {
      vazgecildi.current = true;
      e.currentTarget.blur();
      return;
    }
    if (ileri || geri) {
      e.preventDefault();
      const hedef = document.querySelector<HTMLInputElement>(
        `input[data-rut-alan="${alan}"][data-rut-sira="${sira + (geri ? -1 : 1)}"]`,
      );
      if (hedef) hedef.focus();
      else e.currentTarget.blur();
    }
  };

  const gorunen = deger || oneri;
  return (
    <td className={`rut-duzen ${alan === 'durum' ? durumSinifi(gorunen) : ''}`}>
      <input
        className={`rut-girdi${SAAT_ALANI.has(alan) ? ' saat' : ''}`}
        value={deger}
        placeholder={oneri}
        title={oneri && !deger ? `Öneri: ${oneri} (yazarsanız sizin değeriniz geçer)` : undefined}
        list={alan === 'durum' ? 'rut-durumlar' : undefined}
        inputMode={SAAT_ALANI.has(alan) ? 'numeric' : undefined}
        maxLength={SAAT_ALANI.has(alan) ? 5 : 200}
        data-rut-alan={alan}
        data-rut-sira={sira}
        aria-label={alan}
        onChange={(e) => setDeger(e.target.value)}
        onFocus={(e) => e.currentTarget.select()}
        onBlur={() => void bitir()}
        onKeyDown={tus}
      />
    </td>
  );
}

/* ================================================================== ekip sayfası */

function EkipSayfasi({
  gun,
  satirlar,
  kaydet,
}: {
  gun: RutGun;
  satirlar: RutSatir[];
  kaydet: (s: RutSatir, alan: RutAlan, deger: string) => Promise<boolean>;
}) {
  if (!satirlar.length) return <p className="rut-bos">Bu ekibin bu gün randevusu yok.</p>;
  return (
    <div className="rut-kaydir">
      <table className="rut-tablo">
        <thead>
          <tr>
            <th className="rut-no">#</th>
            {gun.sutunlar.map((c) => (
              <th key={c.id} className={c.duzenlenir ? 'rut-bas-duzen' : undefined}>
                {c.baslik}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {satirlar.map((s, i) => (
            <tr key={s.task_no} className={s.tur === 'yan' ? 'rut-yan' : undefined}>
              <td className="rut-no">{i + 1}</td>
              {gun.sutunlar.map((c) =>
                c.duzenlenir ? (
                  <DuzenHucre
                    key={`${c.id}:${s.elle.includes(c.id) ? String(s[c.id] ?? '') : ''}`}
                    satir={s}
                    alan={c.id as RutAlan}
                    sira={i}
                    kaydet={kaydet}
                  />
                ) : (
                  <td key={c.id} className={`rut-c-${c.id}`} title={s[c.id] != null ? String(s[c.id]) : undefined}>
                    {s[c.id] != null ? String(s[c.id]) : ''}
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
      <datalist id="rut-durumlar">
        {gun.durumlar.map((d) => (
          <option key={d} value={d} />
        ))}
      </datalist>
    </div>
  );
}

/* ================================================================== özet */

function OzetSayfasi({ gun, mesaiKaydet }: { gun: RutGun; mesaiKaydet: (bas: string, bit: string) => void }) {
  const [bas, setBas] = useState(gun.mesai.bas);
  const [bit, setBit] = useState(gun.mesai.bit);
  useEffect(() => {
    setBas(gun.mesai.bas);
    setBit(gun.mesai.bit);
  }, [gun.mesai.bas, gun.mesai.bit]);
  const toplam = (a: 'mesai_ici' | 'iptal_erteleme' | 'mesai_disi' | 'yan_is') =>
    gun.ozet.reduce((t, o) => t + o[a], 0);
  const degisti = bas !== gun.mesai.bas || bit !== gun.mesai.bit;
  return (
    <>
      <div className="rut-kaydir">
        <table className="rut-tablo rut-ozet">
          <thead>
            <tr>
              {gun.ozet_sutunlari.map((c) => (
                <th key={c.id}>{c.baslik}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {gun.ozet.map((o) => (
              <tr key={o.sef}>
                {gun.ozet_sutunlari.map((c) => (
                  <td key={c.id} className={typeof o[c.id] === 'number' ? 'rut-sayi' : undefined}>
                    {o[c.id] ?? ''}
                  </td>
                ))}
              </tr>
            ))}
            <tr className="rut-toplam">
              {gun.ozet_sutunlari.map((c) => (
                <td key={c.id} className="rut-sayi">
                  {c.id === 'sef'
                    ? 'TOPLAM'
                    : c.id === 'mesai_ici' || c.id === 'iptal_erteleme' || c.id === 'mesai_disi' || c.id === 'yan_is'
                      ? toplam(c.id)
                      : ''}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      <form
        className="rut-mesai"
        onSubmit={(e) => {
          e.preventDefault();
          mesaiKaydet(bas, bit);
        }}
      >
        <span>Mesai</span>
        <input type="time" className="o-girdi kucuk" value={bas} onChange={(e) => setBas(e.target.value)} aria-label="Mesai başlangıcı" />
        <span>–</span>
        <input type="time" className="o-girdi kucuk" value={bit} onChange={(e) => setBit(e.target.value)} aria-label="Mesai bitişi" />
        <Dugme type="submit" boy="kucuk" disabled={!degisti || !bas || !bit}>
          Kaydet
        </Dugme>
        <span className="rut-not">
          Mesai içi/dışı: kurulan fiber kurulumun çıkış saatine (yoksa giriş, yoksa randevu) göre. Yan iş: TV, donanım,
          arıza.
        </span>
      </form>
    </>
  );
}

/* ================================================================== ekran */

export function Rut() {
  const { goster } = useBildirim();
  const [tarih, setTarih] = useState(bugun);
  const [gun, setGun] = useState<RutGun | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [sekme, setSekme] = useState<string>(OZET);
  const [aktariliyor, setAktariliyor] = useState(false);
  const istekNo = useRef(0);

  const yukle = useCallback(
    async (sessiz = false) => {
      const no = ++istekNo.current;
      if (!sessiz) {
        setGun(null);
        setHata(null);
      }
      try {
        const y = await rutGetir(tarih);
        if (no === istekNo.current) setGun(y);
      } catch (e) {
        if (no === istekNo.current && !sessiz) setHata(e instanceof Error ? e.message : 'Rut alınamadı.');
      }
    },
    [tarih],
  );

  useEffect(() => {
    void yukle();
  }, [yukle]);

  /* Arka planda tazele (BOSS'tan yeni randevu gelmiş olabilir) — hücre yazılırken değil. */
  useEffect(() => {
    const t = window.setInterval(() => {
      const odak = document.activeElement;
      if (document.hidden || (odak instanceof HTMLInputElement && odak.closest('.rut'))) return;
      void yukle(true);
    }, TAZELEME_MS);
    return () => window.clearInterval(t);
  }, [yukle]);

  const kaydet = useCallback(
    async (s: RutSatir, alan: RutAlan, deger: string) => {
      try {
        istekNo.current++; // süren tazelemenin eski yanıtı yeni yazının üstüne yazmasın
        const y = await rutHucreYaz(tarih, s.task_no, alan, deger);
        setGun(y);
        return true;
      } catch (e) {
        goster(e instanceof Error ? e.message : 'Kaydedilemedi.', 'uyari');
        return false;
      }
    },
    [tarih, goster],
  );

  const mesaiKaydet = useCallback(
    async (bas: string, bit: string) => {
      try {
        await rutMesaiYaz(bas, bit);
        goster('Mesai saatleri kaydedildi.', 'basari');
        void yukle(true);
      } catch (e) {
        goster(e instanceof Error ? e.message : 'Kaydedilemedi.', 'uyari');
      }
    },
    [goster, yukle],
  );

  const aktar = async () => {
    if (!gun) return;
    setAktariliyor(true);
    try {
      const sonuc = await rutExcel(gun);
      goster(sonuc === 'acildi' ? 'Rut Excel’de açıldı.' : 'Rut indirildi.', 'basari');
    } finally {
      setAktariliyor(false);
    }
  };

  const ekip = useMemo(() => gun?.ekipler.find((e) => e.ad === sekme) ?? null, [gun, sekme]);
  useEffect(() => {
    if (gun && sekme !== OZET && !ekip) setSekme(OZET);
  }, [gun, sekme, ekip]);

  return (
    <>
      <YonUst
        baslik="RUT"
        altYazi={gun ? `${tarihMetni(tarih)} · ${gun.ekipler.length} ekip · ${gun.adet} iş` : tarihMetni(tarih)}
      />
      <Icerik>
        <div className="rut">
          <div className="xg-arac">
            <SimgeDugme etiket="Önceki gün" onClick={() => setTarih(gunKaydir(tarih, -1))}>
              <Geri boyut={16} />
            </SimgeDugme>
            <input
              type="date"
              className="o-girdi rut-tarih"
              value={tarih}
              onChange={(e) => e.target.value && setTarih(e.target.value)}
              aria-label="Tarih"
            />
            <SimgeDugme etiket="Sonraki gün" onClick={() => setTarih(gunKaydir(tarih, 1))}>
              <Ileri boyut={16} />
            </SimgeDugme>
            {tarih !== bugun() ? (
              <Dugme tur="metin" onClick={() => setTarih(bugun())}>
                Bugün
              </Dugme>
            ) : null}
            <span className="xg-bosluk" />
            <Dugme tur="metin" onClick={() => void yukle()}>
              Yenile
            </Dugme>
            <Dugme onClick={() => void aktar()} disabled={!gun || !gun.adet || aktariliyor}>
              Excel’e aktar
            </Dugme>
          </div>

          {hata ? (
            <HataKutusu mesaj={hata} tekrar={() => void yukle()} />
          ) : !gun ? (
            <Iskelet satir={6} yukseklik={28} />
          ) : !gun.adet ? (
            <p className="rut-bos">
              Bu gün için randevulu iş yok.
            </p>
          ) : (
            <>
              <div className="rut-sayfa">
                {sekme === OZET || !ekip ? (
                  <OzetSayfasi gun={gun} mesaiKaydet={(a, b) => void mesaiKaydet(a, b)} />
                ) : (
                  <EkipSayfasi key={`${gun.tarih}:${ekip.ad}`} gun={gun} satirlar={ekip.satirlar} kaydet={kaydet} />
                )}
              </div>
              <nav className="rut-sekmeler" aria-label="Sayfalar">
                <button
                  type="button"
                  className={sekme === OZET ? 'secili' : undefined}
                  aria-current={sekme === OZET ? 'page' : undefined}
                  onClick={() => setSekme(OZET)}
                >
                  Özet
                </button>
                {gun.ekipler.map((e) => (
                  <button
                    type="button"
                    key={e.ad}
                    className={sekme === e.ad ? 'secili' : undefined}
                    aria-current={sekme === e.ad ? 'page' : undefined}
                    onClick={() => setSekme(e.ad)}
                  >
                    {e.ad} <span className="rut-sekme-sayi">{e.satirlar.length}</span>
                  </button>
                ))}
              </nav>
            </>
          )}
        </div>
      </Icerik>
    </>
  );
}
