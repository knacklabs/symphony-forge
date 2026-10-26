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
export type OrganisationMembership = { organisationId: string; role: 'admin' | 'member' };

export interface OrganisationsApi {
  createForAccount(account: OrganisationAccount): Promise<{ role: 'admin' | 'member' }>;
  invite(email: string, account: OrganisationPrincipal): Promise<void>;
  openInvite(token: string): Promise<OrganisationInvite>;
  joinFromInvite(invite: OrganisationInvite, account: OrganisationAccount): Promise<{ role: 'admin' | 'member' }>;
  membershipFor(accountId: string): Promise<OrganisationMembership | null>;
}
