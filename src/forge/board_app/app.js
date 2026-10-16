// The board's shell: it loads the Now snapshot, keeps it fresh, and owns the pinned Board
// interfaces that the screens (now.js, item.js, releases.js, insights.js, assign.js) build on.
'use strict';
(function () {
  const token = new URLSearchParams(location.search).get('token') || '';
  const listeners = [];
  const PAGES = ['now', 'releases', 'insights', 'item'];
  const POLL_MS = 10000;
  let snapshot = null;
  let poller = null;
  let opener = null; // the control that opened the drawer, to return focus to on close

  const $ = (id) => document.getElementById(id);
  const address = (path, params) => {
    const query = new URLSearchParams(Object.assign({}, params, { token }));
    return `${path}?${query}`;
  };
  const say = (element, text, kind) => {
    element.textContent = text;
    element.dataset.kind = kind || '';
  };
  const findItem = (id) => {
    for (const parent of (snapshot && snapshot.items) || []) {
      for (const row of [parent, ...(parent.children || [])]) if (row.id === id) return row;
    }
    return null;
  };

  async function load() {
    try {
      const answer = await fetch(address('board.json'), { cache: 'no-store' });
      const body = await answer.json();
      if (!answer.ok) throw new Error(body.error || 'The board could not load.');
      snapshot = body;
      $('repo-name').textContent = (body.repo_root || '').split(/[\\/]/).pop();
      const empty = !(body.items || []).length;
      say($('now-state'), empty ? 'Nothing is in flight yet. Stories and fixes show here once they start.'
        : (body.team && body.team.sentence) || '', '');
      listeners.forEach((fn) => fn(body));
    } catch (error) {
      say($('now-state'), snapshot ? 'The board could not refresh. It shows the last work it read and tries again.'
        : 'The board could not load. Check that the board still runs in your terminal, then reload this page.', 'error');
    }
  }

  function live(state) {
    const badge = $('live');
    badge.dataset.state = state;
    badge.textContent = state === 'live' ? 'Live' : 'Reconnecting';
  }

  // Server-sent events say when a new snapshot exists; polling every 10 seconds covers a drop.
  function listen() {
    const stream = new EventSource(address('events'));
    stream.addEventListener('changed', load);
    stream.onopen = () => {
      live('live');
      clearInterval(poller);
      poller = null;
    };
    stream.onerror = () => {
      live('polling');
      if (!poller) poller = setInterval(load, POLL_MS);
    };
  }

  function navigate(page) {
    const name = PAGES.includes(page) ? page : 'now';
    document.querySelectorAll('main > section').forEach((section) => {
      section.hidden = section.dataset.page !== name;
    });
    document.querySelectorAll('.bar nav a').forEach((link) => {
      if (link.dataset.page === name) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
    if (name !== 'item' && location.hash !== `#${name}`) history.replaceState(null, '', `#${name}`);
    Board.page = name;
  }

  function openDrawer(itemId) {
    const row = findItem(itemId);
    const drawer = $('drawer');
    opener = document.activeElement;
    drawer.dataset.item = itemId;
    $('drawer-title').textContent = row ? row.title : 'unknown';
    say($('drawer-state'), row ? row.status || 'unknown' : 'This item is no longer on the board.', '');
    drawer.hidden = false;
    $('drawer-close').focus();
  }

  function closeDrawer() {
    const drawer = $('drawer');
    if (drawer.hidden) return;
    drawer.hidden = true;
    delete drawer.dataset.item;
    if (opener && opener.isConnected) opener.focus();
  }

  const Board = {
    page: 'now',
    view: 'team',
    // fn(snapshot) runs now when a snapshot is loaded, and again on each new one.
    onSnapshot(fn) {
      listeners.push(fn);
      if (snapshot) fn(snapshot);
    },
    snapshot: () => snapshot,
    item: findItem,
    address,
    // Highlights an item and shows its detail beside the cards.
    select(itemId) {
      Board.selected = itemId;
      openDrawer(itemId);
    },
    openDrawer,
    closeDrawer,
    // The item's full page; item.js fills it.
    openItem(itemId) {
      const row = findItem(itemId);
      closeDrawer();
      navigate('item');
      history.replaceState(null, '', `#item=${encodeURIComponent(itemId)}`);
      $('item-title').textContent = row ? row.title : 'unknown';
      say($('item-state'), row ? row.status || 'unknown' : 'This item is no longer on the board.', '');
    },
    navigate,
    api: {
      // Gives a story to a developer; assign.js replaces this with the call to /assign.
      async assign(key, login) {
        return { ok: false, message: 'Giving a story to a developer is not ready yet.' };
      },
    },
  };
  window.Board = Board;

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.bar nav a').forEach((link) => link.addEventListener('click', (event) => {
      event.preventDefault();
      navigate(link.dataset.page);
    }));
    document.querySelectorAll('.bar .views button').forEach((button) => button.addEventListener('click', () => {
      Board.view = button.dataset.view;
      document.querySelectorAll('.bar .views button').forEach((other) => {
        other.setAttribute('aria-pressed', String(other === button));
      });
      if (snapshot) listeners.forEach((fn) => fn(snapshot));
    }));
    $('drawer-close').addEventListener('click', closeDrawer);
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') closeDrawer();
    });
    const start = location.hash.slice(1);
    navigate(start.startsWith('item=') ? 'item' : start);
    load().then(() => {
      if (start.startsWith('item=')) Board.openItem(decodeURIComponent(start.slice(5)));
    });
    listen();
  });
})();
