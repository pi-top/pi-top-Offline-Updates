import logging
import os
from functools import partial
from typing import Dict

from pt_miniscreen.components.mixins import Actionable, HasGutterIcons, Navigable
from pt_miniscreen.components.right_gutter import RightGutter
from pt_miniscreen.core.component import Component
from pt_miniscreen.core.components import Stack
from pt_miniscreen.core.utils import apply_layers, layer
from pt_miniscreen.utils import ButtonEvents

from pi_top_usb_setup.mixins import HandlesAllButtons
from pi_top_usb_setup.pages import ConfirmSetupPage, RunSetupPage, SetupStatusPage
from pi_top_usb_setup.utils import close_app, umount_usb_drive

logger = logging.getLogger(__name__)


class RootComponent(Component):
    right_gutter_width = 10
    gutter_icon_padding = (3, 7)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        def on_complete(data: Dict):
            message = data.get("message", "")
            requires_reboot = data.get("requires_reboot", False)
            logger.info(
                f"Setup finished with message {message}; needs reboot: {requires_reboot}"
            )
            self.stack.push(
                partial(SetupStatusPage, message, requires_reboot), animate=False
            )
            self._set_gutter_icons()

        def on_confirm():
            logger.info("User confirmed, starting setup process...")
            self.stack.push(
                partial(RunSetupPage, on_complete=on_complete), animate=False
            )
            self._set_gutter_icons()

        def on_cancel():
            logger.info("User cancelled, exiting...")
            umount_usb_drive(os.environ.get("PT_USB_SETUP_MOUNT_POINT", ""))
            close_app()

        self.stack = self.create_child(Stack)

        if os.environ.get("PT_USB_SETUP_SKIP_DIALOG") == "1":
            logger.info(
                "Skipping confirmation dialog; script called with --skip-dialog"
            )
            self.stack.push(partial(RunSetupPage, on_complete=on_complete))
        else:
            self.stack.push(
                partial(
                    ConfirmSetupPage,
                    parent=self,
                    on_confirm=on_confirm,
                    on_cancel=on_cancel,
                )
            )

        self.right_gutter = self.create_child(
            RightGutter,
            upper_icon_padding=self.gutter_icon_padding,
            lower_icon_padding=self.gutter_icon_padding,
        )
        self._set_gutter_icons()

    @property
    def active_component(self):
        return self.stack.active_component

    def handle_button(
        self,
        button_event: ButtonEvents,
    ):
        logger.info(f"Handling {button_event} for component {self.active_component}")

        try:
            if isinstance(self.active_component, HandlesAllButtons):
                self.active_component.handle_button_press()

            if isinstance(self.active_component, Actionable):
                if button_event == ButtonEvents.SELECT_RELEASE:
                    self.active_component.perform_action()
                    return

            if isinstance(self.active_component, Navigable):
                if button_event == ButtonEvents.UP_RELEASE:
                    self.active_component.go_previous()
                    return

                if button_event == ButtonEvents.DOWN_RELEASE:
                    self.active_component.go_next()
                    return

                if button_event == ButtonEvents.CANCEL_RELEASE:
                    self.active_component.go_top()
                    return

        except Exception as e:
            logger.error(f"Error: {e}")
            if self.active_component is None:
                self.stack.pop()
        finally:
            self._set_gutter_icons()

    def _set_gutter_icons(self):
        if isinstance(self.active_component, HasGutterIcons):
            self.right_gutter.state.update(
                {
                    "upper_icon_path": self.active_component.top_gutter_icon(),
                    "lower_icon_path": self.active_component.bottom_gutter_icon(),
                }
            )

    def render(self, image):
        if isinstance(self.active_component, HasGutterIcons):
            return apply_layers(
                image,
                (
                    layer(
                        self.stack.render,
                        size=(image.width - self.right_gutter_width, image.height),
                    ),
                    layer(
                        self.right_gutter.render,
                        size=(self.right_gutter_width, image.height),
                        pos=(image.size[0] - self.right_gutter_width, 0),
                    ),
                ),
            )

        return self.stack.render(image)
