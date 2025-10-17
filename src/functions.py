import os
from collections import defaultdict

import pandas as pd

import src.globals as g
import src.ui.controls as c
import supervisely as sly
from src.stats import class_balance, object_balance


def process_video_annotation(
    ann,
    class_objects_counter,
    class_figures_counter,
    objcls_frames_counter,
    obj_figures_counter,
):
    classname2frames = objcls_frames_counter.setdefault(g.BY_CLS_NAME, {})
    objkey_dict = objcls_frames_counter.setdefault(g.BY_OBJ_KEY, {})
    objkey2frames = objkey_dict.setdefault(g.FRAMES, {})
    objkey2tags = objkey_dict.setdefault(g.TAGS, {})
    for obj in ann.objects:
        obj: sly.VideoObject
        tags_collection = obj.tags
        objkey2tags[str(obj.key())] = tags_collection
        class_objects_counter[obj.obj_class.name] += 1
    for frame in ann.frames:
        frame: sly.Frame
        cls_already_on_frame = set()
        obj_already_on_frame = set()
        for fig in frame.figures:
            fig: sly.VideoFigure
            class_figures_counter[fig.video_object.obj_class.name] += 1
            obj_figures_counter[str(fig.video_object.key())] += 1
            if fig.video_object.obj_class.name not in cls_already_on_frame:
                classname2frames.setdefault(fig.video_object.obj_class.name, []).append(frame.index)
                cls_already_on_frame.add(fig.video_object.obj_class.name)

            if fig.video_object.key() not in obj_already_on_frame:
                objkey2frames.setdefault(str(fig.video_object.key()), []).append(frame.index)
                obj_already_on_frame.add(fig.video_object.key())


def get_annotated_frames_count_by_classes_in_dataset(ds_frames):
    """Return dict with class name as key and annotated frames count as value"""
    object_name_to_annotated_frames = defaultdict(int)
    for video_name, objects_on_video in ds_frames.items():
        for obj_name, annotated_frames_list in objects_on_video[g.BY_CLS_NAME].items():
            object_name_to_annotated_frames[obj_name] += len(annotated_frames_list)
    return object_name_to_annotated_frames


def get_frames_tags_by_objects_on_videos(video_frames):
    """
    Return:
        - dict with object key as key and value is tuple with annotated frames count,
    first annotated frame and last annotated frame
        - dict with object key as key and all tags for this object as value
    """
    objkey_to_annotated_frames = defaultdict(lambda: defaultdict(int))
    objkey_to_tags = defaultdict(lambda: defaultdict(int))
    for obj_key, frames_list in video_frames[g.BY_OBJ_KEY][g.FRAMES].items():
        objkey_to_annotated_frames[obj_key] = (len(frames_list), min(frames_list), max(frames_list))
    for obj_key, tags in video_frames[g.BY_OBJ_KEY][g.TAGS].items():
        objkey_to_tags[obj_key] = tags
    return objkey_to_annotated_frames, objkey_to_tags


