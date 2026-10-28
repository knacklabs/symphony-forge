import { Global, Module } from '@nestjs/common';
import { PROJECTS_API } from '@app/projects-contracts';
import { ProjectsController } from './projects.controller';
import { ProjectsService } from './projects.service';
// forge:feature:mcp:start
import { ProjectsTools } from './projects.tools';
// forge:feature:mcp:end

@Global()
@Module({
  controllers: [ProjectsController],
  providers: [ProjectsService, { provide: PROJECTS_API, useExisting: ProjectsService },
    // forge:feature:mcp:start
    ProjectsTools,
    // forge:feature:mcp:end
  ],
  exports: [ProjectsService, PROJECTS_API],
})
export class ProjectsModule {}
