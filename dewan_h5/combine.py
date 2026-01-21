import argparse
import h5py
import numpy as np
from pathlib import Path

# file1 = Path(r'R:\5_Projects\1_Sniffing\3_benzaldehyde\Raw_Data\212\mouse212_sess1_D2025_9_21T15_10_39.h5')
# file2 = Path(r'R:\5_Projects\1_Sniffing\3_benzaldehyde\Raw_Data\212\mouse212_sess1_D2025_9_21T15_36_54.h5')
# new_file = file2.with_name(f"{file2.stem}-combined.h5")

def combine(file1: Path, file2: Path, new_file: Path|None =None):

    if new_file is None:
        new_file = file1.with_stem(f'{file1.stem}-combined')

    with h5py.File(file1, 'r') as f1, h5py.File(file2, 'r')  as f2, h5py.File(new_file, 'w') as nf:
            for attr in f1.attrs:
                nf.attrs[attr] = f1.attrs[attr]

            f1_keys = list(f1.keys())[:-1] # Ignore the 'Trials' key
            f2_keys = list(f2.keys())[10:-1] # Ignore the first ten and the 'Trials' key
            next_trial_num = len(f1_keys) + 1 # Trials are 1-indexed, and there is one extra key, so it works out
            num_f2_trials = len(f2_keys)
            new_trial_num = np.arange(next_trial_num, next_trial_num + num_f2_trials)
            new_trial_names = ['Trial' + str(num).zfill(4) for num in new_trial_num]
            for f1_key in f1_keys:
                f1.copy(f1_key, nf, f1_key)

            for f2_original, f2_new in zip(f2_keys, new_trial_names):
                f2.copy(f2_original, nf, f2_new)

            f1_trial_matrix = f1['Trials']
            f2_trial_matrix = f2['Trials']

            f1_trial_matrix_data = f1_trial_matrix[:]
            f2_trial_matrix_data = f2_trial_matrix[10:]
            nf_trial_matrix = np.concat((f1_trial_matrix_data, f2_trial_matrix_data), axis=0)
            num_rows = len(nf_trial_matrix)
            nf_trial_matrix_dataset = nf.create_dataset('Trials', data=nf_trial_matrix)
            for attr in f1_trial_matrix.attrs:
                nf_trial_matrix_dataset.attrs[attr] = f1_trial_matrix.attrs[attr]
            nf_trial_matrix_dataset.attrs['NROWS'] = num_rows

def main():
    parser = argparse.ArgumentParser(description='Combine two HDF5 files')
    parser.add_argument('file1', help='First HDF5 file')
    parser.add_argument('file2', help='Second HDF5 file')
    parser.add_argument('-o', '--output', help='New HDF5 file')

    args = parser.parse_args()

    file1_path = Path(args.file1)
    file2_path = Path(args.file2)

    if not file1_path.exists():
        raise FileNotFoundError(f'File 1 [{args.file1}] does not exist')
    if not file2_path.exists():
        raise FileNotFoundError(f'File 2 [{args.file2}] does not exist')

    kwargs = {
        'file1': args.file1,
        'file2': args.file2,
    }

    if args.output:
        output_path = Path(args.output)
        if not output_path.parent.exists():
            raise FileNotFoundError(f'Output directory {args.output} does not exist')

        kwargs['new_file'] = args.output

    combine(**kwargs)
