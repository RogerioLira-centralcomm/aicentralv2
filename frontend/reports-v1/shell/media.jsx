import React, {useEffect, useRef} from 'react';
import {Empty} from '../reportsCommon.jsx';

// Media formatting and the ApexCharts wrapper shared by the overview, the Mídia hub and the campaign detail.
export const money = (micros, currency) => micros == null || !currency ? '—' : new Intl.NumberFormat('pt-BR', {style: 'currency', currency}).format(micros / 1_000_000);
export const amount = (value, currency) => value == null || !currency ? '—' : new Intl.NumberFormat('pt-BR', {style: 'currency', currency}).format(Number(value));
export const platformName = value => ({manual:'Manual',google_ads: 'Google Ads', meta_ads: 'Meta Ads', microsoft_ads: 'Microsoft Ads', other: 'Outra'})[value||'manual'] || String(value).replaceAll('_', ' ');

/**
 * One series (`values`) or several (`series: [{name, data}]`), e.g. the period and the comparison period.
 * Optional: `dash` per series ([0, 4] draws the comparison dashed), `colors`, `format` for tooltip values and `legend={false}` when the page draws its own key.
 */
export function Chart({type = 'bar', labels, values, series, height = 260, horizontal = false, dash, colors, format, legend = true}) {
  const host = useRef(null);
  const formatter = useRef(format);
  formatter.current = format;
  useEffect(() => {
    const data = series || [{name: 'Total', data: values || []}];
    if (!host.current || !window.ApexCharts || !data[0]?.data?.length) return undefined;
    const chart = new window.ApexCharts(host.current, {
    chart: {type, height, toolbar: {show: false}, animations: {enabled: false}, fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Arial, sans-serif'},
      series: data,
      colors: colors || ['#175cd3', '#98a2b3', '#53b1fd'],
      dataLabels: {enabled: false},
      grid: {borderColor: '#eaecf0', strokeDashArray: 0},
      stroke: {curve: 'smooth', width: type === 'bar' ? 0 : 2, dashArray: dash || 0},
      // A dashed comparison series stays a plain line, without the area fill of the main one.
      fill: type === 'bar' ? {type: 'solid', opacity: 1} : {type: 'gradient', opacity: dash ? dash.map(item => item ? 0 : 1) : 1, gradient: {shadeIntensity: 0, opacityFrom: dash ? dash.map(item => item ? 0 : 0.1) : 0.1, opacityTo: 0, stops: [0, 90, 100]}},
      markers: {size: 0, hover: {size: 4}},
      plotOptions: {bar: {horizontal, borderRadius: 5, columnWidth: '44%'}},
      xaxis: {categories: labels, tickPlacement: 'on', tickAmount: Math.min(6, Math.max(1, (labels?.length || 1) - 1)), labels: {rotate: 0, hideOverlappingLabels: true, style: {colors: '#667085', fontSize: '12px'}}, axisBorder: {show: false}, axisTicks: {show: false}},
      yaxis: {labels: {style: {colors: '#667085', fontSize: '12px'}, formatter: value => new Intl.NumberFormat('pt-BR', {notation: 'compact', maximumFractionDigits: 1}).format(value)}, forceNiceScale: true, min: 0},
      tooltip: {theme: 'light', ...(formatter.current ? {y: {formatter: value => value == null ? '—' : formatter.current(value)}} : {})},
      responsive: [{breakpoint: 640, options: {xaxis: {tickAmount: Math.min(3, Math.max(1, (labels?.length || 1) - 1))}}}],
      legend: {show: legend && data.length > 1, position: 'top', horizontalAlign: 'right', fontSize: '12px', labels: {colors: '#475467'}},
    });
    chart.render();
    return () => chart.destroy();
  }, [type, height, horizontal, legend, JSON.stringify(labels), JSON.stringify(values), JSON.stringify(series), JSON.stringify(dash), JSON.stringify(colors)]);
  return (series?.[0]?.data?.length || values?.length) ? <div ref={host} className="reports-chart" /> : <Empty message="O gráfico aparece quando houver dados para esta seleção." />;
}
