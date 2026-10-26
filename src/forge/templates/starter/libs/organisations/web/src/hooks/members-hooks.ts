import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { ChangeRoleInput, Member } from '@app/organisations-contracts';
import type { InviteInput } from '@app/auth-contracts';
import { apiRequest } from '@app/core-web';

type MemberList = { items: Member[] };

const membersKey = ['members'] as const;

export function useMembers() {
  return useQuery({
    queryKey: membersKey,
    // ponytail: the first 100 members, the API's page limit; add paging when an organisation outgrows it.
    queryFn: () => apiRequest<MemberList>('/members?page=1&limit=100'),
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
  return useMutation({
    mutationFn: (input: InviteInput) => apiRequest<{ message: string }>('/invites', {
      method: 'POST',
      body: JSON.stringify(input),
    }),
  });
}
