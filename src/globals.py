import os

from dotenv import load_dotenv

import supervisely as sly

if sly.is_development():
    load_dotenv("local.env")
    load_dotenv(os.path.expanduser("~/supervisely.env"))

api = sly.Api.from_env()

TEAM_ID = sly.env.team_id()
TASK_ID = sly.env.task_id()
WORKSPACE_ID = sly.env.workspace_id()
PROJECT_ID = sly.env.project_id(raise_not_found=False)
DATASET_ID = sly.env.dataset_id(raise_not_found=False)
PROJECT = api.project.get_info_by_id(PROJECT_ID)
DATASET = None
if DATASET_ID is not None:
    DATASET = api.dataset.get_info_by_id(DATASET_ID)

ANNOTATED_FRAMES = {}
PROJECT_META = sly.ProjectMeta.from_json(api.project.get_meta(PROJECT.id))

if PROJECT is None:
    raise RuntimeError("Project {!r} not found".format(PROJECT.name))
if PROJECT.type != str(sly.ProjectType.VIDEOS):
    raise TypeError(
        "Project type is {!r}, but has to be {!r}".format(PROJECT.type, sly.ProjectType.VIDEOS)
    )

sly.logger.info(
    "Script arguments",
    extra={
        "TEAM_ID": TEAM_ID,
        "WORKSPACE_ID": WORKSPACE_ID,
        "VIDEO_PROJECT_ID": PROJECT_ID,
        "VIDEO_DATASET_ID": DATASET_ID,
    },
)

STORAGE_DIR = sly.app.get_data_dir()

# constants
BY_CLS_NAME = "by_class_name"
BY_OBJ_KEY = "by_object_key"
FRAMES = "frames"
TAGS = "tags"
