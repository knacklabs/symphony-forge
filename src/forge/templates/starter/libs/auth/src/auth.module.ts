import { Module } from '@nestjs/common';
import { MailModule } from '@app/core';
import { OrganisationsModule } from '@app/organisations';
import { AuthController } from './auth.controller';
import { AuthService } from './auth.service';
import { InvitesController } from './invites.controller';

@Module({
  imports: [OrganisationsModule, MailModule],
  exports: [AuthService],
  controllers: [AuthController, InvitesController],
  providers: [AuthService],
})
export class AuthModule {}
