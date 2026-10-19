// The Assign control beside an owner in a story's or part's drawer and full page. It posts to the
// server's /assign, which runs Forge's assign command, and shows the reason Forge gives beside it.

const TOKEN = location.search;
const ASSIGNABLE = /^[A-Z][A-Z0-9-]*(\/[A-Z0-9-]+)?$/; // story keys and their parts; fixes have no owner to give
const UNREACHABLE = 'The board cannot reach its server. Start the board again from the terminal.';

let Board;
// Each item's control state survives the redraws a live refresh makes: { open, login, note, ok, busy }.
const states = new Map();
let last = null; // { id, part, node }: the control part that had focus last, to keep it across a redraw

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs)) {
    if (name === 'class') node.className = value;
    else if (name.startsWith('on')) node.addEventListener(name.slice(2), value);
    else if (value !== false) node.setAttribute(name, value === true ? '' : value);
  }
  node.append(...children.filter((child) => child !== null && child !== undefined));
  return node;
}

async function assign(key, login) {
  let answer;
  try {
    answer = await fetch(`assign${TOKEN}`, {
      method: 'POST', cache: 'no-store', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key, login }),
    });
  } catch {
    return { ok: false, message: UNREACHABLE };
  }
  let body = {};
  try {
    body = await answer.json();
  } catch {}
  if (!answer.ok) return { ok: false, message: body.error || 'The board could not give this item. Try again in a moment.' };
  return { ok: Boolean(body.ok), message: body.message || 'Forge gave no reason. The terminal that runs the board shows why.' };
}

// The people the board already knows, offered as suggestions; any GitHub username is accepted.
function logins() {
  const found = new Set([Board.snapshot?.viewer]);
  for (const parent of Board.snapshot?.items || []) {
    for (const row of [parent, ...(parent.children || [])]) {
      for (const who of [row.owner, row.developer_login, row.started_by_login]) found.add(who);
    }
  }
  return [...found].filter((who) => typeof who === 'string' && who).map((who) => who.replace(/^@/, '')).sort();
}

function control(id) {
  const state = states.get(id) || {};
  const name = `assign-${id.replace(/\W/g, '-')}`;
  const box = el('span', { class: 'assign', 'data-assign-for': id });
  const remember = (event) => {
    const part = event.target.dataset.part;
    if (part) last = { id, part, node: event.target };
  };
  const shut = (part) => {
    states.set(id, { ...states.get(id), open: false, note: null });
    redraw(box, id, part);
  };
  box.addEventListener('focusin', remember);
  // Leaving the control closes it; a redraw that removed it does not.
  box.addEventListener('focusout', () => setTimeout(() => {
    const now = states.get(id) || {};
    if (box.isConnected && !box.contains(document.activeElement) && !now.busy && (now.open || now.note)) shut();
  }));
  box.addEventListener('keydown', (event) => {
    const now = states.get(id) || {};
    if (event.key !== 'Escape' || !(now.open || now.note)) return;
    event.stopPropagation(); // the first Escape closes this control, not the drawer around it
    shut('open');
  });
  const open = el('button', {
    type: 'button', class: 'assign-open', 'data-part': 'open', 'aria-expanded': String(Boolean(state.open)),
    'aria-controls': `${name}-form`,
    onclick: () => {
      const now = states.get(id) || {};
      states.set(id, { ...now, open: !now.open, note: null });
      redraw(box, id, now.open ? 'open' : 'login');
    },
  }, 'Assign', el('span', { 'aria-hidden': 'true' }, ' ▾'));
  box.append(open);
  if (state.open) {
    const field = el('input', {
      id: `${name}-login`, name: 'login', 'data-part': 'login', type: 'text', required: true, autocomplete: 'off',
      spellcheck: 'false', autocapitalize: 'none', list: `${name}-people`, value: state.login || '',
      'aria-describedby': state.note ? `${name}-note` : false,
      oninput: (event) => states.set(id, { ...states.get(id), login: event.target.value }),
    });
    field.value = state.login || '';
    const form = el('form', { id: `${name}-form`, class: 'assign-layer', 'aria-busy': String(Boolean(state.busy)),
                              onsubmit: (event) => give(event, box, id) },
      el('label', { for: field.id }, 'GitHub username'),
      el('span', { class: 'assign-row' }, field,
        el('button', { type: 'submit', class: 'assign-give', 'data-part': 'give', 'aria-disabled': String(Boolean(state.busy)) },
          state.busy ? 'Giving…' : 'Give')),
      el('datalist', { id: `${name}-people` }, ...logins().map((who) => el('option', { value: who }))),
      state.note && !state.ok ? el('p', { id: `${name}-note`, role: 'alert', class: 'assign-note refused' }, state.note) : null);
    box.append(form);
  } else if (state.note) {
    box.append(el('p', { id: `${name}-note`, role: 'status', class: 'assign-layer assign-note' }, state.note));
  }
  return box;
}

async function give(event, box, id) {
  event.preventDefault();
  const state = states.get(id) || {};
  if (state.busy) return;
  const login = (state.login || '').trim();
  if (!login) {
    states.set(id, { ...state, note: 'Type the GitHub username of the person who gets this work.', ok: false });
    return redraw(box, id, 'login');
  }
  states.set(id, { ...state, busy: true, note: null });
  redraw(box, id, 'login');
  const result = await Board.api.assign(id, login);
  states.set(id, result.ok ? { open: false, login: '', note: result.message, ok: true }
    : { ...states.get(id), busy: false, note: result.message, ok: false });
  redraw(document.querySelector(`.assign[data-assign-for="${CSS.escape(id)}"]`) || box, id, result.ok ? 'open' : 'login');
}

// Draw the control again in place and put the keyboard on the named part.
function redraw(box, id, part) {
  if (!box.isConnected) return;
  const fresh = control(id);
  box.replaceWith(fresh);
  if (part) fresh.querySelector(`[data-part=${part}]`)?.focus();
}

// Add the control beside every new slot. A live refresh redraws the drawer and the page, so this
// runs after each redraw and puts the keyboard back where it was.
function mount() {
  for (const slot of document.querySelectorAll('[data-assign]:not([data-assign-ready])')) {
    slot.dataset.assignReady = '';
    const id = slot.dataset.assign;
    if (!ASSIGNABLE.test(id)) continue;
    const box = control(id);
    slot.after(box);
    const lost = last && last.id === id && !last.node.isConnected
      && (document.activeElement === document.body || document.activeElement === null);
    if (lost) box.querySelector(`[data-part=${last.part}]`)?.focus(), last = null;
  }
}

export function install(board) {
  Board = board;
  document.head.append(el('link', { rel: 'stylesheet', href: `assign.css${TOKEN}` }));
  Board.api.assign = assign;
  new MutationObserver(mount).observe(document.body, { childList: true, subtree: true });
  mount();
}
