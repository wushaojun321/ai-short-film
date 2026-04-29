from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from beanie import PydanticObjectId
from app.models.project import Project, ProjectInitStatus
from app.models.episode import Episode, EpisodeStatus
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate, ParseScriptRequest, ConfirmEpisodesRequest
from app.services import project_service
import app.services.storage_service as storage_service
from app.deps import get_current_user, get_owned_project

router = APIRouter(prefix="/projects", tags=["projects"], dependencies=[Depends(get_current_user)])


@router.get("")
async def list_projects(current_user: User = Depends(get_current_user)):
    return await project_service.list_projects(current_user.id)


@router.post("", status_code=201)
async def create_project(data: ProjectCreate, current_user: User = Depends(get_current_user)):
    return await project_service.create_project(data, current_user.id)


@router.get("/{project_id}")
async def get_project(project: Project = Depends(get_owned_project)):
    return project


@router.patch("/{project_id}")
async def update_project(data: ProjectUpdate, project: Project = Depends(get_owned_project)):
    return await project_service.update_project(project, data)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project: Project = Depends(get_owned_project)):
    await project_service.delete_project(project)


@router.post("/{project_id}/upload-script")
async def upload_script(
    file: UploadFile = File(...),
    project: Project = Depends(get_owned_project),
):
    content = await file.read()
    filename = f"projects/{project.id}/script/{file.filename}"
    url = await storage_service.upload_bytes(
        data=content,
        filename=filename,
        content_type=file.content_type or "application/octet-stream",
    )

    script_text: str | None = None
    try:
        script_text = content.decode("utf-8")
    except Exception:
        pass

    await project.set({
        "script_file_url": url,
        "script_text": script_text,
        "init_status": ProjectInitStatus.script_uploaded,
    })
    return {"script_file_url": url, "init_status": ProjectInitStatus.script_uploaded}


@router.post("/{project_id}/confirm-episodes")
async def confirm_episodes(data: ConfirmEpisodesRequest, project: Project = Depends(get_owned_project)):
    for ep_data in data.episodes:
        ep_id = ep_data.get("id")
        if ep_id:
            try:
                episode = await Episode.get(PydanticObjectId(ep_id))
            except Exception:
                episode = None
            if episode:
                await episode.set({
                    "title": ep_data.get("title", episode.title),
                    "summary": ep_data.get("summary", episode.summary),
                    "word_count": ep_data.get("word_count", episode.word_count),
                    "estimated_duration": ep_data.get("estimated_duration", episode.estimated_duration),
                })
                continue

        episode = Episode(
            project_id=project.id,
            number=ep_data.get("number", 0),
            title=ep_data.get("title", ""),
            summary=ep_data.get("summary", ""),
            word_count=ep_data.get("word_count", 0),
            estimated_duration=ep_data.get("estimated_duration", 0),
            status=EpisodeStatus.not_started,
        )
        await episode.insert()

    await project_service.advance_init_status(project, ProjectInitStatus.episodes_confirmed)
    return {"init_status": ProjectInitStatus.episodes_confirmed}


@router.post("/{project_id}/confirm-assets")
async def confirm_assets(project: Project = Depends(get_owned_project)):
    if project.init_status not in (
        ProjectInitStatus.episodes_confirmed,
        ProjectInitStatus.assets_confirmed,
    ):
        raise HTTPException(400, f"Cannot confirm assets in status: {project.init_status}")
    await project_service.advance_init_status(project, ProjectInitStatus.initialized)
    return {"init_status": ProjectInitStatus.initialized}
