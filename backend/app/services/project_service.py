from beanie import PydanticObjectId
from app.models.project import Project, ProjectInitStatus
from app.models.episode import Episode
from app.models.asset import Asset
from app.schemas.project import ProjectCreate, ProjectUpdate


async def create_project(data: ProjectCreate) -> Project:
    project = Project(**data.model_dump())
    await project.insert()
    return project


async def get_project(project_id: PydanticObjectId) -> Project | None:
    return await Project.get(project_id)


async def list_projects() -> list[Project]:
    return await Project.find_all().to_list()


async def update_project(project: Project, data: ProjectUpdate) -> Project:
    update_data = data.model_dump(exclude_unset=True)
    if update_data:
        await project.set(update_data)
    return project


async def delete_project(project: Project) -> None:
    # cascade delete episodes, shots, assets
    episodes = await Episode.find(Episode.project_id == project.id).to_list()
    for ep in episodes:
        await ep.delete()
    await Asset.find(Asset.project_id == project.id).delete()
    await project.delete()


async def advance_init_status(project: Project, next_status: ProjectInitStatus) -> Project:
    await project.set({"init_status": next_status})
    return project
