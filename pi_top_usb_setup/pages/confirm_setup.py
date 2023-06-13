from pt_miniscreen.components.confirmation_page import ConfirmationPage


class ConfirmSetupPage(ConfirmationPage):
    def __init__(self, parent, on_confirm, on_cancel, **kwargs):
        super().__init__(
            parent=parent,
            on_confirm=on_confirm,
            on_cancel=on_cancel,
            title="Would you like to configure your pi-top from this usb drive?",
            confirm_text="Yes",
            cancel_text="No",
            font_size=10,
            options_font_size=10,
            title_max_height=33,
            **kwargs,
        )
