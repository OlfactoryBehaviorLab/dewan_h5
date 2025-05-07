"""
Dewan Lab H5 Parsing Library
Author: Austin Pauley (pauley@psy.fsu.edu)
Date: 01-04-2025
"""

import warnings

import h5py
import numpy as np
import pandas as pd

from datetime import datetime
from pathlib import Path
from typing import Union

FIRST_GOOD_TRIAL = 10  # We typically ignore the first ten trials
PRE_FV_TIME_MS = 2000
MS_PER_PACKET = 1 # (ms) 100 Samples / 1000ms

TRIAL_PARAMETER_COLUMNS = {
        'Odor': 'odor',
        'fvdur' : 'fv_duration_ms',
        'grace_period': 'grace_period_ms',
        'iti': 'iti_ms',
        'Odorconc': 'concentration',
        'paramsgottime': 'params_got_time_ms',
        'starttrial': 'trial_start_ms',
        'endtrial': 'trial_end_ms',
        'trialNumber': 'trial_number',
        'trialdur': 'trial_duration_ms',
        'waterdur': 'water_duration_ms',
        'waterdur2': 'water_duration_ms_2',
        'Odorvial': 'vial_number',
        'Trialtype': 'trial_type',
        '_result': 'result',
        '_threemissed': 'three_missed',
        'fvOnTime': 'fv_on_time_ms'
}

