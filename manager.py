import sys

from PyQt5 import QtCore, QtWidgets

class TaskManager(QtCore.QObject):
    started = QtCore.pyqtSignal()
    finished = QtCore.pyqtSignal()
    progressChanged = QtCore.pyqtSignal(int, QtCore.QByteArray)

    def __init__(self, parent=None):
        QtCore.QObject.__init__(self, parent)
        self._process = QtCore.QProcess(self)
        self._process.finished.connect(self.handleFinished)
        self._progress = 0

    def start_tasks(self, tasks):
        self._tasks = iter(tasks)
        self.fetchNext()
        self.started.emit()
        self._progress = 0

    def add_task(self, task):
        self._tasks.append(task)

    def fetchNext(self):
            try:
                task = next(self._tasks)
            except StopIteration:
                return False
            else:
                self._process.start(*task)
            return True

    def processCurrentTask(self):
        output = self._process.readAllStandardOutput()
        self._progress += 1
        self.progressChanged.emit(self._progress, output)

    def handleFinished(self):
        self.processCurrentTask()
        if not self.fetchNext():
            self.finished.emit()