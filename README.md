# Dewan Lab H5 Library

---

This library serves to load, parse, and serve the contents of H5 files from the lab's Arduino- and Voyeur-based behavior setups.

## Installation
1) Using PyPi: Simply run `pip install dewan_h5` and the latest version will be pulled from PyPi
2) Local Installation
   1) Clone the repository using `git clone https://github.com/OlfactoryBehaviorLab/dewan_h5`
   2) Navigate into the `dewan_h5` directory
   3) Execute `pip install .` or `pip install -e .` if you want the repository to be editable

## Usage
> Info: The DewanH5 class is intended to be used within a Python [context manager](https://docs.python.org/3/reference/datamodel.html#context-managers).  
> Usage outside a context manager is not supported

### Example:
```python
from dewan_h5 import DewanH5

file_path = 'path/to/h5/file/file.h5'

with DewanH5(file_path) as dh5:
    # Do things here
    # When done, the file is automatically closed when the context is exited
    print(dh5)  # Print summary of contents of file

# Context is now exited
```

## Class Constructor

---

### `DewanH5(file_path, trim_trials=True, suppress_errors=False)`

- `file_path : None, Path, or str` Path to the H5 file
  - None: If None is explicitly supplied, a file selector will open
  - Path: pathlib.Path representing the location of the H5 file
  - str: string containing raw path to H5 file; internally converted to a pathlib.Path
- `trim_trials : bool` Indicates whether below trials are trimmed from the raw dataset
  - When set to `true` the following are trimmed:
      - The first 10 Go Trials
      - If three Go trials are missed in a row, everything after (and including) the third missed trial are dropped
- `suppress_errors : bool` Determines whether certain errors are suppressed and handled silently or allowed to propagate to the context manager

## Public Parameters

---

### Constructor Parameters
- `file_path : pathlib.Path` System-agnostic path to the H5 file
- `file_name : str` Filename with suffix
- `suppress_errors : bool` Determines whether errors are suppressed and handled silently or allowed to propagate to the context manager
- `trim_trial : bool` Normally, certain trials are trimmed from the raw dataset. This indicates whether those trials were trimmed or left in the dataset

### General Parameters
- `date : str` Date the H5 file was created
- `time : str` Time the H5 file was created
- `mouse : int` ID number of animal ran in experiment
- `rig : str` Rig name experiment was ran in
### Odor Information
- `odors : list[str]` List of all odors present in H5 File
  - This includes blank
- `concentrations : list[str]` List of all concentrations present in H5 file
### Performance Values
> All performance values are calculated **after** trimming (if applicable)
- `total_trials : int` Total number of trials in experiment
- `go_performance : float` Percentage of correct go trials vs total number of go trials
- `nogo_performance : float` Percentage of correct nogo trials vs total number of nogo trials
- `total_performance : float` Percentage of correct go and nogo trials vs total number of trials
  - (correct go trials + correct nogo trials) / total number of trials
- `three_missed : bool` Indicates whether the animal missed three go trials in a row
- `last_good_trial : int` If three_missed is _true_, this is the last trial included in the data
- `did_cheat : bool` Indicates whether cheating was detected
  - See description of cheating check below
- `cheat_check_tirals : list[int]` List of cheating check trial indices
### Data Containers
> Note 1: If trimming the dataset, the below containers are also trimmed  
> Note 2: All the timestamps are offset by the FV on time. Negative values represent events before the FV turned on

- `trial_parameters : pd.DataFrame` Pandas DataFrame containing the parameters recorded for each trial
  - See list of important parameters below
- `sniff : dict[int, pd.Series]` Dictionary where each key is an int representing a trial number; each Pandas Series contains timestamped samples representing data recorded from the sniff sensor
- `lick1 : dict[int, list]` Dictionary where each key is an int representing a trial number; each list contains timestamps for licks of lick sensor 1
- `lick2: dict[int, list]` Dictionary where each key is an int representing a trial number; each list contains timestamps for licks of lick sensor 2

## H5 File Structure
___
- **Values**:
  - `N` -> number of trials 
  - `n` -> references any arbitrary trial
  - `x` -> arbitrary number
- **File Structure**
  - `/`: Contains N number of Groups for each trial with an additional group containing the trial data matrix
  - `Trials`: Matrix containing n rows with columns for multiple parameters captured for each trial
  - `Trial000n` [type: group] (one group per trial): Holds samples for each trial
    - `Events` [type: dataset] (x number of tuples): (timestamp, number of sniff samples)
    - `lick1` [type: dataset] (x number of arrays): each array contains a variable number of lick timestamps for the 'left' lick tube
    - `lick2` [type: dataset] (x number of arrays): each array contains a variable number of lick timestamps for the 'right' lick tube
    - `sniff` [type: dataset]  (len(Events) number of arrays): each array contains samples recorded from the sniff sensor

### Pertinent Trial Parameters:
#### Matrix located at `/Trials` that contains parameters for each trial
##### Each entry in the following format `Common Name [column_name, data type]`
> Note: the column names are strings, but I have left the quotations off for clarity
- `Trial Type [Trialtype, int]`: Value which encodes the trial type
  - **1**: Go (no licking)
  - **2**: NoGo (licking)
- `Response [_result, int]`: Value that represents the response of the animal
  - **1**: Correct "Go" Response >>> The stimulus was a 'Go' stimulus and the animal correctly withheld licking
  - **2**: Correct "NoGo" Response >>> The stimulus was a 'NoGo' stimulus and the animal correctly licked 
  - **3**: False Alarm / Incorrect "NoGo" Response >>> The stimulus was a "NoGo" stimulus and the animal incorrectly withheld licking
  - **4**: Unused
  - **5**: Missed "Go" Response >>> The stimulus was a 'Go' stimulus and the animal incorrectly licked

>Note: Some trials are designated "cheating checks" to test whether the animal is utilizing a non-odor cue to get
 extra water rewards. A cheating check is identified by a trial type of `2` with an odor of `blank`.  
> \- A response of `2` indicates **CHEATING**  
 \- A response of `3` indicates **NO CHEATING**

- `Odor Name [Odor, str]`: Name of odorant presented during the trial
- `Odor Concentration [Odorconc, str]`: Concentration of odorant presented during the trial
- `Odor Vial Number [Odorvial, int]`: Olfactometer vial used to deliver the odorant during the trial
- `Inter Trial Interval (ITI) [iti, str]`: Time in milliseconds between current trial and next trial
- `Mouse ID [mouse, int]`: ID number of animal ran in the experiment
- `Rig Name [rig, str]`: Name of behavioral chamber 

## License

This project is licensed under GNU General Public License v3.0. You can find the included copy of the license [here](LICENSE.txt). For more information about the license and its terms, please visit [SPDX](https://spdx.org/licenses/GPL-3.0-or-later.html)