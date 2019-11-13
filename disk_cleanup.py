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
import hashlib
import pathlib

BTN_CAPTION_SELECT_FILE    = 'Select File'
BTN_CAPTION_SELECT_DIR     = 'Select Directory'
BTN_CAPTION_START_ANALYSIS = 'Start Analysis'
BTN_CAPTION_STOP_ANALYSIS  = 'Stop Analysis'

CONF_FILE_NAME        = '.file_compare.json'

CONF_FLD_WIDTH        = 'width'
CONF_FLD_HEIGHT       = 'height'
CONF_FLD_POS_X        = 'x'
CONF_FLD_POS_Y        = 'y'
CONF_FLD_PROJECT_FILE = 'project_file'
CONF_FLD_COMPARE_DIR  = 'compare_dir'

HASH_CALC_CHUNK_SIZE = 4096

LOG_CMD_CLEAR            = 'CLEAR'
LOG_TEXT_ANALYZING_FILE  = 'Analyzing: %s'
LOG_TEXT_CALCULATED_HASH = 'Calculated Hash: %s'
LOG_TEXT_FINISHED        = '\n------------------------------ FINISHED '\
                           '-------------------------------\n'
LOG_TEXT_HASH            = 'Hash: %s'
LOG_TEXT_FINDING_FILES   = 'Findind files...'
LOG_TEXT_FILE_FOUND      = 'File Found %s'
LOG_TEXT_NO_DUPLICATE    = 'No duplicte files found!'
LOG_TEXT_TAB             = '    %s'
LOG_TEXT_WARNING         = '\n WARNING: These files are 1-(2^-128) * 100 '\
                           'percent equal \n'

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

def alliter(p):
	"""

	Helper function to iterate over Pathlib strctures while
	providing interactivity

	"""
	yield p
	try:
		for sub in p.iterdir():
			if sub.is_dir():
				yield from alliter(sub)
			else:
				yield sub
	except Exception as e:
		Dbg("Error processing file")

