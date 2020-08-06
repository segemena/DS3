'''!
@brief This file contains the process elements and their attributes.
'''
import simpy
import copy

import common                                                                           # The common parameters used in DASH-Sim are defined in common_parameters.py
import DTPM_power_models
import DASH_Sim_utils
import DTPM_policies

class PE:
    '''!
    A processing element (PE) is the basic resource that defines the simpy processes.
    '''
    def __init__(self, env, type, name, ID, cluster_ID, capacity):
        '''!
        @param env: Pointer to the current simulation environment
        @param type: Type of the PE (e.g., BIG, LTL, ACC, MEM, etc.)
        @param name: Name of the current processing element
        @param ID: ID of the current processing element
        @param cluster_ID: ID of the cluster to which this PE belongs
        @param capacity: Number tasks that a resource can run simultaneously
        '''
        self.env = env
        self.type = type
        self.name = name
        self.ID = ID
        self.capacity = capacity                                                # Current capacity of the PE (depends on the number of active cores)
        self.total_capacity = capacity                                          # Total capacity of the PE
        self.cluster_ID = cluster_ID

        self.enabled = True                                                     # Indicate if the PE is ON
        self.utilization = 0                                                    # Describes how much one PE is utilized
        self.utilization_list = []                                              # List containing the PE utilization for each sample inside a snippet
        self.current_power_active_core = 0                                      # Indicate the current power for the active cores (dynamic + static)
        self.current_leakage_core = 0                                           # Indicate the current leakage power
        self.snippet_energy = 0                                                 # Indicate the energy consumption of the current snippet
        self.total_energy = 0                                                   # Indicate the total energy consumed by the given PE

        self.Cdyn_alpha = 0                                                     # Variable that stores the dynamic capacitance * switching activity for each PE

        self.queue = []                                                         # List of currently running task on a PE
        self.available_time = 0                                                 # Estimated available time of the PE
        self.available_time_list = [0]*self.capacity                            # Estimated available time for each core os the PE
        self.idle = True                                                        # The variable indicates whether the PE is active or not
        self.blocking = 0                                                       # Duration that a PE is busy when some other tasks are ready to execute 
        self.active = 0                                                         # Total active time for a PE while executing a workload
        
        self.info = []                                                          # List to record all the events happened on a PE
        self.process = simpy.Resource(env, capacity=self.capacity)

        if (common.DEBUG_CONFIG):
            print('[D] Constructed PE-%d with name %s' %(ID,name))

    # Start the "run" process for this PE
    def run(self, sim_manager, task, resource, DVFS_module):
        '''!
        Run this PE to execute a given task.
        The execution time is retrieved from resource_matrix and task name.
        @param sim_manager: Simulation environment object (DASH_Sim_core)
        @param task: Task to be executed
        @param resource: Resource object for this PE
        @param DVFS_module: DVFS module object
        '''
        try:
            with self.process.request() as req:                                 # Requesting the resource for the task
                yield req

                if common.ClusterManager.cluster_list[self.cluster_ID].current_frequency == 0:                                 # Initialize the frequency if it was not set yet
                    # Depending on the DVFS policy on this PE, set the initial frequency and voltage accordingly
                    if common.ClusterManager.cluster_list[self.cluster_ID].DVFS != 'none' or len(common.ClusterManager.cluster_list[self.cluster_ID].OPP) != 0:
                        DTPM_policies.initialize_frequency(common.ClusterManager.cluster_list[self.cluster_ID])

                        DASH_Sim_utils.trace_frequency(self.env.now)

                self.idle = False                                               # Since the PE starts execution of a task, it is not idle anymore
                common.TaskQueues.running.list.append(task)                     # Since the execution started for the task we should add it to the running queue 
                task.start_time = self.env.now                                  # When a resource starts executing the task, record it as the start time

                # if this is the leading task of this job, increment the injection counter
                if ((task.head == True) and
                    (self.env.now >= common.warmup_period)):
                    common.results.injected_jobs += 1
                    if (common.DEBUG_JOB):
                        print('[D] Time %d: Total injected jobs becomes: %d'
                              %(self.env.now, common.results.injected_jobs))

                    # Store the injected job for validation
                    if (common.simulation_mode == 'validation'):
                       common.Validation.injected_jobs.append(task.jobID)
                # end of if ( (next_task.head == True) and ...

                if (common.DEBUG_JOB):
                    print('[D] Time %d: Task %s execution is started with frequency %d by PE-%d %s'
                      % (self.env.now, task.ID, common.ClusterManager.cluster_list[self.cluster_ID].current_frequency, self.ID, self.name))

                # Retrieve the execution time and power consumption from the model
                task_runtime_max_freq, randomization_factor = DTPM_power_models.get_execution_time_max_frequency(task, resource)           # Get the run time and power consumption

                dynamic_energy = 0
                static_energy = 0
                task_complete = False
                task_elapsed_time = task.task_elapsed_time_max_freq
                while task_complete is False:
                    # The predicted time takes into account the current frequency and subtracts the time that the task already executed
                    predicted_exec_time = (task_runtime_max_freq - task_elapsed_time) + (task_runtime_max_freq - task_elapsed_time) * DTPM_power_models.compute_DVFS_performance_slowdown(common.ClusterManager.cluster_list[self.cluster_ID])
                    window_remaining_time = common.sampling_rate - self.env.now % common.sampling_rate
                    # Test if the task finished before the next sampling period
                    if predicted_exec_time - window_remaining_time > 0:
                        # Run until the next sampling timestamp
                        simulation_step = window_remaining_time
                        slowdown = DTPM_power_models.compute_DVFS_performance_slowdown(common.ClusterManager.cluster_list[self.cluster_ID]) + 1
                        task_elapsed_time += simulation_step / slowdown
                    else:
                        # Run until the task ends
                        simulation_step = predicted_exec_time
                        task_complete = True

                    # Compute the static energy
                    current_leakage = DTPM_power_models.compute_static_power_dissipation(self.cluster_ID)
                    static_energy += current_leakage * simulation_step * 1e-6

                    max_power_consumption, freq_threshold = DTPM_power_models.get_max_power_consumption(common.ClusterManager.cluster_list[self.cluster_ID], sim_manager.PEs)  # of this task on this resource running at max frequency

                    # Based on the total power consumption and the leakage, get the dynamic power
                    if max_power_consumption > 0:
                        dynamic_power_cluster = max_power_consumption - current_leakage * len(common.ClusterManager.cluster_list[self.cluster_ID].power_profile[freq_threshold])
                        # After obtaining the dynamic power for the cluster, divide it by the number of cores being used to get the power per core
                        dynamic_power_max_freq_core = dynamic_power_cluster / DASH_Sim_utils.get_num_tasks_being_executed(common.ClusterManager.cluster_list[self.cluster_ID], sim_manager.PEs)
                    else:
                        dynamic_power_max_freq_core = 0

                    # Compute the capacitance and alpha based on the dynamic power
                    self.Cdyn_alpha = DTPM_power_models.compute_Cdyn_and_alpha(resource, dynamic_power_max_freq_core, freq_threshold)

                    # Compute the dynamic energy
                    dynamic_power = DTPM_power_models.compute_dynamic_power_dissipation(common.ClusterManager.cluster_list[self.cluster_ID].current_frequency,
                                                                                        common.ClusterManager.cluster_list[self.cluster_ID].current_voltage,
                                                                                        self.Cdyn_alpha)
                    dynamic_energy +=  dynamic_power * simulation_step * 1e-6

                    # Scale the power based on the number of active cores
                    common.ClusterManager.cluster_list[self.cluster_ID].current_power_cluster = dynamic_power * DASH_Sim_utils.get_num_tasks_being_executed(common.ClusterManager.cluster_list[self.cluster_ID], sim_manager.PEs) + \
                                                                                                current_leakage * common.ClusterManager.cluster_list[self.cluster_ID].num_active_cores
                    self.current_leakage_core = current_leakage
                    self.current_power_active_core = dynamic_power + current_leakage

                    if (common.simulation_mode == "performance" and self.env.now >= common.warmup_period) or common.simulation_mode == "validation":
                        energy_sample = (dynamic_power + current_leakage) * simulation_step * 1e-6
                        self.snippet_energy += energy_sample
                        self.total_energy += energy_sample
                        common.results.cumulative_energy_consumption += energy_sample

                    yield self.env.timeout(simulation_step)
                    task.task_elapsed_time_max_freq = task_elapsed_time
                    # At each sample:
                    if self.env.now % common.sampling_rate == 0:
                        # Case 1: If the task is not complete, evaluate this PE at this moment
                        if task_complete is False:
                            DVFS_module.evaluate_PE(resource, self, self.env.now)

                task.finish_time = int(self.env.now)

                # As the task finished its execution, reset the task time
                task.task_elapsed_time_max_freq = 0

                if (common.DEBUG_JOB):
                    print('[D] Time %d: Task %s execution is finished by PE-%d %s'
                      % (self.env.now, task.ID, self.ID, self.name))
                
                task_time = task.finish_time - task.start_time
                self.idle = True
                
                if task.finish_time > common.warmup_period:
                    if task.start_time <= common.warmup_period:
                        self.active += (task.finish_time - common.warmup_period)
                    else:
                        self.active += task_time

                # If there are no OPPs in the model, use the measured power consumption from the model
                if len(common.ClusterManager.cluster_list[self.cluster_ID].OPP) == 0:
                    total_energy_task = dynamic_power_max_freq_core * task_time * 1e-6
                else:
                    total_energy_task = dynamic_energy + static_energy

                if (task.tail):
                    common.results.job_counter -= 1
                    
                    if (common.simulation_mode == 'performance'):
                        sim_manager.update_completed_queue()

                    if (self.env.now >= common.warmup_period):
                        common.results.execution_time = self.env.now
                        common.results.completed_jobs += 1

                        # Interrupts the timeout of job generator if the inject_jobs_ASAP flag is active
                        if sim_manager.job_gen.generate_job and common.inject_jobs_ASAP:
                            sim_manager.job_gen.action.interrupt()

                        for completed in common.TaskQueues.completed.list:
                            if ((completed.head == True) and 
                                (completed.jobID == task.jobID)):
                                common.results.cumulative_exe_time += (self.env.now - completed.job_start)

                                if (common.DEBUG_JOB):
                                    print('[D] Time %d: Job %d is completed' %(self.env.now, task.jobID+1))
                    #print('[D] total completed jobs becomes: %d' %(common.results.completed_jobs))
                    #print('[D] Cumulative execution time: %f' %(common.results.cumulative_exe_time))

                    # Store the completed job for validation
                    if (common.simulation_mode == 'validation'):
                        common.Validation.completed_jobs.append(task.jobID)
                # end of if ((task.tail) and ...

                if (common.INFO_SIM):
                    print('[I] Time %d: Task %s is finished by PE-%d %s with %.2f us and energy consumption %.2f J'
                      % (self.env.now, task.ID, self.ID, self.name, round(task_time,2), round(total_energy_task,2)) )
                DASH_Sim_utils.trace_tasks(task, self, task_time, total_energy_task)
                #for i, executable_task in enumerate(common.TaskQueues.executable.list):
                #    print('Task %d can be executed on PE-%d after time %d'%(executable_task.ID, executable_task.PE_ID, executable_task.time_stamp))

                # Retrieve the energy consumption for the task
                # that the PE just finished processing
                common.results.energy_consumption += total_energy_task

                # Since the current task is processed, it should be removed
                # from the outstanding task queue 
                sim_manager.update_ready_queue(task)

                # Case 2: Evaluate the PE after the queues are updated
                if self.env.now % common.sampling_rate == 0:
                    DVFS_module.evaluate_PE(resource, self, self.env.now)

                if (task.tail) and (self.env.now >= common.warmup_period) and (common.results.completed_jobs % common.snippet_size == 0):

                    # Reset energy of the snippet
                    for PE in sim_manager.PEs:
                        PE.snippet_energy = 0

                    common.snippet_start_time = self.env.now
                    common.snippet_initial_temp = copy.deepcopy(common.current_temperature_vector)

                    common.snippet_throttle = -1
                    for cluster in common.ClusterManager.cluster_list:
                        cluster.snippet_power_list = []
                    common.snippet_temp_list = []
                    common.snippet_ID_exec += 1
                    if common.job_list != []:
                        if common.snippet_ID_exec < common.max_num_jobs / common.snippet_size:
                            common.current_job_list = common.job_list[common.snippet_ID_exec]

                    # Ends the simulation if all jobs are executed (if inject_fixed_num_jobs is enabled)
                    if common.results.completed_jobs == common.max_num_jobs:
                        #common.simulation_length = self.env.now
                        sim_manager.sim_done.succeed()
                        
                # end of with self.process.request() as req:
            
        except simpy.Interrupt:
            print('Expect an interrupt at %s' % (self.env.now))
    # end of def run(self, sim_manager, task, resource):


# end class PE(object):
