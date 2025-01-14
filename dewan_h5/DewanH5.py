"""
Dewan Lab H5 Parsing Library
Author: Austin Pauley (pauley@psy.fsu.edu)
Date: 01-04-2025
"""
import traceback
import warnings

import h5py
import pandas as pd

from datetime import datetime
from pathlib import Path
from typing import Union


class DewanH5:
    ## Dewan H5 File Description
    ## Values:
    ##      - N -> number of trials
    ##      - n -> references any arbitrary trial
    ##      - x -> arbitrary number
    ## File Structure
    ## '/': Contains N number of Groups for each trial with an additional group containing the trial data matrix
    ##      - 'Trials': Matrix containing n rows with columns for multiple parameters captured for each trial
    ##      - 'Trial000n' [type: group] (one group per trial): Holds samples for each trial
    ##          - 'Events' [type: dataset] (x number of tuples): (timestamp, number of sniff samples)
    ##          - 'lick1' [type: dataset] (x number of arrays): each array contains a variable number of lick timestamps for the 'left' lick tube
    ##          - 'lick2' [type: dataset] (x number of arrays): each array contains a variable number of lick timestamps for the 'right' lick tube
    ##          - 'sniff' [type: dataset]  (len(Events) number of arrays): each array contains samples recorded from the sniff sensor

    def __init__(self, file_path:  Union[None, Path] = None, suppress_errors=False):


        self.file_path = file_path
        self.suppress_errors = suppress_errors
        self._file: Union[h5py.File, None] = None

        # General parameters from H5 File
        self.date = None
        self.time = None
        self.mouse_number: int = 0
        self.rig: str = 'None Specified'

        # Quantitative Values
        self.total_trials: int = 0
        self.total_water_ul: int = 0
        self.go_performance: int = 0
        self.nogo_performance: int = 0
        self.total_performance: int = 0

        # Data Containers
        self.trial_parameters: Union[pd.DataFrame, None] = None
        self.sniff: dict[int, pd.Series] = {}
        self.lick1: dict[int, list] = {}
        self.lick2: dict[int, list] = {}


    def _parse_packets(self):
        trial_names = list(self._file.keys())[:-1]

        for index in range(len(trial_names)):
            timestamps = []
            sniff_samples = []
            lick_1_timestamps = []
            lick_2_timestamps = []
            trial_packet = self._file[trial_names[index]]

            sniff_events = trial_packet['Events']
            raw_sniff_samples = trial_packet['sniff']
            raw_lick_1_timestamps = trial_packet['lick1']
            raw_lick_2_timestamps = trial_packet['lick2']

            fv_on_time = self.trial_parameters.iloc[index]['fvOnTime'].astype(int)

            for timestamp, num_samples in sniff_events:
                new_ts = list(range(timestamp, timestamp + num_samples))
                timestamps.extend(new_ts)

            # Equivalent of np.hstack() should be a bit better than nested for loops
            _ = [sniff_samples.extend(sample_bin) for sample_bin in raw_sniff_samples]
            _ = [lick_1_timestamps.extend(lick_bin) for lick_bin in raw_lick_1_timestamps]
            _ = [lick_2_timestamps.extend(lick_bin) for lick_bin in raw_lick_2_timestamps]

            fv_offset_ts = [int(ts - fv_on_time) for ts in timestamps]
            lick_1_timestamps = [int(ts - fv_on_time) for ts in lick_1_timestamps]
            lick_2_timestamps = [int(ts - fv_on_time) for ts in lick_2_timestamps]
            sniff_data = pd.Series(sniff_samples, index=fv_offset_ts, name='sniff')

            self.sniff[index] = sniff_data
            self.lick1[index] = lick_1_timestamps
            self.lick2[index] = lick_2_timestamps


    def _parse_trial_matrix(self):
        trial_matrix = self._file['Trials']
        trial_matrix_attrs = trial_matrix.attrs
        table_col = [trial_matrix_attrs[key].astype(str) for key in trial_matrix_attrs.keys() if 'NAME' in key]
        data_dict = {}

        for col in table_col:
            data_dict[col] = trial_matrix[col]

        trial_parameters = pd.DataFrame(data_dict)
        self.trial_parameters = trial_parameters.map(lambda x: x.decode() if isinstance(x, bytes) else x)
        # Convert all the bytes to strings


    def _set_experiment_vals(self):
        self.rig = str(self.trial_parameters['rig'].values[0])
        self.mouse_number = self.trial_parameters['mouse'].values[0]
        self.total_trials = self.trial_parameters.shape[0]


    def _set_time(self):
        file_time = self._file.attrs['start_date']
        self.date, self.time = DewanH5.convert_date(file_time)


    def _open(self):
        try:
            self._file = h5py.File(self.file_path, 'r')
        except FileNotFoundError as e:
            print(f'Error! {self.file_path} not found!')
            print(traceback.format_exc())
            self._file = None
            self.__exit__(None, None, None)


    def debug_enter(self):
        warnings.warn("Using DewanH5 outside of a context manager is NOT recommended! "
                      "You must manually close the file reference using the close() method before deleting this instance!")

        return self.__enter__()



    def close(self):
        self.__exit__(None, None, None)

    def __enter__(self):
        if not self.file_path:
            print('No file path passed, opening file browser!')
            #open file browser

        self._open()
        self._parse_trial_matrix()
        self._set_experiment_vals()
        self._set_time()
        self._parse_packets()
        return self


    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._file:
            self._file.close()

        if exc_type is not None:
            if self.suppress_errors:
                return True
            else:
                return False


    def __str__(self):
        return (f'Dewan Lab H5 file: {self.file_path.name}\n'
                f'Mouse: {self.mouse_number}\n'
                f'Experiment Date: {self.date}\n'
                f'Experiment Time: {self.time}\n'
                f'Rig: {self.rig}\n'
                f'Total Trials: {self.total_trials}\n')


    def __repr__(self):
        return str(f'Type: type(self)')


    @staticmethod
    def convert_date(time):
        unix_time_datetime = datetime.fromtimestamp(time)
        date = unix_time_datetime.strftime('%a %b %d, %Y')
        time = unix_time_datetime.strftime('%I:%M%p')
        return date, time

