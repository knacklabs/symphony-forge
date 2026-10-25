import { Module } from '@nestjs/common';
import { MailModule } from '@app/core';
import { HistoryModule } from '@app/history';
import { OrganisationsController } from './organisations.controller';
import { OrganisationsService } from './organisations.service';

@Module({ imports: [MailModule, HistoryModule], controllers: [OrganisationsController], providers: [OrganisationsService], exports: [OrganisationsService] })
export class OrganisationsModule {}
