// An item's detail: the drawer beside the cards (Board.select, Board.openDrawer) and its full page
// at #item/<id> (Board.openItem), with the tabs Overview, Plan (stories only), Rounds and Known issues.

const TOKEN = location.search;
const { renderPlan } = await import(`./markdown.js${TOKEN}`);
const STAGES = {
  working: 'Building', fixing: 'Building', building: 'Building', 'checks failed': 'Building',
  reviewing: 'Review', 'waiting for checks': 'Review', hotspot: 'Review',
  ready: 'Ready', 'ready to merge': 'Ready', merged: 'Merged', done: 'Merged',
};
const TONE = { Building: 'moving', Review: 'moving', Ready: 'ready', Merged: 'ready', Planned: 'waiting' };

let Board;
let drawer = null; // { id, node, opener, seen }
let page = null; // { id, node, tab, row, seen }

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs)) {
    if (name === 'class') node.className = value;
    else if (name.startsWith('on')) node.addEventListener(name.slice(2), value);
    else node.setAttribute(name, value);
  }
  node.append(...children.flat().filter((child) => child !== null && child !== undefined && child !== false));
  return node;
}

let lostFocus = null; // the control a redraw removed before its copy loaded, such as a plan link

// A control without a data-focus key is known by its tag, address and words.
function focusKey(control) {
  return control.dataset.focus || `${control.tagName} ${control.getAttribute('href')} ${control.textContent}`;
}

function refocus(node, key) {
  const control = [...node.querySelectorAll('a, button, summary, [tabindex]')].find((one) => focusKey(one) === key);
  if (!control) return false;
  if (control.tagName !== 'SUMMARY') control.closest('details:not([open])')?.setAttribute('open', '');
  control.focus({ preventScroll: true });
  return true;
}

function replaceContent(node, ...children) {
  const active = document.activeElement;
  const key = active !== node && node.contains(active) ? focusKey(active) : null;
  node.replaceChildren(...children);
  if (key) lostFocus = refocus(node, key) ? null : { node, key };
}

function restoreLostFocus(part) {
  if (!lostFocus || !lostFocus.node.contains(part) || document.activeElement !== document.body) return;
  if (refocus(part, lostFocus.key)) lostFocus = null;
}

