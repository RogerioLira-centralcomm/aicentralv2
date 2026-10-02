import React from 'react';
import {ArrowDown, ArrowUp, Eye, EyeOff, Plus, Trash01} from '@untitledui/icons';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {ReportsTextArea} from './ReportsTextArea.jsx';

// Same catalogue as aicentralv2/cadu_connect/report_blocks.py.
const DATA = {results: 'Resultados', funnel: 'Da mídia à conversão', campaigns: 'Campanhas'};
const FIELDS = {objective: ['Objetivo', 'objective', 2000], goals: ['Metas', 'goals', 4000], notes: ['Contexto de gestão', 'management_notes', 8000]};
const TEXT = {text: 'Texto', recommendations: 'Recomendações', next_steps: 'Próximos passos'};

export const defaultBlocks = document => [...Object.entries(DATA), ...Object.entries(FIELDS).map(([key, [title]]) => [key, title])]
  .map(([key, title]) => ({id: key, type: key, title, hidden: key === 'funnel' && document?.scope !== 'flow'}));

/** Saved blocks, plus any built-in block the saved list predates (added hidden), as the server does. */
export const blocksOf = document => {
  const saved = Array.isArray(document?.blocks) && document.blocks.length ? document.blocks : null;
  if (!saved) return defaultBlocks(document);
  const present = new Set(saved.map(block => block.type));
  return [...saved, ...defaultBlocks(document).filter(block => !present.has(block.type)).map(block => ({...block, hidden: true}))];
};

/** Report blocks: order, title, visibility and text. Data blocks are filled from the period; field blocks edit the classic fields. */
export function ReportBlocksEditor({blocks, onChange, draft, onField, disabled}) {
  const set = (index, patch) => onChange(blocks.map((block, at) => at === index ? {...block, ...patch} : block));
  const move = (index, step) => {
    const next = [...blocks]; const target = index + step;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]]; onChange(next);
  };
  const add = type => onChange([...blocks, {id: `${type.replace('_', '-')}-${Date.now().toString(36)}`, type, title: TEXT[type], hidden: false, text: ''}]);
  return <div className="flex flex-col gap-3">
    {blocks.map((block, index) => {
      const field = FIELDS[block.type];
      return <div key={block.id} className={`flex flex-col gap-3 rounded-xl p-4 ring-1 ring-inset ${block.hidden ? 'bg-secondary_subtle ring-secondary opacity-70' : 'bg-primary ring-secondary'}`}>
        <div className="flex items-center gap-2">
          <input aria-label="Título do bloco" disabled={disabled} maxLength={120} value={block.title} onChange={event => set(index, {title: event.target.value})}
            className="min-w-0 flex-1 rounded-md bg-transparent px-2 py-1 text-md font-semibold text-primary ring-secondary ring-inset hover:ring-1 focus:ring-2 focus:ring-brand focus:outline-none"/>
          <span className="hidden text-xs text-tertiary sm:inline">{DATA[block.type] ? 'dados do período' : field ? 'campo do relatório' : 'texto livre'}</span>
          {!disabled && <>
            <Button size="sm" color="tertiary" iconLeading={ArrowUp} aria-label="Subir" isDisabled={!index} onPress={() => move(index, -1)}/>
            <Button size="sm" color="tertiary" iconLeading={ArrowDown} aria-label="Descer" isDisabled={index === blocks.length - 1} onPress={() => move(index, 1)}/>
            <Button size="sm" color="tertiary" iconLeading={block.hidden ? EyeOff : Eye} aria-label={block.hidden ? 'Mostrar no relatório' : 'Ocultar do relatório'} onPress={() => set(index, {hidden: !block.hidden})}/>
            {TEXT[block.type] && <Button size="sm" color="tertiary-destructive" iconLeading={Trash01} aria-label="Remover bloco" onPress={() => onChange(blocks.filter((_, at) => at !== index))}/>}
          </>}
        </div>
        {DATA[block.type] && <p className="px-2 text-sm text-tertiary">{block.type === 'results' ? 'KPIs de mídia e comparação com o período anterior.' : block.type === 'funnel' ? 'Mídia → entradas → conversões do fluxo. Só aparece em relatórios por fluxo.' : 'Tabela por campanha.'} Preenchido ao publicar.</p>}
        {field && <ReportsTextArea aria-label={field[0]} disabled={disabled} maxLength={field[2]} rows={3} value={draft[field[1]] || ''} onChange={event => onField(field[1], event.target.value)}/>}
        {TEXT[block.type] && <ReportsTextArea aria-label={block.title} disabled={disabled} maxLength={8000} rows={4} value={block.text || ''} onChange={event => set(index, {text: event.target.value})}/>}
      </div>;
    })}
    {!disabled && <div className="flex flex-wrap gap-2">{Object.entries(TEXT).map(([type, label]) =>
      <Button key={type} size="sm" color="secondary" iconLeading={Plus} isDisabled={blocks.length >= 30} onPress={() => add(type)}>{label}</Button>)}</div>}
  </div>;
}
