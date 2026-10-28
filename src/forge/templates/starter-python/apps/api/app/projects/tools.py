from app.core import define_feature_tools
from app.projects.permissions import PROJECT_PERMISSIONS
from app.projects.schema import Project, ProjectInput, ProjectListQuery
from app.projects.service import ProjectService

# forge:feature:tool-imports:start
# forge:feature:tool-imports:end


def register_tools() -> None:
    # Resources come from these schemas. Add a prompt with define_prompt only for a
    # repeated task in the constitution's Agent tasks section, with strict arguments
    # and one permission. Send no elicitation or sampling requests.
    define_feature_tools(
        feature="projects",
        one="project",
        permissions=PROJECT_PERMISSIONS,
        input_model=ProjectInput,
        output_model=Project,
        query_model=ProjectListQuery,
        service=ProjectService,
        api="projects",
        # forge:feature:tool-fields:start
        label="name",
        concise=["name", "status"],
        links={},
        # forge:feature:tool-fields:end
    )
