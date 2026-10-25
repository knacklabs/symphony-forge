import { useEffect, useState } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { FolderKanban, HistoryIcon, Search, Settings, UserRound, Users, Sun, Moon, Monitor } from 'lucide-react';
import type { ComponentProps } from 'react';
import { toast } from 'sonner';
import type { Account } from '@app/shared';
import { useTheme } from '@/components/theme-provider';
import { useSignOut } from '@/features/auth/hooks/auth-hooks';
import { Button } from '@/components/ui/button';
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
} from '@/components/ui/breadcrumb';
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Separator } from '@/components/ui/separator';
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
  useSidebar,
} from '@/components/ui/sidebar';

function AppSidebar({ account, ...props }: ComponentProps<typeof Sidebar> & { account: Account }) {
  const pathname = useLocation().pathname;
  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader><span className="sr-only">Workspace navigation</span></SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Workspace</SidebarGroupLabel>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton asChild isActive={pathname === '/projects'} tooltip="Projects">
                <Link to="/projects"><FolderKanban /><span>Projects</span></Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
            <SidebarMenuItem>
              <SidebarMenuButton asChild isActive={pathname === '/members'} tooltip="Members">
                <Link to="/members"><Users /><span>Members</span></Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
            {account.role === 'admin' && (
              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={pathname === '/history'} tooltip="Change history">
                  <Link to="/history"><HistoryIcon /><span>Change history</span></Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            )}
            <SidebarMenuItem>
              <SidebarMenuButton asChild isActive={pathname === '/settings'} tooltip="Settings">
                <Link to="/settings"><Settings /><span>Settings</span></Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>
      <SidebarRail tabIndex={0} aria-label="Collapse or expand navigation" title="Collapse or expand navigation" />
    </Sidebar>
  );
}

function UserMenu({ account }: { account: Account }) {
  const { theme, setTheme } = useTheme();
  const signOut = useSignOut();
  const navigate = useNavigate();

  async function handleSignOut() {
    try {
      await signOut.mutateAsync();
      navigate('/sign-in');
    } catch {
      toast.error('Could not sign out. Try again.');
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Open user menu">
          <UserRound aria-hidden="true" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="truncate">{account.email}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link to="/settings#profile">Profile</Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link to="/settings#appearance"><Settings aria-hidden="true" />Settings</Link>
        </DropdownMenuItem>
        <DropdownMenuSub>
          <DropdownMenuSubTrigger>
            {theme === 'dark' ? <Moon aria-hidden="true" /> : theme === 'light' ? <Sun aria-hidden="true" /> : <Monitor aria-hidden="true" />}
            Theme
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent>
            <DropdownMenuItem onSelect={() => setTheme('light')}>Light</DropdownMenuItem>
            <DropdownMenuItem onSelect={() => setTheme('dark')}>Dark</DropdownMenuItem>
            <DropdownMenuItem onSelect={() => setTheme('system')}>System</DropdownMenuItem>
          </DropdownMenuSubContent>
        </DropdownMenuSub>
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled={signOut.isPending} onSelect={() => void handleSignOut()}>
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function SearchBox({ account }: { account: Account }) {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setOpen(true);
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  function goTo(path: string) {
    navigate(path);
    setOpen(false);
  }

  return (
    <>
      <Button variant="outline" className="w-9 justify-center px-0 font-normal text-muted-foreground sm:w-52 sm:justify-between sm:px-3" aria-label="Search" onClick={() => setOpen(true)}>
        <span className="flex items-center gap-2"><Search aria-hidden="true" className="size-4" /><span className="sr-only sm:not-sr-only">Search</span></span>
        <kbd className="pointer-events-none hidden rounded border px-1.5 text-xs sm:inline">⌘/Ctrl K</kbd>
      </Button>
      <CommandDialog open={open} onOpenChange={setOpen} title="Search" description="Search pages and actions.">
        <CommandInput placeholder="Search pages..." aria-label="Search pages" />
        <CommandList>
          <CommandEmpty>No matching pages.</CommandEmpty>
          <CommandGroup heading="Pages">
            <CommandItem onSelect={() => goTo('/projects')}>Projects</CommandItem>
            <CommandItem onSelect={() => goTo('/members')}>Members</CommandItem>
            {account.role === 'admin' && <CommandItem onSelect={() => goTo('/history')}>Change history</CommandItem>}
            <CommandItem onSelect={() => goTo('/settings')}>Settings</CommandItem>
          </CommandGroup>
        </CommandList>
      </CommandDialog>
    </>
  );
}

function ShellContent({ account }: { account: Account }) {
  const location = useLocation();
  const { open, openMobile, isMobile } = useSidebar();
  const pageTitle = ({ '/settings': 'Settings', '/members': 'Members', '/history': 'Change history' } as Record<string, string>)[location.pathname] ?? 'Projects';

  return (
    <SidebarInset>
      <header className="flex h-14 shrink-0 items-center gap-3 border-b px-4">
        <SidebarTrigger aria-expanded={isMobile ? openMobile : open} aria-label="Toggle Sidebar" />
        <Separator orientation="vertical" className="h-5" />
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem><BreadcrumbPage>{pageTitle}</BreadcrumbPage></BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
        <div className="ml-auto flex items-center gap-2">
          <SearchBox account={account} />
          <UserMenu account={account} />
        </div>
      </header>
      <div id="main-content" tabIndex={-1} className="min-w-0 flex-1 p-6">
        <Outlet context={account} />
      </div>
    </SidebarInset>
  );
}

export function AppShell({ account }: { account: Account }) {
  const savedSidebarState = document.cookie.split('; ').find((cookie) => cookie.startsWith('sidebar_state='))?.split('=')[1];
  return (
    <SidebarProvider defaultOpen={savedSidebarState !== 'false'}>
      <AppSidebar account={account} />
      <ShellContent account={account} />
    </SidebarProvider>
  );
}
