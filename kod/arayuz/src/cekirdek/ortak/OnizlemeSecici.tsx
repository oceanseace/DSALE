/**
 * Administrator "Görünüm" seçici: Administrator | <unvan listesi>.
 *
 * Bir unvan seçilince arayüz o unvandaki biri gibi çizilir (menü + açılış
 * ekranı). Yalnız istemci önizlemesidir; sunucu yetkisi değişmez, Administrator
 * bütün haklarını korur. Üstte ince "Önizleme: <unvan> — çık" şeridi durur.
 */

import { useEffect, useState } from 'react';
import { matrisOku } from '../api/yonetim';
import type { UnvanMatrisi } from '../api/yonetimTipleri';
import type { Rol } from '../api/tipler';
import { ROLLER } from './yetki';
import { useOturum, type Onizleme } from '../yerel/oturum';

/** Matris bir kez çekilir (sayfa ömrü boyunca). */
let onbellek: Promise<UnvanMatrisi> | null = null;

function onizlemeHesapla(m: UnvanMatrisi, id: number): Onizleme | null {
  const u = m.unvanlar.find((x) => x.id === id);
  if (!u) return null;
  const izinler = new Set<string>();
  const gorevler = new Set<Rol>();
  for (const kod of u.yetkinlikler) {
    const y = m.yetkinlikler.find((t) => t.kod === kod);
    if (!y) continue;
    y.izinler.forEach((i) => izinler.add(i));
    if (y.gorev) gorevler.add(y.gorev);
  }
  izinler.add('oturum');
  return { id: u.id, ad: u.ad, izinler: [...izinler], gorevler: ROLLER.filter((r) => gorevler.has(r)) };
}

export function OnizlemeSecici({ kucuk = false }: { kucuk?: boolean }) {
  const { gercekAdministrator, onizleme, onizlemeSec } = useOturum();
  const [matris, setMatris] = useState<UnvanMatrisi | null>(null);

  useEffect(() => {
    if (!gercekAdministrator) return;
    let iptal = false;
    onbellek ??= matrisOku();
    onbellek
      .then((m) => !iptal && setMatris(m))
      .catch(() => {
        onbellek = null;
      });
    return () => {
      iptal = true;
    };
  }, [gercekAdministrator]);

  if (!gercekAdministrator) return null;
  const unvanlar = (matris?.unvanlar ?? []).filter((u) => u.aktif);

  return (
    <label className={kucuk ? 'kabuk-onizleme' : 'onizleme-secici'}>
      <span>Görünüm:</span>
      <select
        value={onizleme ? String(onizleme.id) : ''}
        onChange={(o) => {
          const id = Number(o.target.value);
          if (!o.target.value || !matris) {
            onizlemeSec(null);
            return;
          }
          onizlemeSec(onizlemeHesapla(matris, id));
        }}
      >
        <option value="">Administrator</option>
        {onizleme && !unvanlar.some((u) => u.id === onizleme.id) ? (
          <option value={String(onizleme.id)}>{onizleme.ad}</option>
        ) : null}
        {unvanlar.map((u) => (
          <option key={u.id} value={String(u.id)}>
            {u.ad}
          </option>
        ))}
      </select>
    </label>
  );
}

/** Önizleme açıkken en üstte ince şerit: "Önizleme: <unvan> — çık". */
export function OnizlemeSeridi() {
  const { onizleme, onizlemeSec } = useOturum();
  if (!onizleme) return null;
  return (
    <div className="onizleme-seridi" role="status">
      <span>
        Önizleme: <strong>{onizleme.ad}</strong>
      </span>
      <button type="button" onClick={() => onizlemeSec(null)}>
        çık
      </button>
    </div>
  );
}
