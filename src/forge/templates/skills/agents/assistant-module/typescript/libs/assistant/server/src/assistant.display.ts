import { z } from 'zod';
import { blockSchema, type Block } from '@app/assistant-contracts';

const project = z.object({ name: z.string(), status_label: z.string() });
const projects = z.object({ items: z.array(project), total: z.number(), total_is_capped: z.boolean() });

function detail(data: Record<string, unknown>): Block[] {
  const row = project.parse(data);
  return [{ kind: 'detail', props: { title: row.name, fields: [{ label: 'Status', value: row.status_label }] } }];
}

// Add a report's typed result here when the app has a report service. Never use
// model output to choose a component or supply its props.
export const DISPLAY: Record<string, (data: Record<string, unknown>) => Block[]> = {
  projects_search: (data) => {
    const page = projects.parse(data);
    return [{ kind: 'table', props: {
      columns: [{ key: 'name', label: 'Name' }, { key: 'status_label', label: 'Status' }],
      rows: page.items, ...(page.total_is_capped ? {} : { total: page.total }),
    } }];
  },
  projects_get: detail,
  projects_create: detail,
  projects_update: detail,
  projects_restore: detail,
};

export function displayResult(name: string, data: Record<string, unknown>): Block[] {
  return (DISPLAY[name]?.(data) ?? []).map((block) => blockSchema.parse(block));
}
