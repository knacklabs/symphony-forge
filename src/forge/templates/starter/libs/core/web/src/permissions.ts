import { createContext, useContext } from 'react';

/** The signed-in account's permissions, as `<feature>.<action>`; the app shell provides them. */
export const PermissionsContext = createContext<readonly string[]>([]);

/** Whether the signed-in account may do this, such as `useCan('projects.delete')`. */
export function useCan(permission: string): boolean {
  return useContext(PermissionsContext).includes(permission);
}
