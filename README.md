# Dewan Lab H5 Library

This library serves to load, parse, and serve the contents of H5 files from the lab's Arduino- and Voyeur-based behavior setups.

## Pertinent Trial Parameters:
#### Matrix located at `/Trials` that contains parameters for each trial
##### Each entry in the following format `Common Name [column_name, data type]`

- `Trial Type (int)`: Value which encodes the trial type
  - **1**: Go (no licking)
  - **2**: NoGo (licking)
- `Response (int)`: Value that represents the response of the animal
  - **1**: Correct "Go" Response >>> The stimulus was a 'Go' stimulus and the animal correctly withheld licking
  - **2**: Correct "NoGo" Response >>> The stimulus was a 'NoGo' stimulus and the animal correctly licked 
  - **3**: False Alarm / Incorrect "NoGo" Response >>> The stimulus was a "NoGo" stimulus and the animal incorrectly withheld licking
  - **4**: Unused
  - **5**: Missed "Go" Response >>> The stimulus was a 'Go' stimulus and the animal incorrectly licked

>Note: Some trials are designated "cheating checks" to test whether the animal is utilizing a non-odor cue to get
 extra water rewards. A cheating check is identified by a trial type of `2` with an odor of `blank`.  
> \- A response of `2` indicates **CHEATING**  
 \- A response of `3` indicates **NO CHEATING**

- `Odor Name ["Odor", str]`: Name of odorant presented during the trial
- `Odor Concentration ["Odorconc", str]`: Concentration of odorant presented during the trial
- `Odor Vial Number ["Odorvial", int]`: Olfactometer vial used to deliver the odorant during the trial
- 
### H5 File Structure
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
___