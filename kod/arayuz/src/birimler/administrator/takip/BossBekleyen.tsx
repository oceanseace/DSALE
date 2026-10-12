/**
 * Pano ▸ Hijyen ▸ "BOSS’a yazılmayı bekleyen": uygulamada yapılıp BOSS'a henüz yazılmamış işlemler
 * (sunucunun `boss_bekleyen` sayacı; Excel'den gelmez). Satırın yanında yazma durumu
 * (`GET /api/boss/durum` → yazma.ayar): açıksa "otomatik yazılıyor", kapalıysa "yazma kapalı (atama)".
 * Tıklayınca çekmece: hangi iş, hangi eylem (atama · randevu · askı · SMS) — `GET /api/boss/giden`.
 * Notlar artık kendiliğinden BOSS'a gider; bu listede yer almaz. Uçlar yoksa / izin yoksa sessizce boş.
 */

import { useEffect, useMemo, useState } from 'react';
import { bossDurum, bossGiden, hataMetni } from '../../../cekirdek/is/api';
import type { BossGiden } from '../../../cekirdek/is/tipler';
import { Panel } from '../../../cekirdek/ortak/Panel';
import { HataKutusu, Iskelet } from '../../../cekirdek/ortak/Bos';
import { KopyalaNo } from '../../../cekirdek/ortak/KopyalaNo';
import { Hap } from '../../../cekirdek/ortak/Rozet';
import { sayi } from '../../../cekirdek/ortak/bicim';
import { tarihSaatMetni } from './parcalar';

const EYLEM: Record<string, string> = { ekip: 'Atama', randevu: 'Randevu', aski: 'Askı', sms: 'SMS', not: 'Not' };

export function eylemler(neden: string): string[] {
  return [...new Set(neden.split(',').map((n) => EYLEM[n.trim()] ?? n.trim()).filter(Boolean))];
}

/** Yazma anahtarının kısa durumu; okunamazsa null. */
export function useBossYazmaDurumu(): string | null {
  const [durum, setDurum] = useState<string | null>(null);
  useEffect(() => {
    let iptal = false;
    bossDurum()
      .then((d) => {
        if (iptal || !d?.yazma) return;
        setDurum(d.yazma.ayar === 'acik' ? 'otomatik yazılıyor' : 'yazma kapalı (atama)');
      })
      .catch(() => undefined);
    return () => {
      iptal = true;
    };
  }, []);
  return durum;
}

export function BossBekleyenPaneli({
  acik,
  kapat,
  durum,
  tasksaGit,
}: {
  acik: boolean;
  kapat: () => void;
  durum: string | null;
  /** TASKS'ın "BOSS'a işlenecek" bölümüne git (izin varsa). */
  tasksaGit: (() => void) | null;
}) {
  const [liste, setListe] = useState<BossGiden[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);

  useEffect(() => {
    if (!acik) return;
    let iptal = false;
    setHata(null);
    bossGiden()
      .then((l) => !iptal && setListe(Array.isArray(l) ? l : []))
      .catch((e) => !iptal && setHata(hataMetni(e)));
    return () => {
      iptal = true;
    };
  }, [acik]);

  const sayilar = useMemo(() => {
    const s = new Map<string, number>();
    for (const g of liste ?? []) for (const e of eylemler(g.neden)) s.set(e, (s.get(e) ?? 0) + 1);
    return [...s.entries()];
  }, [liste]);

  return (
    <Panel
      acik={acik}
      kapat={kapat}
      baslik="BOSS’a yazılmayı bekleyen"
      altBaslik={durum ?? undefined}
      alt={
        tasksaGit ? (
          <>
            <span className="bosluk" />
            <button type="button" className="o-dugme" onClick={tasksaGit}>
              TASKS’ta aç
            </button>
          </>
        ) : undefined
      }
    >
      <p className="tp-bb-aciklama">
        Uygulamada yapılan, BOSS’a henüz yazılmamış işlemler. Excel’den gelmez. Notlar kendiliğinden BOSS’a gider.
      </p>
      {hata ? <HataKutusu mesaj={hata} /> : null}
      {!liste && !hata ? <Iskelet satir={5} /> : null}
      {liste && !liste.length ? <p className="tp-bos">Bekleyen işlem yok.</p> : null}
      {sayilar.length ? (
        <div className="tp-bb-ozet">
          {sayilar.map(([e, n]) => (
            <Hap key={e} renk="gri">
              {e} · {sayi(n)}
            </Hap>
          ))}
        </div>
      ) : null}
      {liste && liste.length ? (
        <ul className="tp-bb-liste">
          {liste.map((g) => (
            <li key={g.is_no}>
              <KopyalaNo deger={g.boss_task_no ?? g.is_no} />
              <span className="eylem">{eylemler(g.neden).join(' · ')}</span>
              <span className="zaman">{tarihSaatMetni(g.olusma)}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </Panel>
  );
}
