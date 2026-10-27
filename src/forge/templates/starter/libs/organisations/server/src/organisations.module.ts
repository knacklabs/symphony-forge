import { Global, Module } from '@nestjs/common';
import { MailModule } from '@app/core-server';
import { ORGANISATIONS_API } from '@app/organisations-contracts';
import { AgentToolsController, OrganisationsController } from './organisations.controller';
import { OrganisationsService } from './organisations.service';

@Global()
@Module({
  imports: [MailModule],
  controllers: [OrganisationsController, AgentToolsController],
  providers: [OrganisationsService, { provide: ORGANISATIONS_API, useExisting: OrganisationsService }],
  exports: [ORGANISATIONS_API],
})
export class OrganisationsModule {}
