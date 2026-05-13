"""
Generic background worker — runs any callable in a QThread.
Emits result_ready(object) on success, error_occurred(str) on exception.
"""

from PySide6.QtCore import QThread, Signal


class ServiceWorker(QThread):
    result_ready = Signal(object)
    error_occurred = Signal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            result = self._func(*self._args, **self._kwargs)
            self.result_ready.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))
