/*
 * Saha eklentisi — BÜTÜN ekran seçicileri bu tek dosyadadır (belgeler/eklenti/SAYFA_HARITASI.md kuralı).
 *
 * Turkcell ekranı değişince yalnız bu dosya güncellenir. Eklentiyi yeniden kurmadan düzeltmek için
 * sunucudaki eklenti ayarı (`GET /api/eklenti/ayar` → `secici_ek`) aynı anahtarlarla bu değerlerin
 * üstüne yazılabilir: yalnız VERİ (metin / metin listesi) kabul edilir, kod asla.
 *
 * Seçici bulunamazsa eklenti sessizce bozulmaz; "Bu ekran tanınmadı" der ve "Yapı keşfi"ni önerir.
 *
 * Durum (30.09.2026):
 *   BOSS     — canlı haritalanamadı (B1–B10 boş). Etiket/başlık eşanlamlılarıyla çalışır; kesin seçiciler
 *              ilk "Yapı keşfi"nden sonra `liste_tablo`, `detay_kok`, `form.*.secici` alanlarına yazılır.
 *   OWA      — giriş gerekliydi; OWA 2016/2019 bilinen kalıpları + sağ tık "seçili metin" yolu.
 *   WhatsApp — canlı haritalandı (data-testid, role, data-id, data-pre-plain-text).
 *   Atmosfer — sayfa kodundan kesin (.dealer-employees__*, .person-card__text1/2).
 */
