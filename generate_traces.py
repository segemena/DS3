'''
Description: This file contains the script to generate the traces of several configurations at once.
'''

import os
import sys
import itertools
import multiprocessing
import fnmatch
import pandas as pd
import csv
import time
import numpy, itertools

import common
import DASH_Sim_v0
import DASH_Sim_utils
import configparser
import DASH_SoC_parser
import DTPM_utils
import processing_element

# Test ondemand, performance, and powersave results
test_individual_configs = True
# Define the DVFS modes to generate the traces
heterogeneous_PEs = True
SoC_file = "MULTIPLE_BAL" # WIFI_5X_BAL, MULTIPLE_BAL_SMALL, MULTIPLE_BAL

N_jobs = 10
N_applications = 5

if not heterogeneous_PEs:
    # Homogenerous mode
    DVFS_modes = ['constant-2000',
                  # 'constant-1900',
                  'constant-1800',
                  # 'constant-1700',
                  'constant-1600',
                  # 'constant-1500',
                  'constant-1400',
                  # 'constant-1300',
                  'constant-1200',
                  # 'constant-1100',
                  'constant-1000',
                  'constant-800',
                  'constant-600'  # ,
                  # 'constant-400',
                  # 'constant-200'
                  ]
else:
    # Heterogeneous mode
    # WIFI_5X_BAL
    if SoC_file == "WIFI_5X_BAL":
        DVFS_modes = [
            ['constant-2000', 'constant-1800', 'constant-1600', 'constant-1400', 'constant-1200', 'constant-1000', 'constant-800', 'constant-600'], # 0
            ['constant-2000', 'constant-1800', 'constant-1600', 'constant-1400', 'constant-1200', 'constant-1000', 'constant-800', 'constant-600'], # 1
            ['constant-2000', 'constant-1800', 'constant-1600', 'constant-1400', 'constant-1200', 'constant-1000', 'constant-800', 'constant-600'], # 2
            ['constant-2000', 'constant-1800', 'constant-1600', 'constant-1400', 'constant-1200', 'constant-1000', 'constant-800', 'constant-600'], # 3
            ['performance'],  # 4
            ['performance'],  # 5
            ['performance'],  # 6
            ['performance'],  # 7
            ['performance'],  # 8
            ['performance'],  # 9
            ['constant-1000', 'constant-800', 'constant-600', 'constant-400'], # 10
            ['constant-1000', 'constant-800', 'constant-600', 'constant-400'], # 11
            ['constant-1000', 'constant-800', 'constant-600', 'constant-400'], # 12
            ['constant-1000', 'constant-800', 'constant-600', 'constant-400'], # 13
            ['performance'],  # 14
            ['performance']  # 15
        ]
    elif SoC_file == "MULTIPLE_BAL_SMALL":
        DVFS_modes = [
            ['constant-1400', 'constant-1200', 'constant-1000', 'constant-800', 'constant-600'],  # 0 (LTL)
            ['constant-2000', 'constant-1800', 'constant-1600', 'constant-1400', 'constant-1200', 'constant-1000', 'constant-800', 'constant-600']  # 1 (BIG)
        ]
    elif SoC_file == "MULTIPLE_BAL":
        DVFS_modes = [
            ['constant-1400', 'constant-1200', 'constant-1000', 'constant-800', 'constant-600'],  # 0 (LTL)
            ['constant-2000', 'constant-1800', 'constant-1600', 'constant-1400', 'constant-1200', 'constant-1000', 'constant-800', 'constant-600'],  # 1 (BIG)
            ['performance'],  # 2 (Scrambler)
            ['performance'],  # 3 (Scrambler)
            ['performance'],  # 4 (FFT)
            ['performance'],  # 5 (FFT)
            ['performance'],  # 6 (FFT)
            ['performance'],  # 7 (FFT)
            ['performance'],  # 8 (Viterbi)
            ['performance']   # 9 (Viterbi)
        ]
    else:
        print("[E] SoC config not found")
        sys.exit()

N_little_list   = [1, 2, 3, 4]
N_big_list      = [1, 2, 3, 4]

resource_matrix = common.ResourceManager()  # This line generates an empty resource matrix

if __name__ == '__main__':
    start_time = time.time()
    DASH_Sim_utils.clean_traces()
    # Parse the resource file
    config = configparser.ConfigParser()
    config.read('config_file.ini')
    resource_file = config['DEFAULT']['resource_file']
    # Update the number os PEs in the common.py file
    DASH_SoC_parser.resource_parse(resource_matrix, resource_file)  # Parse the input configuration file to populate the resource matrix

    # Run all possible combinations among the frequency points that were generated
    DTPM_utils.run_parallel_sims(DVFS_modes, N_little_list, N_big_list, N_jobs, N_applications, heterogeneous_PEs)

    # Create configuration lists (all PEs have the same DVFS mode) and run the simulator
    if test_individual_configs:
        cfg = ['ondemand', 'performance', 'powersave']
        job_config = [[2, 2, 2, 2, 2]]
        sim_ID = -1
        for c in cfg:
            DVFS_cfg_list = []
            for i in range(common.num_PEs_TRACE):
                DVFS_cfg_list.append(c)
            for N_little in N_little_list:
                for N_big in N_big_list:
                    config_list = (sim_ID, DVFS_cfg_list, job_config, N_little, N_big, common.num_PEs_TRACE)
                    sim_ID -= 1
                    DTPM_utils.run_sim_traces(config_list)

    # Merge and delete temp csv files - System
    for trace_name in DASH_Sim_utils.trace_list:
        print("Trace name:", trace_name)
        data = set()
        if os.path.exists(trace_name):
            os.remove(trace_name)
        file_list = fnmatch.filter(os.listdir('.'), trace_name.split(".")[0] + '__*.csv')
        if len(file_list) > 0:
            for i, file in enumerate(file_list):
                print("\tFile name:", file)
                if i == 0:
                    with open(file, "r") as f:
                        reader = csv.reader(f)
                        header = next(reader)
                    with open(trace_name, 'w', newline='') as csvfile:
                        wr = csv.writer(csvfile, delimiter=',')
                        wr.writerow(header)
                for i, chunk in enumerate(pd.read_csv(file, chunksize=1000000, iterator=True)):
                    print("\t\tLoading chunk {}...".format(i))
                    data.update(set(chunk.itertuples(index=False, name=None)))
                os.remove(file)
            with open(trace_name, 'a', newline='') as csvfile:
                file_out = csv.writer(csvfile, delimiter=',')
                for line in data:
                    file_out.writerow(list(line))

    sim_time = float(float(time.time() - start_time)) / 60.0
    print("--- {:.2f} minutes ---".format(sim_time))
