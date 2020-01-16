'''
Description: This file contains functions that are used by the DTPM module.
'''

import configparser
import pandas as pd
import multiprocessing
import itertools
import matplotlib
import numpy as np
from itertools import islice
import sys
import math
import ast
# matplotlib.use('Agg')
import os

import common
import DASH_Sim_v0
import job_parser
import DTPM_power_models
import DASH_Sim_utils
import DTPM_policies

def get_EDP(trace_system_file):
    # Return the EDP for a given trace_system*.py file
    result = pd.read_csv(trace_system_file)
    return (result['Energy (uJ)'] * result['Exec. Time (us)']).sum()

def run_sim_traces(sim_params):
    sim_num, DVFS_cfg_list, job_config, N_little, N_big, num_PEs = sim_params
    common.CLEAN_TRACES = False
    common.generate_complete_trace = True
    common.TRACE_FREQUENCY = False
    common.TRACE_PES = False
    common.enable_real_time_constraints = False
    common.DVFS_cfg_list = DVFS_cfg_list
    common.job_list = job_config
    if job_config == []:
        common.current_job_list = []
    else:
        common.current_job_list = job_config[0]
    common.gen_trace_capacity_little = N_little
    common.gen_trace_capacity_big = N_big
    common.sim_ID = sim_num
    common.num_PEs_TRACE = num_PEs

    common.trace_file_num = os.getpid()
    DASH_Sim_v0.run_simulator()

def run_parallel_sims(DVFS_config_list, N_little_list, N_big_list, N_jobs, N_applications, heterogeneous_PEs=False):
    # Run all possible combinations for the provided frequency points in parallel
    # Create the simulation parameters for all simulations
    if heterogeneous_PEs:
        DVFS_config_list_prod = itertools.product(*DVFS_config_list)
    else:
        DVFS_config_list_prod = itertools.product(DVFS_config_list, repeat=common.num_PEs_TRACE)

    job_list = multinomial_combinations(N_jobs, N_applications)

    num_sim, config_list = create_config_list(DVFS_config_list_prod, N_little_list, N_big_list, job_list)

    print("Number of job configurations:", len(job_list))
    print("Number of simulations:", num_sim)

    pool = multiprocessing.Pool(min(num_sim, multiprocessing.cpu_count()))
    # Run all simulations
    pool.map(run_sim_traces, config_list)
    pool.close()
    return 0

def create_config_list(DVFS_config_list_prod, N_little_list, N_big_list, job_list):
    config_list = []
    num_sim = 0
    pool = multiprocessing.Pool(min(len(job_list)*len(N_big_list)*len(N_little_list), multiprocessing.cpu_count()))

    for cfg_first_sample in DVFS_config_list_prod:
        if len(cfg_first_sample) < 2:
            print("[E] Trace generation must have at least little and big clusters, check run_parallel_sims method")
            sys.exit()
        for N_little in N_little_list:
            for N_big in N_big_list:
                for job_config in job_list:
                    config_list.append((num_sim, cfg_first_sample, [list(job_config)], N_little, N_big, common.num_PEs_TRACE))
                    num_sim += 1
    print(len(config_list))
    pool.close()
    return (num_sim, config_list)

def multinomial_combinations(n, k, max_power=None):
    """returns a list (2d numpy array) of all length k sequences of
    non-negative integers n1, ..., nk such that n1 + ... + nk = n."""
    bar_placements = itertools.combinations(range(1, n+k), k-1)
    tmp = [(0,) + x + (n+k,) for x in bar_placements]
    sequences =  np.diff(tmp) - 1
    if max_power:
        return list(sequences[np.where((sequences<=max_power).all(axis=1))][::-1])
    else:
        return list(sequences[::-1])

def get_num_tasks():
    # Return the number of tasks
    config = configparser.ConfigParser()
    config.read('config_file.ini')
    num_tasks = 0
    jobs = common.ApplicationManager()
    job_files_list = common.str_to_list(config['DEFAULT']['task_file'])
    for job_file in job_files_list:
        job_parser.job_parse(jobs, job_file)
    num_of_jobs = len(jobs.list)
    for ii in range(num_of_jobs):
        num_tasks += len(jobs.list[ii].task_list)
    return num_tasks
