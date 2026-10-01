/**
 * Giriş — telefon numarası + 4 haneli PIN.
 *
 * Telefonun kendi klavyesi açılmaz; ekrandaki büyük tuşlar kullanılır. Sebebi
 * basit: eldivenle, güneşte, tek elle çalışan biri için sistem klavyesi küçük
 * ve kaygandır. Tuşlar 68 px, rakamlar 28 px.
 *
 * İLK GİRİŞ KENDİLİĞİNDEN ANLAŞILIR: "Devam"a basıldığında uygulama sunucuya
 * PIN'siz bir yoklama gönderir. Hesabın PIN'i yoksa ekran doğrudan DAVET KODU
 * adımına geçer ve sunucunun kendi cümlesini yazar. Eskiden hesabı yeni açılan
 * satışçı "Şifren" ekranına düşüyor, olmayan bir şifreyi tahmin etmeye
 * çalışıyor ve kendi hesabını kilitletiyordu.
 *
 * Masaüstünde (operasyon, yönetici) FİZİKSEL KLAVYE de çalışır: rakamlar,
 * Backspace ve Enter (§6.12). Sütun en çok 360 px; tek marka işareti.
 */

import { useCallback, useEffect, useState } from 'react';
import { giris as girisUcu, pinBelirle, saglik } from '../api/uclar';
import { SahaHatasi } from '../api/istemci';
import { useOturum } from '../depo/oturum';
import { telefonBicimle } from '../ortak/bicim';
import { Geri, Kilit, Telefon } from '../ortak/Ikon';
import { Marka } from '../ortak/Marka';

/**
 * İlk giriş üç adımdır: telefon → yöneticiden alınan 6 haneli DAVET KODU →
 * kendi seçtiği 4 haneli PIN (iki kez). Davet kodu olmadan sunucu PIN
 * belirlemeye izin vermez; kod olmasaydı telefon numarasını bilen herkes
 * başkasının hesabına şifre koyabilirdi.
 */
type Adim = 'telefon' | 'pin' | 'davet' | 'pin-belirle' | 'pin-dogrula';

/** Adımın kaç hane beklediği. */
const HANE: Record<Adim, number> = {
  telefon: 10,
  pin: 4,
  davet: 6,
  'pin-belirle': 4,
  'pin-dogrula': 4,
};

/**
 * `saha/guvenlik.py: pin_zayif_mi` ile AYNI kural: tek rakam (1111), artan
 * (1234) ya da azalan (4321) diziler. Sunucu son sözü söyler; buradaki kopya
 * yalnız satışçıyı gereksiz bir tur tuşlamaktan kurtarır.
 */
function pinZayif(pin: string): boolean {
  if (new Set(pin).size === 1) return true;
  const r = [...pin].map(Number);
  const artan = r.every((d, i) => i === 0 || d - r[i - 1] === 1);
  const azalan = r.every((d, i) => i === 0 || r[i - 1] - d === 1);
  return artan || azalan;
}

