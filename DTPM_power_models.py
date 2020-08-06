'''!
@brief This file contains functions that are used by the DVFS mechanism and PEs to get performance, power, and thermal values.

This file contains the analytical models used for power and thermal, it computes performance, power, energy, and temperature, and it contains methods to change the frequency and number of active cores.
'''
from math import exp
import numpy as np
import sys
import copy

import DASH_Sim_utils
import common

# Thermal model (Odroid XU3 board)
A_model = [[0.9928,    0.000566,   0.004281,  0.0003725, 1.34e-5  ],
           [0.006084,  0.9909,     0,         0.001016,  8.863e-5 ],
           [0,         0.0008608,  0.993,     0,         0.0008842],
           [0.006844,  -0.0005119, 0,         0.9904,    0.0003392],
           [0.0007488, 0.003932,   8.654e-5, 0.002473,   0.9905   ]]

# Big cluster model (Odroid XU3 board)
B_model_big     = [[0.0471  ],
                   [0.01265 ],
                   [0.113   ],
                   [0.01646 ],
                   [0.01476 ]]
# Little cluster model (Odroid XU3 board)
B_model_little  = [[0.02399 ],
                   [0       ],
                   [0.02819 ],
                   [0.007198],
                   [0.03902 ]]
# Memory model (Odroid XU3 board)
B_model_mem     = [[0.07423 ],
                   [0       ],
                   [0.6708  ],
                   [0       ],
                   [0.01404 ]]
# GPU model (Odroid XU3 board)
B_model_gpu     = [[6.898e-7],
                   [0.001971],
                   [2.108e-6],
                   [0.01682 ],
                   [0.03811 ]]
# Accelerator model
B_model_acc     = [[0       ],
                   [0       ],
                   [0       ],
                   [0       ],
                   [0       ]]

# Memory power (Odroid XU3 board)
P_mem = 0.0473

# GPU power (Odroid XU3 board)
P_GPU = 0.1201

def compute_DVFS_performance_slowdown(cluster):
    '''!
    Compute the slowdown from running a given task with lower frequency.
    @param cluster: Cluster object
    @return Slowdown for the given task
    '''
    # Calculate the slowdown based on the current frequency
    if cluster.current_frequency == 0 or len(cluster.OPP) == 0:
        return 0
    else:
        max_freq = get_max_freq(cluster.OPP)
        slowdown_ratio = float(max_freq) / float(cluster.current_frequency)
        return slowdown_ratio - 1
# end compute_DVFS_performance_slowdown(cluster)

def compute_Cdyn_and_alpha(resource, max_power_consumption, freq_threshold, OPP=None):
    '''!
    Based on the maximum frequency, voltage, and measured power dissipation, compute the capacitance C times the switching activity Alpha for the given task.
    Pdyn = Cdyn * alpha * f * V^2
    @param resource: Current resource object
    @param max_power_consumption: Baseline maximum power consumption
    @param freq_threshold: Frequency at which the baseline power consumption was profiled (based on the configurations defined in the SoC file)
    @param OPP: Allows a given OPP to be used as parameter in order to estimate the Cdyn_alpha for an OPP that is not the current one. Otherwise, use the current OPP. (Optional)
    @return Computed Cdyn_alpha for the current cluster
    '''
    max_freq = get_frequency_in_Hz(freq_threshold)
    if OPP is None:
        max_volt = get_voltage_in_V(get_voltage_constant_mode(common.ClusterManager.cluster_list[resource.cluster_ID].OPP, freq_threshold))
        if len(common.ClusterManager.cluster_list[resource.cluster_ID].OPP) > 0:
            Cdyn_alpha = max_power_consumption / (max_freq * max_volt ** 2)
        else:
            Cdyn_alpha = 0
    else:
        max_volt = get_voltage_in_V(get_voltage_constant_mode(OPP, freq_threshold))
        if len(OPP) > 0:
            Cdyn_alpha = max_power_consumption / (max_freq * max_volt ** 2)
        else:
            Cdyn_alpha = 0
    return Cdyn_alpha
