from PyQt5 import QtWidgets

def error_message(text,title="Error has occured"):
	dialog = QtWidgets.QMessageBox()
	dialog.setWindowTitle(title)
	dialog.setText(text)
	dialog.setIcon(QtWidgets.QMessageBox.Warning)
	dialog.exec_()