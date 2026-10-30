# forge:feature:module-exports:start
from app.projects.routes import router
from app.projects.service import ProjectService

# forge:feature:mcp:start
# forge:feature:tools:start
from app.projects.tools import register_tools

register_tools()
# forge:feature:tools:end
# forge:feature:mcp:end

__all__ = ["ProjectService", "router"]
# forge:feature:module-exports:end
