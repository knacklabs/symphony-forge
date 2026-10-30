// The Releases page: what the next release carries and whether it is ready, past releases from the
// repo's tags, and the problems kept for later by file. It reads the untrimmed board, so finished
// work of any age is here. It also holds the helpers the Insights page shares.

const TOKEN = location.search;
const FINISHED = ['merged', 'done'];
const STORY = /^[A-Z][A-Z0-9-]*$/;
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const FILES = 10; // files in the known issues rail, then "and N more"
let everyFile = false; // the known issues rail shows every file
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

// Titles come from people and agents and can name a command; the board says what it means instead.
export function plain(text) {
  return String(text ?? '').replace(/`([^`]*)`/g, '$1').replace(/\bforge\s+([a-z][a-z-]*)/gi, "Forge's $1 step")
    .replace(/(^|\s)--[a-z][\w-]*/gi, '$1').replace(/\s+/g, ' ').trim();
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
          h('span', {}, h('b', {}, plain(story.title)), ' ', h('span', { class: 'key' }, story.id)),
          h('span', { class: 'parts', 'aria-hidden': 'true' }, story.children.map((part) => h('span', {
            'data-stage': FINISHED.includes(part.stage) ? 'merged' : part.stage === 'unstarted' ? 'waiting' : 'moving' }))),
          h('span', { class: 'note-end' }, story.stage === 'done' ? 'done' : 'held back'))),
        carried.filter((row) => row.kind === 'fix').slice(0, 5).map((row) => h('li', {},
          h('span', {}, plain(row.title)), h('span'), h('span', { class: 'note-end' }, 'fix'))),
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

// One file's row: Enter opens its kept problems and Escape closes them.
function file([name, titles], most) {
  return h('li', {}, h('details', {},
    h('summary', {}, h('span', { class: 'file' }, name,
      h('span', { class: 'meter', 'aria-hidden': 'true' }, h('span', { '--w': `${(titles.length / most) * 100}%` }))),
      h('span', { class: 'count' }, titles.length)),
    h('ul', { class: 'titles' }, titles.map((title) => h('li', {}, title)))));
}

// The rail shows the files with the most kept problems; "and N more" opens all of them in its place,
// as the Now screen does, and Escape or Close gives it back with focus on the button.
function known(view) {
  const body = [];
  let sorted = [];
  if (!Array.isArray(view.known_issues)) {
    body.push(h('p', {}, 'Known issues: unknown. The board could not read the kept review findings.'));
  } else if (!view.known_issues.length) {
    body.push(h('p', {}, 'No problems kept for later. Review findings kept below the bar show here by file.'));
  } else {
    const files = new Map();
    for (const issue of view.known_issues) {
      const name = issue.file || 'No file named';
      files.set(name, [...(files.get(name) || []), plain(issue.title) || 'A problem with no title']);
    }
    sorted = [...files].sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0]));
  }
  const most = sorted[0]?.[1].length;
  let section;
  const swap = (all, focus) => {
    everyFile = all;
    const next = known(view);
    section.replaceWith(next);
    next.querySelector(focus).focus();
  };
  if (everyFile && sorted.length > FILES) {
    section = h('section', { class: 'panel known list', role: 'dialog', 'aria-modal': 'false', 'aria-labelledby': 'known-issues' },
      h('header', {}, h('h2', { id: 'known-issues', tabindex: '-1' }, `Known issues by file, all ${sorted.length}`),
        h('button', { type: 'button', class: 'close' }, 'Close')),
      h('ul', {}, sorted.map((entry) => file(entry, most))));
    section.querySelector('.close').addEventListener('click', () => swap(false, '.more'));
  } else {
    if (sorted.length) body.push(h('ul', {}, sorted.slice(0, FILES).map((entry) => file(entry, most))));
    if (sorted.length > FILES) {
      const more = h('button', { type: 'button', class: 'more', 'aria-haspopup': 'dialog' }, `and ${sorted.length - FILES} more`);
      more.addEventListener('click', () => swap(true, 'h2'));
      body.push(more);
    }
    section = region('known-issues', 'known', 'Known issues by file', ...body);
  }
  section.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    const open = event.target.closest('details[open]');
    if (open) {
      open.open = false;
      open.querySelector('summary').focus();
    } else if (section.matches('.list')) swap(false, '.more');
  });
  return section;
}

export function install(Board) {
  Board.screens.releases = (main) => load(Board, 'releases', main, (view) =>
    h('div', { class: 'releases' }, h('h1', { class: 'hidden' }, 'Releases'), h('div', {}, upcoming(view), past(view)), known(view)));
}