class FileAnalysis(QThread):
	"""

	Main Thread to run file scan while keeping interactivity

	"""
	# Signal to log info for user
	log_line = pyqtSignal(str)
	# Signal to control text-box
	log_cmd = pyqtSignal(str)
	# Sihnal to report status if processed items
	set_proc_percent = pyqtSignal(int)

	def __init__(self, parent, idir, ofile):
		"""

		Constructor of object

		@parent: parent Qt Object required by QT Framework
		@idir:   directory to be scanned
		@ofile:  json file where result is written

		"""
		super(FileAnalysis, self).__init__(parent)
		self._idir = idir
		self._ofile = ofile
		# bytes processed
		self._processed_bytes = 0
		# total amount of bytes to be processed
		self._total_bytes = 0;

	def _get_processed_percent(self):
		"""

		Function to calculate the completion precentage. The Max value of
		QProgressBar is not used as file-size might exceed the max size the
		continer can handle.

		"""
		return int(self._processed_bytes * 100 / self._total_bytes)

	def _get_hash(self, file_name):
		"""

		Function to calculate an md5 hash on the file content.

		@file_name: Name o the file

		"""
		m = hashlib.md5()
		"""
		
		Let's save the value of processed bytes. This is restored after the
		file is processed. This is needed for multiple reason:
		    1.) if error happens during processing the file the rest of
		        the processing shows the correct value
		    2.) the interactivity of the form is increased as the progress 
		        bar is updated continously.

		"""
		psave = self._processed_bytes
		try:
			with open(file_name, 'rb') as f:
				# read the file in 4K chunks
				for chunk in iter(lambda: f.read(HASH_CALC_CHUNK_SIZE), b""):
					m.update(chunk)
					# update processed_bytes
					self._processed_bytes+=len(chunk)
					# Communicate  processing status to ProgressBar
					self.set_proc_percent.emit(self._get_processed_percent())
					# Call a yield, so other events can be processed
					self.yieldCurrentThread()
		except Exception as e:
			# TODO: Add proper exception handling. Error pop-up window
			Dbg('Erro processing file: %s' % file_name)

		"""
		 
		 Restore _processed_bytes. In case error happened. the value is updated
		 in the outer loop too.

		 """
		self._processed_bytes = psave

		return m.hexdigest()

	def _find_files(self):
		"""

		Find all file-names in the given directory. Also get file-siz info so
		progess bar can be calculated.

		"""
		fname = os.path.join(self._idir, '**')
		files_list = []
		for f in alliter(pathlib.Path(self._idir)):
			# No support for symlinks yet
			if os.path.islink(f):
				continue

			# Check if file found, as glob will mention directories too
			if os.path.isfile(f):
				self.log_line.emit(LOG_TEXT_FILE_FOUND % f)
				filed = FileRecord(f)
				files_list.append(filed)
				self._total_bytes+=filed.size
				# Make sure interactivity is provided
				self.yieldCurrentThread()

		return files_list

	def _build_file_compare_db(self, files_list):
		"""

		Function to calculate md5 hash on all files. Creates a dictionary, where
		the md5 hash of the ile content is th key and a list of filenames are
		assigned to it. Example:

		file_compare_db = { 'asghha28238hhj' : [ 'file1', 'file2'],
		                    '62872ksakajs81' : [ 'file3'] }

		If an entry has more than one file in the list, it means that they are
		equal. 2^-128 chance that they are different

		@files_list: list of FileRecord objects

		"""
		files_db = {}
		for filed in files_list:
			self.log_line.emit(LOG_TEXT_ANALYZING_FILE % str(filed.path))
			
			fh_key = self._get_hash(filed.path)
			self.log_line.emit(LOG_TEXT_CALCULATED_HASH % fh_key)
			
			# get the list for md5 hash, or init to to empty list
			flist = files_db.get(fh_key, [])
			flist.append(str(filed.path)) 
			files_db[fh_key] = flist
			
			# update progress bar
			self._processed_bytes+=filed.size
			self.set_proc_percent.emit(self._get_processed_percent())

		return files_db;

	def _generate_duplicate_report(self, files_db):
		"""

		Search the database of files and build a sictionary of duplicate files

		@files_db: a dictionary of file infomation. For format see: 
		           _build_file_compare_db
		
		"""
		dup_files = {}
		for key, file_list in files_db.items():
			# If more than 1 file in the list then there are duplicates
			if len(file_list) > 1:
				self.log_line.emit(LOG_TEXT_HASH %key)
				dup_files[key] = file_list
				for filename in file_list:
					self.log_line.emit(LOG_TEXT_TAB % filename)

		if not bool(dup_files):
			self.log_line.emit(LOG_TEXT_NO_DUPLICATE)

		return dup_files

	def _save_duplicate_files_report(self, duplicate_files):
		"""

		Function to dump the duplicate_file informmation to a JSON file

		@duplicate_files: dictionary of duplicate files

		"""
		try:
			with open(self._ofile, 'w') as fp:
				json.dump(duplicate_files, fp, indent=4, sort_keys=True)
		except Exception as e:
			#TODO: implement proper error handling
			Dbg('Error saving output file: %s' % self._ofile)
	
	def run(self):
		"""

		Main thread to run the actual analysis.

		"""
		# Find files in directory
		self.log_line.emit(LOG_TEXT_FINDING_FILES)
		files_list = self._find_files()
		# Calculate md5 hash on files to detect duplcates
		files_db = self._build_file_compare_db(files_list)
		
		# Cleat reported information before finishing the report for dup files
		self.log_cmd.emit(LOG_CMD_CLEAR)
		self.log_line.emit(LOG_TEXT_FINISHED)
		self.log_line.emit(LOG_TEXT_WARNING)

		# Report all duplicated files
		dup_files_report = self._generate_duplicate_report(files_db)
		# Save duplicated files into JSON file
		self._save_duplicate_files_report(dup_files_report)

	def stop(self):
		self.quit()

