from supervisely.app.widgets import Card, Container, FastTable

fast_table = FastTable()

card = Card(
    title="Class Balance",
    description="general statistics and balances for every class",
    content=Container(widgets=[fast_table]),
)
