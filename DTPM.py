'''
Description: This file contains the code for the DTPM module.
'''
import sys
import copy
import common
import DTPM_power_models
import DASH_Sim_utils
import DTPM_policies

class DTPMmodule:
    '''
    The DTPM module is responsible for evaluating the PE utilization and changing the V/F according to the defined policy
    '''
    def __init__(self, env, resource_matrix, PEs):
        '''
        env: Pointer to the current simulation environment
        resource_matrix: The data structure that defines power/performance
        PEs: The PEs available in the current SoC
        timestamp_last_update: Contains the timestamp from the last time each PE was evaluated
        '''
        self.env = env
        self.resource_matrix = resource_matrix
        self.PEs = PEs
        self.timestamp_last_update = [-1] * len(PEs)
        self.timestamp_last_update_cluster = [-1] * len(common.ClusterManager.cluster_list)

        DTPM_power_models.initialize_B_model()

        if (common.DEBUG_CONFIG):
            print('[D] DVFS module was initialized')

    def evaluate_PE(self, resource, current_PE, timestamp):

        if self.timestamp_last_update[current_PE.ID] != timestamp and timestamp != 0:

            self.timestamp_last_update[current_PE.ID] = timestamp

            DASH_Sim_utils.update_PE_utilization_and_info(current_PE, timestamp)

            if timestamp > common.warmup_period:
                current_PE.utilization_list.append(current_PE.utilization)

            # if (common.DEBUG_SIM):
            #     print('%12s' % (''), 'Utilization for %s is %.2f' % (current_PE.name, current_PE.utilization))

            if common.ClusterManager.cluster_list[current_PE.cluster_ID].DVFS != 'none':
                DASH_Sim_utils.trace_PEs(self.env.now, current_PE)

        # Apply cluster decisions if the cluster was not updated in this sample and all other PEs in that cluster are already updated
        if self.timestamp_last_update_cluster[current_PE.cluster_ID] != timestamp and timestamp != 0 and common.ClusterManager.cluster_list[current_PE.cluster_ID].PE_list[-1] == current_PE.ID:

            self.timestamp_last_update_cluster[current_PE.cluster_ID] = timestamp

            current_cluster = common.ClusterManager.cluster_list[current_PE.cluster_ID]

            if current_cluster.DVFS == 'ondemand' or current_cluster.DVFS == 'powersave' or \
                    str(current_cluster.DVFS).startswith("constant"):
                # The only DVFS mode that does not require OPPs is the performance one
                if len(current_cluster.OPP) == 0:
                    print("[E] PEs using %s DVFS mode must have at least one OPP, please check the resource file" % common.ClusterManager.cluster_list[current_PE.cluster_ID].DVFS)
                    sys.exit()

            # Custom DVFS policies
            if current_cluster.DVFS == 'ondemand':
                DTPM_policies.ondemand_policy(current_cluster, self.PEs, self.env.now)

            # Update temperature
            if timestamp % common.sampling_rate_temperature == 0 and self.timestamp_last_update.count(timestamp) == (len(self.timestamp_last_update) - 1):
                common.current_temperature_vector = DTPM_power_models.predict_temperature()
                common.snippet_temp_list.append(max(common.current_temperature_vector))

                # Evaluate and apply throttling
                if common.enable_throttling:
                    input_frequency = []
                    for i, cluster in enumerate(common.ClusterManager.cluster_list):
                        if cluster.DVFS == 'ondemand' or cluster.DVFS == 'performance':
                            input_frequency.append(DTPM_power_models.get_max_freq(cluster.OPP))
                        elif cluster.DVFS == 'powersave':
                            input_frequency.append(DTPM_power_models.get_min_freq(cluster.OPP))
                        elif str(cluster.DVFS).startswith('constant'):
                            DVFS_str_split = str(cluster.DVFS).split("-")
                            input_frequency.append(int(DVFS_str_split[1]))
                        elif cluster.DVFS != 'none':
                            input_frequency.append(self.PEs[i].current_frequency)
                    DTPM_power_models.evaluate_throttling(timestamp, input_frequency)

                DASH_Sim_utils.trace_temperature(timestamp)

            if current_cluster.DVFS != 'none':
                DASH_Sim_utils.trace_frequency(self.env.now, common.ClusterManager.cluster_list[current_PE.cluster_ID])
            if self.timestamp_last_update.count(timestamp) == (len(self.timestamp_last_update) - 1):
                DASH_Sim_utils.trace_load(timestamp, self.PEs)

    def evaluate_idle_PEs(self):
        '''
        Check all PEs and, for those that are idle, adjust the frequency and power accordingly.
        '''
        # if (common.DEBUG_SIM):
        #     print('[D] Time %s: DVFS module is evaluating PE utilization' % self.env.now)
        base_power = DTPM_power_models.P_mem + DTPM_power_models.P_GPU
        base_energy = base_power * common.sampling_rate * 1e-6 / (len(self.resource_matrix.list) - 1)
        for i, resource in enumerate(self.resource_matrix.list):
            current_PE = self.PEs[i]
            if common.ClusterManager.cluster_list[current_PE.cluster_ID].type != 'MEM':
                if current_PE.process.count == 0:
                    # Only evaluate the PE if there is no process running, otherwise the PE itself will call the DVFS evaluation
                    self.evaluate_PE(resource, current_PE, self.env.now)
                    # Update the power dissipation to be only the static power as the PE is currently idle
                    current_PE.current_leakage_core = DTPM_power_models.compute_static_power_dissipation(current_PE)
                    common.ClusterManager.cluster_list[current_PE.cluster_ID].current_power_cluster = current_PE.current_leakage_core * common.ClusterManager.cluster_list[current_PE.cluster_ID].num_active_cores
                    common.ClusterManager.cluster_list[current_PE.cluster_ID].current_power_cluster += base_power
                if current_PE.process.count < current_PE.capacity:
                    # Add leakage power for the idle cores in the PE
                    energy_sample = current_PE.current_leakage_core * common.sampling_rate * 1e-6 + base_energy
                    common.results.energy_consumption += energy_sample
                    if (common.simulation_mode == "performance" and self.env.now >= common.warmup_period) or common.simulation_mode == "validation":
                        current_PE.snippet_energy += energy_sample
                        current_PE.total_energy += energy_sample
                        common.results.cumulative_energy_consumption += energy_sample
                else:
                    # Add base energy when all cores are being used
                    common.results.energy_consumption += base_energy
                    if (common.simulation_mode == "performance" and self.env.now >= common.warmup_period) or common.simulation_mode == "validation":
                        current_PE.snippet_energy += base_energy
                        current_PE.total_energy += base_energy
                        common.results.cumulative_energy_consumption += base_energy
    # end def evaluate_idle_PEs()

# end class DTPM
