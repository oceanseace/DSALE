/**
 * BOSS bağlantısının canlı durumu (BOSS Yardımcısı eklentisi → sunucu).
 * 30 sn'de bir ve sekme öne gelince tazelenir.
 */

import { useCallback, useEffect, useState } from 'react';
import { bossDurum, hataMetni, type BossDurum } from './api';

export type BossHal = 'yukleniyor' | 'kurulmadi' | 'bagli' | 'kopuk' | 'hata';

export function useBossDurum(araMs = 30000) {
  const [durum, setDurum] = useState<BossDurum | null>(null);
  const [hal, setHal] = useState<BossHal>('yukleniyor');
  const [hata, setHata] = useState<string | null>(null);

  const tazele = useCallback(async () => {
    try {
      const d = await bossDurum();
      setDurum(d);
      setHata(null);
      setHal(!d ? 'kurulmadi' : d.bagli ? 'bagli' : 'kopuk');
    } catch (h) {
      setHata(hataMetni(h));
      setHal('hata');
    }
  }, []);

  useEffect(() => {
    void tazele();
    const t = window.setInterval(() => document.visibilityState === 'visible' && void tazele(), araMs);
    const odak = () => void tazele();
    window.addEventListener('focus', odak);
    return () => {
      window.clearInterval(t);
      window.removeEventListener('focus', odak);
    };
  }, [tazele, araMs]);

  return { durum, hal, hata, tazele };
}

export const BOSS_HAL_METNI: Record<BossHal, string> = {
  yukleniyor: 'Bağlantı denetleniyor…',
  kurulmadi: 'Bağlantı kurulmadı',
  bagli: 'Bağlı',
  kopuk: 'Bağlantı koptu',
  hata: 'Durum alınamadı',
};
