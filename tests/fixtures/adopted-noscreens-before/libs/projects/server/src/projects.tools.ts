import { Injectable } from '@nestjs/common';
import { ModuleRef } from '@nestjs/core';
import { defineFeatureTools, type AccountPrincipal } from '@app/core-server';
import { projectSchema, projectListQuerySchema, PROJECTS_API } from '@app/projects-contracts';
import { ProjectsService } from './projects.service';
import { PROJECT_PERMISSIONS } from './projects.permissions';
// forge:feature:link-imports:start
// forge:feature:link-imports:end

@Injectable()
export class ProjectsTools {
  constructor(projects: ProjectsService, moduleRef: ModuleRef) {
    // Resources come from these schemas. Add a definePrompt here only for a repeated project
    // task in the constitution's Agent tasks section, with strict arguments and one permission.
    // Never send elicitation or sampling requests.
    defineFeatureTools({
      feature: 'projects', one: 'project', permissions: PROJECT_PERMISSIONS,
      api: PROJECTS_API,
      input: projectSchema, query: projectListQuerySchema, service: projects,
      // forge:feature:tool-fields:start
      label: 'name',
      concise: ['name', 'status'],
      links: {},
      // forge:feature:tool-fields:end
      resolve: (token) => moduleRef.get<{ get(account: AccountPrincipal, id: string): Promise<object> }>(token, { strict: false }),
    });
  }
}
