import { useEffect, useState } from 'react';

/** Tarayıcı "internet var mı" diyor mu? (Kesin değil ama iyi bir ilk işaret.) */
export function useCevrimici() {
  const [cevrimici, setCevrimici] = useState(() =>
    typeof navigator === 'undefined' ? true : navigator.onLine,
  );

  useEffect(() => {
    const acik = () => setCevrimici(true);
    const kapali = () => setCevrimici(false);
    window.addEventListener('online', acik);
    window.addEventListener('offline', kapali);
    return () => {
      window.removeEventListener('online', acik);
      window.removeEventListener('offline', kapali);
    };
  }, []);

  return cevrimici;
}
