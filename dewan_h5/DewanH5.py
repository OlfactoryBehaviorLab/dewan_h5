"""
Dewan Lab H5 Parsing Library
Author: Austin Pauley (pauley@psy.fsu.edu)
Date: 01-04-2025
"""
import traceback

import h5py
import pandas as pd

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
        self.trial_parameters: Union[pd.DataFrame, None] = None

        self._file = None


    def _open(self):
        try:
            self._file = h5py.File(self.file_path, 'r')
        except FileNotFoundError as e:
            print(f'Error! {self.file_path} not found!')
            self._file = None


    def _parse_trial_matrix(self):
        trial_matrix = self._file['Trials']
        trial_matrix_attrs = trial_matrix.attrs
        table_col = [trial_matrix_attrs[key].astype(str) for key in trial_matrix_attrs.keys() if 'NAME' in key]
        data_dict = {}

        for col in table_col:
            data_dict[col] = trial_matrix[col]

        self.trial_parameters = pd.DataFrame(data_dict)

    def __enter__(self):
        if not self.file_path:
            print('No file path passed, opening file browser!')
            #open file browser

        self._open()
        self._parse_trial_matrix()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None and exc_val is None and exc_tb is None:
            if self._file:
                self._file.close()
            return False
        else:
            if self._file:
                self._file.close()


    def __str__(self):
        return (f'Dewan Lab H5 file:\n'
                f'Mouse: {self.mouse_number}\n'
                f'Experiment Date: {self.date}\n'
                f'Experiment Time: {self.time}\n')

    def __repr__(self):
        return type(self)