class DewanH5:

    def __init__(self, file_path: Union[None, Path, str], trim_trials: Union[None, bool]=True, suppress_errors: bool=False):

        if isinstance(file_path, str):
            file_path = Path(file_path)

        if not file_path:
            # Open a file selector
            pass

        self.file_path: Path = file_path
        self.file_name: str = file_path.name
        self.suppress_errors: bool = suppress_errors
        self.trim_trials: bool = trim_trials

        self._file: Union[h5py.File, None] = None

        # General parameters from H5 File
        self.date: str = 'None Specified'
        self.time: str = 'None Specified'
        self.mouse: int = 0
        self.rig: str = 'None Specified'

        # Odor information
        self.odors: list[str] = []
        self.concentrations: list[float] = []

        # Performance Values
        self.total_trials: int = 0
        self.go_performance: float = 0
        self.nogo_performance: float = 0
        self.total_performance: float = 0
        self.three_missed: bool = False
        self.last_good_trial: int = 0
        self.did_cheat: bool = False
        self.cheat_check_trials: list[int] = []

        # Data Containers
        self.trial_parameters: pd.DataFrame = None
        self.sniff: dict[int, pd.Series] = {}
        self.lick1: dict[int, list] = {}
        self.lick2: dict[int, list] = {}

        # Raw Data
        self._raw_trial_parameters: pd.DataFrame = None
        self._raw_sniff: dict[int, pd.Series] = {}
        self._raw_lick1: dict[int, list] = {}
        self._raw_lick2: dict[int, list] = {}


    def _parse_packets(self):
        try:
            trial_names = list(self._file.keys())[:-1] # Not zero indexed
            prev_trial_name = trial_names[FIRST_GOOD_TRIAL-1]
            current_trial_names = self.trial_parameters.index.values
            prev_trial_names = np.hstack((prev_trial_name, current_trial_names[:-1]))

            trial_pairs = zip(current_trial_names, prev_trial_names)
            shortest_ITI = self.trial_parameters['iti_ms'].min()

            if shortest_ITI > PRE_FV_TIME_MS:
                shortest_ITI = PRE_FV_TIME_MS

            # Relevant Trial Parameters: These are already trimmed from FIRST_GOOD_TRIAL -> last good trial
            fv_times = self.trial_parameters['fv_on_time_ms'].astype(int)
            start_times = self.trial_parameters['trial_start_ms'].astype(int)
            all_end_times = self.trial_parameters['trial_end_ms'].astype(int)
            trial_durations = all_end_times - start_times

            # Loop through the pairs of trials; trial_pairs will be from FIRST_GOOD_TRIAL -> last good trial
            for index, (trial_name, prev_trial_name) in enumerate(trial_pairs):
                timestamps = []
                #trial_number = int(trial_name[5:])
                fv_on_time = fv_times[trial_name]

                trial_packet = self._file[trial_name]
                sniff_events = trial_packet['Events']
                raw_sniff_samples = trial_packet['sniff']
                raw_lick_1_timestamps = trial_packet['lick1']
                raw_lick_2_timestamps = trial_packet['lick2']

                prev_trial_packet = self._file[prev_trial_name]
                raw_prev_sniff_samples = prev_trial_packet['sniff']

                # Get Timestamps
                events = sniff_events[:]
                end_times = events['packet_sent_time']
                steps = events['sniff_samples']

                for end_time, num_samples in zip(end_times, steps):
                    elapsed_time = num_samples * MS_PER_PACKET
                    start_time = end_time - elapsed_time
                    ts = np.linspace(start_time, end_time, num_samples, endpoint=False)
                    timestamps.extend(ts)
                timestamps = np.array(timestamps)

                # Stack all samples together
                sniff_samples = self.hstack_or_none(raw_sniff_samples[:])
                prev_sniff_samples = self.hstack_or_none(raw_prev_sniff_samples[:])
                lick_1_timestamps = self.hstack_or_none(raw_lick_1_timestamps[:])
                lick_2_timestamps = self.hstack_or_none(raw_lick_2_timestamps[:])

                # Offset times by final valve on time
                lick_1_timestamps = self.sub_or_none(lick_1_timestamps, fv_on_time)
                lick_2_timestamps = self.sub_or_none(lick_2_timestamps, fv_on_time)
                fv_offset_timestamps = self.sub_or_none(timestamps, fv_on_time)
                earliest_timestamp = int(fv_offset_timestamps[0])
                earliest_timestamp_magnitude = abs(earliest_timestamp)

                # If there is not enough pre-FV time, we need to fill in some data from the previous trial
                if earliest_timestamp_magnitude < shortest_ITI:
                    # The amount of time we need to fill from the previous trial
                    time_to_fill = shortest_ITI - earliest_timestamp_magnitude
                    # The number of frames that hypothetically fill that time
                    num_pretrial_frames = np.floor(time_to_fill / MS_PER_PACKET).astype(int)
                    start_timestamp = int(earliest_timestamp - time_to_fill)

                    fill_ts = np.linspace(start_timestamp, earliest_timestamp, num_pretrial_frames, endpoint=False)
                    pretrial_frames = prev_sniff_samples[-num_pretrial_frames:]

                    # Add frames from previous ITI to the beginning to get our full preFV time
                    filled_sniff_samples = np.hstack([pretrial_frames, sniff_samples])
                    filled_timestamps = np.hstack([fill_ts, fv_offset_timestamps])

                    sniff_data = pd.Series(filled_sniff_samples, index=filled_timestamps, name='sniff')
                else:
                    sniff_data = pd.Series(sniff_samples, index=fv_offset_timestamps, name='sniff')

                # If trimming the trials, we only want PRE_FV_TIME_MS -> trial_duration (end - start)
                if self.trim_trials:
                    trim_timestamp = trial_durations[trial_name]
                    sniff_data = sniff_data.loc[-PRE_FV_TIME_MS:trim_timestamp]

                self.sniff[trial_name] = sniff_data
                self.lick1[trial_name] = lick_1_timestamps
                self.lick2[trial_name] = lick_2_timestamps

        except Exception as e:
            print('Error parsing licking and sniffing packets!')
            raise e


    def _parse_trial_matrix(self):
        try:
            trial_matrix = self._file['Trials']
            _trial_names = list(self._file.keys())[:-1] # Not zero indexed
            #trial_names = np.arange(1, len(_trial_names) + 2) # Reindex attributes to not be zero indexed

            trial_matrix_attrs = trial_matrix.attrs
            table_col = [trial_matrix_attrs[key].astype(str) for key in trial_matrix_attrs.keys() if 'NAME' in key]
            data_dict = {}

            for col in table_col:
                data_dict[col] = trial_matrix[col]

            trial_parameters = pd.DataFrame(data_dict)
            trial_parameters.index = _trial_names
            trial_parameters = trial_parameters.rename(columns=TRIAL_PARAMETER_COLUMNS)
            self.trial_parameters = trial_parameters.map(lambda x: x.decode() if isinstance(x, bytes) else x)
            # Convert all the bytes to strings

            # See if three-missed was triggered
            three_missed_mask = self.trial_parameters['three_missed'] == 1

            if three_missed_mask.sum() > 0:
                self.three_missed = True

            first_good_trial = self.trial_parameters.index[FIRST_GOOD_TRIAL]
            last_good_trial = self.trial_parameters.index[-1]  # By default, we won't trim anything

            if self.three_missed: # We need to trim everything after three-missed
                three_missed_index = self.trial_parameters.loc[three_missed_mask].index
                last_good_trial = three_missed_index[-2]
                # The first 1 is the first trial after the third missed "Go" trial
                # We also do not want the third missed "Go" trial, so we subtract two to get to the final trial

            self.first_good_trial = first_good_trial
            self.last_good_trial = last_good_trial
            self._raw_trial_parameters = self.trial_parameters.copy()
            self.trial_parameters = self.trial_parameters.loc[first_good_trial:last_good_trial]
        except TypeError as te:
            print('Error reading or parsing the trial parameters matrix!')
            raise te


    def _parse_general_params(self):
        try:
            _rig = str(self.trial_parameters['rig'].values[0])
            _rig = _rig.split(" ")
            if len(_rig) > 1:
                self.rig = "-".join(_rig)
            else:
                self.rig = _rig[0]
            # Remove spaces if they exist from the rig name

            self.odors = self.trial_parameters['odor'].unique()
            self.concentrations = self.trial_parameters['concentration'].unique()
            self.mouse = self.trial_parameters['mouse'].values[0]
            self.total_trials = self.trial_parameters.shape[0]
        except Exception as e:
            print('Error when parsing general experiment parameters!')
            raise e


    def _set_time(self):
        try:
            file_time = self._file.attrs['start_date']
            self.date, self.time = DewanH5.convert_date(file_time)
        except Exception as e:
            print('Error converting and setting time!')
            raise e


    def _calculate_performance(self):
        # TODO: Do cheating checks need to be removed?

        results = self.trial_parameters['result']

        correct_go_trials = sum(results == 1) # Response 1
        incorrect_go_trials = sum(results == 5) # Response 5

        total_gos = correct_go_trials + incorrect_go_trials

        correct_nogo_trials = sum(results == 2) # Response 2
        incorrect_nogo_trials = sum(results == 3) # Response 3

        total_nogos = correct_nogo_trials + incorrect_nogo_trials

        total_trials = total_gos + total_nogos
        correct_trials = correct_go_trials + correct_nogo_trials

        self.nogo_performance = round((correct_nogo_trials / total_nogos) * 100, 2)
        self.go_performance = round((correct_go_trials / total_gos) * 100, 2)
        self.total_performance = round((correct_trials / total_trials) * 100, 2)


    def _get_cheating_trials(self):
        cheat_trial_mask = (self.trial_parameters['odor'] == 'blank') & (self.trial_parameters['trial_type'] == 2)
        cheat_check_trials = self.trial_parameters.loc[cheat_trial_mask]
        cheat_check_results = cheat_check_trials['result']
        num_cheating_trials = sum(cheat_check_results == 2)

        if num_cheating_trials > 0:
            self.did_cheat = True

        self.cheat_check_trials = cheat_check_trials


    def _open(self):
        try:
            self._file = h5py.File(self.file_path, 'r')
        except FileNotFoundError as e:
            print(f'Error! {self.file_path} not found!')
            raise e


    def export(self, path: Union[None, Path, str] = None, file_name: Union[None, str] = None) -> None:

        export_dir = self.file_path.parent
        export_name = self.file_path.with_suffix('.xlsx').with_stem(f'{self.file_path.stem}-TrialParams').name

        if path:
            if isinstance(path, str): # If the user passes a string, convert it to a path first
                path = Path(path)
            path.mkdir(parents=True, exist_ok=True)
            export_dir = path

        if file_name:
            export_name = f'{file_name}.xlsx'

        export_file_path = export_dir.joinpath(export_name)

        self.trial_parameters.to_excel(export_file_path)


    def debug_enter(self):
        warnings.warn("Using DewanH5 outside of a context manager is NOT recommended! "
                      "You must manually close the file reference using the close() method before deleting this instance!")

        return self.__enter__()


    def close(self):
        self.__exit__(None, None, None)


    def __enter__(self):
        if not self.file_path:
            print('No file path passed, opening file browser!')
            # open file browser

        self._open()
        self._parse_trial_matrix()
        self._parse_packets()
        self._parse_general_params()
        self._set_time()

        self._calculate_performance()
        self._get_cheating_trials()

        return self


    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._file:
            self._file.close()

        if exc_type is not None:
            if self.suppress_errors:
                print('Error opening H5 File!')
                return True
            else:
                return False
        else:
            return True


    def __str__(self):
        return (f'Dewan Lab H5 file: {self.file_path.name}\n'
                f'Mouse: {self.mouse}\n'
                f'Experiment Date: {self.date}\n'
                f'Experiment Time: {self.time}\n'
                f'Rig: {self.rig}\n'
                f'Total Trials: {self.total_trials}\n')


    def __repr__(self):
        return str(f'Type: {type(self)}')


    @staticmethod
    def convert_date(time):
        unix_time_datetime = datetime.fromtimestamp(time)
        date = unix_time_datetime.strftime('%a %b %d, %Y')
        time = unix_time_datetime.strftime('%I:%M%p')
        return date, time


    @staticmethod
    def hstack_or_none(data):
        if len(data) > 0:
            return np.hstack(data)

        return None


    @staticmethod
    def sub_or_none(data, val):
        if data is not None:
            return data - val
        else:
            return []

