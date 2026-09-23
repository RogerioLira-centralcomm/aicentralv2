import React, {useState} from 'react';
import {safeUrl} from '../lib/api';
import {normalizeInlineMarkdown, restoreEscapedMarkdown, splitInlineMarkdown, splitTableRow, isTableDivider} from '../lib/markdownModel.mjs';

function LinkWithFavicon({href, label}) {
  const [failed, setFailed] = useState(false);
  let domain = '';
  let favicon = '';
  try {
    const url = new URL(href);
    domain = url.hostname.replace(/^www\./, '');
    favicon = `${url.origin}/favicon.ico`;
  } catch (_) { return label; }
  return <a className="cv-inline-link" href={href} target="_blank" rel="noreferrer" referrerPolicy="no-referrer">
    <span className="cv-inline-link__favicon" aria-hidden="true">{favicon && !failed
      ? <img src={favicon} alt="" loading="lazy" onError={() => setFailed(true)}/>
      : domain.slice(0, 1).toUpperCase()}</span>
    <span>{label || domain}</span>
  </a>;
}

function Inline({text}) {
  const normalized = normalizeInlineMarkdown(text);
  const tokens = splitInlineMarkdown(normalized);
  return tokens.map((token, index) => {
    if (/^(?:\*\*.*\*\*|__.*__)$/.test(token)) {
      const emphasis = token.slice(2, -2);
      const words = emphasis.trim().split(/\s+/).filter(Boolean);
      // Long bold spans make generated prose look like an alert and often
      // originate from an over-eager model. Keep emphasis for labels and
      // short phrases, never for complete paragraphs.
      return words.length <= 4 && emphasis.length <= 44
        ? <strong key={index}>{restoreEscapedMarkdown(emphasis)}</strong>
        : restoreEscapedMarkdown(emphasis);
    }
    if (/^(?:\*[^*].*\*|_[^_].*_)$/.test(token)) return <em key={index}>{restoreEscapedMarkdown(token.slice(1, -1))}</em>;
    if (/^~~.*~~$/.test(token)) return <del key={index}>{restoreEscapedMarkdown(token.slice(2, -2))}</del>;
    if (/^`.*`$/.test(token)) return <code key={index}>{restoreEscapedMarkdown(token.slice(1, -1))}</code>;
    const link = token.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/);
    if (link) {
      const href = safeUrl(link[2]);
      return href ? <LinkWithFavicon key={index} href={href} label={link[1]}/> : token;
    }
    const rawHref = token.replace(/[),.;!?]+$/, '');
    const suffix = token.slice(rawHref.length);
    const href = safeUrl(rawHref);
    if (href && /^https?:\/\//i.test(token)) return <React.Fragment key={index}><LinkWithFavicon href={href} label={href.replace(/^https?:\/\/(?:www\.)?/i, '')}/>{suffix}</React.Fragment>;
    return restoreEscapedMarkdown(token);
  });
}

export function Markdown({children, onOpenResource}) {
  const blocks = [];
  let list = null;
  let paragraph = [];
  let fence = null;
  const flush = () => { if (list) { blocks.push(list); list = null; } };
  const flushParagraph = index => {
    if (!paragraph.length) return;
    blocks.push(<p key={`p-${index}`}><Inline text={paragraph.join(' ')}/></p>);
    paragraph = [];
  };
  const lines = String(children || '').replace(/\r\n/g, '\n').split('\n');
  for (let index = 0; index < lines.length; index += 1) {
    const raw = lines[index];
    const line = raw.trim();
    const headers = splitTableRow(line);
    if (!fence && line.includes('|') && isTableDivider(lines[index + 1], headers.length)) {
      flush(); flushParagraph(index);
      const rows = [];
      index += 1;
      while (index + 1 < lines.length && lines[index + 1].trim().includes('|')) {
        const cells = splitTableRow(lines[index + 1]);
        if (cells.length !== headers.length) break;
        rows.push(cells);
        index += 1;
      }
      blocks.push(<div className="cv-table-scroll" role="region" aria-label="Tabela da resposta" tabIndex={0} key={`table-${index}`}>
        <table className="cv-markdown-table"><thead><tr>{headers.map((cell, column) => <th scope="col" key={column}><Inline text={cell}/></th>)}</tr></thead>
          <tbody>{rows.map((cells, row) => <tr key={row}>{cells.map((cell, column) => <td key={column}><Inline text={cell}/></td>)}</tr>)}</tbody>
        </table>
      </div>);
      continue;
    }
    const fenceMarker = line.match(/^```([a-z0-9_-]*)\s*$/i);
    if (fenceMarker) {
      flush(); flushParagraph(index);
      if (fence) { blocks.push(<pre key={`code-${fence.key}`}><code className={fence.language ? `language-${fence.language}` : undefined}>{fence.lines.join('\n')}</code></pre>); fence = null; }
      else fence = {key: index, language: fenceMarker[1], lines: []};
      continue;
    }
    if (fence) { fence.lines.push(raw); continue; }
    if (!line) { flush(); flushParagraph(index); continue; }
    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    const bullet = line.match(/^[-*+]\s+(.+)$/);
    const numbered = line.match(/^\d+[.)]\s+(.+)$/);
    const quote = line.match(/^>\s?(.+)$/);
    const rule = /^(?:-{3,}|\*{3,}|_{3,})$/.test(line);
    if (heading) {
      flush(); flushParagraph(index);
      const level = heading[1].length <= 2 ? 'h2' : 'h3';
      blocks.push(React.createElement(level, {key: `h-${index}`}, <Inline text={heading[2]}/>));
    } else if (quote) {
      flush(); flushParagraph(index);
      blocks.push(<blockquote key={`q-${index}`}><Inline text={quote[1]}/></blockquote>);
    } else if (rule) {
      flush(); flushParagraph(index);
      blocks.push(<hr key={`hr-${index}`}/>);
    } else if (bullet || numbered) {
      flushParagraph(index);
      const type = numbered ? 'ol' : 'ul';
      if (!list || list.listType !== type) { flush(); list = {kind: 'list', listType: type, key: index, items: []}; }
      list.items.push(<li key={index}><Inline text={(bullet || numbered)[1]}/></li>);
    } else {
      flush();
      paragraph.push(line);
    }
  }
  if (fence) blocks.push(<pre key={`code-${fence.key}`}><code className={fence.language ? `language-${fence.language}` : undefined}>{fence.lines.join('\n')}</code></pre>);
  flush(); flushParagraph('last');
  return <>{blocks.map(block => block?.kind === 'list' ? React.createElement(block.listType, {key: `l-${block.key}`}, block.items) : block)}</>;
}