# end compute_Cdyn_and_alpha(resource, max_power_consumption, freq_threshold, OPP=None)

def compute_static_power_dissipation(cluster_ID, input_temperature=None, input_voltage=None):
    '''!
    Compute the static power dissipation of the PE.
    @param cluster_ID: ID of the current cluster
    @param input_temperature: If specified, use an input temperature vector. Otherwise, use the current one. (Optional)
    @param input_voltage: If specified, use an input voltage. Otherwise, use the current one. (Optional)
    '''
    if common.ClusterManager.cluster_list[cluster_ID].type == "ACC":
        static_power_core = 0
    else:
        if input_temperature is None:
            current_temperature = max(common.current_temperature_vector)
        else:
            current_temperature = max(input_temperature)
        if input_voltage is None:
            current_voltage = common.ClusterManager.cluster_list[cluster_ID].current_voltage
        else:
            current_voltage = input_voltage
        temp_K = 273 + current_temperature # Convert the temperature to Kelvin
        voltage_V = get_voltage_in_V(current_voltage)
        static_power_cluster = voltage_V * common.C1 * temp_K * temp_K * exp(-common.C2/temp_K) + common.Igate*voltage_V
        if common.ClusterManager.cluster_list[cluster_ID].type == "LTL":
            static_power_cluster /= 4 # Scaling the leakage power based on the area differece between big and little cores. (C1 and C2 are obtained for the big cluster)
        static_power_core = static_power_cluster / 4  # Max 4 cores per cluster
    return static_power_core
# end compute_static_power_dissipation(PE, input_temperature=None, input_voltage=None)

def compute_dynamic_power_dissipation(current_frequency, current_voltage, Cdyn_alpha):
    '''!
    Compute the dynamic power dissipation for the current task based on the current state of the PE.
    @param current_frequency: PE's current frequency
    @param current_voltage: PE's current voltage
    @param Cdyn_alpha: PE's current Cdyn_alpha
    @return Dynamic power dissipation for the current PE
    '''
    current_frequency_Hz = get_frequency_in_Hz(current_frequency)
    current_voltage_V = get_voltage_in_V(current_voltage)
    dynamic_power_core =  Cdyn_alpha * current_frequency_Hz * (current_voltage_V**2)
    return dynamic_power_core
# end compute_dynamic_power_dissipation(current_frequency, current_voltage, Cdyn_alpha)

def get_execution_time_max_frequency(task, resource):
    '''!
    Get the execution time of the current task if it was running at maximum frequency and considering the randomization factor that was used.
    @param task: Current task object
    @param resource: Current resource object
    @return Execution time of the current task
    '''
    task_ind = resource.supported_functionalities.index(task.name)                  # Retrieve the index of the task
    execution_time = resource.performance[task_ind]                                 # Retrieve the mean execution time of a task
    if(resource.performance[task_ind]):
        # Randomize the execution time based on a gaussian distribution
        #randomized_execution_time = max(round(
        #       random.gauss(execution_time,common.standard_deviation * execution_time)), 1)
        
        # randomized_execution_time = max(round(
        #         np.random.normal(execution_time,common.standard_deviation * execution_time)), 1)

        randomized_execution_time = execution_time

        if (common.DEBUG_SIM):
            print('Randomized execution time is %s, the original was %s' 
                  %(randomized_execution_time, execution_time))                                                       										# finding execution time using randomization values by mean value (expected execution time) 
        return randomized_execution_time, float(randomized_execution_time)/float(execution_time)
    else:                                                                                        										# if the expected execution time is 0, ie. if it is dummy task, then no randomization
        # If a task has a 0 us of execution (dummy ending task), it should stay the same
        return execution_time, 1
        
# end get_execution_time_max_frequency(task, resource)

