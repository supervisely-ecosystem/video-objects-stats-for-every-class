from supervisely.app.widgets import Card, Container, FastTable

fast_table = FastTable()

card = Card(
    title="Objects",
    description="general statistics for every single object in dataset/project",
    content=Container(widgets=[fast_table]),
)
