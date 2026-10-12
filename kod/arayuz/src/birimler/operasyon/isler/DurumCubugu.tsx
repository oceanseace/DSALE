/**
 * TASKS'ın durum bilgisi — kabuğun alt durum çubuğuna yazılır (DurumIcerigi): kayıt sayısı
 * ("2.903 kayıttan 2.871 tanesi bulundu"), seçim özeti "Sayı: N · Seçili: N satır" (sayısal hücre varsa
 * Toplam ve Ortalama), kısa "Kopyalandı"; sağda ızgara yakınlaştırma kaydırıcısı (%50–200, Excel gibi). Giriş: <DurumCubugu …/>. Kim: Isler.tsx. Hesap: secim.ts → secimOzeti.
 */

import { useMemo } from 'react';
import type { IsSatir } from '../../../cekirdek/is/tipler';
import { DurumIcerigi } from '../../../cekirdek/ortak/Ilkel';
import { secimOzeti, type Alan } from './secim';
import type { Sutun } from './sutunlar';

const sayi = (n: number) => n.toLocaleString('tr-TR', { maximumFractionDigits: 2 });

export function DurumCubugu({
  satirlar,
  sutunlar,
  alan,
  toplamKayit,
  bildiri,
  yakinlik,
  yakinlikDegisti,
}: {
  satirlar: IsSatir[];
  sutunlar: Sutun[];
  alan: Alan | null;
  toplamKayit: number;
  /** Kısa süreli bilgi ("Kopyalandı: 12 satır"). */
  bildiri: string | null;
  /** Izgara yakınlaştırması (yüzde); verilmezse kaydırıcı görünmez. */
  yakinlik?: number;
  yakinlikDegisti?: (y: number) => void;
}) {
  const ozet = useMemo(() => secimOzeti(satirlar, sutunlar, alan), [satirlar, sutunlar, alan]);
  return (
    <DurumIcerigi>
      <span>
        {satirlar.length === toplamKayit
          ? `${sayi(toplamKayit)} kayıt`
          : `${sayi(toplamKayit)} kayıttan ${sayi(satirlar.length)} tanesi bulundu`}
      </span>
      {bildiri ? <span className="xg-durum-bildiri">{bildiri}</span> : null}
      {ozet ? (
        <span className="xg-durum-ozet">
          <span>Sayı: {sayi(ozet.sayi)}</span>
          <span>Seçili: {sayi(ozet.satir)} satır</span>
          {ozet.toplam !== null ? <span>Toplam: {sayi(ozet.toplam)}</span> : null}
          {ozet.ortalama !== null ? <span>Ortalama: {sayi(ozet.ortalama)}</span> : null}
        </span>
      ) : null}
      {yakinlik !== undefined && yakinlikDegisti ? (
        <span className="xg-yakinlik">
          <button type="button" aria-label="Uzaklaştır" title="Uzaklaştır (Ctrl+tekerlek)" onClick={() => yakinlikDegisti(Math.max(50, yakinlik - 10))}>
            −
          </button>
          <input
            type="range"
            min={50}
            max={200}
            step={10}
            value={yakinlik}
            aria-label="Tablo yakınlaştırma"
            onChange={(o) => yakinlikDegisti(Number(o.target.value))}
          />
          <button type="button" aria-label="Yakınlaştır" title="Yakınlaştır (Ctrl+tekerlek)" onClick={() => yakinlikDegisti(Math.min(200, yakinlik + 10))}>
            +
          </button>
          <button type="button" className="xg-yakinlik-yuzde" title="%100'e dön" onClick={() => yakinlikDegisti(100)}>
            %{yakinlik}
          </button>
        </span>
      ) : null}
    </DurumIcerigi>
  );
}
