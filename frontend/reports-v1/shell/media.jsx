import React, {useEffect, useRef} from 'react';
import {Empty} from '../reportsCommon.jsx';

// Media formatting and the ApexCharts wrapper shared by the overview, the Mídia hub and the campaign detail.
export const money = (micros, currency) => micros == null || !currency ? '—' : new Intl.NumberFormat('pt-BR', {style: 'currency', currency}).format(micros / 1_000_000);
export const amount = (value, currency) => value == null || !currency ? '—' : new Intl.NumberFormat('pt-BR', {style: 'currency', currency}).format(Number(value));
export const platformName = value => ({manual:'Manual',google_ads: 'Google Ads', meta_ads: 'Meta Ads', microsoft_ads: 'Microsoft Ads', other: 'Outra'})[value||'manual'] || String(value).replaceAll('_', ' ');

export function Chart({type = 'bar', labels, values, height = 260, horizontal = false}) {
  const host = useRef(null);
  useEffect(() => {
    if (!host.current || !window.ApexCharts || !values?.length) return undefined;
    const chart = new window.ApexCharts(host.current, {
    chart: {type, height, toolbar: {show: false}, animations: {enabled: false}, fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Arial, sans-serif'},
      series: [{name: 'Total', data: values}],
      colors: ['#175cd3'],
      dataLabels: {enabled: false},
      grid: {borderColor: '#eaecf0', strokeDashArray: 0},
      stroke: {curve: 'smooth', width: type === 'area' ? 2 : 1},
      fill: {type: 'gradient', gradient: {shadeIntensity: 0, opacityFrom: 0.1, opacityTo: 0, stops: [0, 90, 100]}},
      markers: {size: 0, hover: {size: 4}},
      plotOptions: {bar: {horizontal, borderRadius: 5, columnWidth: '44%'}},
      xaxis: {categories: labels, tickPlacement: 'on', tickAmount: Math.min(6, Math.max(1, (labels?.length || 1) - 1)), labels: {rotate: 0, hideOverlappingLabels: true, style: {colors: '#667085', fontSize: '12px'}}, axisBorder: {show: false}, axisTicks: {show: false}},
      yaxis: {labels: {style: {colors: '#667085', fontSize: '12px'}, formatter: value => new Intl.NumberFormat('pt-BR', {notation: 'compact', maximumFractionDigits: 1}).format(value)}, forceNiceScale: true},
      tooltip: {theme: 'light'},
      responsive: [{breakpoint: 640, options: {xaxis: {tickAmount: Math.min(3, Math.max(1, (labels?.length || 1) - 1))}}}],
      legend: {show: false},
    });
    chart.render();
    return () => chart.destroy();
  }, [type, height, horizontal, JSON.stringify(labels), JSON.stringify(values)]);
  return values?.length ? <div ref={host} className="reports-chart" /> : <Empty message="O gráfico aparece quando houver dados para esta seleção." />;
}
