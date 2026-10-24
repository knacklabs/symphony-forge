import { Module } from '@nestjs/common';
import { MailModule } from '@app/core';
import { OrganisationsController } from './organisations.controller';
import { OrganisationsService } from './organisations.service';

@Module({ imports: [MailModule], controllers: [OrganisationsController], providers: [OrganisationsService], exports: [OrganisationsService] })
export class OrganisationsModule {}
