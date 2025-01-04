"""
Dewan Lab H5 Parsing Library
Author: Austin Pauley (pauley@psy.fsu.edu)
Date: 01-04-2025
"""


class DewanH5:
    def __init__(self):
        self.mouse_number = 0
        self.total_trials = 0
        self.date = None
        self.time = None

    def __str__(self):
        return (f'Dewan Lab H5 file:\n'
                f'Mouse: {self.mouse_number}\n'
                f'Experiment Date: {self.date}\n'
                f'Experiment Time: {self.time}\n')

