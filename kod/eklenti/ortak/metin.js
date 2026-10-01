/*
 * Saha eklentisi — ortak metin yardımcıları (Türkçe karşılaştırma, telefon, tarih).
 * Hem içerik betiklerinde (global DSMetin) hem Node testlerinde (module.exports) çalışır.
 * Dış bağımlılık yok; ağ çağrısı yok.
 */
(function (kok, fabrika) {
  const m = fabrika();
  if (typeof module === 'object' && module.exports) module.exports = m;
  else kok.DSMetin = m;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  /** Türkçe büyük harf: i→İ, ı→I (toUpperCase('tr') her motorda yok). */
  function trUst(s) {
    return String(s == null ? '' : s).replace(/i/g, 'İ').replace(/ı/g, 'I').toUpperCase();
  }

  const KATLA = { 'İ': 'I', 'I': 'I', 'Ş': 'S', 'Ğ': 'G', 'Ü': 'U', 'Ö': 'O', 'Ç': 'C', 'Â': 'A', 'Î': 'I', 'Û': 'U' };

  /** Karşılaştırma anahtarı: Türkçe büyük harf, şapkasız, yalnız A-Z0-9 ("Randevu Başlangıç:" → "RANDEVUBASLANGIC"). */
  function anahtar(s) {
    return trUst(s).replace(/[İIŞĞÜÖÇÂÎÛ]/g, (h) => KATLA[h] || h).replace(/[^A-Z0-9]/g, '');
  }

  /** Boşlukları tek boşluğa indirir, baş/son boşluğu atar. */
  function sade(s) {
    return String(s == null ? '' : s).replace(/[\s ​‎‏]+/g, ' ').trim();
  }

  /** Telefonu 10 haneye indirir (5321112233 / 2242223344). Geçersizse null. Maskeli (•, *, x) değer → null. */
  function telefonDuzelt(ham) {
    if (!ham) return null;
    const s0 = String(ham);
    if (/[•*xX]{2,}/.test(s0)) return null;
    let s = s0.replace(/\D+/g, '');
    if (s.startsWith('0090')) s = s.slice(4);
    if (s.startsWith('90') && s.length === 12) s = s.slice(2);
    if (s.startsWith('0') && s.length === 11) s = s.slice(1);
    if (s.length === 10 && /^[2-5]/.test(s)) return s;
    return null;
  }

  /** 5321112233 → "0532 ••• •• 33" (ekranda gösterim için). */
  function telefonMaskeli(t) {
    if (!t) return '—';
    if (t.length === 10) return '0' + t.slice(0, 3) + ' ••• •• ' + t.slice(8);
    return '•'.repeat(Math.max(0, t.length - 2)) + t.slice(-2);
  }

  const iki = (n) => String(n).padStart(2, '0');

  function _tarihParca(s) {
    s = sade(s);
    let m = s.match(/(\d{4})-(\d{1,2})-(\d{1,2})(?:[T ](\d{1,2}):(\d{2})(?::(\d{2}))?)?/);
    let y, a, g, sa, dk, sn;
    if (m) {
      [, y, a, g, sa, dk, sn] = m;
    } else {
      m = s.match(/(\d{1,2})[./-](\d{1,2})[./-](\d{4})(?:[ T,]+(\d{1,2})[:.](\d{2})(?:[:.](\d{2}))?)?/);
      if (!m) return null;
      [, g, a, y, sa, dk, sn] = m;
    }
    const ay = Number(a), gun = Number(g);
    if (ay < 1 || ay > 12 || gun < 1 || gun > 31) return null;
    const p = { y: Number(y), a: ay, g: gun, saatVar: sa != null, sa: Number(sa || 0), dk: Number(dk || 0), sn: Number(sn || 0), son: m.index + m[0].length };
    if (p.sa > 23 || p.dk > 59 || p.sn > 59) return null;
    return p;
  }

  /** "01.10.2026 09:30" / "2026-10-01T09:30" → "2026-10-01 09:30:00"; saatsiz → "2026-10-01". Tanınmazsa null. */
  function tarihNormal(s) {
    const p = _tarihParca(s);
    if (!p) return null;
    const gun = p.y + '-' + iki(p.a) + '-' + iki(p.g);
    return p.saatVar ? gun + ' ' + iki(p.sa) + ':' + iki(p.dk) + ':' + iki(p.sn) : gun;
  }

  /** "01.10.2026 09:00 - 11:00" → {bas:"2026-10-01 09:00:00", bit:"2026-10-01 11:00:00"}. */
  function randevuAraligi(s) {
    const metin = sade(s);
    const p = _tarihParca(metin);
    if (!p) return { bas: null, bit: null };
    const bas = tarihNormal(metin);
    const kalan = metin.slice(p.son);
    const ikinciTarih = _tarihParca(kalan);
    if (ikinciTarih) return { bas, bit: tarihNormal(kalan) };
    const saat = kalan.match(/^\s*[-–—]\s*(\d{1,2})[:.](\d{2})/);
    if (saat && p.saatVar) {
      const gun = p.y + '-' + iki(p.a) + '-' + iki(p.g);
      return { bas, bit: gun + ' ' + iki(saat[1]) + ':' + iki(saat[2]) + ':00' };
    }
    return { bas, bit: null };
  }

  /** "2026-10-01 09:30:00" → biçime göre alan değeri. */
  function tarihBicimle(normal, bicim) {
    const p = _tarihParca(normal);
    if (!p) return '';
    const gun = p.y + '-' + iki(p.a) + '-' + iki(p.g);
    const saat = iki(p.sa) + ':' + iki(p.dk);
    switch (bicim) {
      case 'datetime-local': return gun + 'T' + saat;
      case 'date': return gun;
      case 'time': return saat;
      case 'iso': return gun + ' ' + saat;
      case 'tr-tarih': return iki(p.g) + '.' + iki(p.a) + '.' + p.y;
      default: return iki(p.g) + '.' + iki(p.a) + '.' + p.y + (p.saatVar ? ' ' + saat : '');
    }
  }

  /** Ekranda kısa gösterim: "1 Eki 09:00". */
  const AYLAR = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara'];
  function tarihKisa(normal) {
    const p = _tarihParca(normal || '');
    if (!p) return '';
    return p.g + ' ' + AYLAR[p.a - 1] + (p.saatVar ? ' ' + iki(p.sa) + ':' + iki(p.dk) : '');
  }

  function saatKisa(normal) {
    const p = _tarihParca(normal || '');
    return p && p.saatVar ? iki(p.sa) + ':' + iki(p.dk) : '';
  }

  /**
   * Yapı keşfi için değer maskesi: 3+ rakam dizisi → "#", e-posta → "<e-posta>", uzunluk ≤ 60.
   * Etiket metinleri gönderilir, DEĞERLER asla; bu maske ikinci bir emniyettir.
   */
  function maskele(s, enCok) {
    const t = sade(s)
      .replace(/[\w.+-]+@[\w-]+(\.[\w-]+)+/g, '<e-posta>')
      .replace(/\d[\d\s./-]{2,}\d|\d{3,}/g, '#');
    const sinir = enCok || 60;
    return t.length > sinir ? t.slice(0, sinir) + '…' : t;
  }

  return { trUst, anahtar, sade, telefonDuzelt, telefonMaskeli, tarihNormal, randevuAraligi, tarihBicimle, tarihKisa, saatKisa, maskele };
});
