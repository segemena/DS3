'''!
@brief This file contains the DVFS policies.

Default and custom DVFS policies are implemented in this file, some of the default policies include Linux's Performance, Ondemand, and Powersave modes,
and custom policies such as DyPO (https://dl.acm.org/doi/10.1145/3126530) and HiLITE (https://ieeexplore.ieee.org/document/9085952)

Steps to include other user-defined DVFS policies:
- Define a name for the custom policy, which will be used in the SoC config file and must be applied to all clusters (excluding the memory).
- Define an initial frequency for the custom policy in the initialize_frequency method.
- Create a method at the end of this file that receives the required parameters and changes the clusters' frequency according to the defined policy.
- Add a call for the new DVFS policy in the evaluate_PE method of DTPM.py
'''

import sys
import math
import csv
import os
import ast
from math import exp
import numpy as np

import common
import DTPM_power_models
import DASH_Sim_utils

def initialize_frequency(cluster):
    '''!
    Initialize the frequency for the given cluster.
    Used when the simulation starts.
    @param cluster: Cluster object
    '''
    if cluster.current_frequency == 0:
        if cluster.DVFS == 'ondemand':
            cluster.current_frequency = DTPM_power_models.get_max_freq(cluster.OPP)
            cluster.current_voltage = DTPM_power_models.get_max_voltage(cluster.OPP)
            cluster.policy_frequency = DTPM_power_models.get_max_freq(cluster.OPP)
        elif cluster.DVFS == 'performance':
            cluster.current_frequency = DTPM_power_models.get_max_freq(cluster.OPP)
            cluster.current_voltage = DTPM_power_models.get_max_voltage(cluster.OPP)
            cluster.policy_frequency = DTPM_power_models.get_max_freq(cluster.OPP)
        elif cluster.DVFS == 'powersave':
            cluster.current_frequency = DTPM_power_models.get_min_freq(cluster.OPP)
            cluster.current_voltage = DTPM_power_models.get_min_voltage(cluster.OPP)
            cluster.policy_frequency = DTPM_power_models.get_min_freq(cluster.OPP)
        elif str(cluster.DVFS).startswith('constant'):
            DVFS_str_split = str(cluster.DVFS).split("-")
            constantFrequency = int(DVFS_str_split[1])
            cluster.current_frequency = constantFrequency
            cluster.current_voltage = DTPM_power_models.get_voltage_constant_mode(cluster.OPP, constantFrequency)
            cluster.policy_frequency = constantFrequency

def ondemand_policy(cluster, PEs, timestamp):
    '''!
    Default Linux's ondemand policy.
    High and low utilization thresholds are configured in config_file.ini (util_high_threshold and util_low_threshold).
    @param cluster: Cluster object
    @param PEs: The PEs available in the current SoC
    @param timestamp: Current timestamp
    '''
    # When using ondemand, evaluate the PE utilization and adjust the frequency accordingly
    utilization = DASH_Sim_utils.get_cluster_utilization(cluster, PEs) * cluster.num_active_cores
    if utilization <= common.util_high_threshold and utilization >= common.util_low_threshold:
        # Keep the current frequency
        DTPM_power_models.keep_frequency(cluster, timestamp)
    elif utilization > common.util_high_threshold:
        # Only modify the frequency if the cluster is not being throttled
        if common.throttling_state == -1:
            # Set the maximum frequency
            DTPM_power_models.set_max_frequency(cluster, timestamp)
    elif utilization < common.util_low_threshold:
        # Decrease the frequency
        DTPM_power_models.decrease_frequency(cluster, timestamp)
    else:
        print("[E] Error while evaluating the PE utilization in the DVFS module, all test cases must be previously covered")
        sys.exit()
    cluster.policy_frequency = cluster.current_frequency
