from supervisely.app.widgets import Card, Container, DatasetThumbnail, ProjectThumbnail

import src.globals as g

input_thumbnail = ProjectThumbnail(g.PROJECT)
if g.DATASET is not None:
    input_thumbnail = DatasetThumbnail(g.PROJECT, g.DATASET)

card = Card(
    title="Input",
    content=Container(widgets=[input_thumbnail]),
)
