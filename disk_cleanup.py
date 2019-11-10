"""

Disk Duplicate File Analysis Tool

Author:

		Zoltan Bacskai (z.bacskai.jr@gmail.com)

		2019

"""
from PyQt5.QtWidgets import (
	QApplication,
	QWidget, 
	QPushButton,
	QVBoxLayout,
	QHBoxLayout,
	QLineEdit,
	QFileDialog, 
	QTextEdit, 
	QProgressBar )
from PyQt5.QtCore import (
	QThread,
	QObject,
	pyqtSignal)

import time
from pathlib import Path
import os
import json
import glob
import hashlib

BTN_CAPTION_SELECT_FILE    = 'Select File'
BTN_CAPTION_SELECT_DIR     = 'Select Directory'
BTN_CAPTION_START_ANALYSIS = 'Start Analysis'
BTN_CAPTION_STOP_ANALYSIS  = 'Stop Analysis'


CONF_FILE_NAME='.file_compare.json'

HASH_CALC_CHUNK_SIZE = 4096

LOG_CMD_CLEAR            = 'CLEAR'
LOG_TEXT_ANALYZING_FILE  = 'Analyzing: %s'
LOG_TEXT_CALCULATED_HASH = 'Calculated Hash: %s'
LOG_TEXT_FINISHED        = '\n------------------------------ FINISHED -------------------------------\n'
LOG_TEXT_HASH            = 'Hash: %s'
LOG_TEXT_TAB             = '    %s'
LOG_TEXT_WARNING         = '\n WARNING: These files are 1-(2^-128) * 100 percent equal \n'

WINDOW_TITLE_MAIN     = 'Find Duplicate Files'
WINDOW_TITLE_ANALYSIS = 'Analysis'

class Dbg(object):
	"""

	Wrapper class around debug linies

	"""
	def __init__(self, dbg_msg):
		self._dbg_msg = dbg_msg

	def __del__(self):
		print(self._dbg_msg)

class FileRecord(object):
	"""

	File Record. Filled to hold file size and path info during
	analysis of the disk

	"""
	def __init__(self, path):
		self.path = path
		self.size = os.path.getsize(path)

class FileAnalysis(QThread):
	log_line = pyqtSignal(str)
	log_cmd = pyqtSignal(str)
	set_proc_percent = pyqtSignal(int)

	def __init__(self, parent, idir, ofile):
		super(FileAnalysis, self).__init__(parent)
		self._idir = idir
		self._ofile = ofile
		self._processed_bytes = 0
		self._total_bytes = 0;

	def _get_processed_percent(self):
		return int(self._processed_bytes * 100 / self._total_bytes)

	def _get_hash(self, file_name):
		m = hashlib.md5()
		psave = self._processed_bytes
		with open(file_name, 'rb') as f:
			for chunk in iter(lambda: f.read(HASH_CALC_CHUNK_SIZE), b""):
				m.update(chunk)
				self._processed_bytes+=len(chunk)
				self.set_proc_percent.emit(self._get_processed_percent())
				self.yieldCurrentThread()

		self._processed_bytes = psave

		return m.hexdigest()

	def _find_files(self):
		fname = os.path.join(self._idir, '**')
		files_list = []
		for f in glob.glob(fname, recursive=True):
			if os.path.islink(f):
				continue

			if os.path.isfile(f):
				filed = FileRecord(f)
				files_list.append(filed)
				self._total_bytes+=filed.size

		return files_list

	def _build_file_compare_db(self, files_list):
		files_db = {}
		for filed in files_list:
			self.log_line.emit(LOG_TEXT_ANALYZING_FILE % str(filed.path))
			file_hash = self._get_hash(filed.path)
			
			fh_key = str(file_hash)
			self.log_line.emit(LOG_TEXT_CALCULATED_HASH % fh_key)
			flist = files_db.get(fh_key, [])
			flist.append(str(filed.path)) 
			files_db[fh_key] = flist
			
			self._processed_bytes+=filed.size
			self.set_proc_percent.emit(self._get_processed_percent())

		return files_db;

	def _generate_duplicate_report(self, files_db):
		dup_files = {}
		for key, file_list in files_db.items():
			if len(file_list) > 1:
				self.log_line.emit(LOG_TEXT_HASH %key)
				dup_files[key] = file_list
				for filename in file_list:
					self.log_line.emit(LOG_TEXT_TAB % filename)

		return dup_files

	def _save_duplicate_files_report(self, duplicate_files):
		with open(self._ofile, 'w') as fp:
			json.dump(duplicate_files, fp, indent=4, sort_keys=True)
	
	def run(self):
		files_list = self._find_files()
		files_db = self._build_file_compare_db(files_list)
		
		self.log_cmd.emit(LOG_CMD_CLEAR)
		self.log_line.emit(LOG_TEXT_FINISHED)
		self.log_line.emit(LOG_TEXT_WARNING)

		dup_files_report = self._generate_duplicate_report(files_db)
		self._save_duplicate_files_report(dup_files_report)

		while True:
			time.sleep(1.0)

	def stop(self):
		self.terminate()

