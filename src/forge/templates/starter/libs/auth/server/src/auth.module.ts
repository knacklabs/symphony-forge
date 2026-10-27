import { Global, Module } from '@nestjs/common';
import { MailModule } from '@app/core-server';
import { AUTH_API } from '@app/auth-contracts';
import { AgentsController } from './agents.controller';
import { AuthController } from './auth.controller';
import { AuthService } from './auth.service';
import { InvitesController } from './invites.controller';

// Global, so other modules reach accounts only through AUTH_API.
@Global()
@Module({
  imports: [MailModule],
  exports: [AuthService, AUTH_API],
  controllers: [AuthController, InvitesController, AgentsController],
  providers: [AuthService, { provide: AUTH_API, useExisting: AuthService }],
})
export class AuthModule {}
