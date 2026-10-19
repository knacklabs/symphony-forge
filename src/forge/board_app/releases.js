// The Releases page: what the next release carries and whether it is ready, past releases from the
// repo's tags, and the problems kept for later by file. It reads the untrimmed board, so finished
// work of any age is here. It also holds the helpers the Insights page shares.

const TOKEN = location.search;
const FINISHED = ['merged', 'done'];
const STORY = /^[A-Z][A-Z0-9-]*$/;
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
let asked = 0; // the newest page read; an older answer that comes later is dropped

export function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs)) {
    if (name.startsWith('--')) node.style.setProperty(name, value); // the page's policy blocks style attributes
    else node.setAttribute(name, value);
  }
  node.append(...children.flat(2).filter((child) => child != null && child !== false));
  return node;
}

export function day(iso) {
  if (!iso) return 'unknown';
  const at = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  return `${at.getUTCDate()} ${MONTHS[at.getUTCMonth()]}`;
}

export function rows(view) {
  return view.items.flatMap((item) => [item, ...item.children]);
}

// Reads the untrimmed board for `page` and draws it into main. The first read shows a loading line;
// later reads keep the page on screen until the new answer arrives.
export async function load(Board, page, main, draw) {
  if (!document.querySelector('link[data-pages]')) {
    document.head.append(h('link', { rel: 'stylesheet', href: `pages.css${TOKEN}`, 'data-pages': '' }));
  }
  const shown = main.firstElementChild?.dataset.page === page;
  if (!shown) {
    main.replaceChildren(h('p', { class: 'note' }, 'Reading the work…'));
    main.setAttribute('aria-busy', 'true');
  }
  const mine = ++asked;
  let view;
  try {
    const answer = await fetch(`board.json${TOKEN}&page=${page}`, { cache: 'no-store' });
    const text = await answer.text();
    if (!answer.ok) {
      let reason = 'The board could not read the work. The terminal that runs it shows why.';
      try {
        reason = JSON.parse(text).error || reason;
      } catch {}
      throw new Error(reason);
    }
    view = JSON.parse(text);
  } catch (error) {
    if (mine !== asked || Board.page !== page) return;
    main.setAttribute('aria-busy', 'false');
    const reason = error instanceof TypeError
      ? 'The board cannot reach its server. Start the board again from the terminal.' : error.message;
    if (!shown) main.replaceChildren(h('p', { class: 'problem' }, reason));
    return;
  }
  if (mine !== asked || Board.page !== page) return;
  const drawn = draw(view);
  drawn.dataset.page = page;
  main.replaceChildren(drawn);
  main.setAttribute('aria-busy', 'false');
}

function region(id, className, title, ...body) {
  return h('section', { class: `panel ${className}`, 'aria-labelledby': id }, h('h2', { id }, title), ...body);
}

