import sys

from pyqtgraph import ImageView
from PySide2.QtCore import QDateTime, QFile, QSize, QTimer
from PySide2.QtGui import QIcon
from PySide2.QtUiTools import QUiLoader
from PySide2.QtWidgets import QApplication

import essai_camera_rc
from vimba import CameraEvent, Vimba, VimbaCameraError, VimbaFeatureError, VimbaTimeout
from vimba.c_binding import VimbaCError


def load_ui(app, fn):
    loader = QUiLoader(parent=app)
    uifile = QFile(fn)
    uifile.open(QFile.ReadOnly)
    loader.registerCustomWidget(ImageView)
    ui = loader.load(uifile, None)
    uifile.close()

    return ui


def set_button_icon(button, svg):
    icon = QIcon(svg)
    button.setIconSize(QSize(32, 32))
    button.setIcon(icon)


class Cam():
    def __init__(self, vimba, ui, cameraid):
        # super().__init__()
        self.vimba = vimba
        self.ui = ui
        self.cameraid = cameraid
        self.cam = None
        self.reachable = None
        self.continuous_mode = False
        self.exposure_changed = None

        self.ui.play_button.clicked.connect(self.acquire_single)
        self.ui.repeat_button.clicked.connect(self.repeat_button_clicked)
        self.ui.exposition_spinbox.valueChanged.connect(self.exposure_changed_evt)

        self.cam_detect()
        if self.cam is None:
            self.ui.camera_status.clicked.connect(
                lambda void: self.cam_detect())

    def cam_detect(self):
        print("cam_detect called…")
        if self.cam is None:
            try:
                self.cam = self.vimba.get_camera_by_id(self.cameraid)

                try:
                    self.ui.camera_status.clicked.disconnect()
                except RuntimeError:
                    pass

                self.vimba.register_camera_change_handler(
                    self.camera_change_handler())

                self.reachable_evt()

                timer = QTimer(self.ui)
                timer.timeout.connect(self.refresh_ui)
                timer.start(5000)

                with self.cam as cm:
                    cm.get_feature_by_name('AcquisitionMode').set("SingleFrame")
                    cm.get_feature_by_name('TriggerSelector').set('FrameStart')
                    cm.get_feature_by_name('TriggerSource').set('Freerun')

                    cm.get_feature_by_name('TriggerMode').set('On')
                    cm.get_feature_by_name('BandwidthControlMode').set(
                        "StreamBytesPerSecond")
                    cm.get_feature_by_name('StreamBytesPerSecond').set(
                        20000000)
                    exposition = cm.get_feature_by_name('ExposureTimeAbs')
                    self.ui.exposition_spinbox.setValue(exposition.get())
                    cm.get_feature_by_name('Gain').set(0.0)
                    cm.get_feature_by_name('PixelFormat').set("Mono8")
                    cm.get_feature_by_name('Height').set(2056)
                    cm.get_feature_by_name('Width').set(2464)
                    try:
                        cm.GVSPAdjustPacketSize.run()
                        while not cm.GVSPAdjustPacketSize.is_done():
                            pass
                    except (AttributeError, VimbaFeatureError):
                        pass
                self.acquire_single()

            except VimbaCameraError as error:
                print(error)

    def refresh_ui(self):
        if self.reachable:
            if self.cam:
                try:
                    with self.cam as cm:
                        temp = cm.get_feature_by_name("DeviceTemperature")
                        self.ui.camera_status.setText(f"{temp.get():.1f} °C")
                except (VimbaCameraError, VimbaCError):
                    self.unreachable_evt()
        else:
            self.ui.camera_status.setText("--- °C")

    def unreachable_evt(self):
        if self.cam:
            self.reachable = False
            self.ui.camera_status.setToolTip(
                "The camera is not reachable. Trying to reconnect…")
            set_button_icon(self.ui.camera_status,
                            ":/Icons/essai_camera_resources/video-off.svg")
            self.refresh_ui()

    def reachable_evt(self):
        if self.cam:
            self.reachable = True
            camera_id = self.cam.get_id()
            camera_model = self.cam.get_model()
            camera_sn = self.cam.get_serial()
            self.ui.camera_status.setToolTip(
                "<p><b>Camera:</b></p>"
                f"<p><b>Model:</b> {camera_model}</p>"
                f"<p><b>Id:</b> {camera_id}</p>"
                f"<p><b>SN:</b> {camera_sn}</p>")
            set_button_icon(self.ui.camera_status,
                            ":/Icons/essai_camera_resources/video.svg")
            self.refresh_ui()

    def camera_change_handler(self):
        def h(dev, state):
            if state == CameraEvent.Unreachable:
                self.unreachable_evt()
            if state == CameraEvent.Reachable:
                self.reachable_evt()

        return h

    def exposure_changed_evt(self, exp):
        self.exposure_changed = exp
        if not self.continuous_mode:
            self.acquire_single()

    def acquire_single(self):
        if self.reachable:
            try:
                with self.cam as cm:
                    if self.exposure_changed:
                        exposition = cm.get_feature_by_name('ExposureTimeAbs')
                        exposition.set(self.exposure_changed)
                        self.ui.exposition_spinbox.setValue(exposition.get())
                        self.exposure_changed = False
                    try:
                        frame = cm.get_frame().as_numpy_ndarray()
                        (sx, sy, bb) = frame.shape
                        assert (bb == 1)
                        frame = frame.reshape((sx, sy))
                        self.ui.image_view.setImage(frame)
                    except VimbaTimeout:
                        print("Camera timeout")

            except VimbaCameraError:
                self.unreachable_evt()
            if self.continuous_mode:
                QApplication.processEvents()
                self.acquire_single()

    def repeat_button_clicked(self):
        if self.reachable:

            if self.continuous_mode:
                # print("STOP")
                self.continuous_mode = False
                set_button_icon(self.ui.repeat_button,
                                ":/Icons/essai_camera_resources/repeat.svg")
                self.ui.play_button.setEnabled(True)
            else:
                # print("START")
                self.continuous_mode = True
                set_button_icon(self.ui.repeat_button,
                                ":/Icons/essai_camera_resources/pause.svg")
                self.ui.play_button.setDisabled(True)
                self.acquire_single()


def update_date_time(ui):
    def udt():
        ui.date_time.setDateTime(QDateTime.currentDateTime())

    return udt


def main():

    cameraid = "DEV_000F315CD7CA"
    app = QApplication()
    ui = load_ui(app, "essai_camera.ui")
    ui.statusbar.addPermanentWidget(ui.camera_status)
    ui.statusbar.addPermanentWidget(ui.date_time)
    ui.image_view.ui.menuBtn.hide()
    ui.image_view.ui.roiBtn.hide()
    ui.show()

    with Vimba.get_instance() as vimba:

        timer = QTimer(ui)
        timer.timeout.connect(update_date_time(ui))
        timer.start(1000)

        Cam(vimba, ui, cameraid)

        sys.exit(app.exec_())


main()
