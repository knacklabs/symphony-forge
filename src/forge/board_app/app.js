// The board's page shell: it reads the server's snapshot, keeps it fresh, runs the header, and holds
// the pinned Board interfaces that the screen modules fill in.

const TOKEN = location.search; // every request carries this run's token
const PAGES = ['now', 'releases', 'insights'];
// Each screen part adds its module here; a module exports install(Board). The import carries the
// token, because the server checks it on every file.
const SCREENS = [
  'now',
  'item',
  'releases', 'insights',
  'assign',
];
const POLL = 10000; // ms before a page read that failed is asked again
const listeners = [];
const main = document.querySelector('main');
const status = document.querySelector('[role=status]');
// One quiet line under the header says why the page may be old; it is empty, and so hidden, when data is fresh.
const stale = document.createElement('p');
stale.className = 'stale';
stale.setAttribute('aria-live', 'polite');
const header = document.querySelector('header');
header.after(stale);
// The header is 48 pixels tall until it wraps on a narrow window, and the line adds its own height. The item drawer
// (fixed at 48px in item.css) and the Releases and Insights pages (the window less 96px) read the excess here.
const sizes = new ResizeObserver(() => document.documentElement.style.setProperty(
  '--below-bar', `${Math.max(0, header.offsetHeight + stale.offsetHeight - 48)}px`));
sizes.observe(header);
sizes.observe(stale);
const OFFLINE = {
  state: 'offline',
  word: 'Offline',
  line: 'The board has stopped, so this page may be old. Start the board again from the terminal, then open its new link.',
};
const failed = new Map(); // read name -> its mark, line and number; the newest failed read is the one shown
let count = 0; // failures so far: a read that began before a failure cannot clear it
let retry = null;

// A refresh draws a screen again and changes the page only where the drawing differs, so the reader keeps
// scroll, selection, focus and open sections everywhere else. Each drawn node has a copy of itself as built,
// because the live node also holds what the reader and other scripts did to it: an open section, a control
// another script added, and the focus. Only what was built is compared.
// A click handler is not compared: whatever one uses must show in the drawing, such as a link's address.
// ponytail: children are matched by position, so a block put in the middle replaces the blocks after it.
const built = new WeakMap(); // node -> a copy of it without its children, as built, and without `open`

function copyOf(node) {
  const copy = node.cloneNode(false);
  copy.removeAttribute?.('open'); // the reader opens and closes sections; a drawing does not decide it
  return copy;
}

// Records a drawing so a later one can be compared with it.
function keep(node) {
  built.set(node, copyOf(node));
  node.childNodes.forEach(keep);
  return node;
}

function patch(live, fresh) {
  if (!built.get(live)?.isEqualNode(copyOf(fresh))) {
    live.replaceWith(keep(fresh));
    return fresh;
  }
  const kids = [...live.childNodes].filter((node) => built.has(node)); // not the nodes other scripts added
  const next = [...fresh.childNodes];
  next.forEach((child, at) => (kids[at] ? patch(kids[at], child) : live.append(keep(child))));
  kids.slice(next.length).forEach((node) => node.remove());
  return live;
}

export const Board = {
  page: 'now',
  view: 'team', // 'team' or 'me'
  snapshot: null,
  screens: {}, // page -> render(main, snapshot), set by the screen modules
  onSnapshot(fn) {
    listeners.push(fn);
    if (Board.snapshot) fn(Board.snapshot);
  },
  // Puts a screen on the page. The screen already on it changes only where the new one differs.
  show(screen) {
    const live = main.firstChild;
    if (built.has(live)) patch(live, screen);
    else main.replaceChildren(keep(screen));
  },
  patch,
  keep,
  // ponytail: stubs until the drawer and item page part replaces them
  select(itemId) {},
  openDrawer(itemId) {},
  openItem(itemId) {},
  navigate(page) {
    location.hash = page;
  },
  // Every page's read of the server goes through here, so a failed one shows the line under the header.
  async read(name, url) {
    const began = count;
    const answer = await read(name, url);
    if (answer.status < 500) fresh(name, began);
    return answer;
  },
  api: {
    // ponytail: a stub until the assign part posts to the server
    async assign(key, login) {
      return { ok: false, message: 'Giving a story to a person from the board is not ready yet.' };
    },
  },
};

// The same words are not written again: a screen reader says a live region's words each time they are written.
function mark(state, words) {
  status.dataset.state = state;
  if (status.textContent !== words) status.textContent = words;
}

function show() {
  const [newest] = [...failed.values()].reverse();
  if (newest) {
    mark(newest.state, newest.word);
    if (stale.textContent !== newest.line) stale.textContent = newest.line;
  } else if (Board.snapshot) {
    const updating = Boolean(Board.snapshot.snapshot.updating);
    mark(updating ? 'updating' : 'live', updating ? 'Updating' : 'Live');
    stale.textContent = '';
  }
}