(function (kok, fabrika) {
  const m = fabrika();
  if (typeof module === 'object' && module.exports) module.exports = m;
  else kok.DSSecici = m;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const SECICI = {
    surum: '2026-09-30',

    boss: {
      hostlar: ['boss.turkcell.com.tr', 'boss.superonline.net'],
      // location.href (küçük harf) bu parçalardan birini içeriyorsa eklenti BOSS task ekranında sayılır.
      yol_parcalari: ['technical-task', 'teknik-task', 'technicaltask'],
      // Detay adresinden task no: /technical-tasks/412102947 (B5 doğrulanınca kesinleşir).
      detay_yol_deseni: '/technical-tasks?/(\\d{6,})',
      // Kesin seçiciler (keşif turundan sonra doldurulur). Boşsa etiket/başlıktan bulunur.
      liste_tablo: '',
      detay_kok: '',
      tablo_adaylari: ['table', '[role="grid"]', '[role="table"]', 'mat-table', '.mat-table', '.p-datatable', '.ag-root'],
      baslik_hucre: ['thead th', '[role="columnheader"]', 'mat-header-cell', '.mat-header-cell', '.mat-mdc-header-cell', '.ag-header-cell-text'],
      satir: ['tbody tr', '[role="row"]', 'mat-row', '.mat-row', '.mat-mdc-row'],
      hucre: ['td', '[role="gridcell"]', '[role="cell"]', 'mat-cell', '.mat-cell', '.mat-mdc-cell'],
      // Alan → ekrandaki başlık/etiket eşanlamlıları (B4, B7). Yalnız bu alanlar okunur; müşteri adı,
      // müşteri no, adres gibi sütunlar HİÇ okunmaz (beyaz liste).
      alanlar: {
        task_no: ['Task No', 'Task Numarası', 'Task ID', 'Görev No', 'Fox Akış No', 'Akış No', 'İş Emri No', 'Task'],
        task_adi: ['Task Adı', 'Görev Adı', 'Task Tipi', 'İş Tipi', 'Task Türü'],
        durum: ['Durum', 'Statü', 'Task Durumu', 'Task Statüsü', 'Status'],
        ekip: ['Ekip', 'Ekip Adı', 'Atanan Ekip', 'Saha Ekibi', 'Teknisyen', 'Atanan'],
        lokasyon: ['Lokasyon', 'Location Id', 'Lokasyon ID', 'Lokasyon No', 'Location ID'],
        randevu_durumu: ['Randevu Durumu', 'Randevu Statüsü'],
        randevu_baslangic: ['Randevu Başlangıç Tarihi', 'Randevu Başlangıç', 'Randevu Başlangıç Zamanı', 'Randevu Tarihi'],
        randevu_bitis: ['Randevu Bitiş Tarihi', 'Randevu Bitiş', 'Randevu Bitiş Zamanı'],
        randevu: ['Randevu', 'Randevu Zamanı', 'Randevu Aralığı'],
        merkeze_gonder: ['Merkeze Gönder Statüsü', 'Merkeze Gönder Durumu'],
      },
      // B8: yalnız ETİKET. Değer yalnız kullanıcı detayda "Saha'ya gönder"e basınca okunur.
      telefon_etiketleri: ['Müşteri Telefonu', 'Müşteri Tel', 'Müşteri Telefon No', 'İrtibat Telefonu', 'İrtibat Numarası',
        'İrtibat No', 'İletişim Telefonu', 'İletişim Numarası', 'Cep Telefonu', 'Telefon', 'Telefon No', 'GSM', 'MSISDN'],
      // B9: doldurulacak form alanları. `secici` keşiften sonra yazılır; boşsa etiket + ad niteliğinden bulunur.
      form: {
        ekip: {
          secici: '',
          etiket: ['Ekip', 'Ekip Adı', 'Atanan Ekip', 'Atanacak Ekip', 'Saha Ekibi', 'Ekip Seçiniz', 'Teknisyen'],
          ad: ['ekip', 'ekipid', 'ekipadi', 'team', 'teamid', 'teamname', 'crew', 'assignee', 'assignedteam'],
        },
        randevu_baslangic: {
          secici: '',
          etiket: ['Randevu Başlangıç Tarihi', 'Randevu Başlangıç', 'Randevu Başlangıç Zamanı', 'Randevu Tarihi', 'Başlangıç Tarihi', 'Başlangıç'],
          ad: ['randevubaslangic', 'randevubaslangictarihi', 'randevutarihi', 'appointmentstart', 'appointmentstartdate', 'startdate', 'baslangic'],
        },
        randevu_bitis: {
          secici: '',
          etiket: ['Randevu Bitiş Tarihi', 'Randevu Bitiş', 'Randevu Bitiş Zamanı', 'Bitiş Tarihi', 'Bitiş'],
          ad: ['randevubitis', 'randevubitistarihi', 'appointmentend', 'appointmentenddate', 'enddate', 'bitis'],
        },
        randevu_baslangic_saat: {
          secici: '',
          etiket: ['Randevu Başlangıç Saati', 'Başlangıç Saati', 'Randevu Saati'],
          ad: ['randevubaslangicsaati', 'baslangicsaati', 'starttime', 'appointmentstarttime'],
        },
        randevu_bitis_saat: {
          secici: '',
          etiket: ['Randevu Bitiş Saati', 'Bitiş Saati'],
          ad: ['randevubitissaati', 'bitissaati', 'endtime', 'appointmentendtime'],
        },
      },
    },

    owa: {
      hostlar: ['mail.turkcell.com.tr'],
      // OWA 2016/2019 (şirket içi Exchange) bilinen kalıpları. İlk eşleşen kullanılır.
      okuma_bolmesi: ['[aria-label="Okuma Bölmesi"]', '[aria-label="Reading Pane"]', '#ReadingPaneContainerId',
        '[role="main"] .wide-content-host', '[role="main"]'],
      konu: ['[aria-label="Konu"]', '.rpHighlightSubjectClass', '[id$="_SUBJECT"]', '[role="heading"][aria-level="2"]',
        '.allowTextSelection[role="heading"]', 'h1', 'h2'],
      govde: ['[aria-label="İleti gövdesi"]', '[aria-label="Message body"]', '#Item\\.MessageUniqueBody',
        '.ReadMsgBody', '[id^="UniqueMessageBody"]', '.allowTextSelection'],
      gonderen: ['[aria-label^="Kimden"]', '[aria-label^="From"]', '.lpc-hoverTarget', '._rp_Y1 span'],
      // OneDesk bildirim maili işaretleri (gerçek örnek gelince daraltılır; bkz. SAYFA_HARITASI §2).
      onedesk_isaret: ['onedesk', 'one desk', 'çağrı kaydı', 'cagri kaydi', 'ticket'],
    },

    whatsapp: {
      hostlar: ['web.whatsapp.com'],
      uygulama: '#app',
      sohbet_paneli: '#main',
      sohbet_basligi: ['[data-testid="conversation-info-header-chat-title"]', '#main header span[title]', '#main header span[dir="auto"]'],
      mesaj_listesi: ['[data-testid="conversation-panel-messages"]', '#main [role="application"]', '#main'],
      mesaj_satiri: '[role="row"]',
      kimlik: '[data-id]',
      balon: ['[data-testid="msg-container"]', '[data-testid^="conv-msg-"]', '.copyable-text'],
      metin_kabi: '.copyable-text',
      metin: ['[data-testid="selectable-text"]', 'span.selectable-text'],
      on_bilgi: '[data-pre-plain-text]',
      saat: '[data-testid="msg-meta"]',
      // Eklenti buraya ASLA yazmaz (yalnız belge için): footer [data-testid="compose-box"]
    },

    atmosfer: {
      hostlar: ['atmosfer.turkcell.com.tr'],
      yol_parcasi: '/dealer-manager/employee',
      kok: '.dealer-employees',
      yetkili: '.dealer-employees__authorized',
      ekip: '.dealer-employees__team',
      liste: '.dealer-employees__list',
      kart: '.person-card',
      ad: '.person-card__text1',
      unvan: '.person-card__text2',
      bekleme_ms: 10000,
    },
  };

  // Sunucudan gelen ek ayar yalnız BU anahtarlara ve yalnız metin / metin listesi olarak yazılabilir.
  function _duzMu(v) {
    return typeof v === 'string' ? v.length <= 300 : Array.isArray(v) && v.length <= 40 && v.every((x) => typeof x === 'string' && x.length <= 300);
  }

  /** Varsayılanın üstüne güvenli birleştirme (yeni anahtar eklenmez, tür değişmez). */
  function birlestir(temel, ek, derinlik) {
    if (!ek || typeof ek !== 'object' || Array.isArray(ek) || (derinlik || 0) > 4) return temel;
    const out = Array.isArray(temel) ? temel.slice() : Object.assign({}, temel);
    for (const k of Object.keys(ek)) {
      if (!(k in temel)) continue;
      const t = temel[k], v = ek[k];
      if (t && typeof t === 'object' && !Array.isArray(t)) out[k] = birlestir(t, v, (derinlik || 0) + 1);
      else if (_duzMu(v) && (typeof v === typeof t) && (Array.isArray(v) === Array.isArray(t))) out[k] = v;
    }
    return out;
  }

  function al(ek) {
    return ek ? birlestir(SECICI, ek, 0) : SECICI;
  }

  return { SECICI, al, birlestir };
});
