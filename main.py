import sys
import os
import subprocess
import re
import shutil

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout,
                             QVBoxLayout, QTextEdit, QPushButton, QLabel, QLineEdit,
                             QFileDialog, QMessageBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal


# Worker do zapisywania plików, wywoływania komend itp.
class RedirectionWorker(QThread):
    output = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, command_str, cwd=None, parent=None):
        super().__init__(parent)
        self.command_str = command_str
        self.cwd = cwd

    def run(self):
        self.output.emit("Executing command: " + self.command_str)
        try:
            proc = subprocess.Popen(
                self.command_str,
                shell=True,
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

        # Instalacja build-essential do budowania plików .c
        if self.command_exists("make"):
            self.output.emit("Build-essential is installed, skipping installation.")
        else:
            self.output.emit("Build-essential not found, installing build-essential...")
            self.run_command(["sudo", "apt", "install", "-y", "build-essential"])

        # Instalacja narzędzi aeskeyfind/rsakeyfind
        self.output.emit("Installing/updating aeskeyfind...")
        self.run_command(["sudo", "apt", "install", "-y", "aeskeyfind"])
        self.output.emit("Installing/updating rsakeyfind...")
        self.run_command(["sudo", "apt", "install", "-y", "rsakeyfind"])

        # Instalacja Interrogate
        repo = "https://github.com/carmaa/interrogate.git"
        d = "interrogate"
        if not os.path.exists(d):
            self.output.emit("Cloning interrogate...")
            self.run_command(["git", "clone", repo, d])
        else:
            self.output.emit("Updating interrogate...")
            self.run_command(["git", "pull"], cwd=d)
        if os.path.exists(d):
            self.output.emit("Building interrogate...")
            self.run_command(["make"], cwd=d)

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
            return bool(result.stdout.strip())
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

        self.serpent_button = QPushButton("Run serpent finder")
        self.serpent_button.clicked.connect(self.start_serpent)
        control_layout.addWidget(self.serpent_button)

        self.twofish_button = QPushButton("Run twofish finder")
        self.twofish_button.clicked.connect(self.start_twofish)
        control_layout.addWidget(self.twofish_button)

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

    def aes_parser(self, input_path: str, out_path: str) -> None:
        try:
            data = re.sub(r"\s+", "", open(input_path, "r", encoding="utf-8").read())
            pattern = r"FOUNDPOSSIBLE(128|256)-BITKEYATBYTE([0-9A-Fa-f]+)KEY"
            pairs = [(m.group(1), m.group(2)) for m in re.finditer(pattern, data)]
            lines = [f"{size},{offset}" for size, offset in pairs]
            with open(out_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except Exception as e:
            self.log(f"Error in aes_parser: {e}")

    def rsa_parser(self, input_path: str, out_path: str) -> None:
        try:
            data = re.sub(r"\s+", "", open(input_path, "r", encoding="utf-8").read())
            pattern = r"FOUNDPRIVATEKEYAT([0-9A-Fa-f]+)version"
            vals = [m.group(1) for m in re.finditer(pattern, data)]
            with open(out_path, "w", encoding="utf-8") as f:
                f.write("\n".join(vals))
        except Exception as e:
            self.log(f"Error in rsa_parser: {e}")

    def twofish_parser(self, input_path, out_path):
        try:
            data = re.sub(r"\s+", "", open(input_path, encoding="utf-8").read())
            pattern = r"Twofishkeyfoundat([0-9A-Fa-f]+)\."
            lst = [m.group(1) for m in re.finditer(pattern, data)]
            with open(out_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lst))
        except Exception as e:
            self.log("Error in twofish_parser: " + str(e))

    def serpent_parser(self, input_path, out_path):
        try:
            data = re.sub(r"\s+", "", open(input_path, encoding="utf-8").read())
            pattern = r"Found\(probable\)SERPENTkeyatoffset([0-9A-Fa-f]+):"
            lst = [m.group(1) for m in re.finditer(pattern, data)]
            with open(out_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lst))
        except Exception as e:
            self.log("Serpent parser error: " + str(e))

    def start_aeskeyfind(self):
        m = self.mem_path_edit.text().strip()
        r = self.res_path_edit.text().strip()

        # walidacja ścieżek
        if not m or not r:
            QMessageBox.critical(self, "Error", "Provide mem file and results folder")
            return
        if not os.path.isfile(m):
            QMessageBox.critical(self, "Error", f"Memory file not found:\n{m}")
            return

        # walidacja narzędzia
        if shutil.which("aeskeyfind") is None:
            QMessageBox.critical(self, "Error", "aeskeyfind not found. Run startup tasks first.")
            return

        os.makedirs(r, exist_ok=True)
        output_file = os.path.join(r, "aeskeyfind_output.txt")
        cmd = f"aeskeyfind -v -q {m} > {output_file}"
        self.log("Running aeskeyfind on: " + m)

        self.aeskey_worker = RedirectionWorker(cmd)
        self.aeskey_worker.output.connect(self.log)

        def on_aes_done():
            self.log(f"aeskeyfind finished. Output appended to {output_file}")
            self.aes_parser(os.path.join(r, "aeskeyfind_output.txt"),
                            os.path.join(r, "aes_values.txt"))
            self.log(f"AES values saved to {os.path.join(r, 'aes_values.txt')}")

        self.aeskey_worker.finished.connect(on_aes_done)
        self.aeskey_worker.start()


    def start_rsakeyfind(self):
        m = self.mem_path_edit.text().strip()
        r = self.res_path_edit.text().strip()

        # walidacja ścieżek
        if not m or not r:
            QMessageBox.critical(self, "Error", "Provide mem file and results folder")
            return
        if not os.path.isfile(m):
            QMessageBox.critical(self, "Error", f"Memory file not found:\n{m}")
            return

        # walidacja narzędzia
        if shutil.which("rsakeyfind") is None:
            QMessageBox.critical(self, "Error", "rsakeyfind not found. Run startup tasks first.")
            return

        os.makedirs(r, exist_ok=True)
        output_file = os.path.join(r, "rsakeyfind_output.txt")
        cmd = f"rsakeyfind {m} > {output_file}"
        self.log("Running rsakeyfind on: " + m)

        self.rsakey_worker = RedirectionWorker(cmd)
        self.rsakey_worker.output.connect(self.log)

        def on_rsa_done():
            self.log(f"rsakeyfind finished. Output appended to {output_file}")
            self.rsa_parser(os.path.join(r, "rsakeyfind_output.txt"),
                            os.path.join(r, "rsa_values.txt"))
            self.log(f"RSA values saved to {os.path.join(r, 'rsa_values.txt')}")

        self.rsakey_worker.finished.connect(on_rsa_done)
        self.rsakey_worker.start()




    def start_serpent(self):
        m = self.mem_path_edit.text().strip()
        r = self.res_path_edit.text().strip()
        if not m or not r:
            QMessageBox.critical(self, "Error", "Provide mem file and results folder")
            return
        if not os.path.isdir("interrogate"):
            QMessageBox.critical(self, "Error", "Directory 'interrogate' not found. Run startup first.")
            return
        os.makedirs(r, exist_ok=True)
        out = os.path.join(r, "serpent_output.txt")
        cmd = f"./interrogate -a serpent {m} > {out}"
        self.log("Running serpent finder on: " + m)
        self.serpent_worker = RedirectionWorker(cmd, cwd="interrogate")
        self.serpent_worker.output.connect(self.log)
        self.serpent_worker.finished.connect(
            lambda: self._on_crypto_done(out, r, "serpent")
        )
        self.serpent_worker.start()

    def start_twofish(self):
        m = self.mem_path_edit.text().strip()
        r = self.res_path_edit.text().strip()
        if not m or not r:
            QMessageBox.critical(self, "Error", "Provide mem file and results folder")
            return
        if not os.path.isdir("interrogate"):
            QMessageBox.critical(self, "Error", "Directory 'interrogate' not found. Run startup first.")
            return
        os.makedirs(r, exist_ok=True)
        out = os.path.join(r, "twofish_output.txt")
        cmd = f"./interrogate -a twofish {m} > {out}"
        self.log("Running twofish finder on: " + m)
        self.twofish_worker = RedirectionWorker(cmd, cwd="interrogate")
        self.twofish_worker.output.connect(self.log)
        self.twofish_worker.finished.connect(
            lambda: self._on_crypto_done(out, r, "twofish")
        )
        self.twofish_worker.start()

    def _on_crypto_done(self, input_path, res_folder, algo):
        # wybór parsera
        parser = getattr(self, f"{algo}_parser")
        out_values = os.path.join(res_folder, f"{algo}_values.txt")
        parser(input_path, out_values)
        self.log(f"{algo.capitalize()} values saved to {out_values}")


if __name__ == '__main__':
    # Upewnij się, że XDG_RUNTIME_DIR jest ustawione, jeśli uruchamiasz jako root
    if not os.environ.get('XDG_RUNTIME_DIR'):
        os.environ['XDG_RUNTIME_DIR'] = f"/run/user/{os.geteuid()}"
    app = QApplication(sys.argv)
    window = LauncherWindow()
    window.show()
    sys.exit(app.exec_())
