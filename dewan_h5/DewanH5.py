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

FIRST_GOOD_TRIAL = 10  # We typically ignore the first ten trials


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


    def _parse_packets(self):
        trial_names = list(self._file.keys())[:-1]
        if self.trim_trials:
            trial_names = trial_names[FIRST_GOOD_TRIAL:self.last_good_trial]

        for index, trial_name in enumerate(trial_names):
            timestamps = []
            sniff_samples = []
            lick_1_timestamps = []
            lick_2_timestamps = []

            trial_packet = self._file[trial_name]
            sniff_events = trial_packet['Events']
            raw_sniff_samples = trial_packet['sniff']
            raw_lick_1_timestamps = trial_packet['lick1']
            raw_lick_2_timestamps = trial_packet['lick2']

            trial_number_str = trial_name[5:]
            trial_number = int(trial_number_str)

            # We can use the index since trial_parameters was just trimmed
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

            self.sniff[trial_number] = sniff_data
            self.lick1[trial_number] = lick_1_timestamps
            self.lick2[trial_number] = lick_2_timestamps


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

        # See if three-missed was triggered
        three_missed_mask = self.trial_parameters['_threemissed'] == 1

        if three_missed_mask.sum() > 0:
            self.three_missed = True

        if self.trim_trials: # We need to trim the matrix
            last_good_trial = self.trial_parameters.shape[0]  # By default, we won't trim anything

            if self.three_missed: # We need to trim everything after three-missed
                three_missed_index = self.trial_parameters[three_missed_mask].index.tolist()
                last_good_trial = three_missed_index[0] - 2
                # The first 1 is the first trial after the third missed "Go" trial
                # We also do not want the third missed "Go" trial, so we subtract two to get to the final trial

            self.last_good_trial = last_good_trial
            self.trial_parameters = self.trial_parameters.iloc[FIRST_GOOD_TRIAL:last_good_trial]


    def _parse_general_params(self):
        _rig = str(self.trial_parameters['rig'].values[0])
        _rig = _rig.split(" ")
        if len(_rig) > 1:
            self.rig = "-".join(_rig)
        else:
            self.rig = _rig[0]
        # Remove spaces if they exist from the rig name

        self.odors = self.trial_parameters['Odor'].unique()
        self.concentrations = self.trial_parameters['Odorconc'].unique()
        self.mouse = self.trial_parameters['mouse'].values[0]
        self.total_trials = self.trial_parameters.shape[0]


    def _set_time(self):
        file_time = self._file.attrs['start_date']
        self.date, self.time = DewanH5.convert_date(file_time)


    def _calculate_performance(self):
        # TODO: Do cheating checks need to be removed?

        results = self.trial_parameters['_result']

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
        cheat_trial_mask = (self.trial_parameters['Odor'] == 'blank') & (self.trial_parameters['Trialtype'] == 2)
        cheat_check_trials = self.trial_parameters.loc[cheat_trial_mask]
        cheat_check_results = cheat_check_trials['_result']
        num_cheating_trials = sum(cheat_check_results == 2)

        if num_cheating_trials > 0:
            self.did_cheat = True

        self.cheat_check_trials = cheat_check_trials


    def _open(self):
        try:
            self._file = h5py.File(self.file_path, 'r')
        except FileNotFoundError as e:
            print(f'Error! {self.file_path} not found!')
            print(traceback.format_exc())
            self._file = None
            self.__exit__(None, None, None)


    def export(self, path: Union[None, Path, str] = None, file_name: Union[None, str] = None,
               create_output_dir: Union[None, bool] = False) -> None:

        default_path = self.file_path.with_suffix('.xlsx').with_stem(f'{self.file_path.stem}-TrialParams')

        export_dir = None

        if path:
            if isinstance(path, str): # If the user passes a string, convert it to a path first
                path = Path(path)

            if path.exists():
                export_dir = path
            elif create_output_dir:
                path.mkdir(parents=True, exist_ok=True)
                export_dir = path
            else:
                warnings.warn(f'{path} does not exist! Using the default path {default_path}')
                export_dir = default_path.parent

        if file_name:
            export_file_name = f'{file_name}.xlsx'
        else:
            export_file_name = default_path.name

        if export_dir and export_file_name:
            export_file_path = export_dir.joinpath(export_file_name)
        elif export_dir:
            export_file_path = export_dir.joinpath(default_path.name)
        elif export_file_name:
            export_file_path = default_path.parent.joinpath(export_file_name)
        else:
            export_file_path = default_path


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
                return True
            else:
                return False


    def __str__(self):
        return (f'Dewan Lab H5 file: {self.file_path.name}\n'
                f'Mouse: {self.mouse}\n'
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

