import { Global, Module } from '@nestjs/common';
import { MailModule } from '@app/core-server';
import { ORGANISATIONS_API } from '@app/organisations-contracts';
import { OrganisationsController } from './organisations.controller';
import { OrganisationsService } from './organisations.service';

@Global()
@Module({
  imports: [MailModule],
  controllers: [OrganisationsController],
  providers: [OrganisationsService, { provide: ORGANISATIONS_API, useExisting: OrganisationsService }],
  exports: [ORGANISATIONS_API],
})
export class OrganisationsModule {}
