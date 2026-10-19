// The Now screen: what needs you, the parts and fixes in flight as one-line cards in five stages, the
// stories with their parts and owners (or, in Me, this laptop's live runs), and four figures. Every
// item stays reachable: a long stage or list ends in a button that opens all of it beside the cards.

const STAGES = [['planned', 'Planned'], ['building', 'Building'], ['review', 'Review'], ['ready', 'Ready'],
  ['merged', 'Merged']];
const STAGE_OF = {
  unstarted: 'planned', started: 'planned', 'Not started': 'planned', Waiting: 'planned', 'Can start now': 'planned',
  working: 'building', fixing: 'building', 'checks failed': 'building',
  reviewing: 'review', 'waiting for checks': 'review', hotspot: 'review',
  ready: 'ready', merged: 'merged', done: 'merged',
};
const VERB = { approval: 'Approve', 'worker question': 'Answer', merge: 'Merge' }; // every other wait: Decide
const KINDS = [['all', 'All'], ['task', 'Story parts'], ['fix', 'Fixes']];
const RUN = { work: 'Building', worker: 'Building', review: 'Reviewing', read: 'Reading the plan', test: 'Testing' };
const CARDS = 4; // per stage, then "and N more"
const STORIES = 5;
const ASKS = 3;
const MERGED = 3;
const WEEK = 7 * 86400 * 1000;

let Board;
let kind = 'all';
let list = null; // {key, title, entries}: a full list open beside the cards

export function install(board) {
  Board = board;
  const sheet = document.createElement('link');
  sheet.rel = 'stylesheet';
  sheet.href = `now.css${location.search}`;
  document.head.append(sheet);
  Board.screens.now = render;
}

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(props)) {
    if (value == null || value === false) continue;
    if (name === 'class') node.className = value;
    else if (name === 'onclick') node.addEventListener('click', value);
    else node.setAttribute(name, value === true ? '' : value);
  }
  node.append(...children.flat().filter((child) => child != null && child !== false));
  return node;
}

const same = (a, b) => Boolean(a && b) && a.replace(/^@/, '').toLowerCase() === b.replace(/^@/, '').toLowerCase();
const key = (id) => id.split('/')[0];

function hours(seconds) {
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  if (seconds < 48 * 3600) return `${+(seconds / 3600).toFixed(1)} h`;
  return `${+(seconds / 86400).toFixed(1)} d`;
}

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = sorted.length >> 1;
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

// Everything the screen shows, for the Team view or only the viewer's items in the Me view.
function facts(snapshot) {
  const viewer = Board.view === 'me' ? snapshot.viewer || '' : null;
  const mine = (row) => viewer === null || [row.owner, row.developer_login, row.started_by_login].some((who) => same(who, viewer));
  const stories = snapshot.items.filter((row) => row.kind === 'story');
  const rows = snapshot.items.flatMap((row) => (row.kind === 'story' ? row.children : [row]));
  const known = new Set(rows.map((row) => row.id));
  const maps = (snapshot.dependency_maps || []).filter((map) => map.id !== 'fixes');
  // Parts no one has started are on the plan only; they wait in Planned beside the started ones.
  const planned = maps.filter((map) => map.stage !== 'done').flatMap((map) => map.parts)
    .filter((part) => !known.has(part.id) && STAGE_OF[part.status] === 'planned')
    .map((part) => ({ id: part.id, kind: 'task', title: part.title, owner: part.owner, stage: part.status }));
  const cards = [...rows, ...planned].filter(mine).filter((row) => kind === 'all' || row.kind === kind);
  const stages = Object.fromEntries(STAGES.map(([name]) => [name, []]));
  for (const row of cards) stages[STAGE_OF[row.stage] || 'planned'].push(row);
  stages.planned.sort((a, b) => (b.stage === 'Can start now') - (a.stage === 'Can start now'));
  stages.merged.sort((a, b) => (b.merged_at || '').localeCompare(a.merged_at || ''));
  const recent = stages.merged.filter((row) => Date.now() - Date.parse(row.merged_at) < WEEK);
  stages.merged = recent; // one set: the header, the titles and "and N more" all count the last 7 days
  const counted = snapshot.team.counts.finished_last_7_days;
  const timed = recent.filter((row) => row.total_seconds != null);
  const waited = timed.reduce((sum, row) => sum + (row.time_breakdown.waiting_for_owner || 0)
    + (row.time_breakdown.nothing_running || 0), 0);
  const total = timed.reduce((sum, row) => sum + row.total_seconds, 0);
  const ids = new Set([...stories.filter(mine), ...cards].map((row) => row.id));
  return {
    viewer, stages,
    asks: snapshot.team.needs_you.filter((ask) => viewer === null || ids.has(ask.id)),
    merged: viewer === null ? (kind === 'all' ? counted.parts + counted.fixes : counted[kind === 'task' ? 'parts' : 'fixes'])
      : recent.length,
    median: timed.length ? hours(median(timed.map((row) => row.total_seconds))) : 'unknown',
    waiting: total ? `${+(100 * waited / total).toFixed(1)}%` : 'unknown',
    red: cards.filter((row) => row.gates?.ci?.status === 'red' && STAGE_OF[row.stage] !== 'merged').length,
    stories: maps.filter((map) => !['done', 'needs a spec'].includes(map.stage))
      .map((map) => ({ ...map, owner: stories.find((row) => row.id === map.id)?.owner || map.owner }))
      .filter(mine),
    runs: (snapshot.lanes?.agents?.entries || []).filter((run) => run.repo_root === snapshot.repo_root),
  };
}

