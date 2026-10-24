import { Module } from '@nestjs/common';
import { OrganisationsController } from './organisations.controller';
import { OrganisationsService } from './organisations.service';

@Module({ controllers: [OrganisationsController], providers: [OrganisationsService], exports: [OrganisationsService] })
export class OrganisationsModule {}
