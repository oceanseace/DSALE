/**
 * "İnternet yok" / "3 kayıt bekliyor" şeridi.
 * Satışçının en çok merak ettiği şey bu: kaydım gitti mi? Cevabı her ekranda
 * görünen tek satırdır; hiçbir yere tıklamak gerekmez.
 */

import { useSenkron } from '../depo/senkron';
import { useOturum } from '../depo/oturum';
import { Bulut, Onay, Uyari } from './Ikon';

export function DurumSeridi({ basariGoster = false }: { basariGoster?: boolean }) {
  const { bekleyen, takilan, reddedilen, gonderiliyor, cevrimici, simdiGonder } = useSenkron();

  // Sunucunun REDDETTİĞİ kayıtlar her şeyin önüne geçer: bunlar sessizce
  // silinmiyor artık, kullanıcı görüp yöneticisine söyleyebilmeli.
  if (reddedilen.length > 0) {
    return (
      <div className="serit reddedilen" role="alert">
        <Uyari boyut={20} />
        <span>
          {reddedilen.length} kayıt gönderilemedi — yöneticine bildir
          <span className="serit-alt">{reddedilen[0].hata}</span>
        </span>
        <button className="buton" onClick={simdiGonder}>
          Tekrar dene
        </button>
      </div>
    );
  }

  if (bekleyen > 0) {
    // İki bilgi BİRLİKTE verilir. Eskiden çevrimdışıyken kayıt girilince şerit
    // "1 kayıt telefonda güvende" oluyor, internetin hâlâ olmadığı bilgisi
    // kayboluyordu; "güvende" de "gönderildi" gibi okunuyordu.
    const yazi = gonderiliyor
      ? `${bekleyen} kayıt gönderiliyor…`
      : cevrimici
        ? `${bekleyen} kayıt gönderilmeyi bekliyor`
        : `İnternet yok · ${bekleyen} kayıt telefonda bekliyor`;
    return (
      <div className={`serit ${cevrimici ? 'bekleyen' : 'cevrimdisi'}`} role="status">
        <Bulut boyut={20} />
        <span>{yazi}</span>
        {!gonderiliyor && cevrimici ? (
          <button className="buton" onClick={simdiGonder}>
            {takilan > 0 ? 'Tekrar dene' : 'Şimdi gönder'}
          </button>
        ) : null}
      </div>
    );
  }

  if (!cevrimici) {
    return (
      <div className="serit cevrimdisi" role="status">
        <Uyari boyut={20} />
        <span>İnternet yok — çalışmaya devam edebilirsiniz</span>
      </div>
    );
  }

  if (basariGoster) {
    return (
      <div className="serit basarili" role="status">
        <Onay boyut={20} />
        <span>Tüm kayıtlar gönderildi</span>
      </div>
    );
  }

  return null;
}

/**
 * "Bu ekrandaki sayılar gerçek değil" şeridi.
 *
 * Gösterim verisi kuruluyken her ekranın üstünde durur. Bir sistemin en hızlı
 * güven kaybetme yolu, demo sayılarının gerçek sanılmasıdır; bu yüzden uyarı
 * kapatılamaz ve yöneticinin bir şeye tıklamasını beklemez.
 */
export function DemoSeridi() {
  const { ozet } = useOturum();
  if (!ozet?.demo) return null;
  return (
    <div className="serit demo" role="status">
      <Uyari boyut={20} />
      <span>Gösterim verisi — bu sayılar gerçek saha kaydı değildir</span>
    </div>
  );
}