function lose(name, why) {
  failed.delete(name); // set again, so the newest failure is last
  failed.set(name, { ...why, number: ++count });
  show();
  // A failed rebuild is told by the events stream. A page read has no such signal, so it is asked again here.
  if (name !== 'now') {
    clearTimeout(retry);
    retry = setTimeout(askAgain, POLL);
  }
}

function askAgain() {
  if (![...failed.keys()].some((name) => name !== 'now')) return; // it worked, or the person left that page
  if (Board.page === 'now') for (const fn of listeners) fn(Board.snapshot); // the item page and drawer read again
  else render(); // the Releases or Insights page reads again, and changes only when the read works
}

function unread(reason) {
  return {
    state: 'stale',
    word: 'Not updating',
    line: `The server could not read the work, so this page may be old. It said: \u201c${reason}\u201d The page tries again.`,
  };
}

// Clears a failure. `began` is the failure count when the read began: a read that began before the failure
// says nothing about it. With no `began`, the server itself said the failure is over.
function fresh(name, began = Infinity) {
  if ((failed.get(name)?.number ?? 0) <= began) failed.delete(name);
  show();
}

// Asks the server; a read it could not do or could not answer is remembered under `name` until that read works.
async function read(name, url) {
  let answer;
  try {
    answer = await fetch(url, { cache: 'no-store' });
  } catch (error) {
    lose(name, OFFLINE);
    throw error;
  }
  if (answer.status >= 500) {
    let reason = await answer.clone().text();
    try {
      reason = JSON.parse(reason).error;
    } catch {}
    lose(name, unread(reason));
  }
  return answer;
}

function say(className, words) {
  const line = document.createElement('p');
  line.className = className;
  line.textContent = words;
  main.replaceChildren(line);
}

function render() {
  const asked = location.hash.slice(1);
  Board.page = PAGES.includes(asked) ? asked : 'now';
  for (const link of document.querySelectorAll('.pages a')) {
    if (link.hash === `#${Board.page}`) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  }
  for (const button of document.querySelectorAll('[data-view]')) {
    button.setAttribute('aria-pressed', String(button.dataset.view === Board.view));
  }
  const snapshot = Board.snapshot;
  if (!snapshot) return;
  const screen = Board.screens[Board.page];
  if (screen) screen(main, snapshot);
  else if (Board.page !== 'now') say('note', 'This page is not on the board yet.');
  else if (!snapshot.items.length) say('note', 'Nothing is in flight. A story or a fix shows here once it starts.');
  else say('note', `${snapshot.items.length} stories and fixes are on the board.`);
}

async function refresh() {
  const began = count;
  let answer;
  try {
    answer = await read('now', `board.json${TOKEN}`);
  } catch {
    return fail();
  }
  if (!answer.ok) return fail();
  const snapshot = JSON.parse(await answer.text());
  if (Board.snapshot && snapshot.snapshot.version < Board.snapshot.snapshot.version) return; // a slower, older read
  Board.snapshot = snapshot;
  // An answer marked updating is old data while a rebuild runs, so it never clears a failure. A final answer
  // clears one only if its read began after the failure; the stream's "recovered" clears it too.
  if (snapshot.snapshot.updating) show();
  else fresh('now', began);
  document.querySelector('[data-repo]').textContent = snapshot.repo_root.split(/[\\/]/).pop();
  main.setAttribute('aria-busy', 'false');
  render();
  for (const fn of listeners) fn(snapshot);
}

// The events stream is down or has just opened: ask the small status answer, and read the whole board
// only when it says there is a new snapshot.
async function probe() {
  const began = count;
  let answer;
  try {
    answer = await read('now', `board.json${TOKEN}&page=status`);
  } catch {
    return fail();
  }
  if (!answer.ok) return fail();
  const { version, reason } = await answer.json();
  if (reason) lose('now', unread(reason));
  else if (!Board.snapshot || version !== Board.snapshot.snapshot.version) await refresh();
  else fresh('now', began);
}

function fail() {
  main.setAttribute('aria-busy', 'false');
  if (!Board.snapshot) say('note', 'There is no board to show yet.'); // a board already on screen stays
}

function listen() {
  const events = new EventSource(`events${TOKEN}`);
  events.addEventListener('changed', refresh);
  // A rebuild that fails makes no new snapshot, so the stream says it failed, and says when the next one works.
  events.addEventListener('failed', (event) => lose('now', unread(event.data)));
  events.addEventListener('recovered', () => fresh('now'));
  // The stream counts from the snapshot it sees when it connects, so a rebuild that finished before it
  // connected sends no "changed". The browser reconnects a broken stream every few seconds, and each try asks.
  events.addEventListener('open', probe);
  events.addEventListener('error', probe);
}

addEventListener('hashchange', () => {
  for (const name of failed.keys()) if (name !== 'now') failed.delete(name); // the page it came from is gone
  show();
  render();
});
for (const button of document.querySelectorAll('[data-view]')) {
  button.addEventListener('click', () => {
    Board.view = button.dataset.view;
    render();
  });
}
for (const name of SCREENS) (await import(`./${name}.js${TOKEN}`)).install(Board);
render();
await refresh(); // the snapshot first, so the page shows the board before anything else asks
listen();