function open(item) {
  return () => Board.openDrawer(item.id);
}

function card(row, focus = `card:${row.id}`) {
  const note = row.stage === 'Can start now' ? 'can start' : row.stage === 'checks failed' ? 'checks failed' : null;
  return el('button', { type: 'button', class: 'chip', 'data-tone': STAGE_OF[row.stage] || 'planned',
    'data-stage': row.stage, 'data-focus': focus, onclick: open(row) },
  el('span', { class: 'chip-title' }, row.title),
  el('span', { class: 'chip-meta' }, el('span', { class: 'key' }, row.kind === 'fix' ? 'Fix' : key(row.id)),
    note && el('span', { class: 'now-tag', 'data-note': note }, note)));
}

function more(name, title, entries, shown) {
  if (entries.length <= shown) return null;
  return el('button', { type: 'button', class: 'now-more', 'data-focus': `more:${name}`, 'aria-haspopup': 'dialog',
    onclick: () => { list = { key: name, title, entries }; Board.screens.now(...last); } },
  `and ${entries.length - shown} more`);
}

function ask(entry) {
  const verb = VERB[entry.reason] || 'Decide';
  return el('button', { type: 'button', class: 'ask', 'data-focus': `ask:${entry.id}:${entry.reason}`, onclick: open(entry) },
    el('span', { class: 'ask-head' }, el('span', { class: 'verb' }, verb),
      el('span', { class: 'key' }, entry.kind === 'fix' ? 'Fix' : key(entry.id))),
    el('span', { class: 'ask-title' }, entry.title));
}

function strip(shown) {
  const count = shown.asks.length;
  return el('section', { class: 'needs', 'aria-label': 'Needs you' },
    el('p', { class: 'needs-count' }, shown.viewer ? el('span', { class: 'now-who' }, `@${shown.viewer.replace(/^@/, '')}`) : null,
      el('strong', {}, String(count)), ' ', count === 1 ? 'needs you' : 'need you'),
    shown.viewer === '' ? el('p', { class: 'note' }, 'Your GitHub login is unknown, so no item shows as yours.') : null,
    shown.asks.slice(0, ASKS).map(ask),
    more('asks', 'Needs you', shown.asks, ASKS));
}

function switcher() {
  return el('div', { role: 'group', 'aria-label': 'Show', class: 'kinds' }, KINDS.map(([name, words]) =>
    el('button', { type: 'button', 'aria-pressed': String(kind === name), 'data-focus': `kind:${name}`,
      onclick: () => { kind = name; Board.screens.now(...last); } }, words)));
}

