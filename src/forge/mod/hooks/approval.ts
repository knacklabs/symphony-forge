import type { On } from 'claude-code'
import type { Data } from './forge.ts'

// Claude strips caller-supplied ExitPlanMode plan text and reads its session
// plan file instead. Keep this seam empty: approval stays in Plan Mode.
export function registerApproval(_on: On, _data: Data) {}
