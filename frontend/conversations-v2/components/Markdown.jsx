import React from 'react';
import {safeUrl} from '../lib/api';
import {normalizeInlineMarkdown, restoreEscapedMarkdown, splitInlineMarkdown} from '../lib/markdownModel.mjs';

function Inline({text, onOpenResource}) {
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
      return href ? <a key={index} href={href} onClick={event => {
        if (!onOpenResource) return;
        event.preventDefault();
        onOpenResource({url: href, title: link[1], kind: 'Link público', access_type: 'public'});
      }} target={onOpenResource ? undefined : '_blank'} rel={onOpenResource ? undefined : 'noreferrer'}>{link[1]}</a> : token;
    }
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
    blocks.push(<p key={`p-${index}`}><Inline text={paragraph.join(' ')} onOpenResource={onOpenResource}/></p>);
    paragraph = [];
  };
  String(children || '').replace(/\r\n/g, '\n').split('\n').forEach((raw, index) => {
    const line = raw.trim();
    const fenceMarker = line.match(/^```([a-z0-9_-]*)\s*$/i);
    if (fenceMarker) {
      flush(); flushParagraph(index);
      if (fence) { blocks.push(<pre key={`code-${fence.key}`}><code className={fence.language ? `language-${fence.language}` : undefined}>{fence.lines.join('\n')}</code></pre>); fence = null; }
      else fence = {key: index, language: fenceMarker[1], lines: []};
      return;
    }
    if (fence) { fence.lines.push(raw); return; }
    if (!line) { flush(); flushParagraph(index); return; }
    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    const bullet = line.match(/^[-*+]\s+(.+)$/);
    const numbered = line.match(/^\d+[.)]\s+(.+)$/);
    const quote = line.match(/^>\s?(.+)$/);
    const rule = /^(?:-{3,}|\*{3,}|_{3,})$/.test(line);
    if (heading) {
      flush(); flushParagraph(index);
      const level = heading[1].length <= 2 ? 'h2' : 'h3';
      blocks.push(React.createElement(level, {key: `h-${index}`}, <Inline text={heading[2]} onOpenResource={onOpenResource}/>));
    } else if (quote) {
      flush(); flushParagraph(index);
      blocks.push(<blockquote key={`q-${index}`}><Inline text={quote[1]} onOpenResource={onOpenResource}/></blockquote>);
    } else if (rule) {
      flush(); flushParagraph(index);
      blocks.push(<hr key={`hr-${index}`}/>);
    } else if (bullet || numbered) {
      flushParagraph(index);
      const type = numbered ? 'ol' : 'ul';
      if (!list || list.listType !== type) { flush(); list = {kind: 'list', listType: type, key: index, items: []}; }
      list.items.push(<li key={index}><Inline text={(bullet || numbered)[1]} onOpenResource={onOpenResource}/></li>);
    } else {
      flush();
      paragraph.push(line);
    }
  });
  if (fence) blocks.push(<pre key={`code-${fence.key}`}><code className={fence.language ? `language-${fence.language}` : undefined}>{fence.lines.join('\n')}</code></pre>);
  flush(); flushParagraph('last');
  return <>{blocks.map(block => block?.kind === 'list' ? React.createElement(block.listType, {key: `l-${block.key}`}, block.items) : block)}</>;
}