def get_max_power_consumption(cluster, PEs, N_tasks=None, N_cores=None):
    '''!
    Get the power consumption of the current PE.
    @param cluster: Current cluster object
    @param PEs: The PEs available in the current SoC
    @param N_tasks: If specified, use a given number of tasks for predicting the power consumption. Otherwise, use the current number of tasks. (Optional)
    @param N_cores: If specified, use a given number of cores for predicting the power consumption. Otherwise, use the current number of active cores. (Optional)
    @return Maximum power consumption for the current cluster
    '''
    if N_tasks is None:
        num_tasks = DASH_Sim_utils.get_num_tasks_being_executed(cluster, PEs)
    else:
        num_tasks = N_tasks

    if N_cores is None:
        num_cores = cluster.num_active_cores
    else:
        num_cores = N_cores

    if num_tasks > 0:
        for k, v in cluster.power_profile.items():
            if cluster.current_frequency <= k:
                if num_tasks <= num_cores:
                    return v[num_tasks - 1], int(k)
                else:
                    return v[num_cores - 1], int(k)
        print("[E] Power profile (Cluster {} ID {}) does not have a frequency threshold higher than {}".format(cluster.type, cluster.ID, cluster.current_frequency))
        sys.exit()
    else:
        return 0, 0
# end get_execution_time_max_frequency(cluster, PEs, N_tasks=None, N_cores=None)

def initialize_B_model():
    '''!
    Initialize the B_model matrix, used in the temperature prediction.
    '''
    common.B_model = B_model_mem
    common.B_model = np.append(common.B_model, B_model_gpu, axis=1)
    for cluster in common.ClusterManager.cluster_list:
        if cluster.type != "MEM":
            if cluster.type == "BIG":
                common.B_model = np.append(common.B_model, B_model_big, axis=1)
            elif cluster.type == "LTL":
                common.B_model = np.append(common.B_model, B_model_little, axis=1)
            else:
                common.B_model = np.append(common.B_model, B_model_acc, axis=1)
# end initialize_B_model()

def predict_temperature():
    '''!
    Predict the temperature based on the current status of the clusters.
    @return Current temperature vector for the SoC
    '''
    power_list = []
    power_list.append(P_mem) # Memory model
    power_list.append(P_GPU) # GPU model
    for cluster in common.ClusterManager.cluster_list:
        if cluster.type != "MEM":
            power_list.append(cluster.current_power_cluster)

    predicted_temperature = np.matmul(A_model, np.array(common.current_temperature_vector) - common.T_ambient) + \
                            np.matmul(common.B_model, np.array(power_list)) + common.T_ambient
    return predicted_temperature
# end predict_temperature()

