export type AccountPrincipal = {
  id: string;
  email: string;
  organisationId: string;
  role: 'admin' | 'member';
  /** The agent that acts for this person, such as `the assistant`. Unset when the person acts, or when a team agent acts as its own account. */
  viaAgent?: string;
};
