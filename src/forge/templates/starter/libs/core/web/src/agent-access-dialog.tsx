import { useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bot, Check } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@app/shared-ui/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@app/shared-ui/components/ui/dialog';
import { Label } from '@app/shared-ui/components/ui/label';
import { Switch } from '@app/shared-ui/components/ui/switch';
import { apiRequest } from './api-client';

/** The features whose delete and restore tools agents can use, as `GET /api/v1/agent-tools` returns them. */
type AgentTools = { deleteAndRestore: string[] };

const agentToolsKey = ['agent-tools'] as const;

/**
 * The Agent access button and dialog of one feature's list screen, for admins only. `feature` is the
 * feature's plural in kebab case, `one` and `label` its singular and plural in words.
 */
export function AgentAccessDialog({ feature, one, label }: { feature: string; one: string; label: string }) {
  const account = useOutletContext<{ role: string } | undefined>();
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();
  const tools = useQuery({ queryKey: agentToolsKey, queryFn: () => apiRequest<AgentTools>('/agent-tools'), enabled: open });
  const change = useMutation({
    mutationFn: (deleteAndRestore: boolean) => apiRequest<AgentTools>(`/agent-tools/${encodeURIComponent(feature)}`, {
      method: 'PUT',
      body: JSON.stringify({ deleteAndRestore }),
    }),
    onSuccess: (data) => {
      queryClient.setQueryData(agentToolsKey, data);
      toast.success('Agent access updated.');
    },
    onError: () => toast.error('Could not update agent access. Try again.'),
  });

  if (account?.role !== 'admin') return null;
  // While a change saves, the Switch shows it; a failed change goes back to the saved value.
  const on = change.isPending ? change.variables : Boolean(tools.data?.deleteAndRestore.includes(feature));
  const always = [`Search ${label}`, `View ${/^[aeiou]/i.test(one) ? 'an' : 'a'} ${one}`, `Create ${label}`, `Edit ${label}`];
  const switchId = `agent-delete-restore-${feature}`;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline"><Bot aria-hidden="true" />Agent access</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Agent access</DialogTitle>
          <DialogDescription>Choose which {one} tools agents can use.</DialogDescription>
        </DialogHeader>
        {tools.isPending && <p role="status" className="text-sm text-muted-foreground">Loading agent access…</p>}
        {tools.isError && (
          <div role="alert" className="space-y-3">
            <p className="text-sm">Could not load agent access. Check your connection and try again.</p>
            <Button variant="outline" onClick={() => void tools.refetch()}>Try again</Button>
          </div>
        )}
        {tools.data && (
          <ul className="divide-y rounded-md border text-sm">
            {always.map((tool) => (
              <li key={tool} className="flex items-center justify-between gap-4 px-3 py-2.5">
                <span>{tool}</span>
                <span className="flex items-center gap-1.5 text-muted-foreground"><Check aria-hidden="true" className="size-4" />Always on</span>
              </li>
            ))}
            <li className="flex items-center justify-between gap-4 px-3 py-2.5">
              <Label htmlFor={switchId} className="font-normal">Agents can delete and restore {label}</Label>
              {/* Not disabled while it saves, so keyboard focus stays on it; a second change waits for the first. */}
              <Switch id={switchId} checked={on} aria-busy={change.isPending} onCheckedChange={(checked) => { if (!change.isPending) change.mutate(checked); }} />
            </li>
          </ul>
        )}
        <p className="text-sm text-muted-foreground">The agent account's role still applies. A Member agent cannot delete or restore.</p>
        <DialogFooter>
          <Button onClick={() => setOpen(false)}>Done</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
