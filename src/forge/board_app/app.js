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
const POLL = 10000; // ms between reads while the events stream is down
const listeners = [];
const main = document.querySelector('main');
const status = document.querySelector('[role=status]');

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
  api: {
    // ponytail: a stub until the assign part posts to the server
    async assign(key, login) {
      return { ok: false, message: 'Giving a story to a person from the board is not ready yet.' };
    },
  },
};

function mark(state, words) {
  status.dataset.state = state;
  status.textContent = words;
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
    answer = await fetch(`board.json${TOKEN}`, { cache: 'no-store' });
  } catch {
    return fail('The board cannot reach its server. Start the board again from the terminal.');
  }
  const text = await answer.text();
  if (!answer.ok) {
    let reason = text;
    try {
      reason = JSON.parse(text).error;
    } catch {}
    return fail(reason);
  }
  const snapshot = JSON.parse(text);
  if (Board.snapshot && snapshot.snapshot.version < Board.snapshot.snapshot.version) return; // a slower, older read
  Board.snapshot = snapshot;
  const updating = Boolean(snapshot.snapshot.updating);
  mark(updating ? 'updating' : 'live', updating ? 'Updating' : 'Live');
  document.querySelector('[data-repo]').textContent = snapshot.repo_root.split(/[\\/]/).pop();
  main.setAttribute('aria-busy', 'false');
  render();
  for (const fn of listeners) fn(snapshot);
}

function fail(reason) {
  mark('offline', 'Offline');
  main.setAttribute('aria-busy', 'false');
  if (!Board.snapshot) say('problem', reason); // a board already on screen stays; the mark says it is old
}

let polling = null;

function listen() {
  const events = new EventSource(`events${TOKEN}`);
  events.addEventListener('changed', refresh);
  events.addEventListener('open', () => {
    clearInterval(polling);
    polling = null;
    // The stream counts from the snapshot it sees when it connects, so read once more: a
    // rebuild that finished before it connected sends no "changed".
    refresh();
  });
  events.addEventListener('error', () => {
    if (polling) return;
    refresh();
    polling = setInterval(refresh, POLL);
  });
}

addEventListener('hashchange', render);
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
