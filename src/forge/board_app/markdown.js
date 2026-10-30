// An inert Markdown renderer for a story's plan. It builds DOM nodes from text only: HTML in the doc
// stays text, a link stays a link only for http and https, and nothing in the doc can run.
// ponytail: headings, lists, tables, paragraphs, code, emphasis and links; add more when plans use more.

const INLINE = /`([^`]+)`|\*\*([^*]+)\*\*|\*([^*\s][^*]*)\*|\[([^\]]+)\]\(([^)\s]+)\)/g;

function el(tag, ...children) {
  const node = document.createElement(tag);
  node.append(...children);
  return node;
}

function web(address) {
  try {
    return ['http:', 'https:'].includes(new URL(address).protocol);
  } catch {
    return false;
  }
}

function inline(text) {
  const out = [];
  let at = 0;
  for (const found of text.matchAll(INLINE)) {
    out.push(text.slice(at, found.index));
    const [whole, code, strong, em, label, address] = found;
    if (code) out.push(el('code', code));
    else if (strong) out.push(el('strong', ...inline(strong)));
    else if (em) out.push(el('em', ...inline(em)));
    else if (web(address)) {
      const link = el('a', ...inline(label));
      link.href = address;
      link.rel = 'noreferrer';
      out.push(link);
    } else out.push(whole);
    at = found.index + whole.length;
  }
  out.push(text.slice(at));
  return out;
}

function cells(line) {
  return line.trim().replace(/^\||\|$/g, '').split('|').map((cell) => cell.trim());
}

// Block nodes for these lines, appended to `into`.
function blocks(lines, into) {
  let list = null;
  let para = [];
  const flush = () => {
    if (para.length) into.append(el('p', ...inline(para.join(' '))));
    para = [];
  };
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const heading = line.match(/^(#{1,4})\s+(.*)$/);
    const item = line.match(/^\s*(?:([-*])|(\d+)\.)\s+(.*)$/);
    if (list && !item && /^\s+\S/.test(line)) {
      list.lastChild.append(' ', ...inline(line.trim())); // a list item's wrapped line
      continue;
    }
    if (!item) list = null;
    if (!line.trim()) {
      flush();
    } else if (heading) {
      flush();
      into.append(el(`h${heading[1].length + 1}`, ...inline(heading[2])));
    } else if (item) {
      flush();
      const tag = item[1] ? 'ul' : 'ol';
      if (!list || list.tagName.toLowerCase() !== tag) into.append((list = el(tag)));
      list.append(el('li', ...inline(item[3])));
    } else if (line.trim().startsWith('|')) {
      flush();
      const rows = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) rows.push(lines[i++]);
      i--;
      const [head, ...body] = rows.filter((row) => !/^\s*\|[\s|:-]+\|\s*$/.test(row));
      const table = el('table', el('thead', el('tr', ...cells(head).map((cell) => el('th', ...inline(cell))))));
      table.append(el('tbody', ...body.map((row) => el('tr', ...cells(row).map((cell) => el('td', ...inline(cell)))))));
      // A wide table scrolls sideways, so its box takes keyboard focus and has a name.
      const box = el('div', table);
      Object.assign(box, { className: 'table', tabIndex: 0 });
      box.setAttribute('role', 'region');
      box.setAttribute('aria-label', 'Table');
      into.append(box);
    } else {
      para.push(line.trim());
    }
  }
  flush();
}

// The plan as a fragment: everything from "## For the builders" on is folded under a summary.
export function renderPlan(text) {
  const lines = text.replace(/\r\n?/g, '\n').split('\n');
  const fold = lines.findIndex((line) => /^##\s+For the builders\s*$/.test(line));
  const out = document.createDocumentFragment();
  blocks(fold < 0 ? lines : lines.slice(0, fold), out);
  if (fold >= 0) {
    const folded = el('details', el('summary', 'For the builders'));
    blocks(lines.slice(fold + 1), folded);
    out.append(folded);
  }
  return out;
}
