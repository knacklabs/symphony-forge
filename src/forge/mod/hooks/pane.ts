import type { On, RenderInput, RenderNode } from 'claude-code'
import type { Data } from './forge.ts'

// PANE supplies the tab host and the strip after CORE lands.
export function addTab(_name: string, _render: (e: RenderInput<'Pane'>) => RenderNode) {}
export function registerPane(_on: On, _data: Data) {}
