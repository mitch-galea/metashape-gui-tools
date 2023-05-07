import time
from pathlib import Path
from typing import Optional, Dict, List, Callable

from abyss.robotics.metashape.utilities import get_camera

from PySide2.QtWidgets import (
    QApplication,
    QMainWindow,
    QDockWidget,
    QListWidget,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QListWidgetItem,
    QAbstractItemView,
    QFileDialog,
)
from PySide2 import QtCore

import Metashape


def find_main_window() -> Optional[QMainWindow]:
    """function to find the open QMainWindow in an application
    if not found will return None
    """
    app = QApplication.instance()
    for widget in app.topLevelWidgets():
        if isinstance(widget, QMainWindow):
            return widget
    return None


class CameraMonitor(QtCore.QObject):
    """monitors the cameras in Metashape.app.document.chunk"""

    camera_signal = QtCore.Signal()

    def __init__(self, app: Metashape.Application) -> None:
        """initialises with application"""
        super().__init__()
        self.app = app

        self.camera_labels: List[str] = None
        """previous list of camera labels"""

        self.stop = False
        """used to stop the thread"""

    @QtCore.Slot()
    def monitor_cameras(self) -> None:
        """monitors cameras"""
        while not self.stop:
            time.sleep(1.0)
            if not self.app.document:
                continue
            if not self.app.document.chunk:
                continue
            camera_labels = [camera.label for camera in self.app.document.chunk.cameras]
            if not self.camera_labels:
                self.camera_labels = camera_labels
                continue
            if not camera_labels == self.camera_labels:
                self.camera_labels = camera_labels
                self.camera_signal.emit()


class CameraSelector(QWidget):
    """widget for selecting cameras to export

    the widget will provide a list of cameras in the chunk
    each camera will have a checkbox next to it

    you can manually select cameras
    or you can use the 'Add Selected' button, which will
    select all the selected cameras.
    you can clear the selection with the clear button.

    once all are selected you can export the selected camera paths.
    """

    def __init__(self, app: Metashape.Application) -> None:
        """initialises the widget

        Args:
            app (Metashape.Application): metashape app
        """
        super().__init__()

        self.app = app
        """metashape application"""

        self.list = QListWidget()
        """list containing cameras"""

        self.items: Dict[str, QListWidgetItem] = {}
        """dict of camera items, key is camera name"""

        self.initialise_widget()

        self.update_cameras()

    def initialise_widget(self) -> None:
        """initialises the widget layout"""
        layout = QVBoxLayout()
        button_layout = QHBoxLayout()

        def _create_button(
            layout: QHBoxLayout, label: str, callback: Callable[[], None]
        ) -> None:
            """creates button"""
            button = QPushButton(label)
            button.clicked.connect(callback)
            layout.addWidget(button)

        buttons = [
            ("Add Selected", self.check_selected),
            ("Select Checked", self.select_checked),
            ("Clear", self.clear_selected),
            ("Update Cameras", self.update_cameras),
            ("Export", self.export_cameras),
        ]
        for button in buttons:
            _create_button(layout=button_layout, label=button[0], callback=button[1])
        layout.addLayout(button_layout)
        layout.addWidget(self.list)
        self.list.itemSelectionChanged.connect(self.update_items)
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    # def start_cameras_monitor(self) -> None:
    #     """starts the camera monitor to check for changes in cameras"""
    #     self.camera_monitor = CameraMonitor(app=self.app)
    #     self.camera_monitor_thread = QtCore.QThread(self)
    #     self.camera_monitor.camera_signal.connect(self.update_cameras)
    #     self.camera_monitor.moveToThread(self.camera_monitor_thread)
    #     self.camera_monitor_thread.started.connect(self.camera_monitor.monitor_cameras)
    #     self.camera_monitor_thread.start()

    # def stop_cameras_monitor(self):
    #     """stops the camera monitor thread"""
    #     self.camera_monitor.stop = True
    #     self.camera_monitor_thread.quit()
    #     self.camera_monitor_thread.wait()

    # def closeEvent(self, event) -> None:
    #     """close event"""
    #     self.stop_cameras_monitor()

    @QtCore.Slot()
    def update_cameras(self) -> None:
        """updates the cameras list"""
        self.list.clear()
        self.items.clear()
        for camera in self.app.document.chunk.cameras:
            item = QListWidgetItem(camera.label, self.list)
            item.setCheckState(QtCore.Qt.Unchecked)
            self.items[camera.label] = item

    def check_selected(self) -> None:
        """checks selected cameras"""
        for camera in self.app.document.chunk.cameras:
            if camera.selected:
                item = self.items[camera.label]
                item.setCheckState(QtCore.Qt.Checked)

    def clear_selected(self) -> None:
        """clears selected cameras"""
        for item in self.items.values():
            item.setCheckState(QtCore.Qt.Unchecked)

    def select_checked(self) -> None:
        """clears selected cameras"""
        for camera in self.app.document.chunk.cameras:
            item = self.items[camera.label]
            if item.checkState() == QtCore.Qt.Unchecked:
                camera.selected = False
                item.setSelected(False)
            else:
                camera.selected = True
                item.setSelected(True)

    def update_items(self) -> None:
        """signal for when the item selection is changed"""
        selected_items = [item.text() for item in self.list.selectedItems()]
        for camera in self.app.document.chunk.cameras:
            if camera.label in selected_items:
                camera.selected = True
            else:
                camera.selected = False

    def export_cameras(self) -> None:
        """exports the checked cameras"""
        camera_labels = [item.text() for item in self.list.selectedItems()]
        cameras = [
            get_camera(chunk=self.app.document.chunk, label=camera_label)
            for camera_label in camera_labels
        ]
        path = str(Path(Metashape.app.document.path).parent / "cameras.csv")
        export_path, _ = QFileDialog.getSaveFileName(
            self, "Export Cameras", path, "CSV files (*.csv)"
        )
        if not export_path:
            return
        with open(export_path, "w") as export_file:
            for camera in cameras:
                if not camera:
                    continue
                export_file.write(f"{camera.label},{camera.photo.path}\n")


class CameraSelectorDock(QDockWidget):
    """dock widget that is used for camera selector widget cameras"""

    def __init__(self, app: Metashape.Application, main_window: QMainWindow) -> None:
        """initialises the dockable widget

        Args:
            app (Metashape.Application): metashape application
        """
        super().__init__("Select Cameras", main_window)

        self.setWidget(CameraSelector(app=app))
        self.setFloating(False)

    # def closeEvent(self, event) -> None:
    #     """close event"""
    #     self.widget().closeEvent(event)


def add_to_dock():
    """adds the widget to dock"""
    main_window = find_main_window()
    app = Metashape.app
    camera_selector_dock = CameraSelectorDock(app=app, main_window=main_window)
    main_window.addDockWidget(QtCore.Qt.LeftDockWidgetArea, camera_selector_dock)


label = "Abyss/Select Export Cameras"
Metashape.app.addMenuItem(label, add_to_dock)
