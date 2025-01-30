import src.functions as f
import src.globals as g
import src.ui.class_stats as class_stats
import src.ui.controls as controls
import src.ui.input as input
import src.ui.object_stats as object_stats
import src.ui.output as output
from fastapi import Request
import supervisely as sly
from supervisely.app.widgets import Container

input_output = Container(
    widgets=[input.card, controls.card, output.card], direction="horizontal", fractions=[1, 1, 1]
)

layout = Container(widgets=[input_output, class_stats.card, object_stats.card])


@controls.start_btn.click
def calculate_stats():
    # ui
    controls.text.hide()
    controls.start_btn.disable()
    need_to_add_tags = controls.tags_checkbox.is_checked()
    controls.tags_checkbox.hide()

    # calculate and set stats
    cls_stats, obj_stats = f.calculate_stats(need_to_add_tags)
    class_stats.fast_table.read_json(cls_stats, meta=g.PROJECT_META)
    object_stats.fast_table.read_json(obj_stats, meta=g.PROJECT_META)

    # ui
    controls.progress.hide()
    controls.text.show()
    controls.text.set("Calculating statistics finished. Uploading to Team Files...", status="info")

    # upload stats to team files
    report_info = f.save_report(cls_stats, obj_stats)

    # ui
    output.output_thumbnail.set(report_info)
    controls.text.set("Statistics calculated and uploaded to Team Files", status="success")
    controls.finish_text.show()


app = sly.Application(layout=layout)


server = app.get_server()

@server.post("/my_method")
def my_method(request: Request):
    print("Custom exception will be raised")
    raise Exception("Test exception")
