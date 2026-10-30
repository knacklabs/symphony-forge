import { useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { AddAgentInput, AgentKey, ChangeRoleInput, Member } from '@app/organisations-contracts';
import type { InviteInput } from '@app/auth-contracts';
import { apiRequest } from '@app/core-web';

type MemberList = { items: Member[]; pagination: { totalPages: number } };

const membersKey = ['members'] as const;
/** The API's page limit. */
const MEMBERS_PER_PAGE = 100;

export function useMembers() {
  return useQuery({
    queryKey: membersKey,
    // Every page, so people and agent accounts past the first 100 members show too.
    // ponytail: one request per 100 members; add a paged table when an organisation outgrows a few pages.
    queryFn: async () => {
      const items: Member[] = [];
      for (let page = 1; ; page += 1) {
        const list = await apiRequest<MemberList>(`/members?page=${page}&limit=${MEMBERS_PER_PAGE}`);
        items.push(...list.items);
        if (page >= list.pagination.totalPages) return { items };
      }
    },
  });
}

export function useChangeRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ accountId, role }: { accountId: string } & ChangeRoleInput) => apiRequest<Member>(`/members/${encodeURIComponent(accountId)}`, {
      method: 'PATCH',
      body: JSON.stringify({ role }),
    }),
    onSettled: () => queryClient.invalidateQueries({ queryKey: membersKey }),
  });
}

export function useInvite() {
  const idempotencyKey = useRef(crypto.randomUUID());
  return useMutation({
    mutationFn: (input: InviteInput) => apiRequest<{ message: string }>('/invites', {
      method: 'POST',
      body: JSON.stringify(input),
      headers: { 'Idempotency-Key': idempotencyKey.current },
    }),
    onSuccess: () => {
      idempotencyKey.current = crypto.randomUUID();
    },
  });
}

export function useAddAgent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: AddAgentInput) => apiRequest<Member>('/agents', { method: 'POST', body: JSON.stringify(input) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: membersKey }),
  });
}

export function useCreateAgentKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (accountId: string) => apiRequest<AgentKey>(`/members/${encodeURIComponent(accountId)}/key`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: membersKey }),
  });
}

export function useRevokeAgentKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (accountId: string) => apiRequest<null>(`/members/${encodeURIComponent(accountId)}/key`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: membersKey }),
  });
}