class AnalysisForm(QWidget):
	"""

	Form to hold the Text-box and Progress bar, informing the user about the
	status of the file report

	"""
	def _setup_form(self):
		"""

		Assembling the form

		"""
		self._layout = QVBoxLayout()
		self._progress_bar = QProgressBar()
		self._text_box = QTextEdit()

		self._progress_bar.setRange(0, 100)
		self._layout.addWidget(self._progress_bar)
		self._layout.addWidget(self._text_box)
		self.setLayout(self._layout)
		self.setWindowTitle(WINDOW_TITLE_ANALYSIS)

	def _setup_thread(self):
		"""

		Setting up background thread running ananlysis & configuring signals

		"""
		self.thread = FileAnalysis(self,
 								   self._input_data_panel.compare_dir.text(),
 								   self._input_data_panel.project_file.text())
		self.thread.log_line.connect(self.handle_log_line)
		self.thread.log_cmd.connect(self.handle_log_command)
		self.thread.set_proc_percent.connect(self.handle_set_processed_percent)

	def __init__(self, input_data_panel, parent=None):
		"""

		Constructor. Create thread and the panel. Start the thread.

		@input_data_panel: Passed in as information such as file-names are used
		@parent: Parent QtWidget - We're not using it. Separate Widget. 
		"""
		super(AnalysisForm, self).__init__(parent)
		self._input_data_panel = input_data_panel
		self._setup_form()
		self._setup_thread()
		self.thread.start()

	def handle_log_line(self, log_line):
		"""

		Sets teh message generated by the thread, received via signal to the 
		text-box of the panel

		@log_line: A string to be appended to the box

		"""
		self._text_box.append(log_line)

	def handle_log_command(self, log_command):
		"""

		Signal handler to handle different commands affectin the text-box for
		progress report

		@log_command: A strring represantation of the command to be executed

		"""
		if (log_command == LOG_CMD_CLEAR):
			self._text_box.clear()
		else:
			Dbg('Invalid log command')

	def handle_set_processed_percent(self, processed_percent):
		"""

		Signal handler to report progress on progress bar

		@processed_percent: An integer value for the status in %

		"""
		self._progress_bar.setValue(processed_percent)

	def closeEvent(self, event):
		"""

		Override of QT closeEvent method. If the user presses the X button on
		top of the panel the analysis thread has to be interrupted.

		"""
		event.accept()
		# Set the main panel button back to "Stop Analysis"
		self._input_data_panel._stop_analysis(close_panel=False)

	def __del__(self):
		self.thread.stop()
		self.thread.wait()

