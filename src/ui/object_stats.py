from supervisely.app.widgets import Card, Container, FastTable

fast_table = FastTable()

card = Card(
    title="Objects and Tags",
    description="general statistics for every single object and video-level frame-based tag in dataset/project",
    content=Container(widgets=[fast_table]),
)
