from supervisely.app.widgets import Button, Card, Checkbox, Container, Progress, Text

tags_checkbox = Checkbox("Add tags info to the report", checked=True)
start_btn = Button("Start", button_size="mini")
progress = Progress(hide_on_finish=False)
text = Text(color="#697c8d")
text.hide()
finish_text = Text("Please, finish the app after you are done.", status="info")
finish_text.hide()

card = Card(
    title="Controls",
    content=Container(widgets=[progress, tags_checkbox, text, finish_text]),
    content_top_right=start_btn,
)
