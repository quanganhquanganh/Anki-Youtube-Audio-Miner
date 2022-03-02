from mwui import Ui_SetFields

class SetFields(Ui_SetFields):
    def __init__(self, parent=None):
        super().__init__()
        self.setupUi()

    def setupUi(self):
        return

    def set_fields(self, fields):
        self.fields = fields
        self.field_list.clear()
        for field in fields:
            self.field_list.addItem(field)
    