// BOSS görev nesnesi → uygulamanın sade görev biçimi. TEK eşleme yeri: alan adları burada, değerler hiçbir yere
// yazılmaz. Her alan birkaç olası addan (iç içe nesneler dahil) aranır; ilk aday 06.10 canlı akıştaki gerçek BOSS
// alan adıdır (gorev_yapisi olayı: crmTaskId, saleChannel, taskCategory, productInfo …). "alanHaritasi" hangi sade
// alanın hangi BOSS alanından geldiğini DEĞERSİZ döndürür (panelde gösterilir). Görevin BÜTÜN alanları ayrıca
// düzleştirilip ``ham`` olarak uygulamaya gider (sunucu: boss_ham.py → İşler tablosunun ek sütunları).
// Kullananlar: arka.js (importScripts) ve test.mjs.
(function (kok) {
  // sade alan → aday yollar (nokta = iç içe). Düzenli ifadeler alan ADINA bakar.
  const ALANLAR = {
    // Task No = BOSS iş emri / Fox akış no (9 hane). Ayrı bulunur (taskNoBul): yalnız 6–12 haneli SAYISAL değer kabul
    // edilir; uuid ("id") ASLA rakamlarına indirgenip task no yapılmaz.
    task_no: [/^crm.?task.?id$/i, /^task.?no$/i, /^task.?number$/i, /^task\.(no|number)$/i, /^(fox|flow|akis).?(flow.?)?(no|number|id)?$/i,
      /^(work.?)?order.?(no|number|id)$/i, /^is.?emri.?no$/i, /^task.?(code|ref(erence)?(.?no)?)$/i, /^(no|number|code)$/i,
      /^task.?id$/i, /^external.?(id|no)$/i, /^reference.?(no|number)$/i],
    musteri_no: [/^customer.?(no|number|id)$/i, /^musteri.?no$/i, /^customer\.(no|number|customerno|id)$/i, /^subscriber.?no$/i],
    musteri_adi: [/^customer.?name$/i, /^customer.?full.?name$/i, /^musteri.?ad/i, /^customer\.(name|fullname)$/i, /^full.?name$/i],
    telefon: [/^(contact|customer|gsm|mobile)?.?phone(.?number)?$/i, /^gsm(.?no)?$/i, /^msisdn$/i, /^tel(efon)?$/i, /^customer\.(phone|gsm|msisdn)/i, /^contact.?(no|number|gsm)$/i],
    task_adi: [/^task.?(name|type.?name|ad)$/i, /^task.?type\.name$/i, /^task.?type\.description$/i, /^type.?name$/i, /^task.?type$/i],
    kategori: [/^category.?name$/i, /^category\.(name|description)$/i, /^task.?category/i, /^category$/i],
    durum: [/^status.?name$/i, /^status\.(name|description|label)$/i, /^task.?status.?(name|desc)/i, /^status.?desc/i, /^task.?status$/i, /^status$/i],
    ekip: [/^team.?name$/i, /^team\.(name|teamname|description)$/i, /^assigned.?team/i, /^ekip/i, /^team$/i],
    acilis: [/^create.?(d|date|time|dt)$/i, /^created.?(at|date)$/i, /^creation.?date$/i, /^start.?date$/i, /^task.?start/i, /^open.?date$/i],
    randevu_bas: [/^appointment.?start/i, /^appointment\.(start|startdate|begin)/i, /^randevu.?bas/i, /^appointment.?date$/i],
    randevu_bit: [/^appointment.?end/i, /^appointment\.(end|enddate|finish)/i, /^randevu.?bit/i],
    randevu_durumu: [/^appointment.?status/i, /^appointment\.status/i],
    lokasyon: [/^location.?id$/i, /^location\.(id|locationid)$/i, /^lokasyon$/i],
    bina: [/^(building|bina).?(code|serial|no|bn)$/i, /^bn.?(code|no)?$/i, /^location\.(bn|building)/i],
    adres: [/^(full.?)?address(.?text|.?line|.?desc)?$/i, /^open.?address$/i, /^adres$/i, /^location\.(address|fulladdress)/i, /^customer\.address/i],
    il: [/^(city|il|province).?(name)?$/i, /^address\.(city|province)/i, /^location\.(city|province)/i],
    ilce: [/^(district|ilce|county|town).?(name)?$/i, /^address\.(district|county|town)/i, /^location\.(district|county|town)/i],
    segment: [/^segment(.?name)?$/i, /^customer\.segment/i, /^customer.?segment$/i],
    satis_kanali: [/^sales?.?channel(.?name)?$/i, /^channel(.?name)?$/i, /^satis.?kanal/i],
    urun: [/^product.?info$/i, /^product(.?name)?$/i, /^offer(.?name)?$/i, /^tariff(.?name)?$/i, /^service.?type$/i],
    aski_nedeni: [/^(suspend|hold|pause).?reason/i, /^aski/i],
    son_aciklama: [/^last.?(comment|note|description)/i, /^comment$/i, /^description$/i],
    sl: [/^sl$/i, /^sla(.?status)?$/i],
    sl_saat: [/^sl.?(hour|sure|duration)/i, /^sla.?(hour|duration)/i],
    merkeze: [/^center.?status/i, /^merkez/i],
    konum_tarihi: [/^location.?share.?date/i, /^konum.?(paylas)?.?tarih/i],
    basla_tarihi: [/^(work|job).?start.?date/i, /^started.?(at|date)$/i],
    guncelleme: [/^(last.?)?(update|modif(y|ied|ication)).?(d|date|time|dt|at)$/i, /^updated.?(at|date|time)$/i],
  };

  function duzlestir(o, onek = '', cikti = {}, derinlik = 0) {
    if (!o || typeof o !== 'object' || derinlik > 3) return cikti;
    for (const k of Object.keys(o)) {
      const yol = onek ? `${onek}.${k}` : k;
      const v = o[k];
      if (v && typeof v === 'object' && !Array.isArray(v)) duzlestir(v, yol, cikti, derinlik + 1);
      else cikti[yol] = v;
    }
    return cikti;
  }

  // Görevin bütün alanları, düzleştirilmiş (iç içe nesne → "team.name"); değer yalnız metin/sayı/bool/null.
  // Dizi: sade değerler virgülle, nesne dizisi kısaltılmış JSON. En çok 150 alan; uzun metin 2000 karakter.
  function hamDuz(ham) {
    const duz = duzlestir(ham);
    const out = {};
    for (const k of Object.keys(duz).slice(0, 150)) {
      const v = duz[k];
      if (v == null || typeof v === 'number' || typeof v === 'boolean') out[k] = v ?? null;
      else if (typeof v === 'string') out[k] = v.slice(0, 2000);
      else if (Array.isArray(v)) out[k] = v.every((x) => x == null || typeof x !== 'object') ? v.join(', ').slice(0, 2000) : JSON.stringify(v).slice(0, 500);
      else out[k] = String(v).slice(0, 2000);
    }
    return out;
  }

  function bul(duz, kaliplar) {
    const yollar = Object.keys(duz);
    const dolu = (a) => duz[a] != null && duz[a] !== '';
    for (const k of kaliplar) {
      // önce tam yol; sonra iç içe nesnede yalnız son ad (çıplak "id" hariç: müşteri/ekip kimliğiyle karışır)
      let y = yollar.find((a) => k.test(a) && dolu(a));
      if (!y && k.source !== '^id$') y = yollar.find((a) => a.includes('.') && k.test(a.split('.').pop()) && dolu(a));
      if (y) return y;
    }
    return null;
  }

  function tarih(v) {
    if (v == null || v === '') return null;
    if (typeof v === 'number') {
      const d = new Date(v > 1e12 ? v : v * 1000);
      return isNaN(d) ? null : yerel(d);
    }
    const s = String(v).trim();
    const m = s.match(/^(\d{2})[./-](\d{2})[./-](\d{4})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?/);
    if (m) return `${m[3]}-${m[2]}-${m[1]} ${m[4] || '00'}:${m[5] || '00'}:${m[6] || '00'}`;
    const m2 = s.match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?/);
    if (m2 && !/[zZ]|[+-]\d{2}:?\d{2}$/.test(s)) return `${m2[1]}-${m2[2]}-${m2[3]} ${m2[4] || '00'}:${m2[5] || '00'}:${m2[6] || '00'}`;
    const d = new Date(s);
    return isNaN(d) ? s : yerel(d);
  }
  function yerel(d) {
    // Türkiye saati (UTC+3, yaz saati yok)
    const t = new Date(d.getTime() + 3 * 36e5);
    const p = (n) => String(n).padStart(2, '0');
    return `${t.getUTCFullYear()}-${p(t.getUTCMonth() + 1)}-${p(t.getUTCDate())} ${p(t.getUTCHours())}:${p(t.getUTCMinutes())}:${p(t.getUTCSeconds())}`;
  }
  const TARIHLI = new Set(['acilis', 'randevu_bas', 'randevu_bit', 'konum_tarihi', 'basla_tarihi', 'guncelleme']);

  function metin(v) {
    if (v == null) return null;
    if (typeof v === 'object') return v.name || v.description || v.label || null;
    const s = String(v).trim();
    return s || null;
  }

  const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  function uuidYolu(duz) {
    const adaylar = Object.keys(duz).filter((a) => typeof duz[a] === 'string' && UUID.test(duz[a]));
    const kaliplar = [/^(task.?)?(uuid|id)$/i, /^task.?(uuid|id|key)$/i, /^task\.(uuid|id)$/i, /uuid/i];
    for (const k of kaliplar) {
      const y = adaylar.find((a) => k.test(a) && !/^(customer|team|location|address|user|account)/i.test(a));
      if (y) return y;
    }
    return null;
  }

  // Task No yolu: önce ad kalıpları (değer 6–12 haneli sayı olmalı), sonra ad kalıbı tutmasa da 9 haneli sayısal tek
  // alan (müşteri/ekip/konum/telefon vb. hariç). Bulunamazsa null (görev atlanır; uuid'den numara UYDURULMAZ).
  const SAYI_NO = /^\d{6,12}$/;
  const HARIC = /customer|musteri|subscriber|team|ekip|location|address|adres|phone|gsm|msisdn|user|account|dealer|status|type|category|appointment|product|tariff|offer|service|sla|count|total|size|page|version|order.?index/i;
  function taskNoBul(duz) {
    const yollar = Object.keys(duz);
    const uygun = (a) => duz[a] != null && SAYI_NO.test(String(duz[a]).trim());
    for (const k of ALANLAR.task_no) {
      let y = yollar.find((a) => !a.includes('.') && k.test(a) && uygun(a));
      if (!y) y = yollar.find((a) => /^task\./i.test(a) && k.test(a.split('.').pop()) && uygun(a));
      if (y) return y;
    }
    const dokuz = yollar.filter((a) => !HARIC.test(a) && duz[a] != null && /^\d{9}$/.test(String(duz[a]).trim()));
    return dokuz.length ? dokuz[0] : null;
  }

  // Tek görev → {sade, harita}
  function cevir(ham) {
    const duz = duzlestir(ham);
    const sade = {};
    const harita = {};
    for (const [alan, kaliplar] of Object.entries(ALANLAR)) {
      if (alan === 'task_no') {
        const y = taskNoBul(duz);
        if (y) { harita.task_no = y; sade.task_no = String(duz[y]).trim(); }
        else {
          // Son çare (eski davranış): BOSS 9 haneli numarayı hiç vermiyorsa görev yine de kaybolmasın — iç kimliğin
          // rakamları. Sunucu bunu "geçici no" sayar; olay akışındaki gorev_yapisi ile asıl alan bulunur.
          const g = bul(duz, [/^taskid$/i, /^task\.id$/i, /^id$/i]);
          if (g) { harita.task_no = g; sade.task_no = String(duz[g]).replace(/\D/g, '') || String(duz[g]); sade.task_no_gecici = true; }
        }
        continue;
      }
      const yol = bul(duz, kaliplar);
      if (!yol) continue;
      harita[alan] = yol;
      sade[alan] = TARIHLI.has(alan) ? tarih(duz[yol]) : metin(duz[yol]);
    }
    // telefonlar: adında phone/gsm/msisdn geçen bütün alanlar (en çok 3)
    const tel = Object.keys(duz).filter((a) => /phone|gsm|msisdn|telefon/i.test(a) && duz[a]).map((a) => String(duz[a]));
    sade.telefonlar = [...new Set(tel)].slice(0, 3);
    delete sade.telefon;
    // BOSS iç kimliği (uuid): ayrıntı uçları task/{uuid}/... bununla çağrılır
    const uy = uuidYolu(duz);
    if (uy) { sade.boss_uuid = String(duz[uy]).toLowerCase(); harita.boss_uuid = uy; }
    sade.ham = hamDuz(ham);
    return { sade, harita };
  }

  function cevirHepsi(liste) {
    const gorevler = [];
    const kullanilan = {};
    for (const ham of liste || []) {
      if (!ham || typeof ham !== 'object') continue;
      const { sade, harita } = cevir(ham);
      if (!sade.task_no) continue;
      gorevler.push(sade);
      for (const [a, y] of Object.entries(harita)) kullanilan[a] = y;
    }
    return { gorevler, alanHaritasi: kullanilan };
  }

  // Değer içermeyen yapı (Kayıt modu ve alan haritası için)
  function yapi(o, derinlik = 0) {
    if (Array.isArray(o)) return o.length ? [`dizi(${o.length})`, yapi(o[0], derinlik + 1)] : ['dizi(0)'];
    if (o && typeof o === 'object') {
      if (derinlik > 4) return 'nesne';
      const s = {};
      for (const k of Object.keys(o)) s[k] = o[k] && typeof o[k] === 'object' ? yapi(o[k], derinlik + 1) : typeof o[k];
      return s;
    }
    return typeof o;
  }

  // Parmak izi (artımlı eşitleme): sunucudaki boss.iz_hesapla ile AYNI
  const IZ_ALANLARI = ['durum', 'ekip', 'randevu_bas', 'randevu_bit', 'guncelleme'];
  const iz = (g) => IZ_ALANLARI.map((a) => (g && g[a] != null ? String(g[a]) : '')).join('|');

  kok.DehanetEslem = { ALANLAR, cevir, cevirHepsi, hamDuz, tarih, yapi, iz };
})(typeof self !== 'undefined' ? self : globalThis);
