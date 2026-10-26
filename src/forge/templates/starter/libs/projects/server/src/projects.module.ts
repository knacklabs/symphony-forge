import { Global, Module } from '@nestjs/common';
import { PROJECTS_API } from '@app/projects-contracts';
import { ProjectsController } from './projects.controller';
import { ProjectsService } from './projects.service';

@Global()
@Module({
  controllers: [ProjectsController],
  providers: [ProjectsService, { provide: PROJECTS_API, useExisting: ProjectsService }],
  exports: [ProjectsService, PROJECTS_API],
})
export class ProjectsModule {}
