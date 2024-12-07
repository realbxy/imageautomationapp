import os
import sys
import time
import json
import cv2
import numpy as np
import pyautogui
import mss  # Multi-monitor support
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QLabel, QListWidget,
    QFileDialog, QWidget, QMessageBox, QHBoxLayout, QLineEdit, QComboBox, QMenuBar, QMenu, QAction, QSlider, QListWidgetItem, QShortcut
)
from PyQt5.QtGui import QPixmap, QIcon, QKeySequence, QFont
from PyQt5.QtCore import Qt, QTimer
from threading import Thread
import winsound


def resource_path(relative_path):
    """Get the absolute path to the resource, works for dev and PyInstaller"""
    try:
        base_path = sys._MEIPASS  # Temp folder used by PyInstaller
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class AutomationApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BitHelper")
        self.setGeometry(200, 200, 900, 700)

        # Set window icon
        icon_path = resource_path("bitrevamp.ico")
        self.setWindowIcon(QIcon(icon_path))

        # App state variables
        self.confidence_threshold = 0.8
        self.is_dark_mode = False
        self.automation_templates = {}
        self.templates = []
        self.start_time = None
        self.running = False
        self.paused = False
        self.sound_file = None
        self.last_detection_time = None
        self.pause_start_time = None
        self.total_pause_duration = 0

        # Timer for elapsed time
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_elapsed_time)

        # UI components to keep alive
        self.preview_windows = []
        self.slider_window = None

        # Hotkeys
        self.start_hotkey = "Ctrl+Shift+S"
        self.stop_hotkey = "Ctrl+Shift+X"
        self.pause_hotkey = "Ctrl+Shift+P"

        # Main layout
        layout = QVBoxLayout()

        # Modern font
        font = QFont("Arial", 10)

        # Template management
        template_name_layout = QHBoxLayout()
        self.template_name_input = QLineEdit()
        self.template_name_input.setPlaceholderText("Enter automation template name")
        self.template_name_input.setFont(font)
        template_name_layout.addWidget(self.template_name_input)

        self.template_dropdown = QComboBox()
        self.template_dropdown.addItem("Create New Template")
        self.template_dropdown.currentIndexChanged.connect(self.load_automation_template_from_dropdown)
        self.template_dropdown.setFont(font)
        template_name_layout.addWidget(self.template_dropdown)

        layout.addLayout(template_name_layout)

        # Status display
        self.status_label = QLabel("Status: Stopped")
        self.status_label.setFont(font)
        layout.addWidget(self.status_label)
        self.time_label = QLabel("Time Elapsed: 00:00:00")
        self.time_label.setFont(font)
        layout.addWidget(self.time_label)

        # Template list
        self.template_list = QListWidget()
        self.template_list.setFont(font)
        self.template_list.itemDoubleClicked.connect(self.preview_template)
        layout.addWidget(self.template_list)

        # Template management buttons
        button_layout = QHBoxLayout()

        upload_button = QPushButton("Upload Image Template")
        upload_button.clicked.connect(self.upload_image_template)
        upload_button.setFont(font)
        button_layout.addWidget(upload_button)

        remove_button = QPushButton("Remove Selected Template")
        remove_button.clicked.connect(self.remove_selected_template)
        remove_button.setFont(font)
        button_layout.addWidget(remove_button)

        save_button = QPushButton("Save Automation Template")
        save_button.clicked.connect(self.save_automation_template)
        save_button.setFont(font)
        button_layout.addWidget(save_button)

        delete_template_button = QPushButton("Delete Selected Template")
        delete_template_button.clicked.connect(self.delete_automation_template)
        delete_template_button.setFont(font)
        button_layout.addWidget(delete_template_button)

        layout.addLayout(button_layout)

        # Sound selection
        sound_layout = QHBoxLayout()
        sound_label = QLabel("Select Sound File:")
        sound_label.setFont(font)
        sound_layout.addWidget(sound_label)

        self.sound_file_input = QLineEdit()
        self.sound_file_input.setFont(font)
        self.sound_file_input.setReadOnly(True)
        sound_layout.addWidget(self.sound_file_input)

        sound_button = QPushButton("Upload Sound")
        sound_button.clicked.connect(self.upload_sound_file)
        sound_button.setFont(font)
        sound_layout.addWidget(sound_button)

        layout.addLayout(sound_layout)

        # Hotkey settings
        hotkey_layout = QVBoxLayout()
        hotkey_label = QLabel("Hotkeys:")
        hotkey_label.setFont(font)
        hotkey_layout.addWidget(hotkey_label)

        start_hotkey_label = QLabel("Start Automation Hotkey:")
        start_hotkey_label.setFont(font)
        hotkey_layout.addWidget(start_hotkey_label)

        self.start_hotkey_input = QLineEdit(self.start_hotkey)
        self.start_hotkey_input.setFont(font)
        hotkey_layout.addWidget(self.start_hotkey_input)

        stop_hotkey_label = QLabel("Stop Automation Hotkey:")
        stop_hotkey_label.setFont(font)
        hotkey_layout.addWidget(stop_hotkey_label)

        self.stop_hotkey_input = QLineEdit(self.stop_hotkey)
        self.stop_hotkey_input.setFont(font)
        hotkey_layout.addWidget(self.stop_hotkey_input)

        pause_hotkey_label = QLabel("Pause/Resume Automation Hotkey:")
        pause_hotkey_label.setFont(font)
        hotkey_layout.addWidget(pause_hotkey_label)

        self.pause_hotkey_input = QLineEdit(self.pause_hotkey)
        self.pause_hotkey_input.setFont(font)
        hotkey_layout.addWidget(self.pause_hotkey_input)

        save_hotkeys_button = QPushButton("Save Hotkeys")
        save_hotkeys_button.clicked.connect(self.save_hotkeys)
        save_hotkeys_button.setFont(font)
        hotkey_layout.addWidget(save_hotkeys_button)

        layout.addLayout(hotkey_layout)

        # Automation controls
        controls_layout = QHBoxLayout()

        start_button = QPushButton("Start Automation")
        start_button.clicked.connect(self.start_automation)
        start_button.setFont(font)
        controls_layout.addWidget(start_button)

        stop_button = QPushButton("Stop Automation")
        stop_button.clicked.connect(self.stop_automation)
        stop_button.setFont(font)
        controls_layout.addWidget(stop_button)

        pause_button = QPushButton("Pause/Resume Automation")
        pause_button.clicked.connect(self.pause_resume_automation)
        pause_button.setFont(font)
        controls_layout.addWidget(pause_button)

        layout.addLayout(controls_layout)

        # Set central widget
        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # Add menu bar
        self.create_menu_bar()

        # Load saved automation templates
        self.load_saved_automation_templates()

        # Register global shortcuts
        self.register_hotkeys()

    def create_menu_bar(self):
        """Create the menu bar."""
        menu_bar = QMenuBar(self)

        # Settings menu
        settings_menu = QMenu("Settings", self)

        dark_mode_action = QAction("Toggle Dark Mode", self)
        dark_mode_action.triggered.connect(self.toggle_dark_mode)
        settings_menu.addAction(dark_mode_action)

        confidence_action = QAction("Set Matching Confidence", self)
        confidence_action.triggered.connect(self.show_confidence_slider)
        settings_menu.addAction(confidence_action)

        reset_action = QAction("Reset to Default", self)
        reset_action.triggered.connect(self.reset_to_default)
        settings_menu.addAction(reset_action)

        menu_bar.addMenu(settings_menu)
        self.setMenuBar(menu_bar)

    def toggle_dark_mode(self):
        """Toggle dark mode for the app."""
        self.is_dark_mode = not self.is_dark_mode
        if self.is_dark_mode:
            self.setStyleSheet(
                """
                QMainWindow { background-color: #121212; color: #ffffff; }
                QLabel, QLineEdit, QPushButton, QListWidget, QMenuBar {
                    background-color: #1e1e1e; color: #ffffff;
                }
                QPushButton:hover { background-color: #333333; }
                """
            )
        else:
            self.setStyleSheet("")

    def upload_sound_file(self):
        """Upload a sound file to play when automation ends."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Sound File", "", "Sound Files (*.wav *.mp3)"
        )
        if file_path:
            self.sound_file = file_path
            self.sound_file_input.setText(file_path)

    def start_automation(self):
        """Start automation."""
        if not self.templates:
            QMessageBox.warning(self, "Error", "No image templates uploaded!")
            return
        self.running = True
        self.paused = False
        self.status_label.setText("Status: Running")
        self.start_time = time.time()
        self.total_pause_duration = 0
        self.timer.start(1000)
        Thread(target=self.automation_loop, daemon=True).start()

    def pause_resume_automation(self):
        """Pause or resume automation."""
        if not self.running:
            return
        if not self.paused:
            self.paused = True
            self.pause_start_time = time.time()
            self.status_label.setText("Status: Paused")
        else:
            self.paused = False
            self.total_pause_duration += time.time() - self.pause_start_time
            self.status_label.setText("Status: Running")

    def automation_loop(self):
        """Main automation loop."""
        with mss.mss() as sct:
            while self.running:
                if self.paused:
                    time.sleep(0.5)
                    continue

                for monitor in sct.monitors:
                    screen = np.array(sct.grab(monitor))
                    gray_screen = cv2.cvtColor(screen, cv2.COLOR_RGB2GRAY)

                    for template_path in self.templates:
                        template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
                        if template is None:
                            continue

                        result = cv2.matchTemplate(gray_screen, template, cv2.TM_CCOEFF_NORMED)
                        _, max_val, _, max_loc = cv2.minMaxLoc(result)
                        if max_val > self.confidence_threshold:
                            center = (
                                max_loc[0] + template.shape[1] // 2,
                                max_loc[1] + template.shape[0] // 2,
                            )
                            pyautogui.moveTo(center)
                            pyautogui.click()
                            self.last_detection_time = time.time()
                            break

                # Timeout logic
                if self.last_detection_time and time.time() - self.last_detection_time > 300:
                    self.stop_automation()
                    QMessageBox.warning(self, "Timeout", "Automation stopped due to inactivity.")
                    break

                time.sleep(1)

    def update_elapsed_time(self):
        """Update the elapsed time display."""
        if self.start_time:
            elapsed_time = int(time.time() - self.start_time - self.total_pause_duration)
            hours, remainder = divmod(elapsed_time, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.time_label.setText(f"Time Elapsed: {hours:02}:{minutes:02}:{seconds:02}")

    def stop_automation(self):
        """Stop automation."""
        self.running = False
        self.timer.stop()
        self.status_label.setText("Status: Stopped")
        if self.sound_file:
            winsound.PlaySound(self.sound_file, winsound.SND_FILENAME)

    def register_hotkeys(self):
        """Register hotkeys for automation."""
        self.start_shortcut = QShortcut(QKeySequence(self.start_hotkey), self)
        self.start_shortcut.activated.connect(self.start_automation)

        self.stop_shortcut = QShortcut(QKeySequence(self.stop_hotkey), self)
        self.stop_shortcut.activated.connect(self.stop_automation)

        self.pause_shortcut = QShortcut(QKeySequence(self.pause_hotkey), self)
        self.pause_shortcut.activated.connect(self.pause_resume_automation)

    def save_hotkeys(self):
        """Save new hotkeys from user input."""
        self.start_hotkey = self.start_hotkey_input.text()
        self.stop_hotkey = self.stop_hotkey_input.text()
        self.pause_hotkey = self.pause_hotkey_input.text()
        self.register_hotkeys()
        QMessageBox.information(self, "Hotkeys Updated", "Hotkeys have been updated!")

    def upload_image_template(self):
        """Upload an image template."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Image File", "", "Image Files (*.png *.jpg *.jpeg)"
        )
        if file_path:
            self.templates.append(file_path)
            self.update_template_list()

    def remove_selected_template(self):
        """Remove the selected template from the list."""
        selected_items = self.template_list.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            index = self.template_list.row(item)
            self.templates.pop(index)
            self.template_list.takeItem(index)

    def save_automation_template(self):
        """Save the current automation template with a name."""
        template_name = self.template_name_input.text().strip()
        if not template_name:
            QMessageBox.warning(self, "Error", "Please enter a name for the automation template.")
            return
        if not self.templates:
            QMessageBox.warning(self, "Error", "No image templates uploaded.")
            return
        self.automation_templates[template_name] = self.templates
        with open("automation_templates.json", "w") as f:
            json.dump(self.automation_templates, f, indent=4)
        if template_name not in [self.template_dropdown.itemText(i) for i in range(self.template_dropdown.count())]:
            self.template_dropdown.addItem(template_name)
        QMessageBox.information(self, "Success", f"Automation template '{template_name}' saved!")

    def delete_automation_template(self):
        """Delete the selected automation template."""
        template_name = self.template_dropdown.currentText()
        if template_name == "Create New Template":
            QMessageBox.warning(self, "Error", "Cannot delete the default option.")
            return
        if template_name in self.automation_templates:
            del self.automation_templates[template_name]
            with open("automation_templates.json", "w") as f:
                json.dump(self.automation_templates, f, indent=4)
            self.template_dropdown.removeItem(self.template_dropdown.currentIndex())
            QMessageBox.information(self, "Success", f"Automation template '{template_name}' deleted!")
            self.templates = []  # Clear current templates
            self.update_template_list()

    def load_saved_automation_templates(self):
        """Load saved automation templates from a file."""
        if os.path.exists("automation_templates.json"):
            with open("automation_templates.json", "r") as f:
                self.automation_templates = json.load(f)
            for template_name in self.automation_templates:
                if template_name not in [self.template_dropdown.itemText(i) for i in range(self.template_dropdown.count())]:
                    self.template_dropdown.addItem(template_name)

    def load_automation_template_from_dropdown(self):
        """Load a selected automation template from the dropdown."""
        template_name = self.template_dropdown.currentText()
        if template_name == "Create New Template":
            self.templates = []
            self.update_template_list()
            return
        if template_name not in self.automation_templates:
            QMessageBox.warning(self, "Error", f"No automation template found with name '{template_name}'.")
            return
        self.templates = self.automation_templates[template_name]
        self.update_template_list()
        QMessageBox.information(self, "Success", f"Automation template '{template_name}' loaded!")

    def update_template_list(self):
        """Update the displayed image template list."""
        self.template_list.clear()
        for template in self.templates:
            item = QListWidgetItem(os.path.basename(template))
            item.setIcon(QIcon(template))
            self.template_list.addItem(item)

    def preview_template(self, item):
        """Open a larger preview of the selected template."""
        selected_index = self.template_list.row(item)
        if selected_index == -1:
            return
        file_path = self.templates[selected_index]

        preview_window = QWidget()
        self.preview_windows.append(preview_window)

        preview_window.setWindowTitle(f"Preview - {os.path.basename(file_path)}")
        layout = QVBoxLayout()
        pixmap = QPixmap(file_path).scaled(600, 400, Qt.KeepAspectRatio)
        label = QLabel()
        label.setPixmap(pixmap)
        layout.addWidget(label)
        preview_window.setLayout(layout)
        preview_window.show()

    def show_confidence_slider(self):
        """Show a slider to adjust the confidence threshold."""
        if self.slider_window is None or not self.slider_window.isVisible():
            self.slider_window = QWidget()
            self.slider_window.setWindowTitle("Set Matching Confidence")
            self.slider_window.setGeometry(400, 400, 300, 100)

            layout = QVBoxLayout()

            slider_label = QLabel(f"Current Confidence: {self.confidence_threshold:.2f}")
            layout.addWidget(slider_label)

            slider = QSlider(Qt.Horizontal)
            slider.setMinimum(50)  # Represents 0.50
            slider.setMaximum(100)  # Represents 1.00
            slider.setValue(int(self.confidence_threshold * 100))
            slider.valueChanged.connect(lambda val: slider_label.setText(f"Current Confidence: {val / 100:.2f}"))
            slider.sliderReleased.connect(lambda: self.set_confidence_threshold(slider.value()))
            layout.addWidget(slider)

            self.slider_window.setLayout(layout)
            self.slider_window.show()

    def set_confidence_threshold(self, value):
        """Set the confidence threshold from the slider."""
        self.confidence_threshold = value / 100
        QMessageBox.information(self, "Confidence Updated", f"Confidence set to {self.confidence_threshold:.2f}.")

    def reset_to_default(self):
        """Reset all settings to default values."""
        self.confidence_threshold = 0.8
        self.is_dark_mode = False
        self.setStyleSheet("")
        QMessageBox.information(self, "Settings Reset", "All settings have been reset to default.")


if __name__ == "__main__":
    app = QApplication([])

    app.setWindowIcon(QIcon(resource_path("bitrevamp.ico")))

    window = AutomationApp()
    window.show()

    app.exec_()
