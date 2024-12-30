import os
import sys
import time
import json
import cv2
import numpy as np
import pyautogui
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QLabel, QListWidget,
    QFileDialog, QWidget, QMessageBox, QHBoxLayout, QLineEdit, QComboBox,
    QMenuBar, QMenu, QAction, QSlider, QListWidgetItem, QTabWidget, QInputDialog
)
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import Qt
from threading import Thread


def resource_path(relative_path):
    """Get the absolute path to the resource, works for dev and PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class AutomationApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BitHelper")
        self.setGeometry(200, 200, 900, 600)

        # Set window icon
        icon_path = resource_path("bitrevamp.ico")
        self.setWindowIcon(QIcon(icon_path))

        # Central widget with tabs
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        # Add a "+" button for adding groups
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.remove_group)

        add_group_button = QPushButton("+")
        add_group_button.setFixedSize(30, 30)
        add_group_button.clicked.connect(self.prompt_add_group)
        self.tab_widget.setCornerWidget(add_group_button, Qt.TopRightCorner)

        # Default app settings
        self.global_confidence_threshold = 0.8
        self.is_dark_mode = False
        self.groups = {}  # To store groups of automation templates

        # Load saved templates
        self.automation_templates = {}  # {"TemplateName": [image_template_paths]}
        self.load_saved_automation_templates()

        # Create the first default group
        self.add_group("Default Group")

        # Add menu bar
        self.create_menu_bar()

    def create_menu_bar(self):
        """Create the menu bar."""
        menu_bar = QMenuBar(self)

        # Settings menu
        settings_menu = QMenu("Settings", self)

        dark_mode_action = QAction("Toggle Dark Mode", self)
        dark_mode_action.triggered.connect(self.toggle_dark_mode)
        settings_menu.addAction(dark_mode_action)

        confidence_action = QAction("Set Global Confidence", self)
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
        stylesheet = (
            """
            QMainWindow {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLabel, QLineEdit, QPushButton, QListWidget, QComboBox {
                background-color: #3c3c3c;
                color: #ffffff;
            }
            """
            if self.is_dark_mode
            else ""
        )
        self.setStyleSheet(stylesheet)
        for group in self.groups.values():
            group.apply_stylesheet(stylesheet)

    def show_confidence_slider(self):
        """Show a slider to adjust the global confidence threshold."""
        slider_window = QWidget()
        slider_window.setWindowTitle("Set Global Matching Confidence")
        slider_window.setGeometry(400, 400, 300, 100)

        layout = QVBoxLayout()

        slider_label = QLabel(f"Current Confidence: {self.global_confidence_threshold:.2f}")
        layout.addWidget(slider_label)

        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(50)
        slider.setMaximum(100)
        slider.setValue(int(self.global_confidence_threshold * 100))
        slider.valueChanged.connect(lambda val: slider_label.setText(f"Current Confidence: {val / 100:.2f}"))
        slider.sliderReleased.connect(lambda: self.set_global_confidence_threshold(slider.value()))
        layout.addWidget(slider)

        slider_window.setLayout(layout)
        slider_window.show()

    def set_global_confidence_threshold(self, value):
        """Set the global confidence threshold."""
        self.global_confidence_threshold = value / 100
        QMessageBox.information(self, "Confidence Updated", f"Confidence set to {self.global_confidence_threshold:.2f}.")

    def reset_to_default(self):
        """Reset all settings to default values."""
        self.global_confidence_threshold = 0.8
        self.is_dark_mode = False
        self.setStyleSheet("")
        QMessageBox.information(self, "Settings Reset", "All settings have been reset to default.")

    def add_group(self, group_name):
        """Add a new automation group."""
        if group_name in self.groups:
            QMessageBox.warning(self, "Error", f"Group '{group_name}' already exists!")
            return

        group_widget = AutomationGroupWidget(group_name, self.global_confidence_threshold, self.automation_templates)
        self.groups[group_name] = group_widget
        self.tab_widget.addTab(group_widget, group_name)

    def prompt_add_group(self):
        """Prompt the user to add a new group."""
        group_name, ok = QInputDialog.getText(self, "Add New Group", "Enter group name:")
        if ok and group_name:
            self.add_group(group_name)

    def remove_group(self, index):
        """Remove a group by index."""
        group_name = self.tab_widget.tabText(index)
        if group_name == "Default Group":
            QMessageBox.warning(self, "Error", "Cannot remove the default group.")
            return
        del self.groups[group_name]
        self.tab_widget.removeTab(index)

    def load_saved_automation_templates(self):
        """Load saved automation templates from a file."""
        if os.path.exists("automation_templates.json"):
            with open("automation_templates.json", "r") as f:
                self.automation_templates = json.load(f)


class AutomationGroupWidget(QWidget):
    def __init__(self, group_name, confidence_threshold, automation_templates):
        super().__init__()
        self.group_name = group_name
        self.confidence_threshold = confidence_threshold
        self.automation_templates = automation_templates
        self.templates = []
        self.running = False
        self.start_time = None
        self.timer_started = False  # To track if the timer has started

        # Layout
        layout = QVBoxLayout()

        # Template management
        template_name_layout = QHBoxLayout()
        self.template_name_input = QLineEdit()
        self.template_name_input.setPlaceholderText("Enter automation template name")
        template_name_layout.addWidget(self.template_name_input)

        self.template_dropdown = QComboBox()
        self.template_dropdown.addItem("Create New Template")
        self.template_dropdown.addItems(self.automation_templates.keys())
        self.template_dropdown.currentIndexChanged.connect(self.load_automation_template_from_dropdown)
        template_name_layout.addWidget(self.template_dropdown)

        layout.addLayout(template_name_layout)

        # Status and stats
        self.status_label = QLabel("Status: Stopped")
        layout.addWidget(self.status_label)
        self.time_label = QLabel("Time Elapsed: 00:00:00")
        layout.addWidget(self.time_label)

        # Template list
        self.template_list = QListWidget()
        layout.addWidget(self.template_list)

        # Buttons
        button_layout = QHBoxLayout()

        upload_button = QPushButton("Upload Template")
        upload_button.clicked.connect(self.upload_template)
        button_layout.addWidget(upload_button)

        remove_button = QPushButton("Remove Selected Template")
        remove_button.clicked.connect(self.remove_selected_template)
        button_layout.addWidget(remove_button)

        save_button = QPushButton("Save Template")
        save_button.clicked.connect(self.save_automation_template)
        button_layout.addWidget(save_button)

        delete_button = QPushButton("Delete Template")
        delete_button.clicked.connect(self.delete_automation_template)
        button_layout.addWidget(delete_button)

        layout.addLayout(button_layout)

        # Automation controls
        start_button = QPushButton("Start Automation")
        start_button.clicked.connect(self.start_automation)
        layout.addWidget(start_button)

        stop_button = QPushButton("Stop Automation")
        stop_button.clicked.connect(self.stop_automation)
        layout.addWidget(stop_button)

        self.setLayout(layout)

    def upload_template(self):
        """Upload a new image template."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Image File", "", "Image Files (*.png *.jpg *.jpeg)")
        if file_path:
            self.templates.append(file_path)
            self.update_template_list()

    def remove_selected_template(self):
        """Remove the selected template."""
        selected_items = self.template_list.selectedItems()
        for item in selected_items:
            index = self.template_list.row(item)
            self.templates.pop(index)
            self.template_list.takeItem(index)

    def save_automation_template(self):
        """Save the current automation template."""
        template_name = self.template_name_input.text().strip()
        if not template_name:
            QMessageBox.warning(self, "Error", "Please enter a name for the template.")
            return
        if not self.templates:
            QMessageBox.warning(self, "Error", "No templates to save.")
            return
        self.automation_templates[template_name] = self.templates
        with open("automation_templates.json", "w") as f:
            json.dump(self.automation_templates, f, indent=4)
        if template_name not in [self.template_dropdown.itemText(i) for i in range(self.template_dropdown.count())]:
            self.template_dropdown.addItem(template_name)
        QMessageBox.information(self, "Saved", f"Template '{template_name}' saved.")

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
            QMessageBox.information(self, "Deleted", f"Template '{template_name}' deleted.")

    def load_automation_template_from_dropdown(self):
        """Load a selected automation template."""
        template_name = self.template_dropdown.currentText()
        if template_name == "Create New Template":
            self.templates = []
        else:
            self.templates = self.automation_templates.get(template_name, [])
        self.update_template_list()

    def update_template_list(self):
        """Update the displayed template list."""
        self.template_list.clear()
        for template in self.templates:
            item = QListWidgetItem(os.path.basename(template))
            item.setIcon(QIcon(template))
            self.template_list.addItem(item)

    def start_automation(self):
        """Start the automation."""
        if not self.templates:
            QMessageBox.warning(self, "Error", "No templates to run!")
            return
        self.running = True
        self.timer_started = False  # Reset the timer
        self.status_label.setText("Status: Running")
        Thread(target=self.automation_loop, daemon=True).start()
        Thread(target=self.update_time_elapsed, daemon=True).start()

    def stop_automation(self):
        """Stop the automation."""
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
                            self.start_time = time.time()  # Start timer on first detection
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
                    center_x = max_loc[0] + resized_template.shape[1] // 2
                    center_y = max_loc[1] + resized_template.shape[0] // 2
                    return center_x, center_y
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
    app.setWindowIcon(QIcon(resource_path("bitrevamp.ico")))

    window = AutomationApp()
    window.show()

    app.exec_()