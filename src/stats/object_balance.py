import json

import pandas as pd

import src.globals as g
import supervisely as sly


def prepare_video_name_with_link(video_info, frame):
    """Prepare video name for table if it is too long"""
    video_name = video_info.name
    if len(video_name) > 50:
        video_name = video_name[:40] + "..." + video_name[-10:]
    link = sly.video.get_labeling_tool_url(
        video_info.dataset_id, video_info.id, frame=frame, link=True, link_text=video_name
    )
    return link


def seconds_to_time(seconds):
    """Convert seconds to time"""
    if seconds is None:
        return "-"
    if isinstance(seconds, str):
        seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"


def calculate_video_tags_stats(video_info, video_ann, project_meta):
    """Calculate stats for video-level frame-based tags"""
    tag_stats = {}
    
    # Get video-level tags
    for tag in video_ann.tags:
        tag_name = tag.meta.name
        
        if tag_name not in tag_stats:
            tag_stats[tag_name] = {
                'total_frames': 0,
                'frame_ranges': [],
                'first_frame': None,
                'last_frame': None
            }
        
        # Count frames for this tag
        if tag.frame_range is not None:
            # Tag has a frame range
            start_frame = tag.frame_range[0]
            end_frame = tag.frame_range[1]
            frame_count = end_frame - start_frame + 1
            tag_stats[tag_name]['total_frames'] += frame_count
            tag_stats[tag_name]['frame_ranges'].append((start_frame, end_frame))
            
            # Update first and last frame
            if tag_stats[tag_name]['first_frame'] is None or start_frame < tag_stats[tag_name]['first_frame']:
                tag_stats[tag_name]['first_frame'] = start_frame
            if tag_stats[tag_name]['last_frame'] is None or end_frame > tag_stats[tag_name]['last_frame']:
                tag_stats[tag_name]['last_frame'] = end_frame
        else:
            # Tag applies to entire video or single frame
            tag_stats[tag_name]['total_frames'] += video_info.frames_count
            if tag_stats[tag_name]['first_frame'] is None:
                tag_stats[tag_name]['first_frame'] = 0
            tag_stats[tag_name]['last_frame'] = video_info.frames_count - 1
    
    return tag_stats


def calculate_objects_stats(videos_counts, need_to_add_tags=False):
    table_options = {"fixColumns": 1, "pageSize": 10}

    columns = [
        "#",
        "type",  # Changed from "class" to "type" to accommodate both objects and tags
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
        {"subtitle": "object or tag"},  # New column for type
        {"type": "class"},
        {"subtitle": "name"},
        {
            "subtitle": "name",
            "tooltip": "click to open video in labeling tool the first frame with current object",
        },
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
            # Process objects
            for obj_key, annotated_frames_count in objkey2frames_cnt.items():
                obj_figures_count = obj_figures[obj_key]
                try:
                    obj_class_name = objkey2class[obj_key]
                except KeyError:
                    extra_info = {"objkey2class": objkey2class, "video name": video_info.name}
                    sly.logger.warning(
                        "Object class with key {} not found. Skipping...".format(obj_key),
                        extra=extra_info,
                    )
                    continue
                row = [
                    object_id,  # obj_key,
                    "Object",  # Type
                    obj_class_name,
                    ds_name,
                    prepare_video_name_with_link(video_info, annotated_frames_count[1]),
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
            
            # Process video-level tags
            try:
                video_ann_json = g.api.video.annotation.download(video_info.id)
                video_ann = sly.VideoAnnotation.from_json(video_ann_json, g.PROJECT_META)
                video_tag_stats = calculate_video_tags_stats(video_info, video_ann, g.PROJECT_META)
                
                for tag_name, tag_data in video_tag_stats.items():
                    tag_row = [
                        object_id,
                        "Video Tag",  # Type
                        tag_name,
                        ds_name,
                        prepare_video_name_with_link(video_info, tag_data['first_frame'] if tag_data['first_frame'] is not None else 0),
                        seconds_to_time(video_info.duration),
                        video_info.frames_count,
                        tag_data['total_frames'],
                        round(tag_data['total_frames'] / video_info.frames_count * 100, 2) if video_info.frames_count > 0 else 0,
                        len(tag_data['frame_ranges']) if tag_data['frame_ranges'] else 1,  # Number of tag instances
                        tag_data['first_frame'] if tag_data['first_frame'] is not None else 0,
                        tag_data['last_frame'] if tag_data['last_frame'] is not None else video_info.frames_count - 1,
                    ]
                    
                    if need_to_add_tags:
                        for tag_meta in g.PROJECT_META.tag_metas:
                            if tag_meta.applicable_to != sly.TagApplicableTo.IMAGES_ONLY:
                                tag_row.append("")  # Video tags don't have object-level tags
                                tag_row.append("")
                    
                    data.append(tag_row)
                    object_id += 1
            except Exception as e:
                sly.logger.warning(f"Failed to process video tags for video {video_info.name}: {e}")
                continue

    df = pd.DataFrame(data, columns=columns)

    result = json.loads(df.to_json(orient="split"))
    result.update({"columnsOptions": columns_options, "options": table_options})

    return result
