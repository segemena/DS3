'''
Description: This file contains the DVFS policies.
'''

import sys

import common
import DTPM_power_models
import DASH_Sim_utils

def initialize_frequency(cluster):
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
    # When using ondemand, evaluate the PE utilization and adjust the frequency accordingly
    utilization = DASH_Sim_utils.get_cluster_utilization(cluster, PEs) * cluster.num_active_cores

    if utilization <= common.util_high_threshold and utilization >= common.util_low_threshold:
        # Keep the current frequency
        DTPM_power_models.keep_frequency(cluster, timestamp)
    elif utilization > common.util_high_threshold:
        # Set the maximum frequency
        DTPM_power_models.set_max_frequency(cluster, timestamp)
    elif utilization < common.util_low_threshold:
        # Decrease the frequency
        DTPM_power_models.decrease_frequency(cluster, timestamp)
    else:
        print("[E] Error while evaluating the PE utilization in the DVFS module, all test cases must be previously covered")
        sys.exit()
    cluster.policy_frequency = cluster.current_frequency
