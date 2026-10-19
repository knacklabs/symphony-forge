// The Insights page: merged work per week, each person's merges through Forge stacked in alphabetical
// order with the team's merges around Forge on top, and a row per person with open items, stories
// owned and their share of the team's merged work. People are never ranked: rows stay alphabetical.

const { h, day, load, rows } = await import(`./releases.js${location.search}`);
const FINISHED = ['merged', 'done'];
const COLOURS = 6; // --person-1 to --person-6 in pages.css, reused in turn

const login = (value) => (value || '').replace(/^@/, '').toLowerCase();
const merged = (week) => (week ? week.through + week.around : 0);

function weekly(trends) {
  const body = [];
  if (!trends) {
    body.push(h('p', {}, 'Merged work per week: unknown. The board could not read the merged pull requests.'));
  } else if (!trends.team.some((week) => merged(week))) {
    body.push(h('p', {}, 'Nothing merged in the last six weeks. Merged work shows here by week and by person.'));
  } else {
    const colour = (n) => `var(--person-${(n % COLOURS) + 1})`;
    const most = Math.max(...trends.team.map(merged));
    body.push(h('ul', { class: 'legend', 'aria-label': 'People' },
      trends.people.map((person, n) => h('li', { '--swatch': colour(n) }, person.name)),
      h('li', { class: 'around' }, 'around Forge')));
    body.push(h('div', { class: 'chart' },
      h('div', { class: 'bars', '--count': trends.weeks.length }, trends.weeks.map((start, w) => {
        const team = trends.team[w];
        if (!team) {
          return h('div', { role: 'img', 'aria-label': `Week of ${day(start)}: unknown` }, h('span', { class: 'total' }, 'unknown'));
        }
        const parts = trends.people.map((person) => `${person.name} ${person.weeks[w]?.through ?? 'unknown'}`);
        return h('div', { role: 'img', 'aria-label': `Week of ${day(start)}: ${merged(team)} merged (${parts.join(', ')}, around Forge ${team.around})` },
          h('span', { class: 'total', 'aria-hidden': 'true' }, merged(team)),
          h('div', { class: 'stack', 'aria-hidden': 'true', '--h': `${(merged(team) / most) * 100}%` },
            trends.people.map((person, n) => h('span', { '--n': person.weeks[w]?.through || 0, '--swatch': colour(n) })),
            h('span', { class: 'around', '--n': team.around })));
      })),
      h('div', { class: 'weeks', 'aria-hidden': 'true', '--count': trends.weeks.length }, trends.weeks.map((start) => h('span', {}, day(start))))));
  }
  return h('section', { class: 'panel fill', 'aria-labelledby': 'merged-per-week' }, h('h2', { id: 'merged-per-week' }, 'Merged per week'), ...body);
}

function people(view) {
  const all = rows(view);
  const trends = view.team.trends;
  const found = new Map((trends?.people || []).map((person) => [login(person.login || person.name), { ...person }]));
  for (const row of all) {
    const who = login(row.owner || row.developer_login);
    if (who && !found.has(who)) found.set(who, { name: row.owner || row.developer_login, login: who });
  }
  const team = (trends?.team || []).reduce((sum, week) => sum + merged(week), 0);
  const listed = [...found].sort((a, b) => a[1].name.localeCompare(b[1].name, undefined, { sensitivity: 'base' }) || a[0].localeCompare(b[0]));
  if (!listed.length) {
    return h('section', { class: 'panel', 'aria-labelledby': 'people' }, h('h2', { id: 'people' }, 'People'),
      h('p', {}, 'No one has merged or owns work yet. Each person who does shows here with their share of the team\'s work.'));
  }
  const mine = (who, row) => login(row.owner || row.developer_login) === who;
  return h('section', { class: 'panel people', 'aria-labelledby': 'people' }, h('h2', { id: 'people' }, 'People'),
    h('table', {},
      h('thead', {}, h('tr', {}, h('th', { scope: 'col' }, 'Person · alphabetical'), h('th', { scope: 'col', class: 'num' }, 'Open now'),
        h('th', { scope: 'col', class: 'num' }, 'Stories owned'), h('th', { scope: 'col' }, 'Share of the team\'s merged work, last six weeks'))),
      h('tbody', {}, listed.map(([who, person]) => {
        const theirs = (person.weeks || []).reduce((sum, week) => sum + merged(week), 0);
        const share = trends && team ? Math.round((theirs / team) * 100) : null;
        return h('tr', {},
          h('th', { scope: 'row', class: 'who' }, person.name, ' ', h('small', {}, `@${person.login || who}`)),
          h('td', { class: 'num' }, all.filter((row) => row.kind !== 'story' && !FINISHED.includes(row.stage) && mine(who, row)).length),
          h('td', { class: 'num' }, all.filter((row) => row.kind === 'story' && row.stage !== 'done' && mine(who, row)).length),
          h('td', {}, h('span', { class: 'share' },
            h('span', { class: 'meter', 'aria-hidden': 'true' }, h('span', { '--w': `${share ?? 0}%` })),
            h('b', {}, share === null ? 'unknown' : `${share}%`))));
      }))));
}

export function install(Board) {
  Board.screens.insights = (main) => load(Board, 'insights', main, (view) =>
    h('div', { class: 'insights' }, h('h1', { class: 'hidden' }, 'Insights'), weekly(view.team.trends), people(view)));
}
