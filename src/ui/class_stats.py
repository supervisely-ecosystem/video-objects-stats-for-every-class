from supervisely.app.widgets import Card, Container, FastTable

fast_table = FastTable(fixed_columns=2)

card = Card(
    title="Class Balance",
    description="general statistics and balances for every class",
    content=Container(widgets=[fast_table]),
)