class AnalysisForm(QWidget):
	def _setup_form(self):
 		self._layout = QVBoxLayout()
 		self._progress_bar = QProgressBar()
 		self._text_box = QTextEdit()

 		self._progress_bar.setRange(0, 100)
 		self._layout.addWidget(self._progress_bar)
 		self._layout.addWidget(self._text_box)
 		self.setLayout(self._layout)
 		self.setWindowTitle(WINDOW_TITLE_ANALYSIS)

	def _setup_thread(self):
 		self.thread = FileAnalysis(self,
 								   self._input_data_panel.compare_dir.text(),
 								   self._input_data_panel.project_file.text())
 		self.thread.log_line.connect(self.handleLogLine)
 		self.thread.log_cmd.connect(self.handleLogCommand)
 		self.thread.set_proc_percent.connect(self.handleSetProcessedPercent)
 		self.thread.finished.connect(self.close)

	def __init__(self, input_data_panel, parent=None):
 		super(AnalysisForm, self).__init__(parent)
 		self._input_data_panel = input_data_panel
 		self._setup_form()
 		self._setup_thread()
 		self.thread.start()

	def handleLogLine(self, log_line):
 		self._text_box.append(log_line)

	def handleLogCommand(self, log_command):
 		if (log_command == LOG_CMD_CLEAR):
 			self._text_box.clear()
 		else:
 			Dbg('Invalid log command')

	def handleSetProcessedPercent(self, processed_percent):
 		self._progress_bar.setValue(processed_percent)

	def closeEvent(self, event):
 		self.thread.stop()
 		self.thread = None
 		event.accept()
 		self._input_data_panel._stop_analysis()