function upcoming(view) {
  const all = rows(view);
  if (!Array.isArray(view.releases)) {
    return region('next-release', '', 'Next release',
      h('p', {}, 'Next release: unknown. The board has no record of this repo\'s releases yet.'));
  }
  const last = view.releases.at(-1);
  const carried = all.filter((row) => row.kind !== 'story' && FINISHED.includes(row.stage) && !row.released_in);
  const keys = new Set(carried.filter((row) => row.kind === 'task').map((row) => row.id.split('/')[0]));
  const stories = all.filter((row) => row.kind === 'story' && keys.has(row.id));
  const held = stories.filter((row) => row.stage !== 'done');
  const findings = carried.filter((row) => row.gates?.review?.status === 'blocked');
  const fixes = carried.filter((row) => row.kind === 'fix').length;
  const since = last ? `since ${last.tag} · ${day(last.date)}` : 'since the start: no releases tagged yet';
  const check = (name, ok, why) => h('li', ok ? { title: why } : { title: why, 'data-held': '' }, name);
  return h('section', { class: 'panel', 'aria-labelledby': 'next-release' }, h('div', { class: 'head' },
      h('h2', { id: 'next-release' }, 'Next release'),
      h('span', { class: 'big' }, carried.length), h('span', { class: 'sub' }, `changes ${since}`),
      held.length ? h('span', { class: 'tag' }, `${held.length} ${held.length === 1 ? 'story' : 'stories'} not finished`) : null),
    carried.length ? [
      h('ul', { class: 'checks', 'aria-label': 'Ready to release' },
        check(held.length ? 'Stories not finished' : 'Stories finished', !held.length,
          held.length ? `${held.length} of ${stories.length} stories still have parts to merge` : 'Every story in it is finished'),
        check(findings.length ? 'Open findings' : 'No open findings', !findings.length,
          findings.length ? `${findings.length} merged changes have open findings` : 'No merged change has an open finding')),
      h('ul', { class: 'stories' },
        stories.map((story) => h('li', {},
          h('span', {}, h('b', {}, story.title), ' ', h('span', { class: 'key' }, story.id)),
          h('span', { class: 'parts', 'aria-hidden': 'true' }, story.children.map((part) => h('span', {
            'data-stage': FINISHED.includes(part.stage) ? 'merged' : part.stage === 'unstarted' ? 'waiting' : 'moving' }))),
          h('span', { class: 'note-end' }, story.stage === 'done' ? 'done' : 'held back'))),
        carried.filter((row) => row.kind === 'fix').slice(0, 5).map((row) => h('li', {},
          h('span', {}, row.title), h('span'), h('span', { class: 'note-end' }, 'fix'))),
        h('li', { class: 'total' }, h('span', {}, 'Fixes'), h('span'), h('b', { class: 'num' }, fixes))),
    ] : h('p', {}, 'Nothing has merged since the last release. Finished stories and fixes show here until a release carries them.'));
}

function past(view) {
  if (!Array.isArray(view.releases)) {
    return region('past-releases', 'fill', 'Past releases', h('p', {}, 'Past releases: unknown.'));
  }
  if (!view.releases.length) {
    return region('past-releases', 'fill', 'Past releases',
      h('p', {}, 'No releases tagged yet. A version tag on the default branch shows here as a release.'));
  }
  const count = (ids, kind) => ids.filter((id) => kind === 'story' ? STORY.test(id) : !id.includes('/') && !STORY.test(id)).length;
  return region('past-releases', 'fill', 'Past releases', h('table', {},
    h('thead', {}, h('tr', {}, h('th', { scope: 'col' }, 'Release'), h('th', { scope: 'col' }, 'Date'),
      h('th', { scope: 'col', class: 'num' }, 'Stories'), h('th', { scope: 'col', class: 'num' }, 'Fixes'))),
    h('tbody', {}, [...view.releases].reverse().map((release) => h('tr', {},
      h('th', { scope: 'row' }, release.tag), h('td', {}, day(release.date)),
      h('td', { class: 'num' }, count(release.items, 'story')), h('td', { class: 'num' }, count(release.items, 'fix')))))));
}

function known(view) {
  const body = [];
  if (!Array.isArray(view.known_issues)) {
    body.push(h('p', {}, 'Known issues: unknown. The board could not read the kept review findings.'));
  } else if (!view.known_issues.length) {
    body.push(h('p', {}, 'No problems kept for later. Review findings kept below the bar show here by file.'));
  } else {
    const files = new Map();
    for (const issue of view.known_issues) {
      const file = issue.file || 'No file named';
      files.set(file, [...(files.get(file) || []), issue.title]);
    }
    const sorted = [...files].sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0]));
    const most = sorted[0][1].length;
    body.push(h('ul', {}, sorted.map(([file, titles]) => h('li', { title: titles.join('\n') },
      h('span', { class: 'file' }, file,
        h('span', { class: 'meter', 'aria-hidden': 'true' }, h('span', { '--w': `${(titles.length / most) * 100}%` }))),
      h('span', { class: 'count' }, titles.length)))));
  }
  return region('known-issues', 'known', 'Known issues by file', ...body);
}

export function install(Board) {
  Board.screens.releases = (main) => load(Board, 'releases', main, (view) =>
    h('div', { class: 'releases' }, h('h1', { class: 'hidden' }, 'Releases'), h('div', {}, upcoming(view), past(view)), known(view)));
}
