"""
Dewan Lab H5 Parsing Library
Author: Austin Pauley (pauley@psy.fsu.edu)
Date: 01-04-2025
"""

import h5py
import traceback
from pathlib import Path
from typing import Union


class DewanH5:
    def __init__(self, file_path:  Union[None, Path] = None):

        self.file_path = file_path

        # Parameters from H5 File
        self.mouse_number = 0
        self.total_trials = 0
        self.date = None
        self.time = None
        self.sniffing = None
        self.licking = None
        self.trial_parameters = None

        self._file = None

        self._create()

    def _create(self):
        if not self.file_path:
            # Open file selector
            pass
        else:
            self._open()

    def _open(self):
        try:
            self._file = h5py.File(self.file_path, 'r')
        except FileNotFoundError as e:
            print(f'Error! {self.file_path} not found!')
            self._file = None

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None and exc_val is None and exc_tb is None:
            return False
        else:
            pass


    def __str__(self):
        return (f'Dewan Lab H5 file:\n'
                f'Mouse: {self.mouse_number}\n'
                f'Experiment Date: {self.date}\n'
                f'Experiment Time: {self.time}\n')

