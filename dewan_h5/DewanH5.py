# noqa: N999
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
MS_PER_PACKET = 1  # (ms) 100 Samples / 1000ms
EARLY_LICK_BUFFER_MS = 0  # (ms) amount of time before the grace period ends that we will allow early licking
MISSING_DATA_THRESHOLD = 50  # (ms) number of ms allowed between two contiguous packets
TRIAL_PARAMETER_COLUMNS = {
    "Odor": "odor",
    "fvdur": "fv_duration_ms",
    "grace_period": "grace_period_ms",
    "iti": "iti_ms",
    "Odorconc": "concentration",
    "paramsgottime": "params_got_time_ms",
    "starttrial": "trial_start_ms",
    "endtrial": "trial_end_ms",
    "trialNumber": "trial_number",
    "trialdur": "trial_duration_ms",
    "waterdur": "water_duration_ms",
    "waterdur2": "water_duration_ms_2",
    "Odorvial": "vial_number",
    "Trialtype": "trial_type",
    "_result": "result",
    "_threemissed": "three_missed",
    "fvOnTime": "fv_on_time_ms",
}


class DewanH5:
    def __init__(
        self,
        file_path: Union[None, Path, str],
        trim_trials: Union[None, bool] = True,
        drop_early_lick_trials: Union[None, bool] = True,
        drop_cheating_trials: Union[None, bool] = True,
        parse_only: bool = False,
        check_missing_packets: bool = True,
        suppress_errors: bool = False,
    ):
        if isinstance(file_path, str):
            file_path = Path(file_path)

        if not file_path:
            # Open a file selector
            pass

        self.file_path: Path = file_path
        self.file_name: str = file_path.name
        self.suppress_errors: bool = suppress_errors
        self.trim_trials: bool = trim_trials
        self.drop_early_lick_trials: bool = drop_early_lick_trials
        self.parse_only: bool = parse_only
        self.check_missing_packets: bool = check_missing_packets
        self.drop_cheating_trials: bool = drop_cheating_trials

        self._file: Union[h5py.File, None] = None

        # General parameters from H5 File
        self.date: str = "None Specified"
        self.time: str = "None Specified"
        self.mouse: int = 0
        self.rig: str = "None Specified"

        # Odor information
        self.odors: list[str] = []
        self.concentration: float = 0.0

        # Performance Values
        self.total_trials: int = 0
        self.go_performance: float = 0
        self.nogo_performance: float = 0
        self.total_performance: float = 0
        self.three_missed: bool = False
        self.last_good_trial: int = 0
        self.did_cheat: bool = False
        self.cheat_check_trials: list[str] = []

        # Excluded Trials
        self.early_lick_trials: list[str] = []
        self.missing_packet_trials: list[str] = []
        self.short_trials: list[str] = []
        self.zero_trials: list[str] = []
        self.num_initial_trials: int = 0

        self.good_trials: list[str] = []

        self.response_latencies: dict[str, np.ndarray] = {}

        # Data Containers
        self.trial_parameters: pd.DataFrame = None
        self.sniff: dict[str, pd.Series] = {}
        self.lick1: dict[str, list] = {}
        self.lick2: dict[str, list] = {}

        # Raw Data
        self._raw_trial_parameters: pd.DataFrame = None
        self._raw_sniff: dict[int, pd.Series] = {}
        self._raw_lick1: dict[int, list] = {}
        self._raw_lick2: dict[int, list] = {}

    def _parse_packets(self):
        try:
            trial_names = list(self._file.keys())[:-1]  # Not zero indexed
            prev_trial_name = trial_names[FIRST_GOOD_TRIAL - 1]
            current_trial_names = self.trial_parameters.index.to_numpy()
            prev_trial_names = np.hstack((prev_trial_name, current_trial_names[:-1]))
            self.num_initial_trials = len(current_trial_names)
            trial_pairs = zip(current_trial_names, prev_trial_names, strict=True)

            shortest_ITI = self.trial_parameters["iti_ms"].min()

            if shortest_ITI > PRE_FV_TIME_MS:
                shortest_ITI = PRE_FV_TIME_MS

            # Relevant Trial Parameters: These are already trimmed from FIRST_GOOD_TRIAL -> last good trial
            fv_times = self.trial_parameters["fv_on_time_ms"].astype(int)
            start_times = self.trial_parameters["trial_start_ms"].astype(int)
            all_end_times = self.trial_parameters["trial_end_ms"].astype(int)
            grace_period = self.trial_parameters["grace_period_ms"].astype(int)
            self.trial_durations = all_end_times - start_times

            # Loop through the pairs of trials; trial_pairs will be from FIRST_GOOD_TRIAL -> last good trial
            for _, (trial_name, prev_trial_name) in enumerate(trial_pairs):
                timestamps = []
                fv_on_time = fv_times[trial_name]
                grace_period_ms = grace_period[trial_name]

                trial_packet = self._file[trial_name]
                sniff_events = trial_packet["Events"]
                raw_sniff_samples = trial_packet["sniff"]
                raw_lick_1_timestamps = trial_packet["lick1"]
                raw_lick_2_timestamps = trial_packet["lick2"]

                prev_trial_packet = self._file[prev_trial_name]
                raw_prev_sniff_samples = prev_trial_packet["sniff"]

                # Get Timestamps
                events = sniff_events[:]
                end_times = events["packet_sent_time"]
                steps = events["sniff_samples"]

                for end_time, num_samples in zip(end_times, steps, strict=True):
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

                if fv_offset_timestamps[-1] < grace_period_ms:
                    self.short_trials.append(trial_name)
                    print(f"{trial_name} ends before the grace period!")
                    continue

                if (  # noqa: SIM102
                    self.drop_early_lick_trials
                    and lick_1_timestamps is not None
                    and len(lick_1_timestamps) > 0
                ):  # noqa: SIM102
                    if (
                        (grace_period_ms - EARLY_LICK_BUFFER_MS)
                        > lick_1_timestamps[0]
                        >= 0
                    ):
                        self.early_lick_trials.append(trial_name)
                        continue

                # If there is not enough pre-FV time, we need to fill in some data from the previous trial
                if earliest_timestamp_magnitude < shortest_ITI:
                    # The amount of time we need to fill from the previous trial
                    time_to_fill = shortest_ITI - earliest_timestamp_magnitude
                    # The number of frames that hypothetically fill that time
                    num_pretrial_frames = np.floor(time_to_fill / MS_PER_PACKET).astype(
                        int
                    )
                    start_timestamp = int(earliest_timestamp - time_to_fill)

                    fill_ts = np.linspace(
                        start_timestamp,
                        earliest_timestamp,
                        num_pretrial_frames,
                        endpoint=False,
                    )
                    pretrial_frames = prev_sniff_samples[-num_pretrial_frames:]

                    # Add frames from previous ITI to the beginning to get our full preFV time
                    filled_sniff_samples = np.hstack([pretrial_frames, sniff_samples])
                    filled_timestamps = np.hstack([fill_ts, fv_offset_timestamps])

                    sniff_data = pd.Series(
                        filled_sniff_samples, index=filled_timestamps, name="sniff"
                    )
                else:
                    sniff_data = pd.Series(
                        sniff_samples, index=fv_offset_timestamps, name="sniff"
                    )

                # If trimming the trials, we only want PRE_FV_TIME_MS -> trial_duration (end - start)
                if self.trim_trials:
                    trim_timestamp = self.trial_durations[trial_name]
                    sniff_data = sniff_data.loc[-PRE_FV_TIME_MS:trim_timestamp]

                if self.check_missing_packets:
                    timestamp_diffs = np.diff(sniff_data.index)
                    if np.any(timestamp_diffs >= MISSING_DATA_THRESHOLD):
                        print(f"{trial_name} appears to be missing packets!")
                        self.missing_packet_trials.append(trial_name)
                        continue

                self.sniff[trial_name] = sniff_data
                self.lick1[trial_name] = lick_1_timestamps
                self.lick2[trial_name] = lick_2_timestamps

        except Exception as e:
            print("Error parsing licking and sniffing packets!")
            raise e

    def _parse_trial_matrix(self):
        try:
            trial_matrix = self._file["Trials"]
            _trial_names = list(self._file.keys())[:-1]  # Not zero indexed

            trial_matrix_attrs = trial_matrix.attrs
            table_col = [
                trial_matrix_attrs[key].astype(str)
                for key in trial_matrix_attrs
                if "NAME" in key
            ]
            data_dict = {}

            for col in table_col:
                data_dict[col] = trial_matrix[col]

            trial_parameters = pd.DataFrame(data_dict)
            trial_parameters.index = _trial_names
            trial_parameters = trial_parameters.rename(columns=TRIAL_PARAMETER_COLUMNS)
            self.trial_parameters = trial_parameters.map(
                lambda x: x.decode() if isinstance(x, bytes) else x
            )
            # Convert all the bytes to strings
            # See if three-missed was triggered
            three_missed_mask = self.trial_parameters["three_missed"] == 1

            if three_missed_mask.sum() > 0:
                self.three_missed = True

            first_good_trial = self.trial_parameters.index[FIRST_GOOD_TRIAL]
            last_good_trial = self.trial_parameters.index[
                -1
            ]  # By default, we won't trim anything

            if self.three_missed:  # We need to trim everything after three-missed
                three_missed_index = self.trial_parameters.loc[three_missed_mask].index
                last_good_trial = three_missed_index[-2]
                # The first 1 is the first trial after the third missed "Go" trial
                # We also do not want the third missed "Go" trial, so we subtract two to get to the final trial

            zero_trials_mask = self.trial_parameters['trial_type'] == 0
            self.zero_trials = self.trial_parameters.index[zero_trials_mask]
            self._raw_trial_parameters = self.trial_parameters.copy()
            self.trial_parameters = self.trial_parameters.loc[
                first_good_trial:last_good_trial
            ]
        except TypeError as te:
            print("Error reading or parsing the trial parameters matrix!")
            raise te

    def _parse_general_params(self):
        try:
            _rig = str(self.trial_parameters["rig"].to_numpy()[0])
            _rig = _rig.split(" ")
            if len(_rig) > 1:
                self.rig = "-".join(_rig)
            else:
                self.rig = _rig[0]
            # Remove spaces if they exist from the rig name

            self.odors = self.trial_parameters["odor"].unique()
            self.mouse = self.trial_parameters["mouse"].to_numpy()[0]

            # For the blank experiments, the only concentration is zero
            _concentrations = self.trial_parameters["concentration"].unique()
            if len(_concentrations) == 1:
                self.concentration = _concentrations[0]
            else:
                self.concentration = _concentrations[_concentrations > 0][0]
            self.concentration = np.format_float_scientific(self.concentration, 1)

        except Exception as e:
            print("Error when parsing general experiment parameters!")
            raise e

    def _update_trial_numbers(self):
        good_sniff_trials = list(self.sniff.keys())
        # This list already excludes early_sniff, missing_packet, and short_trials
        good_trials = np.setdiff1d(
            good_sniff_trials, self.cheat_check_trials, assume_unique=True
        )  # Remove cheat check trials
        good_trials = np.setdiff1d(
            good_trials, self.zero_trials, assume_unique=True
        ) # Remove type 0 trials

        self.trial_parameters = self.trial_parameters.loc[good_trials]
        self.sniff = {trial: self.sniff[trial] for trial in good_trials}
        self.total_trials = self.trial_parameters.shape[0]
        self.trial_durations = self.trial_durations[good_trials]
        self.good_trials = good_trials
        if self.total_trials == 0:
            warnings.warn(f"No good trials found for {self.file_path}!", stacklevel=2)

    def _get_response_delays(self):
        for trial in self.trial_parameters.index:
            trial_licks = np.array(self.lick1[trial])
            delay = trial_licks[trial_licks > 0]
            if len(delay) > 0:
                self.response_latencies[trial] = delay
            else:
                self.response_latencies[trial] = -1

    def _set_time(self):
        try:
            file_time = self._file.attrs["start_date"]
            self.date, self.time = DewanH5.convert_date(file_time)
        except Exception as e:
            print("Error converting and setting time!")
            raise e

    def _calculate_performance(self):
        # TODO: Do cheating checks need to be removed?

        results = self.trial_parameters["result"]

        correct_go_trials = sum(results == 1)  # Response 1
        incorrect_go_trials = sum(results == 5)  # Response 5

        total_gos = correct_go_trials + incorrect_go_trials

        correct_nogo_trials = sum(results == 2)  # Response 2
        incorrect_nogo_trials = sum(results == 3)  # Response 3

        total_nogos = correct_nogo_trials + incorrect_nogo_trials

        total_trials = total_gos + total_nogos
        correct_trials = correct_go_trials + correct_nogo_trials

        self.nogo_performance = round((correct_nogo_trials / total_nogos) * 100, 2)
        self.go_performance = round((correct_go_trials / total_gos) * 100, 2)
        self.total_performance = round((correct_trials / total_trials) * 100, 2)

    def _get_cheating_trials(self):
        cheat_trial_mask = (self.trial_parameters["odor"] == "blank") & (
            self.trial_parameters["trial_type"] == 2
        )
        cheat_check_trials = self.trial_parameters.loc[cheat_trial_mask]
        cheat_check_results = cheat_check_trials["result"]
        num_cheating_trials = sum(cheat_check_results == 2)

        if num_cheating_trials > 0:
            self.did_cheat = True

        self.cheat_check_trials = cheat_check_trials.index

    def _open(self):
        try:
            self._file = h5py.File(self.file_path, "r")
        except FileNotFoundError as e:
            print(f"Error! {self.file_path} not found!")
            raise e

    def export(
        self, path: Union[None, Path, str] = None, file_name: Union[None, str] = None
    ) -> None:
        export_dir = self.file_path.parent
        export_name = (
            self.file_path.with_suffix(".xlsx")
            .with_stem(f"{self.file_path.stem}-TrialParams")
            .name
        )

        if path:
            if isinstance(
                path, str
            ):  # If the user passes a string, convert it to a path first
                path = Path(path)
            path.mkdir(parents=True, exist_ok=True)
            export_dir = path

        if file_name:
            export_name = f"{file_name}.xlsx"

        export_file_path = export_dir.joinpath(export_name)

        self.trial_parameters.to_excel(export_file_path)

    def debug_enter(self):
        warnings.warn(
            "Using DewanH5 outside of a context manager is NOT recommended! "
            "You must manually close the file reference using the close() method before deleting this instance!",
            stacklevel=2,
        )

        return self.__enter__()

    def close(self):
        self.__exit__(None, None, None)

    def __enter__(self):
        if not self.file_path:
            print("No file path passed, opening file browser!")
            # open file browser

        self._open()
        self._parse_trial_matrix()
        self._parse_packets()
        self._parse_general_params()

        if self.drop_cheating_trials:
            self._get_cheating_trials()

        self._update_trial_numbers()
        self._get_response_delays()
        self._set_time()

        if not self.parse_only:
            self._calculate_performance()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._file:
            self._file.close()

        if exc_type is not None:
            if self.suppress_errors:
                print("Error opening H5 File!")
                return True
            return False
        return True

    def __str__(self):
        return (
            f"Dewan Lab H5 file: {self.file_path.name}\n"
            f"Mouse: {self.mouse}\n"
            f"Experiment Date: {self.date}\n"
            f"Experiment Time: {self.time}\n"
            f"Rig: {self.rig}\n"
            f"Concentration(s): {self.concentration}\n"
            f"Total Trials: {self.total_trials}\n"
        )

    def __repr__(self):
        return str(f"Type: {type(self)}")

    @staticmethod
    def convert_date(time):
        unix_time_datetime = datetime.fromtimestamp(time)
        date = unix_time_datetime.strftime("%a %b %d, %Y")
        time = unix_time_datetime.strftime("%I:%M%p")
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

        return []
