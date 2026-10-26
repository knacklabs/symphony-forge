import { useOutletContext } from 'react-router-dom';
import { Download } from 'lucide-react';
import { formatDateTime } from '@app/shared-util';
import { type Account } from '@app/auth-contracts';
import { Button } from '@app/shared-ui/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@app/shared-ui/components/ui/table';
import { useHistory } from '../hooks/history-hooks';
import { ApiError } from '@app/core-web';

export function HistoryPage() {
  const account = useOutletContext<Account>();
  const history = useHistory(account.role === 'admin');
  // A role can change while the page is open, so a 403 from the API reads the same as the member's view.
  const forbidden = account.role !== 'admin' || (history.error instanceof ApiError && history.error.status === 403);

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Change history</h1>
          <p className="mt-1 text-sm text-muted-foreground">Who changed what in your organisation.</p>
        </div>
        {!forbidden && <Button variant="outline" asChild><a href="/api/v1/history/export" download><Download aria-hidden="true" />Export CSV</a></Button>}
      </div>

      {forbidden && <p role="alert">Only an admin can see the change history.</p>}
      {!forbidden && history.isPending && <p role="status" className="text-sm text-muted-foreground">Loading change history…</p>}
      {!forbidden && history.isError && (
        <div role="alert" className="space-y-3">
          <p>Could not load the change history. Check your connection and try again.</p>
          <Button variant="outline" onClick={() => void history.refetch()}>Try again</Button>
        </div>
      )}
      {!forbidden && history.data?.length === 0 && <p className="text-sm text-muted-foreground">No changes yet.</p>}
      {!forbidden && !!history.data?.length && (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>When</TableHead>
                <TableHead>Who</TableHead>
                <TableHead>What</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {history.data.map((entry) => (
                <TableRow key={entry.id}>
                  <TableCell><time dateTime={entry.createdAtUtc}>{formatDateTime(entry.createdAtUtc)}</time></TableCell>
                  <TableCell className="whitespace-normal break-all">{entry.actorEmail}</TableCell>
                  <TableCell className="min-w-56 whitespace-normal">{entry.summary}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