class InputDataPanel(QWidget):
	"""

	Main panel of application when it is started

	"""
	def _load_config(self):
		"""

		Function to load the configuration file for the user. This file stores
		form size, position and last searches.

		"""
		home = Path.home()
		conf_file = os.path.join(home, CONF_FILE_NAME)
		self._config = {}
		try:
			with open(conf_file) as fp:
				self._config = json.load(fp)
		except Exception as e:
			# TODO: Add better execption handling
			Dbg('Failed to read user-config file.')
		
		#Set Panel based on config, or default values if no config exists
		self.move(self._config.get(CONF_FLD_POS_X, 100), 
			      self._config.get(CONF_FLD_POS_Y,100))
		self.resize(self._config.get(CONF_FLD_WIDTH,250),
			        self._config.get(CONF_FLD_HEIGHT,50))
		self.project_file.setText(self._config.get(CONF_FLD_PROJECT_FILE, ''))
		self.compare_dir.setText(self._config.get(CONF_FLD_COMPARE_DIR, ''))

	def _save_config(self):
		"""

		Save user specific settings on exiting the application.

		"""
		home = Path.home()
		conf_file = os.path.join(home, CONF_FILE_NAME)

		# Create a config object to be saved
		self._config[CONF_FLD_WIDTH] = self.width()
		self._config[CONF_FLD_HEIGHT] = self.height()
		self._config[CONF_FLD_POS_X] = self.pos().x()
		self._config[CONF_FLD_POS_Y] = self.pos().y();
		self._config[CONF_FLD_PROJECT_FILE] = self.project_file.text()
		self._config[CONF_FLD_COMPARE_DIR] = self.compare_dir.text()
		try:
			with open(conf_file, 'w') as fp:
				json.dump(self._config, fp)
		except Exception as e:
			Dbg('Failed to save user information.')
	
	def _update_analysis_button_state(self):
		"""

		Analysis button shall be greyed out if empty fields are empty

		"""
		self._analysis_btn.setEnabled(
			bool(self.compare_dir.text()) and bool(self.project_file.text()))

	def _toggle_input_fields(self, enabled):
		"""
		Function to set the input fields to enabled or disabled. 

		@enabled: boolean. On True both input fields can be read and written

		"""
		self.compare_dir.setEnabled(enabled)
		self.project_file.setEnabled(enabled)
		self._select_project_file_btn.setEnabled(enabled)
		self._open_dir_btn.setEnabled(enabled)

	def _select_compare_dir(self):
		"""

		Function to invoke a directory open panel and save the directory name
		in the compare directory input field

		"""
		Dbg ("Select directory to compare files")
		options = QFileDialog.Options()
		options |= QFileDialog.DontUseNativeDialog
		options |= QFileDialog.ShowDirsOnly
		dir_name = QFileDialog.getExistingDirectory(self,
			"QFileDialog.getCompareDir", "", options=options)      

		self.compare_dir.setText(dir_name)

	def _select_project_file(self):
		"""

		Function to open a save file dialogue to specify a json file name, where
		the result of the file analysis will be saved.

		"""
		options = QFileDialog.Options()
		options |= QFileDialog.DontUseNativeDialog
		file_name, _ = QFileDialog.getSaveFileName(self,
			"QFileDialog.getOpenFileName()", "",
			"Json Files (*json)", options=options)      

		# If filename does not end with .json, append .json
		self.project_file.setText(
			file_name if file_name.endswith('.json') else file_name + '.json')

	def _stop_analysis(self, close_panel=True):
		"""

		Function to stop the analysis

		"""
		Dbg('Stop Analysis')
		self._analysis_btn.setText(BTN_CAPTION_START_ANALYSIS)
		if close_panel:
			self._running_analysis.close()
			self._running_analysis = None
		self._toggle_input_fields(True)

	def _start_analysis(self):
		"""

		Function to start analysis

		"""
		Dbg('Start Analysis')
		self._analysis_btn.setText(BTN_CAPTION_STOP_ANALYSIS)
		self._running_analysis = AnalysisForm(self)
		# Set position of Analysis form relative to our pos
		self._running_analysis.move(self.pos().x(),
									self.pos().y() + self.height() + 50)
		self._running_analysis.resize(self.width() * 2, 300)
		self._running_analysis.show()
		self._toggle_input_fields(False)

	def _analysis_clicked(self):
		"""

		Handler function of Analysis button clicked

		"""
		if self._running_analysis is None:
			self._start_analysis()	
		else:
			self._stop_analysis()

	def closeEvent(self, event):
		"""

		Override function of close window. It saves user data

		"""
		self._save_config()
		event.accept()

	def __init__(self, parent = None):
		"""

		Constructor: Assembling the form

		"""
		super(InputDataPanel, self).__init__(parent)

		my_layout = QVBoxLayout()
		
		compare_dir_layout = QHBoxLayout()
		self.compare_dir = QLineEdit()
		compare_dir_layout.addWidget(self.compare_dir)
		self.compare_dir.textChanged.connect(self._update_analysis_button_state)
		self._open_dir_btn = QPushButton(BTN_CAPTION_SELECT_DIR)
		self._open_dir_btn.clicked.connect(self._select_compare_dir)
		compare_dir_layout.addWidget(self._open_dir_btn)

		save_file_layout = QHBoxLayout()
		self.project_file = QLineEdit()
		save_file_layout.addWidget(self.project_file)
		self.project_file.textChanged.connect(self._update_analysis_button_state)
		self._select_project_file_btn = QPushButton(BTN_CAPTION_SELECT_FILE)
		self._select_project_file_btn.clicked.connect(self._select_project_file)
		save_file_layout.addWidget(self._select_project_file_btn)

		self._analysis_btn = QPushButton(BTN_CAPTION_START_ANALYSIS)
		self._analysis_btn.clicked.connect(self._analysis_clicked)
		self._update_analysis_button_state()

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
