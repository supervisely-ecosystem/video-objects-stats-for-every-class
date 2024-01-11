from supervisely.app.widgets import Card, Container, FolderThumbnail

output_thumbnail = FolderThumbnail()

card = Card(
    title="Output",
    content=Container(widgets=[output_thumbnail]),
)
