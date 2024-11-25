import os
import sys
import time
import json
import cv2
import numpy as np
import pyautogui
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QLabel, QListWidget,
    QFileDialog, QWidget, QMessageBox, QHBoxLayout, QLineEdit, QComboBox, QMenuBar, QMenu, QAction, QSlider, QListWidgetItem
)
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import Qt
from threading import Thread


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
        self.setGeometry(200, 200, 800, 600)

        # Set window icon here for the window icon
        icon_path = resource_path("bitrevamp.ico")  # Make sure path is correct
        self.setWindowIcon(QIcon(icon_path))  # Set the icon to the window

        # Default app settings
        self.confidence_threshold = 0.8  # Default template matching confidence
        self.is_dark_mode = False  # Default theme (light mode)

        # Automation template storage
        self.automation_templates = {}  # {"TemplateName": [image_template_paths]}
        self.templates = []  # Image templates for the current automation
        self.start_time = None
        self.running = False
        self.timer_started = False  # Track if the timer has started

        # Keep references to prevent garbage collection
        self.preview_windows = []
        self.slider_window = None

        # Main layout
        layout = QVBoxLayout()

        # Automation template selection and management
        template_name_layout = QHBoxLayout()
        self.template_name_input = QLineEdit()
        self.template_name_input.setPlaceholderText("Enter automation template name")
        template_name_layout.addWidget(self.template_name_input)

        self.template_dropdown = QComboBox()
        self.template_dropdown.addItem("Create New Template")
        self.template_dropdown.currentIndexChanged.connect(self.load_automation_template_from_dropdown)
        template_name_layout.addWidget(self.template_dropdown)

        layout.addLayout(template_name_layout)

        # Status and stats
        self.status_label = QLabel("Status: Stopped")
        layout.addWidget(self.status_label)
        self.time_label = QLabel("Time Elapsed: 00:00:00")
        layout.addWidget(self.time_label)

        # Image template list
        self.template_list = QListWidget()
        self.template_list.itemDoubleClicked.connect(self.preview_template)
        layout.addWidget(self.template_list)

        # Buttons for managing image templates
        button_layout = QHBoxLayout()

        upload_button = QPushButton("Upload Image Template")
        upload_button.clicked.connect(self.upload_image_template)
        button_layout.addWidget(upload_button)

        remove_button = QPushButton("Remove Selected Template")
        remove_button.clicked.connect(self.remove_selected_template)
        button_layout.addWidget(remove_button)

        save_button = QPushButton("Save Automation Template")
        save_button.clicked.connect(self.save_automation_template)
        button_layout.addWidget(save_button)

        delete_template_button = QPushButton("Delete Selected Template")
        delete_template_button.clicked.connect(self.delete_automation_template)
        button_layout.addWidget(delete_template_button)

        layout.addLayout(button_layout)

        # Automation controls
        start_button = QPushButton("Start Automation")
        start_button.clicked.connect(self.start_automation)
        layout.addWidget(start_button)

        stop_button = QPushButton("Stop Automation")
        stop_button.clicked.connect(self.stop_automation)
        layout.addWidget(stop_button)

        # Central widget
        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # Add menu bar
        self.create_menu_bar()

        # Load saved automation templates
        self.load_saved_automation_templates()

    def create_menu_bar(self):
        """Create the menu bar."""
        menu_bar = QMenuBar(self)

        # Settings menu
        settings_menu = QMenu("Settings", self)

        # Dark mode toggle
        dark_mode_action = QAction("Toggle Dark Mode", self)
        dark_mode_action.triggered.connect(self.toggle_dark_mode)
        settings_menu.addAction(dark_mode_action)

        # Confidence threshold slider
        confidence_action = QAction("Set Matching Confidence", self)
        confidence_action.triggered.connect(self.show_confidence_slider)
        settings_menu.addAction(confidence_action)

        # Reset to default
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
                QMainWindow {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QLabel, QLineEdit, QPushButton, QListWidget {
                    background-color: #3c3c3c;
                    color: #ffffff;
                }
                """
            )
        else:
            self.setStyleSheet("")

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

    def load_saved_automation_templates(self):
        """Load saved automation templates from a file."""
        if os.path.exists("automation_templates.json"):
            with open("automation_templates.json", "r") as f:
                self.automation_templates = json.load(f)
            for template_name in self.automation_templates:
                if template_name not in [self.template_dropdown.itemText(i) for i in range(self.template_dropdown.count())]:
                    self.template_dropdown.addItem(template_name)

    def start_automation(self):
        """Start the automation process."""
        if not self.templates:
            QMessageBox.warning(self, "Error", "No image templates uploaded!")
            return
        self.running = True
        self.timer_started = False  # Reset the timer
        self.status_label.setText("Status: Running")
        Thread(target=self.automation_loop, daemon=True).start()
        Thread(target=self.update_time_elapsed, daemon=True).start()

    def stop_automation(self):
        """Stop the automation process."""
        self.running = False
        self.status_label.setText("Status: Stopped")

    def automation_loop(self):
        """Main automation loop."""
        try:
            while self.running:
                for template_path in self.templates:
                    location = self.find_button(template_path)
                    if location:
                        if not self.timer_started:
                            self.timer_started = True
                            self.start_time = time.time()  # Start timer on first button press
                        pyautogui.click(*location)
                        time.sleep(0.5)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def find_button(self, template_path):
        """Locate a button on the screen using template matching."""
        try:
            screen = pyautogui.screenshot()
            screen = cv2.cvtColor(np.array(screen), cv2.COLOR_RGB2GRAY)
            template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
            if template is None:
                raise ValueError(f"Template {template_path} could not be loaded.")
            for scale in np.linspace(0.8, 1.2, 10):
                resized_template = cv2.resize(template, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
                result = cv2.matchTemplate(screen, resized_template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(result)
                if max_val > self.confidence_threshold:
                    return (max_loc[0] + resized_template.shape[1] // 2,
                            max_loc[1] + resized_template.shape[0] // 2)
        except Exception as e:
            print(f"Error in find_button: {e}")
        return None

    def update_time_elapsed(self):
        """Update the time elapsed in real-time."""
        while self.running:
            if self.timer_started and self.start_time:
                elapsed_time = int(time.time() - self.start_time)
                hours, remainder = divmod(elapsed_time, 3600)
                minutes, seconds = divmod(remainder, 60)
                self.time_label.setText(f"Time Elapsed: {hours:02}:{minutes:02}:{seconds:02}")
            time.sleep(1)


if __name__ == "__main__":
    app = QApplication([])

    # Set the application-wide and window icon
    app.setWindowIcon(QIcon(resource_path("bitrevamp.ico")))

    window = AutomationApp()
    window.setWindowIcon(QIcon(resource_path("bitrevamp.ico")))  # Set icon to window as well
    window.show()

    app.exec_()
