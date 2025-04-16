import sys
import os
import subprocess

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout,
                             QVBoxLayout, QTextEdit, QPushButton, QLabel, QLineEdit,
                             QFileDialog, QMessageBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal


class RedirectionWorker(QThread):
    output = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, command_str, parent=None):
        super().__init__(parent)
        self.command_str = command_str

    def run(self):
        self.output.emit("Executing command: " + self.command_str)
        try:
            proc = subprocess.Popen(
                self.command_str,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            for line in iter(proc.stdout.readline, ""):
                if line:
                    self.output.emit(line.strip())
            proc.stdout.close()
            proc.wait()
            self.output.emit("Command finished with code: " + str(proc.returncode))
        except Exception as e:
            self.output.emit("Error while running command: " + str(e))
        self.finished.emit()


class CommandWorker(QThread):
    output = pyqtSignal(str)
    finished = pyqtSignal(int)  # exit code

    def __init__(self, command, cwd=None, parent=None):
        super().__init__(parent)
        self.command = command
        self.cwd = cwd

    def run(self):
        self.output.emit("Running command: " + " ".join(self.command))
        try:
            proc = subprocess.Popen(
                self.command,
                cwd=self.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            for line in iter(proc.stdout.readline, ""):
                if line:
                    self.output.emit(line.strip())
            proc.stdout.close()
            proc.wait()
            self.output.emit("Command finished with code: " + str(proc.returncode))
            self.finished.emit(proc.returncode)
        except Exception as e:
            self.output.emit("Error executing command: " + str(e))
            self.finished.emit(-1)


class StartupWorker(QThread):
    output = pyqtSignal(str)

    def run(self):
        # Instalacja gita
        if self.command_exists("git"):
            self.output.emit("Git is installed, skipping installation.")
        else:
            self.output.emit("Git not found, installing git...")
            self.run_command(["sudo", "apt", "install", "-y", "git"])

        # Instalacja build-essential do budowania plikow .C
        if self.command_exists("make"):
            self.output.emit("Build-essential is installed, skipping installation.")
        else:
            self.output.emit("Build-essential not found, installing build-essential...")
            self.run_command(["sudo", "apt", "install", "-y", "build-essential"])

        # Instalacja narzedzi aeskeyfind/rsakeyfind
        self.output.emit("Installing/updating aeskeyfind...")
        self.run_command(["sudo", "apt", "install", "-y", "aeskeyfind"])
        self.output.emit("Installing/updating rsakeyfind...")
        self.run_command(["sudo", "apt", "install", "-y", "rsakeyfind"])

        # Pobranie repozytorium z gita
        # Tutaj podałem przykładowe z jakimś kalkulatorem
        repo_url = "https://github.com/kacper0N/kalkulator.git"
        local_dir = "kalkulator"
        if not os.path.exists(local_dir):
            self.output.emit("Cloning kalkulator repository...")
            self.run_command(["git", "clone", repo_url])
        else:
            self.output.emit("Repository exists. Pulling latest changes...")
            self.run_command(["git", "pull"], cwd=local_dir)

        # Automatyczne budowanie kalkulatora - wykonanie make
        if os.path.exists(local_dir):
            self.output.emit("Building calculator (running make)...")
            self.run_command(["make"], cwd=local_dir)

        #To samo trzeba dla Serpent i Twofish



    def command_exists(self, command):
        """Sprawdza, czy dana komenda jest dostępna (używając 'which')."""
        try:
            result = subprocess.run(
                ["which", command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                universal_newlines=True
            )
            return True if result.stdout.strip() else False
        except subprocess.CalledProcessError:
            return False

    def run_command(self, command, cwd=None):
        try:
            proc = subprocess.Popen(
                command,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            for line in iter(proc.stdout.readline, ""):
                if line:
                    self.output.emit(line.strip())
            proc.stdout.close()
            proc.wait()
            self.output.emit("Command finished with code: " + str(proc.returncode))
        except Exception as e:
            self.output.emit("Error: " + str(e))


class LauncherWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Launcher Application")
        self.resize(900, 600)
        self.initUI()

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        # Lewy panel - konsola
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setLineWrapMode(QTextEdit.NoWrap)
        main_layout.addWidget(self.console, stretch=3)

        # Prawy panel - kontrolki
        control_panel = QWidget()
        control_layout = QVBoxLayout()
        control_panel.setLayout(control_layout)
        main_layout.addWidget(control_panel, stretch=1)

        # Sekcja z zadaniami startowymi
        startup_label = QLabel("Startup Tasks")
        control_layout.addWidget(startup_label)
        self.startup_button = QPushButton("Check updates and install tools")
        self.startup_button.clicked.connect(self.start_startup_tasks)
        control_layout.addWidget(self.startup_button)

        control_layout.addSpacing(20)

        # Ścieżki do pliku i folderu wynikowego
        mem_label = QLabel("Path to memory for analysis:")
        control_layout.addWidget(mem_label)
        self.mem_path_edit = QLineEdit()
        control_layout.addWidget(self.mem_path_edit)
        self.mem_browse_button = QPushButton("Browse file")
        self.mem_browse_button.clicked.connect(self.browse_memory_path)
        control_layout.addWidget(self.mem_browse_button)

        res_label = QLabel("Folder for results (.txt):")
        control_layout.addWidget(res_label)
        self.res_path_edit = QLineEdit()
        control_layout.addWidget(self.res_path_edit)
        self.res_browse_button = QPushButton("Browse folder")
        self.res_browse_button.clicked.connect(self.browse_results_folder)
        control_layout.addWidget(self.res_browse_button)

        control_layout.addSpacing(20)

        # Przyciski do uruchamiania narzędzi
        tools_label = QLabel("Run tools:")
        control_layout.addWidget(tools_label)
        self.aeskey_button = QPushButton("Run aeskeyfind")
        self.aeskey_button.clicked.connect(self.start_aeskeyfind)
        control_layout.addWidget(self.aeskey_button)
        self.rsakey_button = QPushButton("Run rsakeyfind")
        self.rsakey_button.clicked.connect(self.start_rsakeyfind)
        control_layout.addWidget(self.rsakey_button)


        #self.twofish_button = QPushButton("Run twofish")


        #self.serpent_button = QPushButton("Run serpent")


        control_layout.addStretch()

    def log(self, message):
        self.console.append(message)

    def start_startup_tasks(self):
        self.startup_button.setEnabled(False)
        self.log("Starting startup tasks...")
        self.startup_worker = StartupWorker()
        self.startup_worker.output.connect(self.log)
        self.startup_worker.finished.connect(self.startup_finished)
        self.startup_worker.start()

    def startup_finished(self):
        self.log("Startup tasks completed.")
        self.startup_button.setEnabled(True)

    def browse_memory_path(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select memory file")
        if file_path:
            self.mem_path_edit.setText(file_path)

    def browse_results_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select results folder")
        if folder_path:
            self.res_path_edit.setText(folder_path)

    def start_aeskeyfind(self):
        mem_path = self.mem_path_edit.text().strip()
        res_folder = self.res_path_edit.text().strip()
        if not mem_path:
            QMessageBox.critical(self, "Error", "Please enter a memory file path!")
            return
        if not res_folder:
            QMessageBox.critical(self, "Error", "Please enter a results folder!")
            return
        if not os.path.exists(res_folder):
            os.makedirs(res_folder)
        output_file = os.path.join(res_folder, "aeskeyfind_output.txt")
        command_str = "aeskeyfind -v -q {} > {}".format(mem_path, output_file)
        self.log("Running aeskeyfind on: " + mem_path)
        self.aeskey_worker = RedirectionWorker(command_str)
        self.aeskey_worker.output.connect(self.log)
        self.aeskey_worker.finished.connect(lambda: self.log("aeskeyfind finished. Output appended to " + output_file))
        self.aeskey_worker.start()

    def start_rsakeyfind(self):
        mem_path = self.mem_path_edit.text().strip()
        res_folder = self.res_path_edit.text().strip()
        if not mem_path:
            QMessageBox.critical(self, "Error", "Please enter a memory file path!")
            return
        if not res_folder:
            QMessageBox.critical(self, "Error", "Please enter a results folder!")
            return
        if not os.path.exists(res_folder):
            os.makedirs(res_folder)
        output_file = os.path.join(res_folder, "rsakeyfind_output.txt")
        command_str = "rsakeyfind {} > {}".format(mem_path, output_file)
        self.log("Running rsakeyfind on: " + mem_path)
        self.rsakey_worker = RedirectionWorker(command_str)
        self.rsakey_worker.output.connect(self.log)
        self.rsakey_worker.finished.connect(lambda: self.log("rsakeyfind finished. Output appended to " + output_file))
        self.rsakey_worker.start()

    #def start_serpent(self):


    #def start_twofish(self):



if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LauncherWindow()
    window.show()
    sys.exit(app.exec_())
