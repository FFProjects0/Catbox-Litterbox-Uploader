import os
import sys
import requests
from PyQt5 import QtWidgets, QtCore, QtGui
from requests_toolbelt.multipart.encoder import MultipartEncoder, MultipartEncoderMonitor
TITLE = "Catbox & Litterbox Uploader - v0.4.6"
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
class UploadWorker(QtCore.QThread):
    progress_changed = QtCore.pyqtSignal(int)
    upload_finished = QtCore.pyqtSignal(str)
    upload_error = QtCore.pyqtSignal(str)
    def __init__(self, filepath=None, url=None, userhash="", mode="catbox", expire="1h", parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.url = url
        self.userhash = userhash
        self.mode = mode
        self.expire = expire
        self.exp_parse()
        if self.mode == "catbox":
            self.api_url = "https://catbox.moe/user/api.php"
        else:
            self.api_url = "https://litterbox.catbox.moe/resources/internals/api.php"
    def exp_parse(self):
        if self.expire == "1 hour":
            self.expire = "1h"
        elif self.expire == "12 hours":
            self.expire = "12h"
        elif self.expire == "1 day":
            self.expire = "24h"
        elif self.expire == "3 days":
            self.expire = "72h"
    def run(self):
        try:
            if self.filepath is not None:
                self._upload_file()
            elif self.url is not None and self.mode == "catbox":
                self._upload_url()
            else:
                self.upload_error.emit("Invalid upload parameters.")
        except Exception as e:
            self.upload_error.emit(str(e))
    def _upload_file(self):
        filename = os.path.basename(self.filepath)
        with open(self.filepath, "rb") as f:
            if self.mode == "catbox":
                fields = {
                    "reqtype": "fileupload",
                    "fileToUpload": (filename, f)
                }
                if self.userhash:
                    fields["userhash"] = self.userhash
            else:
                fields = {
                    "reqtype": "fileupload",
                    "time": self.expire,
                    "fileToUpload": (filename, f)
                }
            encoder = MultipartEncoder(fields=fields)
            def progress_callback(monitor):
                pct = int((monitor.bytes_read / monitor.len) * 100)
                self.progress_changed.emit(pct)
            monitor = MultipartEncoderMonitor(encoder, progress_callback)
            headers = {"Content-Type": monitor.content_type}
            response = requests.post(self.api_url, data=monitor, headers=headers)
            if response.status_code == 200:
                self.upload_finished.emit(response.text.strip())
            else:
                self.upload_error.emit(f"Upload failed (HTTP {response.status_code})")
    def _upload_url(self):
        fields = {"reqtype": "urlupload", "url": self.url}
        if self.userhash:
            fields["userhash"] = self.userhash
        response = requests.post(self.api_url, data=fields)
        if response.status_code == 200:
            self.upload_finished.emit(response.text.strip())
        else:
            self.upload_error.emit(f"Upload failed (HTTP {response.status_code})")
class DropZone(QtWidgets.QFrame):
    file_dropped = QtCore.pyqtSignal(str)
    clicked = QtCore.pyqtSignal()
    def __init__(self, text="Select or drop files", parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #aaa;
                border-radius: 12px;
                background-color: #fafafa;
            }
        """)
        self.setFixedHeight(100)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.setToolTip("Drag & drop files here or click to select")
        layout = QtWidgets.QVBoxLayout(self)
        self.label = QtWidgets.QLabel(text, self)
        self.label.setStyleSheet("font-size: 16pt; color: #333;")
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.label)
        layout.setContentsMargins(0, 0, 0, 0)
    def mousePressEvent(self, event: QtGui.QMouseEvent):
        self.clicked.emit()
    def dragEnterEvent(self, event: QtGui.QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    def dropEvent(self, event: QtGui.QDropEvent):
        if event.mimeData().hasUrls():
            file_path = event.mimeData().urls()[0].toLocalFile()
            self.file_dropped.emit(file_path)
            event.acceptProposedAction()
class CatboxTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        logo = QtWidgets.QLabel(self)
        pixmap = QtGui.QPixmap(resource_path("logo.png"))
        logo.setPixmap(pixmap.scaledToWidth(300, QtCore.Qt.SmoothTransformation))
        logo.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(logo)
        self.drop_zone = DropZone("Select or drop files", self)
        layout.addWidget(self.drop_zone)
        self.drop_zone.clicked.connect(self.select_file)
        self.drop_zone.file_dropped.connect(self.handle_file_dropped)
        url_layout = QtWidgets.QHBoxLayout()
        url_label = QtWidgets.QLabel("Upload via URL:")
        self.url_edit = QtWidgets.QLineEdit()
        self.url_upload_btn = QtWidgets.QPushButton("Go")
        self.url_upload_btn.clicked.connect(self.upload_via_url)
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_edit)
        url_layout.addWidget(self.url_upload_btn)
        layout.addLayout(url_layout)
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        self.result_field = QtWidgets.QLineEdit()
        self.result_field.setReadOnly(True)
        self.result_field.setPlaceholderText("Upload link will appear here...")
        layout.addWidget(self.result_field)
        layout.addStretch(1)
    def select_file(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select File")
        if file_path:
            if not self.validate_file(file_path):
                return
            self.reset_ui()
            self.start_upload(filepath=file_path, mode="catbox")
    def handle_file_dropped(self, file_path):
        if not self.validate_file(file_path):
            return
        self.reset_ui()
        self.start_upload(filepath=file_path, mode="catbox")
    def upload_via_url(self):
        url = self.url_edit.text().strip()
        if not url:
            return
        self.reset_ui()
        self.worker = UploadWorker(url=url, mode="catbox")
        self.worker.progress_changed.connect(self.progress_bar.setValue)
        self.worker.upload_finished.connect(self.on_upload_finished)
        self.worker.upload_error.connect(self.on_upload_error)
        self.worker.start()
    def reset_ui(self):
        self.progress_bar.setValue(0)
        self.result_field.clear()
    def start_upload(self, filepath, mode):
        self.worker = UploadWorker(filepath=filepath, mode=mode)
        self.worker.progress_changed.connect(self.progress_bar.setValue)
        self.worker.upload_finished.connect(self.on_upload_finished)
        self.worker.upload_error.connect(self.on_upload_error)
        self.worker.start()
    def validate_file(self, file_path):
        max_size = 200 * 1024 * 1024  # 200MB
        if os.path.getsize(file_path) > max_size:
            QtWidgets.QMessageBox.warning(self, "File Too Large", "File exceeds the 200MB limit.")
            return False
        ext = os.path.splitext(file_path)[1].lower()
        if ext.startswith(".doc") or ext in [".exe", ".scr", ".cpl", ".jar"]:
            QtWidgets.QMessageBox.warning(self, "File Type Not Allowed", "This file type is not allowed by catbox.")
            return False
        return True
    def on_upload_finished(self, link: str):
        self.result_field.setText(link)
        QtWidgets.QApplication.clipboard().setText(link)
        QtWidgets.QMessageBox.information(self, "Success", "File uploaded!\nLink copied to clipboard.")
    def on_upload_error(self, msg: str):
        QtWidgets.QMessageBox.critical(self, "Upload Error", msg)
class LitterboxTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        logo = QtWidgets.QLabel(self)
        pixmap = QtGui.QPixmap(resource_path("litterbox.png"))
        logo.setPixmap(pixmap.scaledToWidth(300, QtCore.Qt.SmoothTransformation))
        logo.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(logo)
        self.drop_zone = DropZone("Select or drop files", self)
        layout.addWidget(self.drop_zone)
        self.drop_zone.clicked.connect(self.select_file)
        self.drop_zone.file_dropped.connect(self.handle_file_dropped)
        expire_layout = QtWidgets.QHBoxLayout()
        expire_label = QtWidgets.QLabel("Expiration:")
        self.expire_combo = QtWidgets.QComboBox()
        self.expire_combo.addItems(["1 hour", "12 hours", "1 day", "3 days"])
        expire_layout.addWidget(expire_label)
        expire_layout.addWidget(self.expire_combo)
        expire_layout.addStretch(1)
        layout.addLayout(expire_layout)
        # (thought about adding this but didn't in the end)
        #note = QtWidgets.QLabel("Note: URL uploads not supported for Litterbox.", self)
        #note.setStyleSheet("color: #888; font-size: 9pt;")
        #note.setAlignment(QtCore.Qt.AlignCenter)
        #layout.addWidget(note)
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        self.result_field = QtWidgets.QLineEdit()
        self.result_field.setReadOnly(True)
        self.result_field.setPlaceholderText("Upload link will appear here...")
        layout.addWidget(self.result_field)
        layout.addStretch(1)
    def select_file(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select File")
        if file_path:
            if not self.validate_file(file_path):
                return
            self.reset_ui()
            expire = self.expire_combo.currentText()
            self.start_upload(filepath=file_path, mode="litterbox", expire=expire)
    def handle_file_dropped(self, file_path):
        if not self.validate_file(file_path):
            return
        self.reset_ui()
        expire = self.expire_combo.currentText()
        self.start_upload(filepath=file_path, mode="litterbox", expire=expire)
    def reset_ui(self):
        self.progress_bar.setValue(0)
        self.result_field.clear()
    def start_upload(self, filepath, mode, expire):
        self.worker = UploadWorker(filepath=filepath, mode=mode, expire=expire)
        self.worker.progress_changed.connect(self.progress_bar.setValue)
        self.worker.upload_finished.connect(self.on_upload_finished)
        self.worker.upload_error.connect(self.on_upload_error)
        self.worker.start()
    def validate_file(self, file_path):
        max_size = 200 * 1024 * 1024  # 200MB
        if os.path.getsize(file_path) > max_size:
            QtWidgets.QMessageBox.warning(self, "File Too Large", "File exceeds the 200MB limit.")
            return False
        ext = os.path.splitext(file_path)[1].lower()
        if ext.startswith(".doc") or ext in [".exe", ".scr", ".cpl", ".jar"]:
            QtWidgets.QMessageBox.warning(self, "File Type Not Allowed", "This file type is not allowed by catbox.")
            return False
        return True
    def on_upload_finished(self, link: str):
        self.result_field.setText(link)
        QtWidgets.QApplication.clipboard().setText(link)
        QtWidgets.QMessageBox.information(self, "Success", "File uploaded!\nLink copied to clipboard.")
    def on_upload_error(self, msg: str):
        QtWidgets.QMessageBox.critical(self, "Upload Error", msg)
class MainWindow(QtWidgets.QWidget):
    def on_tab_changed(self):
        if self.tab_widget.currentIndex() == 0:
            self.setWindowIcon(QtGui.QIcon(resource_path("faviconCB.ico")))
        elif self.tab_widget.currentIndex() == 1:
            self.setWindowIcon(QtGui.QIcon(resource_path("faviconLB.ico")))
    def __init__(self):
        super().__init__()
        self.setWindowTitle(TITLE)
        self.setWindowIcon(QtGui.QIcon(resource_path("faviconCB.ico")))
        self.resize(700, 300)
        layout = QtWidgets.QVBoxLayout(self)
        self.tab_widget = QtWidgets.QTabWidget(self)
        self.tab_widget.addTab(CatboxTab(), "Catbox")
        self.tab_widget.addTab(LitterboxTab(), "Litterbox")
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        layout.addWidget(self.tab_widget)
def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
if __name__ == "__main__":
    main()