def process_project():
    # Determine scope and total count
    if g.DATASET_ID is not None:
        # Dataset-level execution (including nested datasets)
        parent_dataset = g.api.dataset.get_info_by_id(g.DATASET_ID)

        # Get all datasets recursively and filter by parent relationship
        all_datasets = g.api.dataset.get_list(g.PROJECT.id, recursive=True)

        # Include the selected dataset and all its direct children
        datasets_to_process = [parent_dataset]  # Start with the selected dataset

        # Add all datasets that have the selected dataset as parent
        for dataset in all_datasets:
            if dataset.parent_id == g.DATASET_ID:
                datasets_to_process.append(dataset)

        # Calculate total count for all selected datasets
        total_count = sum(dataset.items_count for dataset in datasets_to_process)

        sly.logger.info(f"Processing dataset: {parent_dataset.name} (ID: {g.DATASET_ID})")
        sly.logger.info(f"Found {len(datasets_to_process)} datasets to process (including nested)")
    else:
        # Project-level execution
        total_count = g.PROJECT.items_count
        datasets_to_process = g.api.dataset.get_list(g.PROJECT.id, recursive=True)
        sly.logger.info(
            f"Processing entire project: {g.PROJECT.name} ({len(datasets_to_process)} datasets)"
        )

    datasets_counts = []
    videos_counts = defaultdict(list)

    key_id_map = sly.KeyIdMap()
    with c.progress(total=total_count, message="Processing video labels ...") as pbar:
        for dataset in datasets_to_process:
            # for classes stats
            ds_objects = defaultdict(int)
            ds_figures = defaultdict(int)

            # for objects stats
            obj_figures = defaultdict(int)

            # common for both stats
            ds_frames = g.ANNOTATED_FRAMES.setdefault(dataset.name, {})

            videos = g.api.video.get_list(dataset.id)
            for video_info in videos:

                ann_info = g.api.video.annotation.download(video_info.id)
                try:
                    ann = sly.VideoAnnotation.from_json(ann_info, g.PROJECT_META, key_id_map)
                except Exception as e:
                    err_msg = "An error occured while deserialization. Skipping annotation..."
                    debug_info = {
                        "json annotation": ann_info,
                        "key id map": key_id_map,
                        "exception message": repr(e),
                    }
                    sly.logger.error(err_msg, extra=debug_info)
                    continue
                video_frames = ds_frames.setdefault(video_info.name, {})

                process_video_annotation(ann, ds_objects, ds_figures, video_frames, obj_figures)
                objkey2frames_cnt, objkey2tags = get_frames_tags_by_objects_on_videos(video_frames)
                objkey2classname = {str(obj.key()): obj.obj_class.name for obj in ann.objects}
                videos_counts[dataset.name].append(
                    (video_info, objkey2classname, objkey2frames_cnt, objkey2tags, obj_figures)
                )
                pbar.update(1)

            obj_name2annotated_frames_count = get_annotated_frames_count_by_classes_in_dataset(
                ds_frames
            )
            datasets_counts.append(
                (dataset.name, ds_objects, ds_figures, obj_name2annotated_frames_count)
            )

    return datasets_counts, videos_counts


def calculate_stats(need_to_add_tags=False):
    datasets_counts, videos_counts = process_project()

    classes_stats = class_balance.calculate_classes_stats(datasets_counts)
    objects_stats = object_balance.calculate_objects_stats(videos_counts, need_to_add_tags)

    return classes_stats, objects_stats


def download_csv(data, filename):
    """Download csv file"""
    csv = pd.DataFrame(data["data"], columns=data["columns"])
    csv.to_csv(filename, index=False)


def save_report(cls_stats, obj_stats):
    """save report to file *.lnk (link to report)"""
    report_dir = os.path.join(g.STORAGE_DIR, "reports")
    sly.fs.mkdir(report_dir)

    report_name = f"{g.PROJECT.id}_{g.PROJECT.name}.lnk"
    report_path = os.path.join(report_dir, report_name)
    with open(report_path, "w") as text_file:
        print(g.api.app.get_url(g.TASK_ID), file=text_file)

    download_csv(cls_stats, os.path.join(report_dir, "classes_stats.csv"))
    download_csv(obj_stats, os.path.join(report_dir, "objects_stats.csv"))

    remote_path = f"/reports/video_objects_stats_for_every_class/{g.TASK_ID}"
    remote_path = g.api.file.get_free_dir_name(g.TEAM_ID, remote_path)
    report_path = os.path.join(remote_path, report_name)
    g.api.file.upload_directory(g.TEAM_ID, report_dir, remote_path)
    file_info = g.api.file.get_info_by_path(g.TEAM_ID, report_path)
    g.api.task.set_output_report(g.TASK_ID, file_info.id, report_name)

    sly.fs.remove_dir(report_dir)
    return file_info
