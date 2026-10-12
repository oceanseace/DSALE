/**
 * Operasyon ▸ BOSS bağlantısı: işler BOSS'tan BOSS Yardımcısı eklentisiyle canlı
 * gelir; elle rapor yüklenmez. Bu ekran bağlantının durumunu, eşleme kodunu ve
 * eklentinin Brave'e kurulum adımlarını gösterir. "BOSS yazma kuyruğu" (BossYazmaKuyrugu): son 7 günün BOSS'a yazma
 * kayıtları; #/yonetici/boss/kuyruk?ara=<task no> doğrudan oraya iner.
 */

import { useEffect, useState } from 'react';
import { bossEslesmeKodu, hataMetni, onemapDurum, type OnemapDurum } from '../../../cekirdek/is/api';
import { BOSS_HAL_METNI, useBossDurum } from '../../../cekirdek/is/boss';
import { Icerik, YonUst } from '../../../cekirdek/konsol/Kabuk';
import { HataKutusu } from '../../../cekirdek/ortak/Bos';
import { Hap } from '../../../cekirdek/ortak/Rozet';
import { DURUM_ETIKET } from '../../../cekirdek/is/tipler';
import { useOturum } from '../../../cekirdek/yerel/oturum';
import { tarihSaatMetni } from './parcalar';
import { BossYazmaDeneme } from './BossYazmaDeneme';
import { BossYazmaKuyrugu } from './BossYazmaKuyrugu';
import './isler.css';

const ADIMLAR: Array<{ baslik: string; ayrinti: string; kod?: string }> = [
  { baslik: 'Uzantılar sayfasını açın', ayrinti: 'Brave adres çubuğuna yazıp Enter’a basın:', kod: 'brave://extensions' },
  { baslik: '“Paketlenmemiş öğe yükle”ye basın', ayrinti: 'Sol üstteki düğme. Açılan pencerede bu klasörü seçin:', kod: 'kod\\eklenti' },
  { baslik: 'BOSS Teknik Havuz’u açın', ayrinti: 'BOSS’a her zamanki gibi girin, Teknik Havuz ekranını bir kez açın.' },
  { baslik: 'Kodu panele yazın', ayrinti: 'Sağdaki BOSS Yardımcısı panelinde aşağıdaki eşleme kodunu yazıp Kaydet’e basın. Bitti: işler 2 dakikada bir kendiliğinden gelir.' },
];

