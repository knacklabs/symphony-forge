import { describe, expect, it, vi } from 'vitest';
import type { PrismaService } from '@app/core-server';
import { HistoryService } from './history.service';

describe('HistoryService', () => {
  it('history records the agent that acts for a person', async () => {
    const create = vi.fn().mockResolvedValue(undefined);
    const tx = { changeRecord: { create } };
    const service = new HistoryService({} as unknown as PrismaService);
    const principal = { id: 'account-id', email: 'person@example.test', organisationId: 'organisation-id' };

    await service.record({ ...principal, viaAgent: 'the assistant' }, 'project.created', 'Created the project', undefined, tx);
    await service.record(principal, 'project.created', 'Created the project', undefined, tx);

    expect(create).toHaveBeenNthCalledWith(1, { data: expect.objectContaining({ viaAgent: 'the assistant' }) });
    expect(create).toHaveBeenNthCalledWith(2, { data: expect.objectContaining({ viaAgent: null }) });
  });
});