export function Giris() {
  const { girisYapildi, girisBilgisi } = useOturum();
  const [adim, setAdim] = useState<Adim>('telefon');
  const [telefon, setTelefon] = useState('');
  const [pin, setPin] = useState('');
  const [ilkPin, setIlkPin] = useState('');
  const [davet, setDavet] = useState('');
  const [hata, setHata] = useState<string | null>(null);
  const [bilgi, setBilgi] = useState<string | null>(null);
  const [sarsiliyor, setSarsiliyor] = useState(false);
  const [bekliyor, setBekliyor] = useState(false);
  const [yardim, setYardim] = useState<{ telefon?: string | null; ad?: string | null } | null>(null);

  /* Yöneticinin yardım numarası (varsa) giriş ekranının altında durur. */
  useEffect(() => {
    let iptal = false;
    void saglik()
      .then((veri) => {
        if (!iptal && veri?.yardim_telefon) {
          setYardim({ telefon: veri.yardim_telefon, ad: veri.yardim_ad });
        }
      })
      .catch(() => {
        /* çevrimdışıysa yardım satırı gösterilmez */
      });
    return () => {
      iptal = true;
    };
  }, []);

  const hataVer = useCallback((mesaj: string) => {
    setHata(mesaj);
    setBilgi(null);
    setPin('');
    setSarsiliyor(true);
    window.setTimeout(() => setSarsiliyor(false), 420);
    try {
      navigator.vibrate?.(60);
    } catch {
      /* titreşim yoksa sorun değil */
    }
  }, []);

  /**
   * "Devam": önce PIN'siz yoklama. Sunucu "bu hesabın PIN'i yok" derse
   * kullanıcıya şifre sormanın anlamı yok — doğrudan davet koduna geçilir.
   */
  const telefonGonder = useCallback(async () => {
    if (telefon.length !== 10 || bekliyor) return;
    setBekliyor(true);
    setHata(null);
    try {
      const yanit = await girisUcu(telefon, '');
      if (yanit.pin_belirle) {
        setPin('');
        setIlkPin('');
        setDavet('');
        setBilgi(yanit.mesaj ?? 'İlk giriş. Yöneticinden aldığın 6 haneli kodu gir.');
        setAdim('davet');
      } else {
        setBilgi(null);
        setAdim('pin');
      }
    } catch (h) {
      // Yoklama yapılamıyorsa (sinyal yok) yine de PIN adımına geçeriz:
      // kullanıcıyı giriş ekranında kilitlemeyiz.
      if (h instanceof SahaHatasi && h.agHatasi) {
        setBilgi(null);
        setAdim('pin');
      } else {
        hataVer(h instanceof Error ? h.message : 'Bağlantı kurulamadı.');
      }
    } finally {
      setBekliyor(false);
    }
  }, [telefon, bekliyor, hataVer]);

  const pinGonder = useCallback(
    async (deger: string) => {
      setBekliyor(true);
      setHata(null);
      try {
        const yanit = await girisUcu(telefon, deger);
        if (yanit.pin_belirle) {
          // Hesap var ama PIN'i yok: önce davet kodu, sonra yeni PIN.
          setPin('');
          setIlkPin('');
          setDavet('');
          setBilgi(yanit.mesaj ?? 'İlk giriş. Yöneticinden aldığın 6 haneli kodu gir.');
          setAdim('davet');
          return;
        }
        if (yanit.token && yanit.kullanici) {
          girisYapildi(yanit.token, yanit.kullanici);
          return;
        }
        hataVer('Beklenmeyen bir yanıt geldi.');
      } catch (h) {
        hataVer(h instanceof Error ? h.message : 'Giriş yapılamadı.');
      } finally {
        setBekliyor(false);
      }
    },
    [telefon, girisYapildi, hataVer],
  );

  const yeniPinGonder = useCallback(
    async (deger: string) => {
      setBekliyor(true);
      setHata(null);
      try {
        const yanit = await pinBelirle(telefon, deger, davet);
        if (yanit.token && yanit.kullanici) girisYapildi(yanit.token, yanit.kullanici);
        else hataVer('PIN kaydedilemedi, tekrar deneyin.');
      } catch (h) {
        hataVer(h instanceof Error ? h.message : 'PIN kaydedilemedi.');
        if (h instanceof SahaHatasi && h.kod === 'kimlik_hatali') {
          // Kod yanlışsa kullanıcıyı PIN ekranında bırakmak anlamsız: koda dön.
          setDavet('');
          setIlkPin('');
          setAdim('davet');
        } else if (h instanceof SahaHatasi && h.durum === 400) {
          // PIN zayıf ya da geçersiz: BAŞTAN seçtirmek gerekir. Eskiden ekran
          // "aynı 4 haneyi bir kez daha gir" derken altında "başka bir 4 hane
          // seç" yazıyordu; kullanıcı ikisini de yapamıyordu.
          setIlkPin('');
          setAdim('pin-belirle');
        }
      } finally {
        setBekliyor(false);
      }
    },
    [telefon, davet, girisYapildi, hataVer],
  );

  /* Davet kodu 6 haneye ulaşınca PIN belirleme adımına geçilir. */
  useEffect(() => {
    if (adim !== 'davet' || davet.length !== 6) return;
    setAdim('pin-belirle');
    setBilgi(null);
    setPin('');
  }, [adim, davet]);

  /* PIN 4 haneye ulaştığında kendiliğinden ilerler — "Tamam" aramaya gerek yok. */
  useEffect(() => {
    if (pin.length !== 4 || bekliyor) return;
    if (adim === 'pin') {
      void pinGonder(pin);
    } else if (adim === 'pin-belirle') {
      // Kolay PIN'i HEMEN söyle. Sunucu da reddediyor ama onun cevabı ancak
      // ikinci girişten sonra geliyordu: satışçı 8 hane tuşluyor, sonra
      // "başka bir 4 hane seç" duyuyordu. Kural ekranda yazılı, burada da
      // uygulanır; sunucudaki denetim yine son sözü söyler.
      if (pinZayif(pin)) {
        hataVer('1234 gibi kolay PIN olmaz. Başka bir 4 hane seçin.');
        setPin('');
        return;
      }
      setIlkPin(pin);
      setPin('');
      setAdim('pin-dogrula');
    } else if (adim === 'pin-dogrula') {
      if (pin === ilkPin) {
        void yeniPinGonder(pin);
      } else {
        hataVer('İki PIN aynı değil. Baştan deneyin.');
        setIlkPin('');
        setAdim('pin-belirle');
      }
    }
  }, [pin, adim, ilkPin, bekliyor, pinGonder, yeniPinGonder, hataVer]);

  const rakamBas = useCallback(
    (rakam: string) => {
      setHata(null);
      const sinir = HANE[adim];
      if (adim === 'telefon') setTelefon((o) => (o.length >= sinir ? o : o + rakam));
      else if (adim === 'davet') setDavet((o) => (o.length >= sinir ? o : o + rakam));
      else setPin((o) => (o.length >= sinir ? o : o + rakam));
    },
    [adim],
  );

  const sil = useCallback(() => {
    setHata(null);
    if (adim === 'telefon') setTelefon((o) => o.slice(0, -1));
    else if (adim === 'davet') setDavet((o) => o.slice(0, -1));
    else setPin((o) => o.slice(0, -1));
  }, [adim]);

  const telefonaDon = useCallback(() => {
    setAdim('telefon');
    setPin('');
    setIlkPin('');
    setDavet('');
    setHata(null);
    setBilgi(null);
  }, []);

  /*
   * Fiziksel klavye (masaüstü, klavyeli tablet): rakam, Backspace, Enter.
   * Ekran tuşlarıyla aynı işlevleri çağırır; Ctrl/Alt kısayollarına karışmaz.
   */
  useEffect(() => {
    const tus = (o: KeyboardEvent) => {
      if (o.ctrlKey || o.metaKey || o.altKey || bekliyor) return;
      const hedef = o.target as HTMLElement | null;
      if (hedef && (hedef.tagName === 'INPUT' || hedef.tagName === 'TEXTAREA')) return;
      if (/^[0-9]$/.test(o.key)) {
        o.preventDefault();
        rakamBas(o.key);
      } else if (o.key === 'Backspace') {
        o.preventDefault();
        sil();
      } else if (o.key === 'Enter' && adim === 'telefon') {
        o.preventDefault();
        void telefonGonder();
      } else if (o.key === 'Escape' && adim !== 'telefon') {
        telefonaDon();
      }
    };
    window.addEventListener('keydown', tus);
    return () => window.removeEventListener('keydown', tus);
  }, [adim, bekliyor, rakamBas, sil, telefonGonder, telefonaDon]);

  return (
    <div className="giris">
      <div className="giris-marka">
        <Marka boyut={72} />
        <h1>Saha Sistemi</h1>
        <p className="aciklama">Dehanet Ev Çözüm Merkezi</p>
      </div>

      {girisBilgisi ? (
        <p className="giris-serit" role="status">
          {girisBilgisi}
        </p>
      ) : null}

      <div className="giris-orta">
        {adim === 'telefon' ? (
          <TelefonAdimi telefon={telefon} sarsiliyor={sarsiliyor} />
        ) : (
          <PinAdimi
            adim={adim}
            telefon={telefon}
            pin={adim === 'davet' ? davet : pin}
            uzunluk={HANE[adim]}
            sarsiliyor={sarsiliyor}
            bekliyor={bekliyor}
            telefonaDon={telefonaDon}
          />
        )}

        <p className={hata ? 'hata-yazi' : 'bilgi-yazi'} role="alert">
          {hata ?? bilgi ?? ''}
        </p>

        <TusTakimi
          rakamBas={rakamBas}
          sil={sil}
          solTus={
            adim === 'telefon' ? null : (
              <button className="tus islem" onClick={telefonaDon} aria-label="Numarayı değiştir">
                <Geri boyut={26} />
              </button>
            )
          }
          kapali={bekliyor}
        />

        {adim === 'telefon' ? (
          <button
            className="dugme birincil buyuk"
            onClick={() => void telefonGonder()}
            disabled={telefon.length !== 10 || bekliyor}
          >
            {bekliyor ? 'Kontrol ediliyor…' : 'Devam'}
          </button>
        ) : null}

        <Yardim yardim={yardim} adim={adim} />
      </div>
    </div>
  );
}

