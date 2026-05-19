import argparse
from datetime import datetime
from pathlib import Path

import h5py
import numpy as np


def sort_files(*file_paths: Path) -> list[Path]:
    dates = []
    for file in file_paths:
        str_date = str(file.stem).split("D")[1]
        date = datetime.strptime(str_date, "%Y_%m_%dT%H_%M_%S")
        dates.append(date)
    sorted_order = np.argsort(dates)
    return [file_paths[i] for i in sorted_order]


def combine(*files: Path, new_file: Path | None = None):
    if new_file is None:
        new_file = files[0].with_stem(f'{files[0].stem}-combined')
    print(f"Output file: {new_file}")

    with h5py.File(files[0], 'r') as f0, h5py.File(new_file, 'w') as nf:
        f0_trial_matrix = f0['Trials']

        combined_trial_matrix = f0_trial_matrix[:]
        # Set to f0 matrix

        for attr in f0.attrs:
            nf.attrs[attr] = f0.attrs[attr]
        # Copy file attributes

        f0_keys = list(f0.keys())[:-1] # Ignore the 'Trials' key
        next_trial_num = len(f0_keys) + 1 # Trials are 1-indexed, and there is one extra key, so it works out

        for f0_key in f0_keys:
            f0.copy(f0_key, nf, f0_key)
        # Copy data


        for file in files[1:]:
            with h5py.File(file, 'r') as old_file:
                old_file_keys = list(old_file.keys())[10:-1] # Ignore the first ten and the 'Trials' key

                num_old_trials = len(old_file_keys)
                new_trial_num = np.arange(next_trial_num, next_trial_num + num_old_trials)
                next_trial_num = next_trial_num + num_old_trials
                # Trials are 1-indexed, and there is one extra key, so it works out

                new_trial_names = ['Trial' + str(num).zfill(4) for num in new_trial_num]

                for old_original, old_new in zip(old_file_keys, new_trial_names):
                    old_file.copy(old_original, nf, old_new)

                old_file_trial_matrix_data = old_file['Trials'][10:]
                # Skip the first ten
                combined_trial_matrix = np.concat((combined_trial_matrix, old_file_trial_matrix_data), axis=0)

        num_rows = len(combined_trial_matrix)
        nf_trial_matrix_dataset = nf.create_dataset('Trials', data=combined_trial_matrix)
        for attr in f0_trial_matrix.attrs:
            nf_trial_matrix_dataset.attrs[attr] = f0_trial_matrix.attrs[attr]
        nf_trial_matrix_dataset.attrs['NROWS'] = num_rows


def main():
    parser = argparse.ArgumentParser(description='Combine two HDF5 files')
    parser.add_argument('files', nargs="+", action="extend", help='HDF Files')
    parser.add_argument('-o', '--output', default=None, help='New HDF5 file')

    args = parser.parse_args()

    file_paths = [Path(file) for file in args.files]

    for file in file_paths:
        if not file.exists():
            raise FileNotFoundError(f'File 1 [{args.file1}] does not exist')


    kwargs = {}

    if args.output:
        output_path = Path(args.output)
        kwargs['output_file'] = output_path
        if not output_path.parent.exists():
            raise FileNotFoundError(f'Output directory {args.output} does not exist')

    combine(*file_paths, **kwargs)

if __name__ == '__main__':
    main()