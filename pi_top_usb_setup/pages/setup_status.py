import logging

from pt_miniscreen.components.mixins import HasGutterIcons
from pt_miniscreen.core.component import Component
from pt_miniscreen.core.components import Text
from pt_miniscreen.utils import get_image_file_path

from pi_top_usb_setup.mixins import HandlesAllButtons
from pi_top_usb_setup.utils import close_app

logger = logging.getLogger(__name__)


class SetupStatusPage(Component, HandlesAllButtons, HasGutterIcons):
    def __init__(self, message: str, **kwargs):
        super().__init__(**kwargs)
        self.text_component = self.create_child(
            Text,
            text=message,
            font_size=10,
            align="center",
            vertical_align="center",
            wrap=True,
        )

    def handle_button_press(self):
        close_app()

    def render(self, image):
        return self.text_component.render(image)

    def top_gutter_icon(self):
        return None

    def bottom_gutter_icon(self):
        return get_image_file_path("gutter/tick.png")