/* ------------------------------ Parçalar ------------------------------ */

/**
 * Takılan satışçının tek çaresi WhatsApp'a dönmek olmamalı. Numara yönetici
 * tarafından Ekip ekranından girilir; girilmemişse yine de ne yapacağını
 * söyleyen bir cümle durur.
 */
function Yardim({
  yardim,
  adim,
}: {
  yardim: { telefon?: string | null; ad?: string | null } | null;
  adim: Adim;
}) {
  if (yardim?.telefon) {
    return (
      <a className="dugme sessiz giris-yardim" href={`tel:0${yardim.telefon}`}>
        <Telefon boyut={18} />
        Giriş yapamıyor musun? {yardim.ad ? `${yardim.ad}'ı ara` : 'Yöneticini ara'}
      </a>
    );
  }
  // Numara girilmemişse hiç değilse ne yapacağını söyle — ama yalnız ilk
  // adımda: davet kodu ekranında bunu zaten ekranın ortası söylüyor.
  if (adim === 'telefon') {
    return (
      <p className="giris-yardim-yazi">
        İlk kez mi giriyorsun? Yöneticinden 6 haneli davet kodunu iste.
      </p>
    );
  }
  return <p className="giris-yardim-yazi">Takıldıysan yöneticini ara.</p>;
}

