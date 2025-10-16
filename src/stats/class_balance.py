import json

import pandas as pd

import src.globals as g
import supervisely as sly


def get_total_frames_counts():
    annotated_frames_totals = {ds_name: 0 for ds_name in g.ANNOTATED_FRAMES.keys()}
    for ds_name, videos_dict in g.ANNOTATED_FRAMES.items():
        for video_name, annotated_frames_by_objects_dict in videos_dict.items():
            set_of_annotated_frames_for_video = set()
            for object_frames_list in annotated_frames_by_objects_dict[g.BY_CLS_NAME].values():
                set_of_annotated_frames_for_video = set_of_annotated_frames_for_video.union(
                    set(object_frames_list)
                )

            annotated_frames_totals[ds_name] += len(set_of_annotated_frames_for_video)
    return annotated_frames_totals


def update_totals_by_datasets(dsname2total, total_row, columns, column_base):
    for idx, (ds_name, total) in enumerate(dsname2total.items()):
        try:
            column_index_for_ds = columns.index(column_base[2]) + len(column_base) * idx
            total_row[column_index_for_ds] = total
        except Exception as ex:
            sly.logger.warning(f"Cannot define total for {ds_name}, reason: {repr(ex)}")

    if len(dsname2total) > 0 and g.DATASET_ID is None:
        total_by_datasets = sum(list(dsname2total.values()))
        # column_index = columns.index("total: frames")
        column_index = 4
        total_row[column_index] = total_by_datasets
    return total_row


def calculate_classes_stats(datasets_counts):
    table_options = {"fixColumns": 1, "pageSize": 10}

    if len(g.PROJECT_META.obj_classes) == 0:
        sly.logger.warn("There are no object classes in the project")
        sly.app.show_dialog(
            title="No object classes",
            description="There are no object classes in the project",
            status="warning",
        )
        return {"data": [], "columns": [], "columnsOptions": {}, "options": {}}

    columns = ["#", "class"]
    columns_options = [{}, {"type": "class"}]
    column_base = ["objects", "figures", "frames"]
    if g.DATASET_ID is None:
        columns.extend([f"total {name}" for name in column_base])
        columns_options.extend([{"subtitle": "in the project"} for name in column_base])

    for dataset in g.api.dataset.get_list(g.PROJECT.id, recursive=True):
        if g.DATASET_ID is not None and dataset.id != g.DATASET_ID:
            continue

        columns.extend(column_base)
        columns_options.extend(
            [{"subtitle": f"in '{dataset.name}' dataset"} for name in column_base]
        )

    data = []
    for idx, obj_class in enumerate(g.PROJECT_META.obj_classes):
        obj_class: sly.ObjClass
        name = obj_class.name
        row = [idx, name]
        if g.DATASET_ID is None:
            row.extend([0, 0, 0])

        for ds_name, ds_objects, ds_figures, ds_frames in datasets_counts:
            row.extend([ds_objects[name], ds_figures[name], ds_frames.get(name, 0)])
            if g.DATASET_ID is None:
                row[2] += ds_objects[name]
                row[3] += ds_figures[name]
                row[4] += ds_frames.get(name, 0)
        data.append(row)

    df = pd.DataFrame(data, columns=columns)
    total_row = list(df.sum(axis=0))
    total_row[0] = len(df)
    total_row[1] = "Total"

    dsname2total = get_total_frames_counts()
    total_row = update_totals_by_datasets(dsname2total, total_row, columns, column_base)
    df.loc[len(df)] = total_row
    data.append(total_row)

    result = json.loads(df.to_json(orient="split"))
    result.update({"columnsOptions": columns_options, "options": table_options})

    return result
