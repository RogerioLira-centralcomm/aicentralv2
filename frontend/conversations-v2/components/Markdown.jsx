import React from 'react';
import {safeUrl} from '../lib/api';

function Inline({text}) {
  const tokens = String(text || '').split(/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\(https?:\/\/[^\s)]+\))/g);
  return tokens.map((token, index) => {
    if (/^\*\*.*\*\*$/.test(token)) {
      const emphasis = token.slice(2, -2);
      const words = emphasis.trim().split(/\s+/).filter(Boolean);
      // Long bold spans make generated prose look like an alert and often
      // originate from an over-eager model. Keep emphasis for labels and
      // short phrases, never for complete paragraphs.
      return words.length <= 8 && emphasis.length <= 80
        ? <strong key={index}>{emphasis}</strong>
        : emphasis;
    }
    if (/^`.*`$/.test(token)) return <code key={index}>{token.slice(1, -1)}</code>;
    const link = token.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/);
    if (link) {
      const href = safeUrl(link[2]);
      return href ? <a key={index} href={href} target="_blank" rel="noreferrer">{link[1]}</a> : token;
    }
    return token;
  });
}

export function Markdown({children}) {
  const blocks = [];
  let list = null;
  const flush = () => { if (list) { blocks.push(list); list = null; } };
  String(children || '').replace(/\r\n/g, '\n').split('\n').forEach((raw, index) => {
    const line = raw.trim();
    if (!line) return flush();
    const heading = line.match(/^#{1,6}\s+(.+)$/);
    const bullet = line.match(/^[-*+]\s+(.+)$/);
    const numbered = line.match(/^\d+[.)]\s+(.+)$/);
    if (heading) {
      flush();
      blocks.push(<h3 key={`h-${index}`}><Inline text={heading[1]}/></h3>);
    } else if (bullet || numbered) {
      const type = numbered ? 'ol' : 'ul';
      if (!list || list.listType !== type) { flush(); list = {kind: 'list', listType: type, key: index, items: []}; }
      list.items.push(<li key={index}><Inline text={(bullet || numbered)[1]}/></li>);
    } else {
      flush();
      blocks.push(<p key={`p-${index}`}><Inline text={line}/></p>);
    }
  });
  flush();
  return <>{blocks.map(block => block?.kind === 'list' ? React.createElement(block.listType, {key: `l-${block.key}`}, block.items) : block)}</>;
}