/**
 * Numara, girildikçe dolan sabit bir maske olarak gösterilir: 5·· ··· ·· ··
 * Böylece kaç hane girildiği tek bakışta anlaşılır, yazı da yerinden oynamaz.
 */
function TelefonAdimi({ telefon, sarsiliyor }: { telefon: string; sarsiliyor: boolean }) {
  const gruplar = [3, 3, 2, 2];
  let sayac = 0;

  return (
    <div style={{ textAlign: 'center' }}>
      <p className="giris-baslik">Telefon numaran</p>
      <div
        className={`giris-numara${sarsiliyor ? ' sarsil' : ''}`}
        aria-live="polite"
        aria-label={`Girilen numara: ${telefon || 'boş'}`}
      >
        {gruplar.map((uzunluk, grupIndeks) => (
          <span key={grupIndeks}>
            {Array.from({ length: uzunluk }, () => {
              const hane = telefon[sayac++];
              return hane ?? '·';
            }).map((karakter, i) =>
              // Boş hane yazı değil, yer tutucu işarettir (CSS çizer; ekran okuyucu
              // yukarıdaki aria-label'ı okur).
              karakter === '·' ? (
                <span key={i} className="bos-hane" aria-hidden="true" />
              ) : (
                <span key={i}>{karakter}</span>
              ),
            )}
          </span>
        ))}
      </div>
      <p className="giris-ipucu">Başında 0 olmadan, 10 hane</p>
    </div>
  );
}

