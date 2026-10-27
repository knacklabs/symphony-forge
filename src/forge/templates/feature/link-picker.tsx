import { useState, type ComponentProps } from 'react';
import { Check, ChevronsUpDown } from 'lucide-react';
import { Button } from '@app/shared-ui/components/ui/button';
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@app/shared-ui/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@app/shared-ui/components/ui/popover';
import { cn } from '@app/shared-ui/lib/utils';
import { useLinkedItem, useLinkedItems } from '../hooks/@@PLURAL@@-hooks';

/** Where a link field's items live: the other feature's address and the field that names an item. */
type LinkTarget = { path: string; nameField: string };

/** The linked item's name, read from the other feature's API; the API returns only its id. */
export function LinkedName({ path, nameField, id }: LinkTarget & { id: string | null }) {
  const linked = useLinkedItem(path, nameField, id);
  if (!id) return null;
  if (linked.isError) return <>Not found</>;
  return <>{linked.data?.name ?? ''}</>;
}

type LinkPickerProps = LinkTarget & Omit<ComponentProps<typeof Button>, 'value' | 'onChange'> & {
  label: string;
  /** The other feature's items in words, such as `clients`. */
  noun: string;
  /** The choice for no item, such as `All clients` in a filter; a required field has none. */
  emptyChoice?: string;
  value: string | undefined;
  onChange: (id: string | undefined) => void;
};

/** A searchable Select over the other feature's list API, for a link field and its filter. */
export function LinkPicker({ path, nameField, label, noun, emptyChoice, value, onChange, className, ...trigger }: LinkPickerProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  // ponytail: one page of 20 matches; the search narrows it, add paging when a list needs more.
  const items = useLinkedItems(path, nameField, search.trim());
  const chosen = useLinkedItem(path, nameField, value ?? null);

  function choose(id: string | undefined) {
    onChange(id);
    setOpen(false);
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" role="combobox" aria-expanded={open} aria-label={label} className={cn('justify-between font-normal', className)} {...trigger}>
          <span className="truncate">{value ? chosen.data?.name ?? '' : emptyChoice ?? `Search ${noun}…`}</span>
          <ChevronsUpDown aria-hidden="true" className="opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-(--radix-popover-trigger-width) min-w-56 p-0">
        <Command shouldFilter={false}>
          <CommandInput placeholder={`Search ${noun}…`} aria-label={`Search ${noun}`} value={search} onValueChange={setSearch} />
          <CommandList>
            {items.isPending && <p role="status" className="p-3 text-sm text-muted-foreground">Loading {noun}…</p>}
            {items.isError && <p role="alert" className="p-3 text-sm">Could not load {noun}. Close this list and try again.</p>}
            {items.data && <CommandEmpty>No {noun} found.</CommandEmpty>}
            <CommandGroup>
              {emptyChoice && !search.trim() && items.data && (
                <CommandItem value="" onSelect={() => choose(undefined)}>
                  <Check aria-hidden="true" className={cn(value ? 'opacity-0' : 'opacity-100')} />{emptyChoice}
                </CommandItem>
              )}
              {items.data?.map((item) => (
                <CommandItem key={item.id} value={item.id} onSelect={() => choose(item.id)}>
                  <Check aria-hidden="true" className={cn(value === item.id ? 'opacity-100' : 'opacity-0')} />{item.name}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
