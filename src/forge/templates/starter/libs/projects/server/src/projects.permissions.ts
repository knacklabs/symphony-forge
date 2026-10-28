import { definePermissions } from '@app/core-server';

/** The one place that says which role may do what with projects. */
export const PROJECT_PERMISSIONS = definePermissions('projects', {
  admin: ['view', 'create', 'edit', 'delete', 'restore'],
  member: ['view', 'create', 'edit'],
});
