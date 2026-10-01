/**
 * Simgeler — hepsi satır içi SVG. Dışarıdan yazı tipi/simge paketi indirilmez,
 * böylece uygulama internet olmadan da eksiksiz görünür.
 */

interface IkonOzellik {
  boyut?: number;
  kalinlik?: number;
  className?: string;
}

function Sarmal({
  boyut = 24,
  kalinlik = 2,
  className,
  children,
}: IkonOzellik & { children: React.ReactNode }) {
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
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

export const Liste = (p: IkonOzellik) => (
  <Sarmal {...p}>
    <path d="M8 6h13M8 12h13M8 18h13" />
    <circle cx="3.5" cy="6" r="1.2" fill="currentColor" stroke="none" />
    <circle cx="3.5" cy="12" r="1.2" fill="currentColor" stroke="none" />
    <circle cx="3.5" cy="18" r="1.2" fill="currentColor" stroke="none" />
  </Sarmal>
);

export const HaritaIkon = (p: IkonOzellik) => (
  <Sarmal {...p}>
    <path d="M9 3 3 5.5v15L9 18l6 3 6-2.5v-15L15 6 9 3Z" />
    <path d="M9 3v15M15 6v15" />
  </Sarmal>
);

export const Kisi = (p: IkonOzellik) => (
  <Sarmal {...p}>
    <circle cx="12" cy="8" r="3.6" />
    <path d="M4.5 20a7.5 7.5 0 0 1 15 0" />
  </Sarmal>
);

export const Yonetici = (p: IkonOzellik) => (
  <Sarmal {...p}>
    <path d="M3 20h18" />
    <path d="M6 20v-7M12 20V7M18 20v-4" />
  </Sarmal>
);

export const Geri = (p: IkonOzellik) => (
  <Sarmal kalinlik={2.6} {...p}>
    <path d="M15 5 8 12l7 7" />
  </Sarmal>
);

export const Ileri = (p: IkonOzellik) => (
  <Sarmal kalinlik={2.4} {...p}>
    <path d="M9 5l7 7-7 7" />
  </Sarmal>
);

export const Onay = (p: IkonOzellik) => (
  <Sarmal kalinlik={2.8} {...p}>
    <path d="M4.5 12.5 9.5 17.5 19.5 6.5" />
  </Sarmal>
);

export const Yol = (p: IkonOzellik) => (
  <Sarmal {...p}>
    <path d="M12 21s7-6.2 7-11.3A7 7 0 0 0 5 9.7C5 14.8 12 21 12 21Z" />
    <circle cx="12" cy="9.8" r="2.6" />
  </Sarmal>
);

export const Pusula = (p: IkonOzellik) => (
  <Sarmal {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="m15.5 8.5-2 5.2-5.2 2 2-5.2 5.2-2Z" />
  </Sarmal>
);

export const Kalem = (p: IkonOzellik) => (
  <Sarmal {...p}>
    <path d="M4 20h4l10.5-10.5a2.4 2.4 0 0 0-3.4-3.4L4.6 16.6 4 20Z" />
  </Sarmal>
);

export const Kapat = (p: IkonOzellik) => (
  <Sarmal kalinlik={2.6} {...p}>
    <path d="M6 6l12 12M18 6 6 18" />
  </Sarmal>
);

export const Ev = (p: IkonOzellik) => (
  <Sarmal {...p}>
    <path d="M4 10.5 12 4l8 6.5V20H4v-9.5Z" />
    <path d="M10 20v-5h4v5" />
  </Sarmal>
);

export const Kapi = (p: IkonOzellik) => (
  <Sarmal {...p}>
    <path d="M6 3h12v18H6z" />
    <circle cx="14.5" cy="12" r="1" fill="currentColor" stroke="none" />
  </Sarmal>
);

export const Uyari = (p: IkonOzellik) => (
  <Sarmal {...p}>
    <path d="M12 4 2.8 19.5h18.4L12 4Z" />
    <path d="M12 10v4" />
    <circle cx="12" cy="17" r="0.9" fill="currentColor" stroke="none" />
  </Sarmal>
);

export const Kilit = (p: IkonOzellik) => (
  <Sarmal {...p}>
    <rect x="4.5" y="10.5" width="15" height="10" rx="2.5" />
    <path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" />
  </Sarmal>
);

export const Saat = (p: IkonOzellik) => (
  <Sarmal {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7.5V12l3 2" />
  </Sarmal>
);

export const Takvim = (p: IkonOzellik) => (
  <Sarmal {...p}>
    <rect x="3.5" y="5" width="17" height="15.5" rx="2.5" />
    <path d="M3.5 10h17M8 3v4M16 3v4" />
  </Sarmal>
);

export const Bulut = (p: IkonOzellik) => (
  <Sarmal {...p}>
    <path d="M7.5 18.5a4 4 0 0 1-.3-8A5.2 5.2 0 0 1 17 9.4a3.6 3.6 0 0 1 .3 7.1" />
    <path d="M12 12v7M9.3 16.3 12 19l2.7-2.7" />
  </Sarmal>
);

export const Yenile = (p: IkonOzellik) => (
  <Sarmal {...p}>
    <path d="M20 12a8 8 0 1 1-2.6-5.9" />
    <path d="M20 4.5V10h-5.5" />
  </Sarmal>
);

export const Cikis = (p: IkonOzellik) => (
  <Sarmal {...p}>
    <path d="M14 20H6.5A2.5 2.5 0 0 1 4 17.5v-11A2.5 2.5 0 0 1 6.5 4H14" />
    <path d="M17 8.5 20.5 12 17 15.5M20 12H10" />
  </Sarmal>
);

export const Artan = (p: IkonOzellik) => (
  <Sarmal kalinlik={3} {...p}>
    <path d="M12 5v14M5 12h14" />
  </Sarmal>
);

export const Azalan = (p: IkonOzellik) => (
  <Sarmal kalinlik={3} {...p}>
    <path d="M5 12h14" />
  </Sarmal>
);

export const Yildiz = (p: IkonOzellik) => (
  <Sarmal {...p}>
    <path d="m12 4 2.4 5 5.6.8-4 3.9 1 5.5-5-2.7-5 2.7 1-5.5-4-3.9 5.6-.8L12 4Z" />
  </Sarmal>
);

/** Telefon — giriş ekranındaki "Yöneticini ara" satırı için. */
export const Telefon = (p: IkonOzellik) => (
  <Sarmal {...p}>
    <path d="M6.5 3h3l1.5 4-2 1.2a12 12 0 0 0 5.3 5.3L15.5 11l4 1.5v3a2 2 0 0 1-2.2 2A15.5 15.5 0 0 1 4.5 5.2 2 2 0 0 1 6.5 3Z" />
  </Sarmal>
);

/** Geri al / düzelt — yanlış işlenen kaydı geri almak için. */
export const GeriAl = (p: IkonOzellik) => (
  <Sarmal {...p}>
    <path d="M3 9h11a5 5 0 1 1 0 10h-4" />
    <path d="m7 5-4 4 4 4" />
  </Sarmal>
);

/** Konum imleci — haritada "beni ortala" ve bina konumu için. */
export const Konum = (p: IkonOzellik) => (
  <Sarmal {...p}>
    <circle cx="12" cy="12" r="3.2" />
    <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
    <circle cx="12" cy="12" r="8.2" />
  </Sarmal>
);
