import os
from collections import defaultdict
import pandas as pd
import json

import supervisely_lib as sly
from supervisely_lib.video_annotation.key_id_map import KeyIdMap

my_app = sly.AppService()

TEAM_ID = int(os.environ['context.teamId'])
WORKSPACE_ID = int(os.environ['context.workspaceId'])
PROJECT_ID = int(os.environ['modal.state.slyProjectId'])
DATASET_ID = os.environ.get('modal.state.slyDatasetId', None)
if DATASET_ID is not None:
    DATASET_ID = int(DATASET_ID)

PROJECT = None


def process_video_annotation(ann, objects_counter, figures_counter, frames_counter):
    for obj in ann.objects:
        objects_counter[obj.obj_class.name] += 1
    for frame in ann.frames:
        already_on_frame = set()
        for fig in frame.figures:
            figures_counter[fig.video_object.obj_class.name] += 1
            if fig.video_object.obj_class.name not in already_on_frame:
                frames_counter[fig.video_object.obj_class.name] += 1
                already_on_frame.add(fig.video_object.obj_class.name)


@my_app.callback("calculate_stats")
@sly.timeit
def calculate_stats(api: sly.Api, task_id, context, state, app_logger):
    total_count = PROJECT.items_count
    if DATASET_ID is not None:
        total_count = api.dataset.get_info_by_id(DATASET_ID).items_count
    progress = sly.Progress("Processing video labels ...", total_count, app_logger)

    fields = [
        {"field": "data.started", "payload": True},
        {"field": "data.progressCurrent", "payload": 0},
        {"field": "data.progressTotal", "payload": total_count},
    ]
    api.app.set_fields(task_id, fields)

    meta_json = api.project.get_meta(PROJECT.id)
    meta = sly.ProjectMeta.from_json(meta_json)
    if len(meta.obj_classes) == 0:
        raise ValueError("There are no object classes in project")

    columns = ['#', 'class']
    if DATASET_ID is None:
        columns.extend(['total: objects', 'total: figures', 'total: frames'])

    datasets_counts = []

    key_id_map = KeyIdMap()
    for dataset in api.dataset.get_list(PROJECT.id):
        if DATASET_ID is not None and dataset.id != DATASET_ID:
            continue

        columns.extend([dataset.name + ': objects', dataset.name + ': figures', dataset.name + ': frames'])
        ds_objects = defaultdict(int)
        ds_figures = defaultdict(int)
        ds_frames = defaultdict(int)

        videos = api.video.get_list(dataset.id)
        for video_info in videos:
            ann_info = api.video.annotation.download(video_info.id)
            ann = sly.VideoAnnotation.from_json(ann_info, meta, key_id_map)
            process_video_annotation(ann, ds_objects, ds_figures, ds_frames)
            progress.iter_done_report()
            api.app.set_fields(task_id, fields=[
                {"field": "data.progressCurrent", "payload": progress.current},
                {"field": "data.progress", "payload": int(progress.current * 100 / total_count)},
            ])
        datasets_counts.append((dataset.name, ds_objects, ds_figures, ds_frames))

    data = []
    for idx, obj_class in enumerate(meta.obj_classes):
        obj_class: sly.ObjClass
        name = obj_class.name
        row = [idx, name]
        if DATASET_ID is None:
            row.extend([0, 0, 0])

        for ds_name, ds_objects, ds_figures, ds_frames in datasets_counts:
            row.extend([ds_objects[name], ds_figures[name], ds_frames[name]])
            if DATASET_ID is None:
                row[2] += ds_objects[name]
                row[3] += ds_figures[name]
                row[4] += ds_frames[name]
        data.append(row)

    df = pd.DataFrame(data, columns=columns)
    total_row = list(df.sum(axis=0))
    total_row[0] = len(df)
    total_row[1] = 'Total'
    df.loc[len(df)] = total_row
    #df = df.append(total_row, ignore_index=True)

    # save report to file *.lnk (link to report)
    report_name = "{}_{}.lnk".format(PROJECT.id, PROJECT.name)
    local_path = os.path.join(my_app.data_dir, report_name)
    sly.fs.ensure_base_path(local_path)
    with open(local_path, "w") as text_file:
        print(my_app.app_url, file=text_file)
    remote_path = "/reports/video_objects_stats/{}".format(report_name)
    remote_path = api.file.get_free_name(TEAM_ID, remote_path)
    report_name = sly.fs.get_file_name_with_ext(remote_path)
    file_info = api.file.upload(TEAM_ID, local_path, remote_path)
    report_url = api.file.get_url(file_info.id)

    fields = [
        {"field": "data.loading", "payload": False},
        {"field": "data.table", "payload": json.loads(df.to_json(orient="split"))},
        {"field": "data.savePath", "payload": remote_path},
        {"field": "data.reportName", "payload": report_name},
        {"field": "data.reportUrl", "payload": report_url},
    ]
    api.app.set_fields(task_id, fields)
    my_app.stop()


def main():
    global PROJECT
    sly.logger.info("Script arguments", extra={
        "TEAM_ID": TEAM_ID,
        "WORKSPACE_ID": WORKSPACE_ID,
        "VIDEO_PROJECT_ID": PROJECT_ID,
        "VIDEO_DATASET_ID": DATASET_ID
    })

    api = my_app.public_api
    PROJECT = api.project.get_info_by_id(PROJECT_ID)
    if PROJECT is None:
        raise RuntimeError("Project {!r} not found".format(PROJECT.name))
    if PROJECT.type != str(sly.ProjectType.VIDEOS):
        raise TypeError("Project type is {!r}, but has to be {!r}".format(PROJECT.type, sly.ProjectType.VIDEOS))

    data = {}
    state = {}

    # input card
    data["projectId"] = PROJECT.id
    data["projectName"] = PROJECT.name
    data["projectPreviewUrl"] = api.image.preview_url(PROJECT.reference_image_url, 100, 100)

    # output card
    data["progressCurrent"] = 0
    data["progressTotal"] = PROJECT.items_count
    data["progress"] = 0
    data["loading"] = True

    # sly-table
    data["table"] = {"columns": [], "data": []}

    # Run application service
    my_app.run(data=data, state=state, initial_events=[{"command": "calculate_stats"}])


if __name__ == "__main__":
    sly.main_wrapper("main", main)