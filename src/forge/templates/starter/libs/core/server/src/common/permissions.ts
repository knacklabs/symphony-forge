import { ForbiddenException, Injectable, SetMetadata, UseGuards, applyDecorators, type CanActivate, type ExecutionContext } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import type { AccountPrincipal } from './account-principal';
import type { AuthenticatedRequest } from './authenticated-request';

type Role = AccountPrincipal['role'];
const ACTIONS = ['view', 'create', 'edit', 'delete', 'restore'] as const;
type Action = (typeof ACTIONS)[number];
export type FeaturePermissions = Record<Action, string>;

// Each module's permissions file fills this map when it loads, before the app takes requests.
const ROLE_PERMISSIONS: Record<Role, string[]> = { admin: [], member: [] };

/** Gives each role its actions on one feature, as `<feature>.<action>`, and returns the five names. */
export function definePermissions(feature: string, roles: Record<Role, readonly Action[]>): FeaturePermissions {
  for (const role of Object.keys(roles) as Role[]) {
    ROLE_PERMISSIONS[role].push(...roles[role].map((action) => `${feature}.${action}`));
  }
  return Object.fromEntries(ACTIONS.map((action) => [action, `${feature}.${action}`])) as FeaturePermissions;
}

export function permissionsFor(role: Role): string[] {
  return [...ROLE_PERMISSIONS[role]];
}

export function hasPermission(account: AccountPrincipal, permission: string): boolean {
  return ROLE_PERMISSIONS[account.role].includes(permission);
}

const PERMISSION = 'permission';

@Injectable()
class PermissionGuard implements CanActivate {
  constructor(private readonly reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    const permission = this.reflector.get<string>(PERMISSION, context.getHandler());
    const { principal } = context.switchToHttp().getRequest<AuthenticatedRequest>();
    if (principal && hasPermission(principal, permission)) return true;

    throw new ForbiddenException({
      code: 'PERMISSION_DENIED',
      message: 'You do not have permission to do this.',
      details: null,
    });
  }
}

export const RequirePermission = (permission: string) => applyDecorators(SetMetadata(PERMISSION, permission), UseGuards(PermissionGuard));
