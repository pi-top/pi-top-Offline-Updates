import logging
from time import sleep

from pitop.common.command_runner import run_command
from pt_miniscreen.components.mixins import HasGutterIcons
from pt_miniscreen.core.component import Component
from pt_miniscreen.core.components import Text
from pt_miniscreen.utils import get_image_file_path

from pi_top_usb_setup.mixins import HandlesAllButtons
from pi_top_usb_setup.utils import close_app

logger = logging.getLogger(__name__)


class SetupStatusPage(Component, HandlesAllButtons, HasGutterIcons):
    def __init__(self, message: str, requires_reboot: bool, **kwargs):
        super().__init__(**kwargs)
        self.requires_reboot = requires_reboot
        self._text = message
        self.text_component = self.create_child(
            Text,
            text=self._text,
            get_text=lambda: self._text,
            font_size=10,
            align="center",
            vertical_align="center",
            wrap=True,
        )

    def handle_button_press(self):
        if self.requires_reboot:
            # Display a 'please wait' message in case the reboot animation
            # doesn't get displayed
            self._text = "Please wait ..."
            sleep(2)
            run_command("reboot", 20)
        else:
            close_app()

    def render(self, image):
        return self.text_component.render(image)

    def top_gutter_icon(self):
        return None

    def bottom_gutter_icon(self):
        return get_image_file_path("gutter/tick.png")