function recordedWords(value, fallback = 'See the recorded review for technical details.') {
  const text = String(value || '');
  return /\b(?:forge|git|uv|npm|npx|pnpm|yarn|python3?|node)\s+[\w-]|--[a-z]|`/i.test(text)
    ? fallback : text || 'unknown';
}

function duration(seconds) {
  if (typeof seconds !== 'number') return 'unknown';
  const minutes = Math.round(seconds / 60);
  if (minutes < 1) return 'under a minute';
  if (minutes < 60) return `${minutes} m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h ${String(minutes % 60).padStart(2, '0')} m`;
  return `${Math.floor(hours / 24)} d ${hours % 24} h`;
}

function day(iso) {
  const when = iso ? new Date(iso) : null;
  return when && !isNaN(when) ? when.toLocaleString(undefined, { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' }) : 'unknown';
}

function rows() {
  return (Board.snapshot?.items || []).flatMap((parent) => [parent, ...parent.children]);
}

function parentOf(id) {
  return (Board.snapshot?.items || []).find((parent) => parent.children.some((child) => child.id === id)) || null;
}

function stage(row) {
  return row.needs_person ? 'Needs you' : STAGES[row.stage] || 'Planned';
}

function tag(row) {
  const name = stage(row);
  return el('span', { class: `tag ${row.needs_person ? 'needs-you' : row.stalled ? 'stuck' : TONE[name]}` }, name);
}

function kind(row) {
  if (row.kind === 'fix') return 'Fix';
  if (row.kind === 'story') return `Story ${row.id}`;
  const parent = parentOf(row.id);
  return `Part of ${parent ? parent.title : row.id.split('/')[0]}`;
}

function person(row) {
  const who = row.owner || row.developer;
  return who ? `${row.owner ? 'Owner' : 'Developer'} ${who}` : 'No owner yet';
}

function issues(row) {
  return (Board.snapshot?.known_issues || []).filter((issue) => issue.item === row.id || issue.item?.startsWith(`${row.id}/`));
}

function roundSeconds(round) {
  return round.seconds ? Object.values(round.seconds).reduce((sum, value) => sum + value, 0) : null;
}

function roundName(round) {
  if (round.first) return `Rounds ${round.first} to ${round.last}`;
  return round.round ? `Round ${round.round}` : 'A round Forge has no number for';
}

function roundWhat(round) {
  const text = String(round.line || '').replace(/^Rounds? [^:]*:\s*/, '');
  // Finding titles follow the measured summary. Keep that summary when a title
  // contains terminal instructions, without exposing the instructions on the board.
  return recordedWords(text, recordedWords(text.split(' — ')[0]));
}

function figures(row) {
  const count = row.findings?.count;
  return el('dl', { class: 'figures' },
    [['review rounds', row.rounds ? row.rounds.reduce((total, round) => total
      + (round.first != null && round.last != null ? round.last - round.first + 1 : 1), 0) : row.round ?? 'unknown'],
     ['known issues kept', issues(row).length],
     ['open findings', typeof count === 'number' ? count : 'unknown']]
      .map(([label, value]) => el('div', {}, el('dt', {}, label), el('dd', {}, String(value)))));
}

function timeBar(row) {
  const parts = [['work', row.working_seconds, 'work'], ['waiting', row.waiting_seconds, 'wait'], ['unknown', row.unknown_seconds, 'unknown']]
    .filter(([, seconds]) => typeof seconds === 'number' && seconds > 0);
  const total = parts.reduce((sum, [, seconds]) => sum + seconds, 0);
  if (!total) return el('section', { class: 'block' }, el('h3', {}, 'Time'), el('p', { class: 'quiet' }, 'Time taken is unknown.'));
  const bar = el('div', { class: 'bar-chart', 'aria-hidden': 'true' }, parts.map(([, seconds, tone]) => {
    const part = el('span', { class: tone });
    part.style.flexGrow = String(seconds);
    return part;
  }));
  const forYou = row.time_breakdown?.waiting_for_owner;
  return el('section', { class: 'block' }, el('h3', {}, `Time · ${duration(total)}`), bar,
    el('p', { class: 'legend' }, parts.map(([name, seconds, tone]) => el('span', { class: tone }, `${name} ${duration(seconds)}`)),
      typeof forYou === 'number' && forYou > 0 ? el('span', { class: 'for-you' }, `waited for a person ${duration(forYou)}`) : null));
}

function roundList(row, limit) {
  const list = (row.rounds || []).slice(-limit);
  if (!list.length) return el('p', { class: 'quiet' }, 'No review rounds yet. They show here once the work is reviewed.');
  return el('ol', { class: 'rounds' }, list.map((round) => el('li', {},
    el('span', { class: `dot ${round.findings?.length || round.new_findings ? 'stuck' : 'moving'}`, 'aria-hidden': 'true' }),
    el('span', { class: 'what' }, el('strong', {}, `${roundName(round)}: `), roundWhat(round)),
    el('span', { class: 'took' }, duration(roundSeconds(round))))));
}

function partList(parts, current) {
  return el('ul', { class: 'part-list' }, parts.map((part) => el('li', {},
    el('button', { type: 'button', class: `part ${part.id === current ? 'current' : ''}`,
                   'data-focus': `part-${part.id}`,
                   'aria-current': part.id === current ? 'true' : 'false', onclick: () => openDrawer(part.id) },
      el('span', {}, part.title), el('span', { class: `state ${TONE[stage(part)] || 'needs-you'}` }, stage(part))))));
}

// The drawer

function drawerBody(row) {
  const parent = row.kind === 'story' ? row : parentOf(row.id);
  const parts = parent ? parent.children : [];
  return [
    el('div', { class: 'head' },
      el('p', { class: 'kind' }, tag(row), el('span', {}, kind(row))),
      el('button', { type: 'button', class: 'close', 'aria-label': 'Close', 'data-focus': 'close', onclick: closeDrawer }, closeIcon()),
      el('h2', { id: 'drawer-title', tabindex: '-1', 'data-focus': 'drawer-title' }, row.title),
      el('p', { class: 'who' }, el('span', { 'data-assign': row.id }, person(row)),
        el('a', { href: `#item/${row.id}`, class: 'more', 'data-focus': 'history' }, 'Full history')),
      el('p', { class: 'state-line' }, row.status || 'Status unknown.')),
    timeBar(row),
    el('section', { class: 'block' }, el('h3', {}, 'Rounds'), roundList(row, 4)),
    parts.length ? el('section', { class: 'block' }, el('h3', {}, row.kind === 'story' ? 'Its parts' : 'Its story’s parts'),
      partList(parts, row.id)) : null,
    figures(row),
  ].filter(Boolean);
}

function closeIcon() {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 16 16');
  svg.setAttribute('aria-hidden', 'true');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', 'M4 4l8 8M12 4l-8 8');
  svg.append(path);
  return svg;
}