def evaluate_throttling(timestamp, input_freq, input_trip_temperature, throttling_type):
    '''!
    Apply throttling if the temperature exceeds the trip points.
    @param timestamp: Current timestamp
    @param input_freq: Current frequency
    @param input_trip_temperature: List of trip points to be evaluated
    @param throttling_type: Define the throttling type: regular or DTPM
    '''
    if (common.enable_throttling and throttling_type == 'regular') or (common.enable_DTPM_throttling and throttling_type == 'DTPM'):
        current_temp = max(common.current_temperature_vector)
        for trip_point, trip_temp in enumerate(input_trip_temperature):
            # If temperature is higher than the trip temp, throttle the PEs
            if current_temp > trip_temp:
                # Check if the PEs are already being throttled
                if common.throttling_state < trip_point:
                    freq_list = []
                    for i, cluster in enumerate(common.ClusterManager.cluster_list):
                        if cluster.DVFS != 'none':
                            if throttling_type == 'regular':
                                current_trip_freq = cluster.trip_freq[trip_point]
                            elif throttling_type == 'DTPM':
                                current_trip_freq = cluster.DTPM_trip_freq[trip_point]
                            else:
                                print('[E] Invalid throttling type, please check evaluate_throttling method')
                                sys.exit()
                            if current_trip_freq != -1:
                                if input_freq[i] > current_trip_freq:
                                    freq_list.append(current_trip_freq)
                                else:
                                    freq_list.append(input_freq[i])
                            else:
                                freq_list.append(input_freq[i])
                    freq_list = [ x / 1000 for x in freq_list]
                    set_frequency(timestamp, freq_list, True)
                    common.throttling_state = trip_point
                if common.snippet_throttle < trip_point:
                    common.snippet_throttle = trip_point
            else:
                if common.throttling_state == trip_point and current_temp < trip_temp - common.trip_hysteresis[trip_point]:
                    # PEs were throttled, but now the temperature has reduced, restore frequency to the previous trip point
                    common.throttling_state -= 1
                    freq_list = []
                    # If trip point is 0, restore the input frequency, otherwise restore the previous trip point
                    if trip_point == 0:
                        freq_list = input_freq
                    else:
                        for i, cluster in enumerate(common.ClusterManager.cluster_list):
                            if cluster.DVFS != 'none':
                                if throttling_type == 'regular':
                                    current_trip_freq = cluster.trip_freq[trip_point - 1]
                                elif throttling_type == 'DTPM':
                                    current_trip_freq = cluster.DTPM_trip_freq[trip_point - 1]
                                else:
                                    print('[E] Invalid throttling type, please check evaluate_throttling method')
                                    sys.exit()
                                if current_trip_freq != -1:
                                    if input_freq[i] > current_trip_freq:
                                        freq_list.append(current_trip_freq)
                                    else:
                                        freq_list.append(input_freq[i])
                                else:
                                    freq_list.append(input_freq[i])
                    freq_list = [ x / 1000 for x in freq_list]
                    set_frequency(timestamp, freq_list, True)
# end evaluate_throttling(timestamp, input_freq, input_trip_temperature, throttling_type)

def get_voltage_constant_mode(OPP_list, constantFrequency):
    '''!
    Get the voltage of the OPP that satisfies the defined constant frequency.
    @param OPP_list: List of OPPs of the current cluster
    @param constantFrequency: Input frequency
    @return Voltage related to the input frequency, following the OPP list
    '''
    if constantFrequency < get_min_freq(OPP_list):
        print("[E] The frequency set in the constant DVFS mode is lower than the minimum frequency that the PE supports, please check the resource file")
        sys.exit()
    for OPP_i, OPP in enumerate(OPP_list):
        if constantFrequency == OPP[0]:
            return OPP[1]
    if constantFrequency > get_max_freq(OPP_list):
        print("[E] The frequency set in the constant DVFS mode is higher than the maximum frequency that the PE supports, please check the resource file")
        sys.exit()
    print("[E] Target frequency was not found in the OPP list:", constantFrequency)
    sys.exit()
# end get_voltage_constant_mode(OPP_list, constantFrequency)

def get_max_freq(OPP_list):
    '''!
    Get the maximum frequency of a cluster.
    @param OPP_list: List of OPPs of the current cluster
    @return The maximum frequency defined in the OPP list
    '''
    if len(OPP_list) > 0:
        opp_tuple_max = OPP_list[len(OPP_list) - 1]
        return  opp_tuple_max[0]
    else:
        return 0
# end get_max_freq(OPP_list)

def get_min_freq(OPP_list):
    '''!
    Get the minimum frequency of a cluster.
    @param OPP_list: List of OPPs of the current cluster
    @return The minimum frequency defined in the OPP list
    '''
    if len(OPP_list) > 0:
        opp_tuple_min = OPP_list[0]
        return opp_tuple_min[0]
    else:
        return 0
# end get_min_freq(OPP_list)

def get_max_voltage(OPP_list):
    '''!
    Get the maximum voltage of a cluster.
    @param OPP_list: List of OPPs of the current cluster
    @return The maximum voltage defined in the OPP list
    '''
    if len(OPP_list) > 0:
        opp_tuple_max = OPP_list[len(OPP_list) - 1]
        return  opp_tuple_max[1]
    else:
        return 0
# end get_max_voltage(OPP_list)

