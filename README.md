# Dewan Lab H5 Library

This library serves to load, parse, and serve the contents of H5 files from the lab's Arduino- and Voyeur-based behavior setups.

### H5 File Structure
___
- **Values**:
  - N -> number of trials 
  - n -> references any arbitrary trial
  - x -> arbitrary number
- **File Structure**
  - '/': Contains N number of Groups for each trial with an additional group containing the trial data matrix
  - 'Trials': Matrix containing n rows with columns for multiple parameters captured for each trial
  - 'Trial000n' [type: group] (one group per trial): Holds samples for each trial
    - 'Events' [type: dataset] (x number of tuples): (timestamp, number of sniff samples)
    - 'lick1' [type: dataset] (x number of arrays): each array contains a variable number of lick timestamps for the 'left' lick tube
    - 'lick2' [type: dataset] (x number of arrays): each array contains a variable number of lick timestamps for the 'right' lick tube
    - 'sniff' [type: dataset]  (len(Events) number of arrays): each array contains samples recorded from the sniff sensor
___