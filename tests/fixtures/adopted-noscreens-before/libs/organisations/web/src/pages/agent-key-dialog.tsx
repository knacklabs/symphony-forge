import { useRef, useState } from 'react';
import { Copy } from 'lucide-react';
import { toast } from 'sonner';
import type { Member } from '@app/organisations-contracts';
import { Alert, AlertDescription } from '@app/shared-ui/components/ui/alert';
import { Button } from '@app/shared-ui/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@app/shared-ui/components/ui/dialog';
import { Input } from '@app/shared-ui/components/ui/input';
import { Label } from '@app/shared-ui/components/ui/label';
import { useCreateAgentKey } from '../hooks/members-hooks';

/** Create key opens the dialog and makes a new key. The key lives only in this component's state, so closing the dialog drops it. */
export function AgentKeyDialog({ agent }: { agent: Member }) {
  const createKey = useCreateAgentKey();
  const [open, setOpen] = useState(false);
  const [key, setKey] = useState('');
  // Each request and each close gets a new number; an answer for an older number is from a closed or retried opening.
  const request = useRef(0);

  async function create() {
    setKey('');
    const current = ++request.current;
    try {
      const created = await createKey.mutateAsync(agent.accountId);
      if (current === request.current) setKey(created.key);
    } catch {
      // The dialog shows the failure; the row keeps its old key.
    }
  }

  function changeOpen(nextOpen: boolean) {
    setOpen(nextOpen);
    if (nextOpen) void create();
    else {
      request.current += 1;
      setKey('');
      createKey.reset();
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(key);
      toast.success('Key copied.');
    } catch {
      toast.error('Could not copy. Select the key and copy it.');
    }
  }

  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" aria-label={`Create key for ${agent.email}`}>Create key</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Agent key</DialogTitle>
          <DialogDescription>The key for {agent.email}. Give it to the agent's connection.</DialogDescription>
        </DialogHeader>
        {createKey.isPending && <p role="status" className="text-sm text-muted-foreground">Creating key…</p>}
        {createKey.isError && (
          <div role="alert" className="space-y-3">
            <p className="text-sm">Could not create a key. Try again.</p>
            <Button variant="outline" onClick={() => void create()}>Try again</Button>
          </div>
        )}
        {key && (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="agent-key">Key</Label>
              <div className="flex gap-2">
                <Input id="agent-key" readOnly value={key} className="font-mono" onFocus={(event) => event.target.select()} />
                <Button variant="outline" onClick={() => void copy()}><Copy aria-hidden="true" />Copy</Button>
              </div>
            </div>
            <Alert role="status"><AlertDescription>Copy this key now. You cannot see it again.</AlertDescription></Alert>
          </div>
        )}
        <DialogFooter>
          <Button onClick={() => changeOpen(false)}>Done</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
