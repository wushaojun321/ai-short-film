from beanie import PydanticObjectId
from app.models.project import Project, ProjectInitStatus
from app.models.episode import Episode
from app.models.asset import Asset
from app.models.shot import Shot
from app.models.task_record import TaskRecord
from app.models.conversation import Conversation
from app.schemas.project import ProjectCreate, ProjectUpdate


async def create_project(data: ProjectCreate, owner_id: PydanticObjectId) -> Project:
    existing = await Project.find_one(Project.title == data.title, Project.owner_id == owner_id)
    if existing:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail=f"项目名「{data.title}」已存在，请使用其他名称")
    project = Project(owner_id=owner_id, **data.model_dump())
    await project.insert()
    return project


async def get_project(project_id: PydanticObjectId) -> Project | None:
    return await Project.get(project_id)


async def list_projects(owner_id: PydanticObjectId) -> list[Project]:
    return await Project.find(Project.owner_id == owner_id).to_list()


async def update_project(project: Project, data: ProjectUpdate) -> Project:
    update_data = data.model_dump(exclude_unset=True)
    if update_data:
        await project.set(update_data)
    return project


async def delete_project(project: Project) -> None:
    # Cascade delete project-owned documents. Generated files in object storage are not removed here.
    await Shot.find(Shot.project_id == project.id).delete()
    await Episode.find(Episode.project_id == project.id).delete()
    await Asset.find(Asset.project_id == project.id).delete()
    await TaskRecord.find(TaskRecord.project_id == project.id).delete()
    await Conversation.find(Conversation.project_id == project.id).delete()
    await project.delete()


async def advance_init_status(project: Project, next_status: ProjectInitStatus) -> Project:
    await project.set({"init_status": next_status})
    return project