def get_min_voltage(OPP_list):
    '''!
    Get the minimum voltage of a cluster.
    @param OPP_list: List of OPPs of the current cluster
    @return The minimum voltage defined in the OPP list
    '''
    if len(OPP_list) > 0:
        opp_tuple_min = OPP_list[0]
        return opp_tuple_min[1]
    else:
        return 0
# end get_min_voltage(OPP_list)

def get_frequency_in_Hz(frequency_MHz):
    '''!
    Convert frequency from MHz to Hz.
    @param frequency_MHz: Frequency in MHz
    @return Frequency in Hz
    '''
    return frequency_MHz * 1e6
# end get_frequency_in_Hz(frequency_MHz)

def get_voltage_in_V(voltage_mV):
    '''!
    Convert voltage from mV to V.
    @param voltage_mV: Voltage in mV
    @return Voltage in V
    '''
    return voltage_mV * 1e-3
# end get_voltage_in_V(voltage_mV)

def decrease_frequency(cluster, timestamp):
    '''!
    Decrease the frequency by one step (based on the defined OPPs).
    @param cluster: Current cluster object
    @param timestamp: Current timestamp
    @return Change the frequency and return whether the frequency is already at the minimum OPP or not
    '''
    for OPP_i, OPP_tuple in enumerate(cluster.OPP):
        if OPP_tuple[0] == cluster.current_frequency:
            if OPP_i == 0:
                # Already at min freq
                cluster.current_frequency = cluster.OPP[OPP_i][0]
                cluster.current_voltage = cluster.OPP[OPP_i][1]
                if (common.DEBUG_SIM):
                    print('[D] Time %d: PE %s - The frequency is already at the minimum: %d' % (timestamp, cluster.name, cluster.current_frequency))
                return False
            else:
                # Decrease the frequency to the previous OPP
                cluster.current_frequency = cluster.OPP[OPP_i - 1][0]
                cluster.current_voltage = cluster.OPP[OPP_i - 1][1]
                if (common.DEBUG_SIM):
                    print('[D] Time %d: PE %s - The frequency was decreased: %d' % (timestamp, cluster.name, cluster.current_frequency))
                return True
# end decrease_frequency(cluster, timestamp)

def increase_frequency(cluster, timestamp):
    '''!
    Increase the frequency by one step (based on the defined OPPs).
    @param cluster: Current cluster object
    @param timestamp: Current timestamp
    @return Change the frequency and return whether the frequency is already at the maximum OPP or not
    '''
    for OPP_i, OPP_tuple in enumerate(cluster.OPP):
        if OPP_tuple[0] == cluster.current_frequency:
            if OPP_i == len(cluster.OPP) - 1:
                # Already at max freq
                cluster.current_frequency = cluster.OPP[OPP_i][0]
                cluster.current_voltage = cluster.OPP[OPP_i][1]
                if (common.DEBUG_SIM):
                    print('[D] Time %d: PE %s - The frequency is already at the maximum: %d' % (timestamp, cluster.name, cluster.current_frequency))
                return False
            else:
                # Increase the frequency to the next OPP
                cluster.current_frequency = cluster.OPP[OPP_i + 1][0]
                cluster.current_voltage = cluster.OPP[OPP_i + 1][1]
                if (common.DEBUG_SIM):
                    print('[D] Time %d: PE %s - The frequency was increased: %d' % (timestamp, cluster.name, cluster.current_frequency))
                return True
# end increase_frequency(cluster, timestamp)

