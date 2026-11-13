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
const POLL = 10000; // ms between reads: the events stream says nothing when a rebuild fails, so the page also asks
const listeners = [];
const main = document.querySelector('main');
const status = document.querySelector('[role=status]');
// One quiet line under the header says why the page may be old; it is empty, and so hidden, when data is fresh.
const stale = document.createElement('p');
stale.className = 'stale';
stale.setAttribute('aria-live', 'polite');
document.querySelector('header').after(stale);
// What sits fixed or sized to the window below the header (the drawer, the Releases page) reads the line's height here.
new ResizeObserver(() => document.documentElement.style.setProperty('--stale-h', `${stale.offsetHeight}px`)).observe(stale);
const OFFLINE = {
  state: 'offline',
  word: 'Offline',
  line: 'The board has stopped, so this page may be old. Start the board again from the terminal, then open its new link.',
};
const failed = new Map(); // read name -> its mark and line; the newest failed read is the one shown

export const Board = {
  page: 'now',
  view: 'team', // 'team' or 'me'
  snapshot: null,
  screens: {}, // page -> render(main, snapshot), set by the screen modules
  onSnapshot(fn) {
    listeners.push(fn);
    if (Board.snapshot) fn(Board.snapshot);
  },
  // ponytail: stubs until the drawer and item page part replaces them
  select(itemId) {},
  openDrawer(itemId) {},
  openItem(itemId) {},
  navigate(page) {
    location.hash = page;
  },
  // Every page's read of the server goes through here, so a failed one shows the line under the header.
  async read(name, url) {
    const answer = await read(name, url);
    if (answer.status < 500) fresh(name);
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
  failed.set(name, why);
  show();
}

function fresh(name) {
  failed.delete(name);
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
    lose(name, {
      state: 'stale',
      word: 'Not updating',
      line: `The server could not read the work, so this page may be old. It said: \u201c${reason}\u201d The page tries again.`,
    });
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
  let answer;
  try {
    answer = await read('now', `board.json${TOKEN}`);
  } catch {
    return fail();
  }
  if (!answer.ok) return fail();
  const snapshot = JSON.parse(await answer.text());
  const held = Board.snapshot?.snapshot;
  const { version, updating } = snapshot.snapshot;
  if (held && version < held.version) return; // a slower, older read
  // While a rebuild runs, the server answers with the old snapshot marked as updating: that is no new data.
  if (updating && held && version === held.version && failed.has('now')) return;
  const unchanged = held && version === held.version && Boolean(updating) === Boolean(held.updating);
  Board.snapshot = snapshot;
  fresh('now');
  document.querySelector('[data-repo]').textContent = snapshot.repo_root.split(/[\\/]/).pop();
  main.setAttribute('aria-busy', 'false');
  if (unchanged && !failed.size) return; // nothing new: the screen stays as it is, with its focus and scroll
  render(); // a page read that failed is tried again here, as every page reads when it is drawn
  for (const fn of listeners) fn(snapshot);
}

function fail() {
  main.setAttribute('aria-busy', 'false');
  if (!Board.snapshot) say('note', 'There is no board to show yet.'); // a board already on screen stays
}

function listen() {
  const events = new EventSource(`events${TOKEN}`);
  events.addEventListener('changed', refresh);
  // The stream counts from the snapshot it sees when it connects, so read once more: a rebuild that
  // finished before it connected sends no "changed". A broken stream is asked about at once too.
  events.addEventListener('open', refresh);
  events.addEventListener('error', refresh);
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
setInterval(refresh, POLL);
