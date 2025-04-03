from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QFileDialog, QListWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QGraphicsOpacityEffect,QSpacerItem, QSizePolicy, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation
from PyQt6.QtGui import QCursor, QPixmap, QFont, QIcon


import sys

class GlassUploader(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LoomOps")
        self.setFixedSize(1200, 900)

        self.setWindowIcon(QIcon("logo.png"))

        self.setStyleSheet(self.styles())

        layout = QVBoxLayout(self)
        layout.setSpacing(32)
        layout.setContentsMargins(50, 50, 50, 50)

        
        # --- Container Box ---
        container = QVBoxLayout()
        container.setSpacing(16)


        inputContainer = QVBoxLayout()
        inputContainer.setSpacing(16)
        inputContainer.addLayout(self.form_row("Google Drive Folder ID:"))
        inputContainer.addLayout(self.form_row("Service Account JSON File:", browse=True))
        inputContainer.addLayout(self.form_row("Space URL:"))

        header_layout = QHBoxLayout()
        # --- Logo ---
        logo = QLabel()
        logo.setPixmap(QPixmap("logo.png").scaledToHeight(200, Qt.TransformationMode.SmoothTransformation))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(logo)

        # Vertical Spacer
        spacer = QSpacerItem(50, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        header_layout.addSpacerItem(spacer)
        header_layout.addLayout(inputContainer)
        
        container.addLayout(header_layout)
        
        btn_row = QHBoxLayout()
        # Map of button text to corresponding method names
        self.button_actions = {
            "Login": self.login_action,
            "Logout": self.logout_action,
            "Download": self.download_action,
            "Auto Loom": self.auto_loom_action,
            "Rename": self.rename_action,
            "Upload": self.upload_action,
            "Pause": self.pause_action,
            "Gen Embeds": self.generate_embeds_action,
            "Sync": self.sync_action
        }

        for text, handler in self.button_actions.items():
            btn = QPushButton(text)
            btn.setObjectName("actionButton")
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setMinimumWidth(120)
            btn.clicked.connect(handler)
            btn_row.addWidget(btn)

        container.addLayout(btn_row)

        layout.addLayout(container)

        # --- Upload List ---
        upload_group = QVBoxLayout()
        upload_group.setSpacing(0)
        upload_group.setContentsMargins(0, 0, 0, 0)

        upload_label = self.card_label("Videos to Upload:")
        self.upload_list = QListWidget()
        self.upload_list.setObjectName("listBox")
        self.upload_list.setMinimumHeight(130)

        upload_group.addWidget(upload_label)
        upload_group.addWidget(self.upload_list)
        layout.addLayout(upload_group)


        # --- Upload Progress Bar ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("uploadProgress")
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setMinimumHeight(24)
        layout.addWidget(self.progress_bar)

        # --- Uploaded Table ---
        table_group = QVBoxLayout()
        table_group.setSpacing(0)
        table_group.setContentsMargins(0, 0, 0, 0)

        table_label = self.card_label("Uploaded Videos:")
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Video Title", "URL", "Embed Code"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setObjectName("uploadTable")
        self.table.setMinimumHeight(180)

        table_group.addWidget(table_label)
        table_group.addWidget(self.table)
        layout.addLayout(table_group)

        # --- Logo Splash Overlay ---
        self.overlay = QWidget(self)


        self.overlay.setGeometry(self.rect())


        overlay_layout = QVBoxLayout(self.overlay)
        overlay_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        splash_logo = QLabel()
        splash_logo.setPixmap(QPixmap("logo.png").scaledToHeight(180, Qt.TransformationMode.SmoothTransformation))
        splash_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        overlay_layout.addWidget(splash_logo)

        self.overlay_opacity = QGraphicsOpacityEffect()
        self.overlay_opacity.setOpacity(1.0)  # Set it explicitly
        self.overlay.setGraphicsEffect(self.overlay_opacity)


        QTimer.singleShot(3000, self.fade_overlay_out)

    def fade_overlay_out(self):
        anim = QPropertyAnimation(self.overlay_opacity, b"opacity")
        anim.setDuration(1000)
        anim.setStartValue(1)
        anim.setEndValue(0)
        anim.finished.connect(self.overlay.hide)
        anim.start()
        self._overlay_anim = anim

    def form_row(self, label_text, browse=False):
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setFixedWidth(200)
        label.setStyleSheet("background: transparent;")
        input_field = QLineEdit()
        input_field.setObjectName("inputField")
        input_field.setMinimumHeight(36)
        row.addWidget(label)
        row.addWidget(input_field)

        if browse:
            btn = QPushButton("Browse")
            btn.setObjectName("actionButton")
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.clicked.connect(lambda: self.browse_file(input_field))
            row.addWidget(btn)

        return row

    def browse_file(self, line_edit):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select JSON File", "", "JSON Files (*.json)")
        if file_path:
            line_edit.setText(file_path)

    def card_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: 1000; font-size: 16px; margin-top: 0px; margin-bottom: 6px; background: transparent;")
        return lbl
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.overlay.setGeometry(self.rect())

    def styles(self):
        return """
        QWidget {
            background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                stop:0 #0D111C, stop:0.5 #1A1F30, stop:1 #2B2F42);
            color: #EEEEEE;
            font-family: 'Segoe UI', sans-serif;
            font-size: 15px;
        }
        QLabel {
            color: #EEEEEE;
            background: transparent;
        }
        QLabel#title {
            font-size: 28px;
            font-weight: bold;
        }
        QFrame#accentLine {
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00E5FF, stop:1 #4DD0E1);
            border-radius: 1px;
        }
        QLineEdit#inputField {
            background-color: #11141F;
            color: #EEEEEE;
            border: 1px solid #4D8891;
            border-radius: 12px;
            padding: 6px 14px;
        }
        QPushButton#actionButton {
            background-color: #1F263A;
            color: #EEEEEE;
            border-radius: 10px;
            padding: 10px 16px;
            font-weight: 600;
        }
        QPushButton#actionButton:hover {
            background-color: #00B0FF;
            color: #0D111C;
        }
        QListWidget#listBox {
            background-color: #11141F;
            border: 2px solid #4D8891;
            border-radius: 12px;
            color: #EEEEEE;
            margin-top: 0px;
        }
        QTableWidget#uploadTable {
            background-color: #11141F;
            border: 2px solid #4D8891;
            border-radius: 12px;
            color: #EEEEEE;
            gridline-color: #4D8891;
            padding: 0px;
            margin: 0px;
            border-top-left-radius: 5px;
            border-top-right-radius: 5px;
        }
        QHeaderView::section {
            background-color: #1F263A;
            color: #EEEEEE;
            font-weight: bold;
            padding: 4px 6px;
            border: none;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            margin: 0px;
            height: 28px;
        }
        QScrollBar:vertical {
            background: #0D111C;
            width: 12px;
        }
        QScrollBar::handle:vertical {
            background: #4D8891;
            border-radius: 6px;
        }

        QProgressBar#uploadProgress {
            background-color: #1A1F30;
            border: 2px solid #4D8891;
            border-radius: 12px;
            text-align: center;
            font-weight: 600;
            color: #EEEEEE;
        }
        QProgressBar::chunk {
            background-color: #00B0FF;
            border-radius: 10px;
        }

        """


    def login_action(self):
        print("Login clicked")

    def logout_action(self):
        print("Logout clicked")

    def download_action(self):
        print("Download clicked")

    def auto_loom_action(self):
        print("Auto Loom clicked")

    def rename_action(self):
        print("Rename clicked")

    def upload_action(self):
        print("Upload clicked")

    def pause_action(self):
        print("Pause clicked")

    def generate_embeds_action(self):
        print("Generate Embeds clicked")

    def sync_action(self):
        print("Sync clicked")

def main():
    app = QApplication(sys.argv)
    win = GlassUploader()
    win.show()
    sys.exit(app.exec())

main()