function stage([name, title], shown) {
  const rows = shown.stages[name];
  const head = el('h2', {}, title, el('span', { class: 'count' }, String(name === 'merged' ? shown.merged : rows.length)));
  if (name === 'merged') {
    return el('section', { class: 'stage', 'aria-label': title }, head,
      rows.length ? el('ul', { class: 'done' }, rows.slice(0, MERGED).map((row) => el('li', {},
        el('button', { type: 'button', 'data-focus': `card:${row.id}`, onclick: open(row) }, row.title))))
        : el('p', { class: 'note' }, 'None.'),
      more(name, title, rows, MERGED));
  }
  return el('section', { class: 'stage', 'aria-label': title }, head,
    rows.length ? el('ul', { class: 'cards' }, rows.slice(0, CARDS).map((row) => el('li', {}, card(row))))
      : el('p', { class: 'note' }, 'None.'),
    more(name, title, rows, CARDS));
}

function story(map) {
  return el('li', {}, el('button', { type: 'button', class: 'story', 'data-focus': `story:${map.id}`, onclick: open(map) },
    el('span', { class: 'story-title' }, map.title),
    el('span', { class: 'parts', 'aria-hidden': 'true' }, map.parts.map((part) =>
      el('span', { 'data-status': part.status }))),
    el('span', { class: 'chip-meta' }, el('span', { class: 'key' }, map.id),
      el('span', { class: 'owner' }, map.owner ? `@${map.owner.replace(/^@/, '')}` : 'unknown'))));
}

function rail(shown) {
  if (shown.viewer !== null) {
    return el('section', { class: 'rail', 'aria-label': 'Live' }, el('h2', {}, 'Live'),
      shown.runs.length ? el('ul', { class: 'runs' }, shown.runs.map((run) => el('li', {},
        el('span', { class: 'story-title' }, run.title || 'unknown'),
        el('span', { class: 'chip-meta' }, RUN[run.kind] || 'Running'))))
        : el('p', { class: 'note' }, 'Nothing runs on this laptop now.'));
  }
  return el('section', { class: 'rail', 'aria-label': 'Stories' }, el('h2', {}, 'Stories'),
    shown.stories.length ? el('ul', { class: 'stories' }, shown.stories.slice(0, STORIES).map(story))
      : el('p', { class: 'note' }, 'No story is building. A story shows here once it is approved.'),
    more('stories', 'Stories', shown.stories, STORIES));
}

function figures(shown) {
  const figure = (value, words, tone) => el('p', { 'data-tone': tone }, el('strong', {}, String(value)), ' ', words);
  return el('section', { class: 'now-figures', 'aria-label': 'Figures' },
    figure(shown.merged, 'merged, 7 days'),
    figure(shown.median, 'median item'),
    figure(shown.waiting, 'waiting on people', 'needs-you'),
    figure(shown.red, 'red checks', shown.red ? 'stuck' : null));
}

function full(shown) {
  if (!list) return null;
  const close = () => { const back = `more:${list.key}`; list = null; Board.screens.now(...last); refocus(back); };
  const entries = list.key === 'asks' ? shown.asks : list.key === 'stories' ? shown.stories : shown.stages[list.key];
  const panel = el('section', { class: 'list', role: 'dialog', 'aria-modal': 'false', 'aria-labelledby': 'now-list-title' },
    el('header', {}, el('h2', { id: 'now-list-title', tabindex: '-1', 'data-focus': 'list' }, `${list.title}, all ${entries.length}`),
      el('button', { type: 'button', class: 'now-close', 'data-focus': 'list-close', onclick: close }, 'Close')),
    el('ul', {}, entries.map((entry) => el('li', {}, list.key === 'asks' ? ask(entry)
      : list.key === 'stories' ? story(entry).firstChild : card(entry, `list:${entry.id}`)))));
  panel.addEventListener('keydown', (event) => { if (event.key === 'Escape') close(); });
  return panel;
}

function refocus(name) {
  document.querySelector(`[data-focus="${CSS.escape(name)}"]`)?.focus();
}

let last = [];

function render(main, snapshot) {
  last = [main, snapshot];
  const focused = document.activeElement?.dataset?.focus;
  const opening = list && !document.querySelector('.now .list');
  const shown = facts(snapshot);
  const screen = el('div', { class: 'now' },
    strip(shown),
    el('div', { class: 'work' },
      el('section', { class: 'pipeline', 'aria-label': 'In flight' }, switcher(),
        el('div', { class: 'stages' }, STAGES.map((entry) => stage(entry, shown)))),
      full(shown) || rail(shown)),
    figures(shown));
  main.replaceChildren(screen);
  if (opening) refocus('list');
  else if (focused) refocus(focused);
}
