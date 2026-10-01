/**
 * ECharts sarmalayıcı + 'dehanet' teması.
 *
 * Yalnız gereken modüller içe alınır (tek dosya HTML'i şişirmemek için).
 * `secenek` değişince `setOption(..., {notMerge:false})` çağrılır — böylece çubuklar
 * yeni değerlere ANİMASYONLA gider (S8 "önce → sonra" yarışı bunu kullanır).
 */
import { useEffect, useRef } from 'react';
import type { CSSProperties } from 'react';
import * as echarts from 'echarts/core';
import { BarChart, LineChart, PieChart } from 'echarts/charts';
import { GridComponent, MarkLineComponent, TooltipComponent, GraphicComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsCoreOption } from 'echarts/core';

import { renk } from './tema';

echarts.use([BarChart, LineChart, PieChart, GridComponent, MarkLineComponent, TooltipComponent, GraphicComponent, CanvasRenderer]);

let temaKurulu = false;

/** Koyu sahne teması: şeffaf zemin, açık gri eksen, Barlow başlıklar. */
export function temayiKur(): void {
  if (temaKurulu) return;
  temaKurulu = true;
  echarts.registerTheme('dehanet', {
    color: [renk.sari, renk.mavi, '#2EE59D', '#FF8A00', '#A36BFF', '#FF4D6D', '#00E5E5', '#F15BB5'],
    backgroundColor: 'transparent',
    textStyle: { fontFamily: "'Inter Variable', system-ui, sans-serif", color: renk.metin2 },
    title: { textStyle: { fontFamily: "'Barlow Condensed', sans-serif", color: renk.metin } },
    valueAxis: {
      axisLine: { lineStyle: { color: 'rgba(130,170,255,0.28)' } },
      axisLabel: { color: renk.metin3 },
      splitLine: { lineStyle: { color: 'rgba(130,170,255,0.10)' } },
    },
    categoryAxis: {
      axisLine: { lineStyle: { color: 'rgba(130,170,255,0.28)' } },
      axisTick: { show: false },
      axisLabel: { color: renk.metin2 },
      splitLine: { show: false },
    },
    tooltip: {
      backgroundColor: 'rgba(3,7,16,0.92)',
      borderColor: 'rgba(130,170,255,0.28)',
      textStyle: { color: renk.metin },
    },
  });
}

export interface GrafikProps {
  secenek: EChartsCoreOption;
  /** yeni seçenekle eski seriyi tamamen değiştir (varsayılan false → animasyonlu geçiş) */
  birlestirme?: boolean;
  style?: CSSProperties;
  className?: string;
  /** ECharts örneğini dışarı verir (nadiren gerekir) */
  onHazir?: (g: echarts.ECharts) => void;
}

export default function Grafik({ secenek, birlestirme = false, style, className, onHazir }: GrafikProps) {
  const kap = useRef<HTMLDivElement>(null);
  const grafik = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    temayiKur();
    const el = kap.current;
    if (!el) return;
    const g = echarts.init(el, 'dehanet', { renderer: 'canvas' });
    grafik.current = g;
    onHazir?.(g);
    const go = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(() => g.resize()) : null;
    go?.observe(el);
    return () => {
      go?.disconnect();
      g.dispose();
      grafik.current = null;
    };
    // onHazir kasıtlı olarak bağımlılıkta değil
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    grafik.current?.setOption(secenek, { notMerge: birlestirme, lazyUpdate: false });
  }, [secenek, birlestirme]);

  return <div ref={kap} className={className} style={{ width: '100%', height: '100%', ...style }} />;
}

export { echarts };
