import { useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Bot, Download, Plus } from 'lucide-react';
import { toast } from 'sonner';
import { formatDate } from '@app/shared-util';
import { type Account } from '@app/auth-contracts';
import { type Member } from '@app/organisations-contracts';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@app/shared-ui/components/ui/alert-dialog';
import { Badge } from '@app/shared-ui/components/ui/badge';
import { Button } from '@app/shared-ui/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@app/shared-ui/components/ui/select';
import { Skeleton } from '@app/shared-ui/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@app/shared-ui/components/ui/table';
import { useChangeRole, useMembers, useRevokeAgentKey } from '../hooks/members-hooks';
import { AddAgentDialog } from './add-agent-dialog';
import { AgentKeyDialog } from './agent-key-dialog';
import { InviteDialog } from './invite-dialog';

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

function RevokeKeyDialog({ agent }: { agent: Member }) {
  const [open, setOpen] = useState(false);
  const revokeKey = useRevokeAgentKey();

  async function revoke() {
    try {
      await revokeKey.mutateAsync(agent.accountId);
      toast.success('Key revoked.');
      setOpen(false);
    } catch {
      toast.error('Could not revoke the key. Try again.');
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      <AlertDialogTrigger asChild>
        <Button variant="outline" size="sm" className="text-destructive hover:text-destructive" aria-label={`Revoke key for ${agent.email}`}>Revoke key</Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Revoke this key?</AlertDialogTitle>
          <AlertDialogDescription>Agents that use it stop working at once.</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction variant="destructive" disabled={revokeKey.isPending} onClick={(event) => { event.preventDefault(); void revoke(); }}>
            {revokeKey.isPending ? 'Revoking…' : 'Revoke key'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

function AgentAccounts({ agents, account }: { agents: Member[]; account: Account }) {
  const isAdmin = account.role === 'admin';
  return (
    <section aria-labelledby="agent-accounts" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 id="agent-accounts" className="text-lg font-semibold tracking-tight">Agent accounts</h2>
          <p className="mt-1 text-sm text-muted-foreground">Agents use this app's tools with their own role and key.</p>
        </div>
        {isAdmin && <AddAgentDialog><Button variant="outline"><Bot aria-hidden="true" />Add agent account</Button></AddAgentDialog>}
      </div>
      {agents.length === 0 ? (
        <div className="rounded-md border p-6">
          <p className="font-medium">No agent accounts yet.</p>
          {isAdmin && <p className="mt-1 text-sm text-muted-foreground">Add one so an agent can use this app's tools.</p>}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Key</TableHead>
                {isAdmin && <TableHead><span className="sr-only">Actions</span></TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {agents.map((agent) => (
                <TableRow key={agent.id}>
                  <TableCell className="min-w-56 whitespace-normal break-all">{agent.email}</TableCell>
                  <TableCell><RoleCell member={agent} account={account} /></TableCell>
                  <TableCell>{agent.hasKey ? <Badge variant="outline">Key active</Badge> : <Badge variant="secondary">No key</Badge>}</TableCell>
                  {isAdmin && (
                    <TableCell>
                      <div className="flex justify-end gap-2">
                        <AgentKeyDialog agent={agent} />
                        {agent.hasKey && <RevokeKeyDialog agent={agent} />}
                      </div>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </section>
  );
}

export function MembersPage() {
  const account = useOutletContext<Account>();
  const members = useMembers();
  const people = members.data?.items.filter((member) => !member.isAgent) ?? [];
  const agents = members.data?.items.filter((member) => member.isAgent) ?? [];

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

      {members.isPending && (
        <div role="status" aria-label="Loading members" className="space-y-2">
          {[0, 1, 2].map((row) => <Skeleton key={row} className="h-10 w-full" />)}
        </div>
      )}
      {members.isError && (
        <div role="alert" className="space-y-3">
          <p>Could not load members. Check your connection and try again.</p>
          <Button variant="outline" onClick={() => void members.refetch()}>Try again</Button>
        </div>
      )}
      {members.data && (
        <>
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
                {people.map((member) => (
                  <TableRow key={member.id}>
                    <TableCell className="min-w-56 whitespace-normal break-all">{member.email}</TableCell>
                    <TableCell><RoleCell member={member} account={account} /></TableCell>
                    <TableCell><time dateTime={member.createdAtUtc}>{formatDate(member.createdAtUtc)}</time></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <AgentAccounts agents={agents} account={account} />
        </>
      )}
    </div>
  );
}
