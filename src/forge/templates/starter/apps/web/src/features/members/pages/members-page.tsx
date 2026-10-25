import { useOutletContext } from 'react-router-dom';
import { Download, Plus } from 'lucide-react';
import { toast } from 'sonner';
import { formatDate, type Account, type Member } from '@app/shared';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useChangeRole, useMembers } from '@/features/members/hooks/members-hooks';
import { InviteDialog } from '@/features/members/pages/invite-dialog';

const ROLE_LABELS: Record<Member['role'], string> = { admin: 'Admin', member: 'Member' };

function RoleCell({ member, account }: { member: Member; account: Account }) {
  const changeRole = useChangeRole();

  if (member.accountId === account.id) {
    return <span className="flex items-center gap-2"><Badge variant="secondary">{ROLE_LABELS[member.role]}</Badge><span className="text-xs text-muted-foreground">You</span></span>;
  }
  if (account.role !== 'admin') return <Badge variant="secondary">{ROLE_LABELS[member.role]}</Badge>;

  async function change(role: string) {
    try {
      await changeRole.mutateAsync({ accountId: member.accountId, role: role as Member['role'] });
      toast.success('Role updated.');
    } catch {
      toast.error('Could not change the role. Try again.');
    }
  }

  return (
    <Select value={member.role} onValueChange={(role) => void change(role)} disabled={changeRole.isPending}>
      <SelectTrigger aria-label={`Role for ${member.email}`} className="w-32"><SelectValue /></SelectTrigger>
      <SelectContent>
        <SelectItem value="admin">Admin</SelectItem>
        <SelectItem value="member">Member</SelectItem>
      </SelectContent>
    </Select>
  );
}

export function MembersPage() {
  const account = useOutletContext<Account>();
  const members = useMembers();

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Members</h1>
          <p className="mt-1 text-sm text-muted-foreground">People in your organisation.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" asChild><a href="/api/v1/members/export" download><Download aria-hidden="true" />Export CSV</a></Button>
          {account.role === 'admin' && <InviteDialog><Button><Plus aria-hidden="true" />Invite person</Button></InviteDialog>}
        </div>
      </div>

      {members.isPending && <p role="status" className="text-sm text-muted-foreground">Loading members…</p>}
      {members.isError && (
        <div role="alert" className="space-y-3">
          <p>Could not load members. Check your connection and try again.</p>
          <Button variant="outline" onClick={() => void members.refetch()}>Try again</Button>
        </div>
      )}
      {members.data && (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Joined</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {members.data.items.map((member) => (
                <TableRow key={member.id}>
                  <TableCell className="min-w-56 whitespace-normal break-all">{member.email}</TableCell>
                  <TableCell><RoleCell member={member} account={account} /></TableCell>
                  <TableCell><time dateTime={member.createdAtUtc}>{formatDate(member.createdAtUtc)}</time></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
