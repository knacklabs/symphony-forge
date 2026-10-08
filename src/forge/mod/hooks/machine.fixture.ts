const at = '1970-01-01T00:00:00Z'
export const entry = (id: string, item: string, kind: string, repo_root = '/repo', started_at: string | null = at) => ({
  id, item, kind, title: 'Recorded run title', repo_root, checkout_root: repo_root, repo_name: repo_root === '/repo' ? 'shop' : 'other-shop',
  model: kind === 'test' ? null : 'model-' + id, effort: kind === 'test' ? null : 'high',
  joined_at: at, started_at, output_path: '/logs/' + id + '.txt', progress: null as { done: number | null; total: number | null } | null,
  place: started_at ? 0 : 1, elapsed: 0,
})
export const fixture = () => ({ version: '1.2.6',
  agents: { size: 3, entries: [entry('worker', 'guide', 'work'), entry('reviewer', 'checkout', 'review'), entry('reader', 'SHOP', 'read'), entry('waiting', 'guide', 'work', '/other', null)] },
  tests: { size: 1, entries: [{ ...entry('tests', 'guide', 'test'), progress: { done: 3, total: 8 } as { done: number | null; total: number | null } | null }, entry('next-tests', 'checkout', 'test', '/other', null)] },
  machine: { load: [5, 2, 1] as number[] | null, cores: 4 },
})
const item = (id: string, title: string, kind = 'build', tool = 'codex') => ({ id, title, kind: 'fix', stage: 'building',
  worker: { kind, tool, model: 'sol', effort: 'medium', round: 2, started_at: at, step: 'editing the guide' },
  round: 2, findings: { count: 2, titles: ['Explain setup', 'Name the command'] },
  gates: { plan_read: { status: 'passed' }, review: { status: 'blocked', count: 2 }, ci: { status: 'red', elapsed: undefined as number | undefined } },
  pr: { number: 7, checks: 'fail', failures: [{ job: 'Windows', cause: 'timeout' }] },
})
export const boardFixture = () => ({ version: '1.2.6', repo_root: '/repo', items: [item('guide', 'Polish the guide'), item('checkout', 'Make checkout clear', 'review'), item('SHOP', 'Plan the shop', 'read', 'claude')], events: [
  { time: '1970-01-01T00:00:01Z', item: 'guide', line: 'Worker started' },
  { time: '1970-01-01T00:00:02Z', item: 'guide', line: 'Tests finished' },
] })
