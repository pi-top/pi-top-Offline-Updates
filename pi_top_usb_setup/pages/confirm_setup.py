from pt_miniscreen.components.confirmation_page import ConfirmationPage
from pt_miniscreen.components.mixins import HasGutterIcons
from pt_miniscreen.utils import get_image_file_path


class ConfirmSetupPage(ConfirmationPage, HasGutterIcons):
    def __init__(self, parent, on_confirm, on_cancel, **kwargs):
        super().__init__(
            parent=parent,
            on_confirm=on_confirm,
            on_cancel=on_cancel,
            title="Configure pi-top from this usb drive?",
            confirm_text="Yes",
            cancel_text="No",
            font_size=12,
            options_font_size=12,
            title_max_height=28,
            **kwargs,
        )

    def top_gutter_icon(self):
        return None

    def bottom_gutter_icon(self):
        return get_image_file_path("gutter/tick.png")
