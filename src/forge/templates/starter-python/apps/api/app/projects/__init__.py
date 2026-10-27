# forge:feature:module-exports:start
from app.projects.routes import router
from app.projects.service import ProjectService

__all__ = ["ProjectService", "router"]
# forge:feature:module-exports:end
