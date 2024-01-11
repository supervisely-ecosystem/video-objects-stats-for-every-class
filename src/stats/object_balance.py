import json

import pandas as pd

import src.globals as g
import supervisely as sly


def prepare_video_name(video_name):
    """Prepare video name for table if it is too long"""
    if len(video_name) > 50:
        video_name = video_name[:45] + "..." + video_name[-10:]
    return video_name


def seconds_to_time(seconds):
    """Convert seconds to time"""
    if seconds is None:
        return "-"
    if isinstance(seconds, str):
        seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def calculate_objects_stats(videos_counts, need_to_add_tags=False):
    table_options = {"fixedColumns": 2, "pageSize": 20}

    if len(g.PROJECT_META.obj_classes) == 0:
        sly.logger.warn("There are no object in the project")
        sly.app.show_dialog(
            title="No object classes",
            description="There are no object classes in the project",
            status="warning",
        )
        return {"data": [], "columns": [], "columnsOptions": {}, "options": {}}

    columns = [
        "#",
        "class",
        "dataset",
        "video",
        "video duration",
        "video duration",
        "frames",
        "presence in video",  # = time stamp of last figure – time stamp of first figure // or by calculation using the frames/seconds measure)
        "figures",
        "first frame",
        "last frame",
        # "frame size",
        # "average area",
        # "average width",
        # "average width",
        # "average height",
        # "average height",
    ]
    columns_options = [
        {},
        {"type": "class"},
        {"subtitle": "name"},
        {"subtitle": "name"},
        {"subtitle": "time"},
        {"subtitle": "frames count", "postfix": "frames"},
        {"subtitle": "count with current object", "postfix": "frames"},
        {
            "subtitle": "% of video",
            "postfix": "%",
            "maxValue": 100,
            "tooltip": "percentage of frames with current object in the video",
        },
        {"subtitle": "count", "postfix": "figures"},
        {"subtitle": "frame index", "tooltip": "first frame index with current object"},
        {"subtitle": "frame index", "tooltip": "last frame index with current object"},
    ]

    if need_to_add_tags:
        for tagmeta in g.PROJECT_META.tag_metas:
            if tagmeta.applicable_to != sly.TagApplicableTo.IMAGES_ONLY:
                columns.append(f"tag: {tagmeta.name}")
                columns_options.append({"subtitle": "object property tag", "postfix": "tagged"})
                columns.append(f"tag: {tagmeta.name}")
                columns_options.append({"subtitle": "object frame tag", "postfix": "frames"})

    data = []
    object_id = 1
    for ds_name, videos_list in videos_counts.items():
        for video_info, objkey2class, objkey2frames_cnt, objkey2tags, obj_figures in videos_list:
            for obj_key, annotated_frames_count in objkey2frames_cnt.items():
                obj_figures_count = obj_figures[obj_key]
                obj_class_name = objkey2class[obj_key]
                row = [
                    object_id,  # obj_key,
                    obj_class_name,
                    ds_name,
                    prepare_video_name(video_info.name),
                    seconds_to_time(video_info.duration),
                    video_info.frames_count,
                    annotated_frames_count[0],
                    round(obj_figures_count / video_info.frames_count * 100, 2),
                    obj_figures_count,
                    annotated_frames_count[1],
                    annotated_frames_count[2],
                ]
                if need_to_add_tags:
                    for tag_meta in g.PROJECT_META.tag_metas:
                        if tag_meta.applicable_to != sly.TagApplicableTo.IMAGES_ONLY:
                            object_tag = ""
                            frame_ranges_tags = []
                            tags = objkey2tags[obj_key].get_by_name(tag_meta.name)
                            if len(tags) == 0:
                                row.append("")
                                row.append("")
                                continue
                            for tag in tags:
                                if tag.frame_range is None:
                                    txt = "✅"
                                    if tag_meta.value_type != sly.TagValueType.NONE:
                                        txt = txt + f" value: {tag.value}"
                                    object_tag = txt
                                else:
                                    frame_ranges_tags.append(
                                        f"{tag.frame_range[0]}-{tag.frame_range[1]}"
                                    )
                            row.append(object_tag)
                            if len(frame_ranges_tags) > 0:
                                row.append(", ".join(frame_ranges_tags))
                            else:
                                row.append("")

                data.append(row)
                object_id += 1

    df = pd.DataFrame(data, columns=columns)

    result = json.loads(df.to_json(orient="split"))
    result.update({"columnsOptions": columns_options, "options": table_options})

    return result
