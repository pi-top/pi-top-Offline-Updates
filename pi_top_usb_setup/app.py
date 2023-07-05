import logging
import traceback

from pitop.system.pitop import Pitop
from pt_miniscreen.core import App as BaseApp
from pt_miniscreen.utils import ButtonEvents

from .root import RootComponent

logger = logging.getLogger(__name__)


class UsbSetupApp(BaseApp):
    def __init__(self):
        self.miniscreen = Pitop().miniscreen

        self.miniscreen.select_button.when_released = self.create_button_handler(
            lambda: self.root.handle_button(ButtonEvents.SELECT_RELEASE)
        )
        self.miniscreen.cancel_button.when_released = self.create_button_handler(
            lambda: self.root.handle_button(ButtonEvents.CANCEL_RELEASE)
        )
        self.miniscreen.up_button.when_released = self.create_button_handler(
            lambda: self.root.handle_button(ButtonEvents.UP_RELEASE)
        )
        self.miniscreen.down_button.when_released = self.create_button_handler(
            lambda: self.root.handle_button(ButtonEvents.DOWN_RELEASE)
        )
        self.miniscreen.up_button.when_pressed = self.create_button_handler(
            lambda: self.root.handle_button(ButtonEvents.UP_PRESS)
        )
        self.miniscreen.down_button.when_pressed = self.create_button_handler(
            lambda: self.root.handle_button(ButtonEvents.DOWN_PRESS)
        )

        super().__init__(
            display=self.miniscreen.device.display,
            Root=RootComponent,
            size=self.miniscreen.size,
        )

    def create_button_handler(self, func):
        def handler():
            try:
                if callable(func):
                    func()

            except Exception as e:
                logger.error("Error in button handler: " + str(e))
                traceback.print_exc()
                self.stop(e)

        return handler
