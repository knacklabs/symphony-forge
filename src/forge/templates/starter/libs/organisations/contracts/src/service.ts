import type { Member, Role } from './index';

export const ORGANISATIONS_API = 'OrganisationsApi';

export type OrganisationAccount = { id: string; email: string };
export type OrganisationPrincipal = { id: string; email: string; organisationId: string };
export type OrganisationInvite = {
  id: string;
  email: string;
  organisationId: string;
  tokenHash: string;
  expiresAtUtc: Date;
};
export type OrganisationMembership = { organisationId: string; role: Role };

export interface OrganisationsApi {
  createForAccount(account: OrganisationAccount): Promise<{ role: Role }>;
  invite(email: string, account: OrganisationPrincipal): Promise<void>;
  openInvite(token: string): Promise<OrganisationInvite>;
  joinFromInvite(invite: OrganisationInvite, account: OrganisationAccount): Promise<{ role: Role }>;
  membershipFor(accountId: string): Promise<OrganisationMembership | null>;
  /** Makes the new account an agent of the admin's organisation, with its Change history row. */
  addAgent(account: OrganisationAccount, role: Role, admin: OrganisationPrincipal): Promise<Member>;
  /** The agent with this key hash and its organisation's agent delete and restore list. */
  agentForKey(keyHash: string): Promise<{ principal: OrganisationPrincipal & { role: Role }; deleteAndRestore: string[] } | null>;
}
