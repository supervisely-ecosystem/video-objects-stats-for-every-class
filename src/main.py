import os
from collections import defaultdict
import supervisely_lib as sly
from supervisely_lib.video_annotation.key_id_map import KeyIdMap
import pandas as pd
import copy
from operator import add

my_app = sly.AppService()


TEAM_ID = int(os.environ['context.teamId'])
WORKSPACE_ID = int(os.environ['context.workspaceId'])
PROJECT_ID = int(os.environ['modal.state.slyProjectId'])
DATASET_ID = os.environ.get('modal.state.slyDatasetId', None)
if DATASET_ID is not None:
    DATASET_ID = int(DATASET_ID)
PROJECT = None


def process_video_annotation(ann, classes_counter, figures_counter, frames_counter):
    for obj in ann.objects:
        classes_counter[obj.obj_class.name] += 1
    for figure in ann.figures:
        figures_counter[figure.video_object.obj_class.name] += 1
    for frame in ann.frames:
        already_on_frame = []
        for fig in frame.figures:
            if fig.video_object.obj_class.name not in already_on_frame:
                frames_counter[fig.video_object.obj_class.name] += 1
                already_on_frame.append(fig.video_object.obj_class.name)
    return classes_counter, figures_counter, frames_counter


def data_counter(data, dataset, classes, classes_counter, figures_counter, frames_counter):
    for class_name in classes:
        data[dataset.name + '_objects'].append(classes_counter[class_name])
        data[dataset.name + '_figures'].append(figures_counter[class_name])
        data[dataset.name + '_frames'].append(frames_counter[class_name])
    data['total_objects'] = list(map(add, data['total_objects'], data[dataset.name + '_objects']))
    data['total_figures'] = list(map(add, data['total_figures'], data[dataset.name + '_figures']))
    data['total_frames'] = list(map(add, data['total_frames'], data[dataset.name + '_frames']))

    return data


@my_app.callback("calculate_stats")
@sly.timeit
def calculate_stats(api: sly.Api, task_id, context, state, app_logger):
    api.task.set_field(task_id, "data.started", True)

    meta_json = api.project.get_meta(PROJECT.id)
    meta = sly.ProjectMeta.from_json(meta_json)
    if len(meta.obj_classes) == 0:
        raise ValueError("There are no object classes in project")
    counter = defaultdict(int)

    columns = ['total: objects', 'total: figures', 'total: frames']
    total_counter = defaultdict(int)
    datasets_counts = []

    key_id_map = KeyIdMap()
    for dataset in api.dataset.get_list(project.id):
        columns.extend([dataset.name + ': objects', dataset.name + ': figures', dataset.name + ': frames'])
        ds_objects = defaultdict(int)
        ds_figures = defaultdict(int)
        ds_frames = defaultdict(int)

        videos = api.video.get_list(dataset.id)
        for video_info in videos:
            ann_info = api.video.annotation.download(video_info.id)
            ann = sly.VideoAnnotation.from_json(ann_info, meta, key_id_map)
            objects, figures, frames = process_video_annotation(ann, classes_counter, figures_counter, frames_counter)

        data = data_counter(data, dataset, classes, classes_counter, figures_counter, frames_counter)
        datasets_counts.append(ds_counter)

    classes.append('Total')
    for key, val in data.items():
        data[key].append(sum(val))
    df = pd.DataFrame(data, columns=columns, index=classes)
    print(df)

    api.task.set_field(task_id, "data.loading", False)
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

    #input card
    data["projectId"] = PROJECT.id
    data["projectName"] = PROJECT.name
    data["projectPreviewUrl"] = api.image.preview_url(PROJECT.reference_image_url, 100, 100)
    data["progressCurrent"] = 0
    data["progressTotal"] = PROJECT.items_count
    data["loading"] = True
    data["table"] = {"columns": [], "data": []}

    # Run application service
    my_app.run(data=data, state=state, initial_events=[{"command": "calculate_stats"}])


if __name__ == "__main__":
    sly.main_wrapper("main", main)