async function openDrawer(id) {
  let row = rows().find((one) => one.id === id);
  const opener = drawer?.opener || document.activeElement;
  // Moving between items keeps the open drawer, so it slides in only once.
  const node = drawer?.node || el('aside', { class: 'drawer', 'aria-labelledby': 'drawer-title' });
  drawer = { id, node, opener, seen: '' };
  if (!node.isConnected) document.body.append(node);
  if (!row) {
    node.append(el('p', { class: 'quiet' }, 'Reading this item…'));
    row = await item(id).catch((error) => error);
    if (drawer?.node !== node) return;
    if (row instanceof Error) {
      node.replaceChildren(el('button', { type: 'button', class: 'close', 'aria-label': 'Close', onclick: closeDrawer }, closeIcon()),
        el('p', { role: 'alert', class: 'problem' }, row.message));
      node.querySelector('.close').focus();
      return;
    }
  }
  fillDrawer(row);
  node.querySelector('h2').focus();
}

function fillDrawer(row) {
  drawer.seen = JSON.stringify(row);
  replaceContent(drawer.node, ...drawerBody(row));
}

function closeDrawer(restore = true) {
  if (!drawer) return;
  drawer.node.remove();
  const { opener } = drawer;
  drawer = null;
  if (restore && opener?.isConnected) opener.focus();
}

// The full page

async function item(id) {
  const answer = await fetch(`board.json${TOKEN}&page=item&id=${encodeURIComponent(id)}`, { cache: 'no-store' });
  let body = {};
  try {
    body = await answer.json();
  } catch {}
  if (!answer.ok) throw new Error(body.error || 'The board could not read this item. Open it again in a moment.');
  return body.item;
}

function openItem(id) {
  location.hash = `item/${id}`;
}

async function showPage() {
  const id = location.hash.startsWith('#item/') ? decodeURIComponent(location.hash.slice(6)) : null;
  if (!id) return closePage();
  if (page?.id === id) return;
  closeDrawer(false);
  closePage();
  const main = document.querySelector('main:not(.item-page)');
  const node = el('main', { class: 'item-page' },
    el('nav', { 'aria-label': 'Breadcrumb', class: 'crumbs' }, el('a', { href: '#now' }, 'Now'), el('span', { 'aria-hidden': 'true' }, '›'),
      el('span', { 'aria-current': 'page' }, id)),
    el('p', { class: 'quiet' }, 'Reading this item…'));
  page = { id, node, tab: 'Overview', row: null, seen: '' };
  main.hidden = true;
  main.after(node);
  try {
    page.row = await item(id);
  } catch (error) {
    if (page?.node !== node) return;
    node.replaceChildren(node.firstChild, el('p', { role: 'alert', class: 'problem' }, `${error.message} Go back to Now to pick another.`));
    return;
  }
  if (page?.node === node) fillPage();
}

function fillPage() {
  const { row } = page;
  const tabId = (name) => `tab-${name.replaceAll(' ', '-')}`;
  page.seen = JSON.stringify(rows().find((one) => one.id === row.id) || null);
  const tabs = ['Overview', ...(row.kind === 'story' ? ['Plan'] : []), 'Rounds', 'Known issues'];
  const kept = issues(row);
  page.node.querySelector('.crumbs [aria-current]').textContent = row.title;
  const tablist = el('div', { role: 'tablist', 'aria-label': row.title, class: 'tabs' }, tabs.map((name) => el('button', {
    type: 'button', role: 'tab', id: tabId(name), 'data-focus': tabId(name), 'aria-controls': 'tab-panel', 'aria-selected': String(name === page.tab),
    onclick: () => { page.tab = name; fillPage(); document.getElementById(tabId(name)).focus(); },
  }, name === 'Known issues' ? `Known issues · ${kept.length}` : name)));
  const panel = el('section', { role: 'tabpanel', id: 'tab-panel', 'aria-labelledby': tabId(page.tab), class: 'panel' });
  panel.append(...{ Overview: overview, Plan: plan, Rounds: roundsTab, 'Known issues': knownIssues }[page.tab](row, panel));
  replaceContent(page.node, page.node.firstChild,
    el('div', { class: 'item-grid' },
      el('div', { class: 'summary' },
        el('p', { class: 'kind' }, tag(row), el('span', {}, kind(row))),
        el('h1', {}, row.title),
        el('p', { class: 'person' }, el('span', { 'data-assign': row.id }, person(row))),
        el('p', { class: 'state-line' }, row.status || 'Status unknown.'),
        figures(row)),
      el('div', { class: 'sheet' }, tablist, panel)));
}

function fact(label, value) {
  return el('div', {}, el('dt', {}, label), el('dd', {}, value || 'unknown'));
}

