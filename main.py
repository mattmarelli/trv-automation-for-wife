import sys
import pandas as pd
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget
)

from automation import create_output_file, create_test_duty_phase_buckets, find_peaks, split_brk_data_by_first_to_clear
from constants import test_duty_table

SELECT_AN_OPTION = "Select an option"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TRV Automation")
        self.resize(800, 500)

        self.local_station_edit = QLineEdit()
        self.local_station_edit.setPlaceholderText("Local station name")
        self.local_station_edit.textChanged.connect(self._update_run_enabled)

        self.remote_station_edit = QLineEdit()
        self.remote_station_edit.setPlaceholderText("Remote station name")
        self.remote_station_edit.textChanged.connect(self._update_run_enabled)

        self.breaker_names_edit = QLineEdit()
        self.breaker_names_edit.setPlaceholderText("Breaker names")
        self.breaker_names_edit.textChanged.connect(self._update_run_enabled)

        self.breaker_interrupting_rating_edit = QLineEdit()
        self.breaker_interrupting_rating_edit.setPlaceholderText("Breaker Interrupting Rating (kA)")
        self.breaker_interrupting_rating_edit.textChanged.connect(self._update_run_enabled)

        self.breaker_trv_voltage_class_select = QComboBox()
        self.breaker_trv_voltage_class_select.addItem(SELECT_AN_OPTION)
        self.breaker_trv_voltage_class_select.addItems(test_duty_table.keys())
        self.breaker_trv_voltage_class_select.setCurrentIndex(0)
        self.breaker_trv_voltage_class_select.model().item(0).setEnabled(False)
        self.breaker_trv_voltage_class_select.currentTextChanged.connect(self._update_run_enabled)

        self.trv_file_edit = QLineEdit()
        self.trv_file_edit.setPlaceholderText("Select TRV file")
        self.trv_file_edit.setReadOnly(True)

        self.brk_file_edit = QLineEdit()
        self.brk_file_edit.setPlaceholderText("Select BKR file")
        self.brk_file_edit.setReadOnly(True)

        browse_1_button = QPushButton("Browse...")
        browse_2_button = QPushButton("Browse...")
        self.run_button = QPushButton("Run Automation")
        self.run_button.setEnabled(False)

        root = QWidget()
        layout = QVBoxLayout(root)

        root = QWidget()
        layout = QVBoxLayout(root)

        local_station_edit_row = QHBoxLayout()
        local_station_edit_row.addWidget(QLabel("Local Station:"))
        local_station_edit_row.addWidget(self.local_station_edit, 1)

        remote_station_edit_row = QHBoxLayout()
        remote_station_edit_row.addWidget(QLabel("Remote Station:"))
        remote_station_edit_row.addWidget(self.remote_station_edit, 1)

        breaker_names_edit_row = QHBoxLayout()
        breaker_names_edit_row.addWidget(QLabel("Breaker Names:"))
        breaker_names_edit_row.addWidget(self.breaker_names_edit, 1)

        breaker_interrupting_rating_row = QHBoxLayout()
        breaker_interrupting_rating_row.addWidget(QLabel("Breaker Interrupting Rating (kA):"))
        breaker_interrupting_rating_row.addWidget(self.breaker_interrupting_rating_edit, 1)

        breaker_trv_voltage_class_select_row = QHBoxLayout()
        breaker_trv_voltage_class_select_row.addWidget(QLabel("IEEE Breaker TRV Voltage Class (kV, rms):"))
        breaker_trv_voltage_class_select_row.addWidget(self.breaker_trv_voltage_class_select, 1) 

        trv_file_edit_row = QHBoxLayout()
        trv_file_edit_row.addWidget(QLabel("File 1:"))
        trv_file_edit_row.addWidget(self.trv_file_edit, 1)
        trv_file_edit_row.addWidget(browse_1_button)

        brk_file_edit_row = QHBoxLayout()
        brk_file_edit_row.addWidget(QLabel("File 2:"))
        brk_file_edit_row.addWidget(self.brk_file_edit, 1)
        brk_file_edit_row.addWidget(browse_2_button)

        layout.addLayout(local_station_edit_row)
        layout.addLayout(remote_station_edit_row)
        layout.addLayout(breaker_names_edit_row)
        layout.addLayout(breaker_interrupting_rating_row)
        layout.addLayout(breaker_trv_voltage_class_select_row)
        layout.addLayout(trv_file_edit_row)
        layout.addLayout(brk_file_edit_row)
        layout.addWidget(self.run_button)


        self.setCentralWidget(root)

        browse_1_button.clicked.connect(lambda: self.pick_file(self.trv_file_edit))
        browse_2_button.clicked.connect(lambda: self.pick_file(self.brk_file_edit))
        self.run_button.clicked.connect(self.run_automation)

    def pick_file(self, target_edit: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select a file",
            str(Path.home()),
            "All Files (*);;CSV (*.csv);;Text (*.txt);;Excel (*.xlsx *.xls)"
        )
        if path:
            target_edit.setText(path)
            self._update_run_enabled()


    def _update_run_enabled(self):
        self.run_button.setEnabled(
            bool(self.local_station_edit.text()) and
            bool(self.remote_station_edit.text()) and
            bool(self.breaker_names_edit.text()) and
            bool(self.breaker_interrupting_rating_edit.text()) and
            bool(self.breaker_trv_voltage_class_select.currentText() != SELECT_AN_OPTION) and
            bool(self.trv_file_edit.text()) and
            bool(self.brk_file_edit.text())
        )


    def run_automation(self):
        trv_file = Path(self.trv_file_edit.text())
        brk_file = Path(self.brk_file_edit.text())

        if not trv_file.exists():
            QMessageBox.critical(self, "Missing TRV File", "The selected TRV file is not a valid path and unable to be found!")
            return

        if not brk_file.exists():
            QMessageBox.critical(self, "Missing BRK File", "The selected BRK file is not a valid path and unable to be found!")

        trv_rows = []
        row_count = 0
        with open(trv_file, "r") as f:
            for line in f:
                line = line.strip()

                if not line:
                    continue

                if row_count == 0:
                    row_count += 1
                    continue

                columns = line.split()
                if row_count != 1:
                    try:
                        int(columns[0])
                    except ValueError:
                        break  # break out of loop if the first value is not an int

                trv_rows.append(columns)
                row_count += 1

        brk_rows = []
        row_count = 0
        with open(brk_file, "r") as f:
            for line in f:
                line = line.strip()

                if not line:
                    continue

                if row_count == 0:
                    row_count += 1
                    continue

                columns = line.split()
                brk_rows.append(columns)

        trv_df = pd.DataFrame(trv_rows[1:], columns=[
            "Run #",
            "Fault_Type",
            "Fault_Location",
            "Loc1/Rem2 First",
            "Bypass Time",
            "CB1_A_Peak(kV)",
            "CB1_B_Peak(kV)",
            "CB1_C_Peak(kV)",
            "CB1_A_RRRV(kV/u)",
            "CB1_B_RRRV(kV/u)",
            "CB1_C_RRRV(kV/u)",
        ])
        trv_df = trv_df.astype(float)

        brk_df = pd.DataFrame(brk_rows[1:], columns=[
            "Run #",
            "BRK1_Int_Rt ",
            "BRK1A_RMS",
            "BRK1B_RMS",
            "BRK1C_RMS",
            "CB1_Excd_A",
            "CB1_Excd_B",
            "CB1_Excd_C",
        ])
        brk_df = brk_df.astype(float)

        breaker_input_rating = float(self.breaker_interrupting_rating_edit.text())
        test_duty_bucket_values = {
            "10%": {
                "low": 0,
                "high": breaker_input_rating * .1,
            },
            "30%": {
                "low": breaker_input_rating * .1,
                "high": breaker_input_rating * .3,
            },
            "60%": {
                "low": breaker_input_rating * .3,
                "high": breaker_input_rating * .6,
            },
            "100%": {
                "low": breaker_input_rating * .6,
                "high": breaker_input_rating,
            },
        }

        brk_local, brk_remote = split_brk_data_by_first_to_clear(brk_df, trv_df)
        runs_per_test_duty_bucket_local = create_test_duty_phase_buckets(brk_local, test_duty_bucket_values)
        runs_per_test_duty_bucket_remote = create_test_duty_phase_buckets(brk_remote, test_duty_bucket_values)
        local_peaks = find_peaks(runs_per_test_duty_bucket_local, trv_df)
        remote_peaks = find_peaks(runs_per_test_duty_bucket_remote, trv_df)

        create_output_file(
            local_peaks,
            remote_peaks,
            self.breaker_trv_voltage_class_select.currentText(),
            self.local_station_edit.text(),
            self.remote_station_edit.text(),
            self.breaker_names_edit.text()
        )

def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()