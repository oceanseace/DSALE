/**
 * BOSS bağlantısı ▸ "BOSS yazma kuyruğu": son 7 günün BOSS'a yazma kayıtları (atama / askı / not) — bekleyen,
 * giden, ✓, hata, önizleme, eksik alan. Kullanıcı gitmeyen yazmaları görür, satır seçip "Hata raporunu kopyala" ile
 * panoya KİŞİSEL VERİ OLMADAN düz metin alır (task no, eylem, durum, mesaj, zaman, eksik alan) ve hata ayıklama için
 * iletir. Hatalı / eksik kayıtta "Yeniden dene" (tek kayıt). Sunucu: GET /api/boss/yazmalar,
 * POST /api/boss/yazmalar/{id}/yeniden (is.ata). Doğrudan adres: #/yonetici/boss/kuyruk?ara=<task no>
 * (İş çekmecesindeki "BOSS kuyruğunda gör").
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { bossKuyruk, bossKuyrukYeniden, hataMetni, type BossKuyruk, type BossKuyrukKaydi } from '../../../cekirdek/is/api';
import { Hap } from '../../../cekirdek/ortak/Rozet';
import { tarihSaatMetni } from './parcalar';

const TAZELE_MS = 15_000;

const DURUMLAR: Array<{ deger: string; etiket: string; renk: 'mavi' | 'yesil' | 'kirmizi' | 'gri' | 'amber' }> = [
  { deger: 'bekliyor', etiket: 'Bekliyor', renk: 'mavi' },
  { deger: 'gonderiliyor', etiket: 'Gönderiliyor', renk: 'mavi' },
  { deger: 'gonderildi', etiket: '✓ BOSS’ta', renk: 'yesil' },
  { deger: 'hata', etiket: 'Hata', renk: 'kirmizi' },
  { deger: 'eksik', etiket: 'Eksik alan', renk: 'amber' },
  { deger: 'onizleme', etiket: 'Önizleme', renk: 'gri' },
];
const DURUM = Object.fromEntries(DURUMLAR.map((d) => [d.deger, d]));
DURUM.zaman_asimi = { deger: 'zaman_asimi', etiket: 'Zaman aşımı', renk: 'kirmizi' };
const EYLEMLER = [
  { deger: 'atama', etiket: 'Atama' },
  { deger: 'aski', etiket: 'Askı' },
  { deger: 'not', etiket: 'Not' },
];
const EYLEM_ADI: Record<string, string> = { atama: 'Atama', aski: 'Askı', not: 'Not' };

/** Kişisel veri içermeyen düz metin rapor (panoya). */
export function hataRaporu(kayitlar: BossKuyrukKaydi[], an: Date = new Date()): string {
  const satirlar = kayitlar.map((k) => {
    const p = [
      `#${k.id}`,
      k.zaman,
      EYLEM_ADI[k.tur] ?? k.tur,
      `Task ${k.task_no}`,
      DURUM[k.durum]?.etiket ?? k.durum,
    ];
    if (k.http) p.push(`HTTP ${k.http}`);
    if (k.return_kodu !== null && k.return_kodu !== undefined && String(k.return_kodu) !== '0') p.push(`returnCode ${k.return_kodu}`);
    if (k.mesaj) p.push(k.mesaj);
    if (k.eksik.length) p.push(`Eksik: ${k.eksik.join(', ')}`);
    return p.join(' · ');
  });
  return [`BOSS yazma hata raporu · ${an.toLocaleString('tr-TR')} · ${kayitlar.length} kayıt`, ...satirlar].join('\n');
}