function overview(row) {
  const pr = row.pr?.url && /^https?:/.test(row.pr.url)
    ? el('a', { href: row.pr.url, rel: 'noreferrer' }, `Pull request ${row.pr.number}`) : null;
  const history = (Board.snapshot?.events || []).filter((event) => event.item === row.id);
  return [
    row.kind === 'story' && row.children?.length ? el('section', { class: 'block' }, el('h2', {}, 'Parts'), partList(row.children, null)) : null,
    el('section', { class: 'block' }, el('h2', {}, 'History'),
      el('dl', { class: 'facts' },
        fact('Started by', row.started_by), fact('Approved by', row.approved_by),
        fact(row.merged_at ? 'Merged' : 'Merged by', row.merged_at ? `${day(row.merged_at)} by ${row.merged_by?.name || 'unknown'}`
          : row.merged_by?.name || (['merged', 'done'].includes(row.stage) ? 'unknown' : 'not yet')),
        pr ? el('div', {}, el('dt', {}, 'Pull request'), el('dd', {}, pr)) : null),
      history.length ? el('ol', { class: 'events' }, history.slice().reverse().map((event) =>
        el('li', {}, el('time', { datetime: event.time }, day(event.time)),
          el('span', {}, recordedWords(event.line, 'A worker asked a technical question.'))))) : null),
    timeBar(row),
    row.took?.length ? el('section', { class: 'block' }, el('h2', {}, 'How long each step took'),
      el('ul', { class: 'took-list' }, row.took.map((line) => el('li', {}, line)))) : null,
  ].filter(Boolean);
}

function plan(row, panel) {
  const doc = el('article', { class: 'plan' }, el('p', { class: 'quiet' }, 'Reading the plan…'));
  fetch(`plan/${encodeURIComponent(row.id)}${TOKEN}`, { cache: 'no-store' })
    .then(async (answer) => {
      const text = await answer.text();
      if (answer.ok) return doc.replaceChildren(renderPlan(text)), restoreLostFocus(doc);
      let reason = 'The board could not read the plan. Open the tab again in a moment.';
      try {
        reason = JSON.parse(text).error;
      } catch {}
      doc.replaceChildren(el('p', { class: 'quiet' }, reason));
    })
    .catch(() => doc.replaceChildren(el('p', { role: 'alert', class: 'problem' }, 'The board cannot reach its server. Start the board again from the terminal.')));
  return [doc];
}

function roundsTab(row) {
  const reads = row.read_rounds || [];
  return [
    el('section', { class: 'block' }, el('h2', {}, 'Review rounds'), roundList(row, Infinity)),
    reads.length ? el('section', { class: 'block' }, el('h2', {}, 'Plan reads'),
      el('ol', { class: 'rounds' }, reads.map((read) => el('li', {},
        el('span', { class: 'dot waiting', 'aria-hidden': 'true' }),
        el('span', { class: 'what' }, el('strong', {}, `Read ${read.round}: `),
          `${read.findings?.length ?? 'unknown'} notes`),
        el('span', { class: 'took' }, read.read_at ? day(read.read_at) : 'unknown'))))) : null,
  ].filter(Boolean);
}

function knownIssues(row) {
  const kept = issues(row);
  if (!kept.length) return [el('p', { class: 'quiet' }, 'No problems were kept for later. Problems a review lets through show here.')];
  const byFile = Map.groupBy(kept, (issue) => issue.file || 'No file named');
  return [...byFile].map(([file, list]) => el('section', { class: 'block' }, el('h2', { class: 'file' }, file),
    el('ul', { class: 'issues' }, list.map((issue) => el('li', {},
      el('span', {}, recordedWords(issue.title)), el('span', { class: 'quiet' },
        recordedWords([issue.kept, issue.reason].filter(Boolean).join(': '), 'The review kept this problem for later.')))))));
}

function closePage() {
  if (!page) return;
  page.node.remove();
  page = null;
  document.querySelector('main:not(.item-page)').hidden = false;
}

export function install(board) {
  Board = board;
  document.head.append(el('link', { rel: 'stylesheet', href: `item.css${TOKEN}` }));
  Object.assign(Board, { select: openDrawer, openDrawer, openItem });
  addEventListener('hashchange', showPage);
  addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    if (drawer) closeDrawer();
    else if (page) Board.navigate('now');
  });
  Board.onSnapshot(() => {
    const row = drawer && rows().find((one) => one.id === drawer.id);
    if (row && JSON.stringify(row) !== drawer.seen) fillDrawer(row);
    if (page?.row && JSON.stringify(rows().find((one) => one.id === page.id) || null) !== page.seen) {
      item(page.id).then((fresh) => { if (page?.id === fresh.id) { page.row = fresh; fillPage(); } }, () => {});
    }
  });
  showPage();
}