/** `deger`: adresin üçüncü parçası ("kuyruk" → kuyruğa in); `?ara=` kuyruğun Task No araması. */
export function BossBaglantisi({ deger = null }: { deger?: string | null }) {
  const { durum, hal, hata, tazele } = useBossDurum();
  const { gercekAdministrator, izinli } = useOturum();
  const kuyrukOdak = deger === 'kuyruk';
  const ilkAra = kuyrukOdak ? (new URLSearchParams(window.location.hash.split('?')[1] ?? '').get('ara') ?? '') : '';
  const [kod, setKod] = useState<string | null | undefined>(undefined);
  const [kodHata, setKodHata] = useState<string | null>(null);

  useEffect(() => {
    let iptal = false;
    bossEslesmeKodu()
      .then((k) => !iptal && setKod(k))
      .catch((h) => !iptal && (setKod(null), setKodHata(hataMetni(h))));
    return () => {
      iptal = true;
    };
  }, []);

  const renk = hal === 'bagli' ? 'yesil' : hal === 'kopuk' ? 'kirmizi' : hal === 'hata' ? 'kirmizi' : 'gri';
  const sayilar = Object.entries(durum?.durum_sayilari ?? {}).filter(([, v]) => v > 0);

  return (
    <>
      <YonUst baslik="BOSS bağlantısı">
        <button type="button" className="o-dugme" onClick={() => void tazele()}>
          Yenile
        </button>
      </YonUst>
      <Icerik>
        <section className={`bb-durum ${hal}`} aria-live="polite">
          <span className="bb-nokta" aria-hidden="true" />
          <div className="bb-durum-metin">
            <div className="bb-durum-bas">
              <b>{BOSS_HAL_METNI[hal]}</b>
              <Hap renk={renk}>{hal === 'bagli' ? 'canlı' : hal === 'kurulmadi' ? 'eklenti yok' : '—'}</Hap>
            </div>
            <span>
              {hal === 'kurulmadi'
                ? 'Sunucu henüz BOSS Yardımcısı’ndan veri almadı. Aşağıdaki adımlarla eklentiyi kurun.'
                : durum?.son_esitleme
                  ? `Son eşitleme ${tarihSaatMetni(durum.son_esitleme)}`
                  : 'Henüz eşitleme yapılmadı.'}
            </span>
          </div>
          {durum ? (
            <div className="bb-sayi">
              <b>{durum.acik_sayisi.toLocaleString('tr-TR')}</b>
              <span>açık iş</span>
            </div>
          ) : null}
        </section>
        {durum?.uyari ? <p className="bb-kod-yok">{durum.uyari}</p> : null}
        {hal === 'hata' && hata ? <HataKutusu mesaj={hata} tekrar={() => void tazele()} /> : null}

        {sayilar.length ? (
          <div className="bb-durumlar">
            {sayilar.map(([d, v]) => (
              <span key={d} className="bb-durum-hap">
                {DURUM_ETIKET[d as keyof typeof DURUM_ETIKET] ?? d} <b>{v.toLocaleString('tr-TR')}</b>
              </span>
            ))}
          </div>
        ) : null}

        <OnemapKarti />

        {izinli('is.ata') ? <BossYazmaKuyrugu ilkAra={ilkAra} odak={kuyrukOdak} /> : null}

        {gercekAdministrator ? <BossYazmaDeneme ozet={durum?.yazma} tazele={() => void tazele()} /> : null}

        <section className="bb-kod">
          <div>
            <h2>Eşleme kodu</h2>
            <p>Eklenti panelinde bu kodu girin; eklenti bu sunucuya bağlanır.</p>
          </div>
          <div className="bb-kod-deger" aria-label="Eşleme kodu">
            {kod === undefined ? '…' : kod ?? '—'}
          </div>
          {kod === null ? <p className="bb-kod-yok">{kodHata ?? 'Eşleme kodu sunucuda henüz yok.'}</p> : null}
        </section>

        <section className="bb-adimlar">
          <h2>Brave’e kurulum</h2>
          <ol>
            {ADIMLAR.map((a, i) => (
              <li key={a.baslik}>
                <span className="bb-adim-no" aria-hidden="true">
                  {i + 1}
                </span>
                <div>
                  <b>{a.baslik}</b>
                  <span>{a.ayrinti}</span>
                  {a.kod ? <code>{a.kod}</code> : null}
                </div>
              </li>
            ))}
          </ol>
        </section>
      </Icerik>
    </>
  );
}

/** OneMap bina eşitlemesinin durumu (eklenti OneMap sekmesi açıkken bina listesini günceller). */
function OnemapKarti() {
  const [d, setD] = useState<OnemapDurum | null | undefined>(undefined);
  useEffect(() => {
    let iptal = false;
    const oku = () =>
      onemapDurum()
        .then((x) => !iptal && setD(x))
        .catch(() => !iptal && setD(null));
    void oku();
    const z = window.setInterval(oku, 60000);
    return () => {
      iptal = true;
      window.clearInterval(z);
    };
  }, []);
  if (!d) return null;
  return (
    <section className="bb-onemap" aria-live="polite">
      <div className="bb-onemap-bas">
        <h2>OneMap</h2>
        <Hap renk={d.bagli ? 'yesil' : 'gri'}>{d.bagli ? 'bağlı' : 'bağlı değil'}</Hap>
      </div>
      <dl className="bb-onemap-sayilar">
        <div>
          <dt>Son eşitleme</dt>
          <dd>{d.son_esitleme ? tarihSaatMetni(d.son_esitleme) : '—'}</dd>
        </div>
        <div>
          <dt>Yeni bina</dt>
          <dd>{d.yeni_bina.toLocaleString('tr-TR')}</dd>
        </div>
        <div>
          <dt>Bilinmeyen lokasyon</dt>
          <dd>{d.bilinmeyen_lokasyon.toLocaleString('tr-TR')}</dd>
        </div>
      </dl>
      {d.son_hata ? <p className="bb-kod-yok">OneMap: {d.son_hata}</p> : null}
      <p className="bb-onemap-not">OneMap sekmesini açık tutun.</p>
    </section>
  );
}