class InputDataPanel(QWidget):
	def _load_config(self):
		home = Path.home()
		conf_file = os.path.join(home, CONF_FILE_NAME)
		self._config = {}
		with open(conf_file) as fp:
			self._config = json.load(fp)
			self.move(self._config.get('x', 100), self._config.get('y',100))
			self.resize(self._config.get('width',250), self._config.get('height',50))
			self.project_file.setText(self._config.get('project_file', ''))
			self.compare_dir.setText(self._config.get('compare_dir', ''))

	def _save_config(self):
		home = Path.home()
		conf_file = os.path.join(home, CONF_FILE_NAME)
		self._config['width'] = self.width()
		self._config['height'] = self.height()
		self._config['x'] = self.pos().x()
		self._config['y'] = self.pos().y();
		self._config['project_file'] = self.project_file.text()
		self._config['compare_dir'] = self.compare_dir.text()
		with open(conf_file, 'w') as fp:
			json.dump(self._config, fp)
	
	def _updateAnalysisButtonState(self):
		self._analysis_btn.setEnabled(
			bool(self.compare_dir.text()) and bool(self.project_file.text()))

	def _toggleInputFields(self, enabled):
		self.compare_dir.setEnabled(enabled)
		self.project_file.setEnabled(enabled)
		self._select_project_file_btn.setEnabled(enabled)
		self._open_dir_btn.setEnabled(enabled)

	def _select_compare_dir(self):
		Dbg ("Select directory to compare files")
		options = QFileDialog.Options()
		options |= QFileDialog.DontUseNativeDialog
		options |= QFileDialog.ShowDirsOnly
		dirName = QFileDialog.getExistingDirectory(self,"QFileDialog.getCompareDir", "", options=options)      

		self.compare_dir.setText(dirName)

	def _select_project_file(self):
		options = QFileDialog.Options()
		options |= QFileDialog.DontUseNativeDialog
		file_name, _ = QFileDialog.getSaveFileName(self,"QFileDialog.getOpenFileName()", "","Json Files (*json)", options=options)      

		self.project_file.setText(file_name if file_name.endswith('.json') else file_name + '.json')

	def _stop_analysis(self):
		Dbg('Stop Analysis')
		self._analysis_btn.setText(BTN_CAPTION_START_ANALYSIS)
		self._running_analysis.close()
		self._running_analysis = None
		self._toggleInputFields(True)

	def _start_analysis(self):
		Dbg('Start Analysis')
		self._analysis_btn.setText(BTN_CAPTION_STOP_ANALYSIS)
		self._running_analysis = AnalysisForm(self)
		self._running_analysis.move(self.pos().x(), self.pos().y() + self.height() + 50)
		self._running_analysis.resize(self.width() * 2, 300)
		self._running_analysis.show()
		self._toggleInputFields(False)

	def _analysis_clicked(self):
		if self._running_analysis is None:
			self._start_analysis()	
		else:
			self._stop_analysis()

	def closeEvent(self, event):
		self._save_config()
		event.accept()

	def __init__(self, parent = None):
		super(InputDataPanel, self).__init__(parent)

		my_layout = QVBoxLayout()
		
		compare_dir_layout = QHBoxLayout()
		self.compare_dir = QLineEdit()
		compare_dir_layout.addWidget(self.compare_dir)
		self.compare_dir.textChanged.connect(self._updateAnalysisButtonState)
		self._open_dir_btn = QPushButton(BTN_CAPTION_SELECT_DIR)
		self._open_dir_btn.clicked.connect(self._select_compare_dir)
		compare_dir_layout.addWidget(self._open_dir_btn)

		save_file_layout = QHBoxLayout()
		self.project_file = QLineEdit()
		save_file_layout.addWidget(self.project_file)
		self.project_file.textChanged.connect(self._updateAnalysisButtonState)
		self._select_project_file_btn = QPushButton(BTN_CAPTION_SELECT_FILE)
		self._select_project_file_btn.clicked.connect(self._select_project_file)
		save_file_layout.addWidget(self._select_project_file_btn)

		self._analysis_btn = QPushButton(BTN_CAPTION_START_ANALYSIS)
		self._analysis_btn.clicked.connect(self._analysis_clicked)
		self._updateAnalysisButtonState()

		my_layout.addLayout(compare_dir_layout)
		my_layout.addLayout(save_file_layout)
		my_layout.addWidget(self._analysis_btn)
		
		self.setLayout(my_layout)
		self.setWindowTitle(WINDOW_TITLE_MAIN)

		self._running_analysis = None
		self._load_config()

class DiskCleanup(QApplication):
	"""

	Main Application Class

	"""
	def __init__(self):
		super(DiskCleanup, self).__init__([])
		self._input_data_panel = InputDataPanel()

	def main(self):
		"""

		Main function

		"""
		self._input_data_panel.show()
		self.exec_()

if __name__ == '__main__':
	fc = DiskCleanup()
	fc.main()