def increase_frequency_all_PEs(current_frequency_list):
    '''!
    Increase the frequency of all PEs by one step (based on the respective defined OPPs).
    @param current_frequency_list: List with current frequencies for all clusters
    @return Return whether all PEs are at maximum frequency and the updated frequency list
    '''
    max_freq_counter = 0
    num_PEs = len(common.ClusterManager.cluster_list) - 1
    for cluster_ID in range(num_PEs):
        current_OPP = common.ClusterManager.cluster_list[cluster_ID].OPP
        for OPP_i, OPP_tuple in enumerate(current_OPP):
            if float(OPP_tuple[0] / 1000) == current_frequency_list[cluster_ID]:
                if OPP_i == len(current_OPP) - 1:
                    # Already at max freq
                    max_freq_counter += 1
                    break
                else:
                    # Increase the frequency to the next OPP
                    current_frequency_list[cluster_ID] = float(current_OPP[OPP_i + 1][0] / 1000)
                    break
    if max_freq_counter == num_PEs:
        return (True, current_frequency_list)
    else:
        return (False, current_frequency_list)
# end increase_frequency_all_PEs(current_frequency_list)

def increase_num_cores_all_PEs(current_num_cores):
    '''!
    Increase the number of active cores by one (based on the respective cluster capacities).
    @param current_num_cores: List with current number of active cores for all clusters
    @return Return whether all clusters are at maximum capacity and the updated list of cores
    '''
    if current_num_cores[0] < 4:
        current_num_cores[0] += 1
    if current_num_cores[1] < 4:
        current_num_cores[1] += 1
    if current_num_cores[0] == 4 and current_num_cores[1] == 4:
        return (True, current_num_cores)
    else:
        return (False, current_num_cores)
# end increase_num_cores_all_PEs(current_num_cores)

def set_max_frequency(cluster, timestamp):
    '''!
    Set the maximum frequency for the current cluster.
    @param cluster: Current cluster object
    @param timestamp: Current timestamp
    '''
    max_freq = get_max_freq(cluster.OPP)
    max_voltage = get_max_voltage(cluster.OPP)
    cluster.current_frequency = max_freq
    cluster.current_voltage = max_voltage
    if (common.DEBUG_SIM):
        print('[D] Time %d: Cluster %s - The frequency was set to the maximum: %d' % (timestamp, cluster.name, cluster.current_frequency))
# end set_max_frequency(cluster, timestamp)

def keep_frequency(cluster, timestamp):
    '''!
    Keep the same frequency for the current cluster.
    @param cluster: Current cluster object
    @param timestamp: Current timestamp
    '''
    cluster.current_frequency = cluster.current_frequency
    cluster.current_voltage = cluster.current_voltage

    if (common.DEBUG_SIM):
        print('[D] Time %d: Cluster %s - The frequency was not modified: %d' % (timestamp, cluster.name, cluster.current_frequency))
# end keep_frequency(cluster, timestamp)

def set_frequency(timestamp, frequency_list, throttling):
    '''!
    Set a given frequency to the respective clusters.
    @param timestamp: Current timestamp
    @param frequency_list: List of frequncies for all clusters
    @param throttling: Throttling variable that indicates whether throttling is being applied
    '''
    for i, cluster in enumerate(common.ClusterManager.cluster_list):
        if cluster.DVFS != "none":
            frequency_MHz = int(frequency_list[i] * 1000)
            freq_search = [item for item in cluster.OPP if item[0] == frequency_MHz]
            if len(freq_search) > 0:
                cluster.current_frequency = frequency_MHz
                cluster.current_voltage   = get_voltage_constant_mode(cluster.OPP, frequency_MHz)
                if not throttling:
                    cluster.policy_frequency = frequency_MHz
            else:
                print("[E] Time %d: Frequency %d not supported by the Cluster %d (set_frequency method)" % (timestamp, frequency_MHz, cluster.ID))
                sys.exit()
# end set_frequency(timestamp, frequency_list, throttling)

def set_active_cores(cluster, PEs, num_cores):
    '''!
    Set a given number of cores to the current cluster.
    @param cluster: Current cluster object
    @param PEs: The PEs available in the current SoC
    @param num_cores: Number of active cores to be set
    '''
    cluster.num_active_cores = num_cores
    capacity = len(cluster.PE_list)
    for i in range(capacity):
        if i + 1 <= num_cores:
            PEs[i].enabled = True
        else:
            PEs[i].enabled = False
# end set_active_cores(cluster, PEs, num_cores)
