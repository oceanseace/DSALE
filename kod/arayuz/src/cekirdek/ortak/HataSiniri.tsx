/**
 * Bir ekran çökerse UYGULAMANIN TAMAMI çökmesin.
 *
 * En gerçekçi senaryo: satışçı sinyalsiz bir yerde "Harita" sekmesine
 * dokunuyor ve harita motoru (ayrı bir dosya) henüz telefona inmemiş.
 * Sınır olmasaydı React bütün ağacı söker; ekran bembeyaz kalır, satışçı
 * bugünün listesini de kaybeder. Bu, uygulamaya duyulan güveni tek seferde
 * bitirecek türden bir hatadır.
 *
 * Bunun yerine: Türkçe tek cümlelik açıklama, "Tekrar dene" ve listeye dönüş.
 * Kuyruktaki kayıtlara hiçbir şey olmaz — onlar IndexedDB'de durur.
 */

import { Component, type ReactNode } from 'react';
import { Sayfa, SayfaGovde, Ust, BosDurum } from './Sayfa';
import { git } from '../yol/rota';

interface Ozellik {
  /** Ekranın adı — başlıkta ve mesajda geçer ("Harita"). */
  baslik: string;
  children: ReactNode;
}

interface Durum {
  hata: Error | null;
}

export class HataSiniri extends Component<Ozellik, Durum> {
  state: Durum = { hata: null };

  static getDerivedStateFromError(hata: Error): Durum {
    return { hata };
  }

  componentDidCatch(hata: Error) {
    // Tarayıcı konsoluna bırakılır; dışarı hiçbir şey gönderilmez.
    console.error('Ekran açılamadı:', hata);
  }

  render() {
    if (!this.state.hata) return this.props.children;

    const cevrimdisi = typeof navigator !== 'undefined' && navigator.onLine === false;
    return (
      <Sayfa>
        <Ust baslik={this.props.baslik} geriyeGit={() => git('/bugun')} ortala />
        <SayfaGovde>
          <BosDurum
            simge="⚠️"
            baslik={`${this.props.baslik} şu an açılamıyor`}
            aciklama={
              cevrimdisi
                ? 'İnternet yok. Bu ekran ilk kez internetle açılmalı. ' +
                  'Listeniz “Bugün” sekmesinde duruyor, kayıtlarınız telefonda güvende.'
                : 'Bir şeyler ters gitti. Listeniz “Bugün” sekmesinde duruyor, ' +
                  'kayıtlarınız telefonda güvende.'
            }
          />
          <div style={{ display: 'grid', gap: 10, marginTop: 4 }}>
            <button
              className="dugme birincil buyuk"
              onClick={() => this.setState({ hata: null })}
            >
              Tekrar dene
            </button>
            <button className="dugme buyuk" onClick={() => git('/bugun')}>
              Bugünün listesine dön
            </button>
          </div>
        </SayfaGovde>
      </Sayfa>
    );
  }
}
