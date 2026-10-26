import { Link, useOutletContext } from 'react-router-dom';
import type { Account } from '@app/auth-contracts';
import { useTheme } from '@/components/theme-provider';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

export function SettingsPage() {
  const account = useOutletContext<Account>();
  const { theme, setTheme } = useTheme();

  function changeTheme(value: string) {
    if (value === 'light' || value === 'dark' || value === 'system') setTheme(value);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
      <section id="profile" className="space-y-4">
        <div>
          <h2 className="text-lg font-medium">Profile</h2>
          <p className="text-sm text-muted-foreground">Your account email.</p>
        </div>
        <div className="max-w-md space-y-2">
          <Label htmlFor="account-email">Email</Label>
          <Input id="account-email" type="email" value={account.email} readOnly />
        </div>
      </section>
      <section id="password" className="space-y-3">
        <div>
          <h2 className="text-lg font-medium">Password</h2>
          <p className="text-sm text-muted-foreground">Use a reset link to choose a new password.</p>
        </div>
        <Link className="text-sm underline underline-offset-4" to="/forgot-password">Reset password</Link>
      </section>
      <section id="appearance" className="space-y-4">
        <div>
          <h2 className="text-lg font-medium">Appearance</h2>
          <p className="text-sm text-muted-foreground">Choose how this app looks on this device.</p>
        </div>
        <div className="max-w-md space-y-2">
          <Label htmlFor="theme">Theme</Label>
          <Select value={theme} onValueChange={changeTheme}>
            <SelectTrigger id="theme" aria-label="Theme">
              <SelectValue placeholder="Choose a theme" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="system">System</SelectItem>
              <SelectItem value="light">Light</SelectItem>
              <SelectItem value="dark">Dark</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </section>
    </div>
  );
}