export function BossYazmaKuyrugu({ ilkAra = '', odak = false }: { ilkAra?: string; odak?: boolean }) {
  const [veri, setVeri] = useState<BossKuyruk | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [durum, setDurum] = useState('');
  const [tur, setTur] = useState('');
  const [ara, setAra] = useState(ilkAra);
  const [secili, setSecili] = useState<Set<number>>(new Set());
  const [bilgi, setBilgi] = useState<string | null>(null);
  const [gidiyor, setGidiyor] = useState<number | null>(null);

  useEffect(() => setAra(ilkAra), [ilkAra]);
  const kutu = useRef<HTMLElement>(null);
  useEffect(() => {
    if (odak) kutu.current?.scrollIntoView({ block: 'start' }); // doğrudan adresle gelindi: kuyruğa in
  }, [odak]);

  const oku = useCallback(async () => {
    try {
      setVeri(await bossKuyruk({ durum, tur, ara: ara.trim() }));
      setHata(null);
    } catch (h) {
      setHata(hataMetni(h));
    }
  }, [durum, tur, ara]);

  useEffect(() => {
    const t = window.setTimeout(() => void oku(), 250); // aramada her tuşta değil
    const z = window.setInterval(() => void oku(), TAZELE_MS);
    return () => {
      window.clearTimeout(t);
      window.clearInterval(z);
    };
  }, [oku]);

  const kayitlar = useMemo(() => veri?.kayitlar ?? [], [veri]);
  useEffect(() => {
    const var_ = new Set(kayitlar.map((k) => k.id));
    setSecili((s) => new Set([...s].filter((i) => var_.has(i))));
  }, [kayitlar]);

  const sec = (id: number) =>
    setSecili((s) => {
      const y = new Set(s);
      if (y.has(id)) y.delete(id);
      else y.add(id);
      return y;
    });
  const hepsiSecili = kayitlar.length > 0 && kayitlar.every((k) => secili.has(k.id));

  const kopyala = async () => {
    const hedef = kayitlar.filter((k) => secili.has(k.id));
    const liste = hedef.length ? hedef : kayitlar.filter((k) => ['hata', 'zaman_asimi', 'eksik'].includes(k.durum));
    if (!liste.length) {
      setBilgi('Kopyalanacak kayıt yok: satır seçin.');
      return;
    }
    try {
      await navigator.clipboard.writeText(hataRaporu(liste));
      setBilgi(`${liste.length} kaydın raporu panoya kopyalandı${hedef.length ? '' : ' (seçim yok: hatalı/eksik olanlar)'}.`);
    } catch {
      setBilgi('Panoya kopyalanamadı.');
    }
  };

  const yeniden = async (k: BossKuyrukKaydi) => {
    setGidiyor(k.id);
    try {
      const y = await bossKuyrukYeniden(k.id);
      setBilgi(`Task ${k.task_no}: ${y.aciklama}`);
      await oku();
    } catch (h) {
      setBilgi(`Task ${k.task_no}: ${hataMetni(h)}`);
    } finally {
      setGidiyor(null);
    }
  };

  const sayilar = veri?.sayilar ?? {};
  return (
    <section className="bk-kuyruk" id="boss-kuyruk" ref={kutu}>
      <div className="bk-bas">
        <h2>BOSS yazma kuyruğu</h2>
        <span className="bk-alt">Son {veri?.gun ?? 7} gün · {(veri?.toplam ?? 0).toLocaleString('tr-TR')} kayıt</span>
      </div>
      <div className="bk-suzgec">
        <select className="o-girdi" value={durum} onChange={(o) => setDurum(o.target.value)} aria-label="Durum">
          <option value="">Bütün durumlar</option>
          {DURUMLAR.map((d) => (
            <option key={d.deger} value={d.deger}>
              {d.etiket}
              {sayilar[d.deger] ? ` (${sayilar[d.deger]})` : ''}
            </option>
          ))}
        </select>
        <select className="o-girdi" value={tur} onChange={(o) => setTur(o.target.value)} aria-label="Eylem">
          <option value="">Bütün eylemler</option>
          {EYLEMLER.map((e) => (
            <option key={e.deger} value={e.deger}>
              {e.etiket}
            </option>
          ))}
        </select>
        <input
          className="o-girdi bk-ara"
          value={ara}
          inputMode="numeric"
          placeholder="Task No ara"
          aria-label="Task No ara"
          onChange={(o) => setAra(o.target.value)}
        />
        <button type="button" className="o-dugme" onClick={() => void kopyala()}>
          Hata raporunu kopyala{secili.size ? ` (${secili.size})` : ''}
        </button>
      </div>
      {bilgi ? <p className="bk-bilgi">{bilgi}</p> : null}
      {hata ? <p className="bb-kod-yok">{hata}</p> : null}
      {veri && !kayitlar.length ? <p className="bk-bos">Bu süzgeçte kayıt yok.</p> : null}
      {kayitlar.length ? (
        <div className="bk-tablo-kap">
          <table className="bk-tablo">
            <thead>
              <tr>
                <th>
                  <input
                    type="checkbox"
                    aria-label="Hepsini seç"
                    checked={hepsiSecili}
                    onChange={() => setSecili(hepsiSecili ? new Set() : new Set(kayitlar.map((k) => k.id)))}
                  />
                </th>
                <th>Zaman</th>
                <th>Eylem</th>
                <th>Task No</th>
                <th>Durum</th>
                <th>Mesaj / eksik alan</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {kayitlar.map((k) => {
                const d = DURUM[k.durum];
                return (
                  <tr key={k.id} className={secili.has(k.id) ? 'secili' : undefined} onClick={() => sec(k.id)}>
                    <td>
                      <input
                        type="checkbox"
                        aria-label={`Task ${k.task_no} seç`}
                        checked={secili.has(k.id)}
                        onClick={(o) => o.stopPropagation()}
                        onChange={() => sec(k.id)}
                      />
                    </td>
                    <td className="bk-zaman">{tarihSaatMetni(k.zaman)}</td>
                    <td>{EYLEM_ADI[k.tur] ?? k.tur}</td>
                    <td className="bk-no">{k.task_no}</td>
                    <td>
                      <Hap renk={d?.renk ?? 'gri'}>{d?.etiket ?? k.durum}</Hap>
                    </td>
                    <td className="bk-mesaj">
                      {k.mesaj ?? ''}
                      {k.eksik.length ? <span className="bk-eksik">Eksik: {k.eksik.join(' · ')}</span> : null}
                    </td>
                    <td>
                      {k.yeniden ? (
                        <button
                          type="button"
                          className="o-dugme kucuk"
                          disabled={gidiyor === k.id}
                          onClick={(o) => {
                            o.stopPropagation();
                            void yeniden(k);
                          }}
                        >
                          Yeniden dene
                        </button>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