function PinAdimi({
  adim,
  telefon,
  pin,
  uzunluk,
  sarsiliyor,
  bekliyor,
  telefonaDon,
}: {
  adim: Adim;
  telefon: string;
  pin: string;
  uzunluk: number;
  sarsiliyor: boolean;
  bekliyor: boolean;
  telefonaDon: () => void;
}) {
  const baslik =
    adim === 'davet'
      ? 'Davet kodun'
      : adim === 'pin-belirle'
        ? 'Yeni PIN belirle'
        : adim === 'pin-dogrula'
          ? 'PIN’i tekrar gir'
          : 'Şifren';
  const aciklama =
    adim === 'davet'
      ? 'Yöneticinin verdiği 6 haneli kod'
      : adim === 'pin-belirle'
        ? 'Kendine 4 haneli bir şifre seç'
        : adim === 'pin-dogrula'
          ? 'Aynı 4 haneyi bir kez daha gir'
          : `0${telefonBicimle(telefon)}`;

  return (
    <div style={{ textAlign: 'center' }}>
      <div className="giris-kilit">
        <Kilit boyut={18} />
        <span className="giris-baslik">{baslik}</span>
      </div>
      <button onClick={telefonaDon} className="giris-alt-yazi">
        {aciklama}
      </button>

      <div
        className={`pin-noktalar${sarsiliyor ? ' sarsil' : ''}`}
        aria-label={`${pin.length} hane girildi`}
      >
        {Array.from({ length: uzunluk }, (_, i) => (
          <span key={i} className={`pin-nokta${i < pin.length ? ' dolu' : ''}`} />
        ))}
      </div>
      <div className="giris-durum">
        {bekliyor
          ? 'Kontrol ediliyor…'
          : adim === 'pin-belirle'
            ? '1111, 1234 gibi kolay şifreler kabul edilmiyor'
            : ''}
      </div>
    </div>
  );
}

function TusTakimi({
  rakamBas,
  sil,
  solTus,
  kapali,
}: {
  rakamBas: (rakam: string) => void;
  sil: () => void;
  solTus?: React.ReactNode;
  kapali?: boolean;
}) {
  return (
    <div className="tus-takimi" role="group" aria-label="Rakam tuşları">
      {['1', '2', '3', '4', '5', '6', '7', '8', '9'].map((r) => (
        <button key={r} className="tus" onClick={() => rakamBas(r)} disabled={kapali}>
          {r}
        </button>
      ))}
      {solTus ?? <span className="tus bos" />}
      <button className="tus" onClick={() => rakamBas('0')} disabled={kapali}>
        0
      </button>
      <button className="tus islem" onClick={sil} disabled={kapali} aria-label="Sil">
        <SilSimgesi />
      </button>
    </div>
  );
}

function SilSimgesi() {
  return (
    <svg
      width="30"
      height="30"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden="true"
    >
      <path d="M21 5.5H9.2L3 12l6.2 6.5H21a1.5 1.5 0 0 0 1.5-1.5V7a1.5 1.5 0 0 0-1.5-1.5Z" />
      <path d="m13 9.5 5 5M18 9.5l-5 5" strokeLinecap="round" />
    </svg>
  );
}
