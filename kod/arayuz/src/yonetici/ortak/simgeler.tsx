/** Yalnız yönetici konsolunda kullanılan ek simgeler (satır içi SVG, dış paket yok). */

interface Ozellik {
  boyut?: number;
  kalinlik?: number;
}

function Sarmal({ boyut = 24, kalinlik = 2, children }: Ozellik & { children: React.ReactNode }) {
  return (
    <svg
      width={boyut}
      height={boyut}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={kalinlik}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

/** Canlı durum — sütun grafik. */
export const Nabiz = (p: Ozellik) => (
  <Sarmal {...p}>
    <path d="M3 20V12M8.5 20V5M14 20v-6M19.5 20V9" />
  </Sarmal>
);

/** Görev atama — kutu/paket. */
export const Paket = (p: Ozellik) => (
  <Sarmal {...p}>
    <path d="M21 8.2v7.6a1.6 1.6 0 0 1-.85 1.41l-7 3.7a1.6 1.6 0 0 1-1.5 0l-7-3.7A1.6 1.6 0 0 1 3.8 15.8V8.2" />
    <path d="m3.4 7.6 8-4.2a1.6 1.6 0 0 1 1.5 0l8 4.2-8.05 4.25a1.6 1.6 0 0 1-1.5 0L3.4 7.6Z" />
    <path d="M12 11.9V21" />
  </Sarmal>
);

/** Rapor — belge. */
export const Belge = (p: Ozellik) => (
  <Sarmal {...p}>
    <path d="M14 3H7.2A1.2 1.2 0 0 0 6 4.2v15.6A1.2 1.2 0 0 0 7.2 21h9.6a1.2 1.2 0 0 0 1.2-1.2V7l-4-4Z" />
    <path d="M14 3v4.2h4M9.5 13h5M9.5 16.5h5" />
  </Sarmal>
);

/** İndir. */
export const Indir = (p: Ozellik) => (
  <Sarmal {...p}>
    <path d="M12 3.5v11M7.5 10.5 12 15l4.5-4.5M4.5 19.5h15" />
  </Sarmal>
);

/** Ekle. */
export const Arti = (p: Ozellik) => (
  <Sarmal {...p}>
    <path d="M12 5v14M5 12h14" />
  </Sarmal>
);

/** Ara. */
export const Buyutec = (p: Ozellik) => (
  <Sarmal {...p}>
    <circle cx="11" cy="11" r="6.5" />
    <path d="m16 16 4.5 4.5" />
  </Sarmal>
);

/** Dikdörtgen seçim. */
export const Cerceve = (p: Ozellik) => (
  <Sarmal {...p}>
    <path d="M4 8V5.2A1.2 1.2 0 0 1 5.2 4H8M16 4h2.8A1.2 1.2 0 0 1 20 5.2V8M20 16v2.8a1.2 1.2 0 0 1-1.2 1.2H16M8 20H5.2A1.2 1.2 0 0 1 4 18.8V16" />
  </Sarmal>
);

/** Sihir — algoritma seçsin. */
export const Kivilcim = (p: Ozellik) => (
  <Sarmal {...p}>
    <path d="M12 3.5 13.7 8l4.5 1.7-4.5 1.7L12 16l-1.7-4.6L5.8 9.7 10.3 8 12 3.5Z" />
    <path d="M18.5 15.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7.7-1.8Z" />
  </Sarmal>
);

/** Bölge planlayıcı — parçalara bölünmüş alan. */
export const Bolgeler = (p: Ozellik) => (
  <Sarmal {...p}>
    <path d="M4 5.2A1.2 1.2 0 0 1 5.2 4h13.6A1.2 1.2 0 0 1 20 5.2v13.6a1.2 1.2 0 0 1-1.2 1.2H5.2A1.2 1.2 0 0 1 4 18.8V5.2Z" />
    <path d="M11 4v6.5L4 13M11 10.5 20 9M13.5 20l-2.5-9.5M13 15.5l7-1.5" />
  </Sarmal>
);

/** Tur raporu yükle — yukarı ok + tepsi. */
export const Yukle = (p: Ozellik) => (
  <Sarmal {...p}>
    <path d="M12 15.5V4.5M7.5 9 12 4.5 16.5 9M4.5 15v3.3A1.2 1.2 0 0 0 5.7 19.5h12.6a1.2 1.2 0 0 0 1.2-1.2V15" />
  </Sarmal>
);

/** Veri kalitesi — onaylı kalkan. */
export const Kalkan = (p: Ozellik) => (
  <Sarmal {...p}>
    <path d="M12 3.5 5 6.2v5.3c0 4.3 2.9 7.7 7 9 4.1-1.3 7-4.7 7-9V6.2L12 3.5Z" />
    <path d="m8.8 12 2.2 2.2 4.2-4.4" />
  </Sarmal>
);

/** Ticketlar — bilet. */
export const Bilet = (p: Ozellik) => (
  <Sarmal {...p}>
    <path d="M4 7.2A1.2 1.2 0 0 1 5.2 6h13.6A1.2 1.2 0 0 1 20 7.2v2.3a2.5 2.5 0 0 0 0 5v2.3a1.2 1.2 0 0 1-1.2 1.2H5.2A1.2 1.2 0 0 1 4 16.8v-2.3a2.5 2.5 0 0 0 0-5V7.2Z" />
    <path d="M14.5 6.5v11" strokeDasharray="1.6 2.2" />
  </Sarmal>
);

/* ------------------------------ v2 menü simgeleri ------------------------------ */

/** İşler — onay işaretli pano. */
export const IsPanosu = (p: Ozellik) => (
  <Sarmal {...p}>
    <rect x="4" y="3.5" width="16" height="17" rx="2.5" />
    <path d="M8 9h8M8 13h8M8 17h5" />
  </Sarmal>
);

/** Aranacaklar — telefon ahizesi. */
export const Ahize = (p: Ozellik) => (
  <Sarmal {...p}>
    <path d="M5 4h3.2l1.6 4-2 1.3a11 11 0 0 0 5 5l1.3-2 4 1.6V17a2 2 0 0 1-2 2A15 15 0 0 1 3 6a2 2 0 0 1 2-2Z" />
  </Sarmal>
);

/** Öbekler — birlikte çalışılan mahalle grubu (üç daire). */
export const Obek = (p: Ozellik) => (
  <Sarmal {...p}>
    <circle cx="8" cy="9" r="4" />
    <circle cx="16" cy="9" r="4" />
    <circle cx="12" cy="16" r="4" />
  </Sarmal>
);

/** Takip — yükselen çizgi. */
export const Grafik = (p: Ozellik) => (
  <Sarmal {...p}>
    <path d="M3 3v18h18" />
    <path d="m7 15 4-4 3 3 5-6" />
  </Sarmal>
);

/** Tablolar — ızgara. */
export const Izgara = (p: Ozellik) => (
  <Sarmal {...p}>
    <rect x="3.5" y="4" width="17" height="16" rx="2" />
    <path d="M3.5 9.5h17M3.5 15h17M9.5 4v16" />
  </Sarmal>
);

/** Rapor geçmişi — saat + ok. */
export const Gecmis = (p: Ozellik) => (
  <Sarmal {...p}>
    <path d="M3.5 12a8.5 8.5 0 1 0 2.5-6" />
    <path d="M3 4v4h4" />
    <path d="M12 8v4.5l3 2" />
  </Sarmal>
);

/** Daha — üç nokta (telefon sekmesi). */
export const Daha = (p: Ozellik) => (
  <Sarmal {...p}>
    <circle cx="5" cy="12" r="1.3" fill="currentColor" />
    <circle cx="12" cy="12" r="1.3" fill="currentColor" />
    <circle cx="19" cy="12" r="1.3" fill="currentColor" />
  </Sarmal>
);

/** Görünüm — yarım ay/güneş. */
export const Gorunum = (p: Ozellik) => (
  <Sarmal {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 3.5v17A8.5 8.5 0 0 0 12 3.5Z" fill="currentColor" />
  </Sarmal>
);

/** Başlangıç ekranı — bayrak. */
export const Bayrak = (p: Ozellik) => (
  <Sarmal {...p}>
    <path d="M5 21V4" />
    <path d="M5 4h11l-2 4 2 4H5" />
  </Sarmal>
);

/** Aç/kapa oku (menü grupları). */
export const AsagiOk = (p: Ozellik) => (
  <Sarmal {...p}>
    <path d="m6 9 6 6 6-6" />
  </Sarmal>
);

/** İşlerim — anahtar/tornavida. */
export const Alet = (p: Ozellik) => (
  <Sarmal {...p}>
    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
  </Sarmal>
);
