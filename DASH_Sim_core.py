'''
Description: This file contains the simulation core that handles the simulation events.
'''
import sys
import os
import csv

import common                                                                   # The common parameters used in DASH-Sim are defined in common_parameters.py
import DTPM
import DASH_Sim_utils
import DTPM_policies
# Define the core of the simulation engine
# This function calls the scheduler, starts/interrupts the tasks,
# and manages collection of all the statistics

class SimulationManager:
    '''
    Define the SimulationManager class to handle the simulation events.
    '''
    def __init__(self, env, sim_done, job_gen, scheduler, PE_list, jobs, resource_matrix):
        '''
        env: Pointer to the current simulation environment
        scheduler: Pointer to the DASH_scheduler
        PE_list: The PEs available in the current SoC
        jobs: The list of all jobs given to DASH-Sim
        resource_matrix: The data structure that defines power/performance
            characteristics of the PEs for each supported task
        '''
        self.env = env
        self.sim_done = sim_done
        self.job_gen = job_gen
        self.scheduler = scheduler
        self.PEs = PE_list
        self.jobs = jobs
        self.resource_matrix = resource_matrix

        self.action = env.process(self.run())  # starts the run() method as a SimPy process


    # As the simulation proceeds, tasks are being processed.
    # We need to update the ready tasks queue after completion of each task
    def update_ready_queue(self,completed_task):
        '''
        This function updates the common.TaskQueues.ready after one task is completed.
        '''

        # completed_task is the task whose processing is just completed
        # Add completed task to the completed tasks queue
        common.TaskQueues.completed.list.append(completed_task)

        # Remove the completed task from the queue of the PE
        for task in self.PEs[completed_task.PE_ID].queue:
            if task.ID == completed_task.ID:
                self.PEs[task.PE_ID].queue.remove(task)

        # Remove the completed task from the currently running queue
        common.TaskQueues.running.list.remove(completed_task)

        # Remove the completed task from the current DAG representation
        if completed_task.ID in common.current_dag:
            common.current_dag.remove_node(completed_task.ID)
        
        # Initialize $remove_from_outstanding_queue which will populate tasks
        # to be removed from the outstanding queue
        remove_from_outstanding_queue = []

        # Initialize $to_memory_comm_time which will be communication time to
        # memory for data from a predecessor task to a outstanding task
        to_memory_comm_time = -1
        
        job_ID = -1
        for ind, job in enumerate(self.jobs.list):
            if job.name == completed_task.jobname:
                job_ID = ind


        # Check if the dependency of any outstanding task is cleared
        # We need to move them to the ready queue
        for i, outstanding_task in enumerate(common.TaskQueues.outstanding.list):                           # Go over each outstanding task
            for ii, predecessor in enumerate(outstanding_task.predecessors):                                # Go over each predecessor
                if (completed_task.ID in outstanding_task.predecessors):                                    # if the completed task is one of the predecessors
                    outstanding_task.predecessors.remove(completed_task.ID)                                 # Clear this predecessor
                    
                    if (common.shared_memory):
                        # Get the communication time to memory for data from a 
                        # predecessor task to a outstanding task 
                        comm_vol = self.jobs.list[job_ID].comm_vol[completed_task.base_ID , outstanding_task.base_ID]
                        comm_band = common.ResourceManager.comm_band[completed_task.PE_ID, self.resource_matrix.list[-1].ID]
                        to_memory_comm_time = int(comm_vol/comm_band)                                           # Communication time from a PE to memory
        
                        if (common.DEBUG_SIM):
                            print('[D] Time %d: Data from task %d for task %d will be sent to memory in %d us'
                                  %(self.env.now, completed_task.ID, outstanding_task.ID, to_memory_comm_time))
        
                        # Based on this communication time, this outstanding task
                        # will be added to the ready queue. That is why, keep track of
                        # all communication times required for a task in the list
                        # $ready_wait_times
                        outstanding_task.ready_wait_times.append(to_memory_comm_time + self.env.now)
                    # end of if (common.shared_memory):
                    
                    
                # end of if (completed_task.ID in outstanding_task.predecessors):
            # end of for ii, predecessor in enumerate(outstanding_task.predecessors):

            no_predecessors = (len(outstanding_task.predecessors) == 0)                            # Check if this was the last dependency
            currently_running = (outstanding_task in                                               # if the task is in the running queue,
                                 common.TaskQueues.running.list)                                   # We should not put it back to the ready queue
            not_in_ready_queue = not(outstanding_task in                                           # If this task is already in the ready queue,
                                  common.TaskQueues.ready.list)                                    # We should not append another copy

            if (no_predecessors and not(currently_running) and not_in_ready_queue):
                if (common.PE_to_PE):                                                              # if PE to PE communication is utilized
                    common.TaskQueues.ready.list.append(common.TaskQueues.outstanding.list[i])     # Add the task to the ready queue immediately

                elif (common.shared_memory):
                    # if shared memory is utilized for communication, then
                    # the outstanding task will wait for a certain amount time
                    # (till the $time_stamp)for being added into the ready queue
                    common.TaskQueues.wait_ready.list.append(outstanding_task)
                    if (common.INFO_SIM) and (common.shared_memory):
                            print('[I] Time %d: Task %d ready times due to memory communication of its predecessors are'
                                  %(self.env.now, outstanding_task.ID))
                            print('%12s'%(''), outstanding_task.ready_wait_times)
                    common.TaskQueues.wait_ready.list[-1].time_stamp = max(outstanding_task.ready_wait_times)

                remove_from_outstanding_queue.append(outstanding_task)
        # end of for i, outstanding_task in...

        # Remove the tasks from outstanding queue that have been moved to ready queue
        for task in remove_from_outstanding_queue:
            common.TaskQueues.outstanding.list.remove(task)

        # At the end of this function:
            # Newly processed $completed_task is added to the completed tasks
            # outstanding tasks with no dependencies are added to the ready queue
            # based on the communication mode and then, they are removed from
            # the outstanding queue
    #end def update_ready_queue(completed_task)

    def update_execution_queue(self, ready_list):
        '''
        This function updates the common.TaskQueues.executable if one task is ready
        for execution but waiting for the communication time, either between
        memory and a PE, or between two PEs (based on the communication mode)
        '''
        # Initialize $remove_from_ready_queue which will populate tasks
        # to be removed from the outstanding queue
        remove_from_ready_queue = []
        
        # Initialize $from_memory_comm_time which will be communication time 
        # for data from memory to a PE
        from_memory_comm_time = -1

        # Initialize $PE_to_PE_comm_time which will be communication time
        # for data from a PE to another PE
        PE_to_PE_comm_time = -1

        job_ID = -1
        for ready_task in ready_list:
            for ind, job in enumerate(self.jobs.list):
                if job.name == ready_task.jobname:
                    job_ID = ind

            for i, task in enumerate(self.jobs.list[job_ID].task_list):
                if ready_task.base_ID == task.ID:
                    if ready_task.head == True:
                        # if a task is the leading task of a job
                        # then it can start immediately since it has no predecessor
                        ready_task.PE_to_PE_wait_time.append(self.env.now)
                        ready_task.execution_wait_times.append(self.env.now)
                    # end of if ready_task.head == True:

                    for predecessor in task.predecessors:
                        if(task.ID==ready_task.ID):
                           ready_task.predecessors = task.predecessors
                              
                        # data required from the predecessor for $ready_task
                        comm_vol = self.jobs.list[job_ID].comm_vol[predecessor, ready_task.base_ID]

                        # retrieve the real ID  of the predecessor based on the job ID
                        real_predecessor_ID = predecessor + ready_task.ID - ready_task.base_ID

                        # Initialize following two variables which will be used if 
                        # PE to PE communication is utilized
                        predecessor_PE_ID = -1
                        predecessor_finish_time = -1

                        if (common.PE_to_PE):
                            # Compute the PE to PE communication time
                            for completed in common.TaskQueues.completed.list:
                                if completed.ID == real_predecessor_ID:
                                    predecessor_PE_ID = completed.PE_ID
                                    predecessor_finish_time = completed.finish_time
                            comm_band = common.ResourceManager.comm_band[predecessor_PE_ID, ready_task.PE_ID]
                            PE_to_PE_comm_time = int(comm_vol/comm_band)                                 
                            ready_task.PE_to_PE_wait_time.append(PE_to_PE_comm_time + predecessor_finish_time)

                            if (common.DEBUG_SIM):
                                print('[D] Time %d: Data transfer from PE-%s to PE-%s for task %d from task %d is completed at %d us'
                                      %(self.env.now, predecessor_PE_ID, ready_task.PE_ID, 
                                        ready_task.ID, real_predecessor_ID, ready_task.PE_to_PE_wait_time[-1]))
                        # end of if (common.PE_to_PE): 

                        if (common.shared_memory):
                            # Compute the memory to PE communication time
                            comm_band = common.ResourceManager.comm_band[self.resource_matrix.list[-1].ID, ready_task.PE_ID]
                            from_memory_comm_time = int(comm_vol/comm_band)
                            if (common.DEBUG_SIM):
                                print('[D] Time %d: Data from memory for task %d from task %d will be sent to PE-%s in %d us'
                                      %(self.env.now, ready_task.ID, real_predecessor_ID, ready_task.PE_ID, from_memory_comm_time))
                            ready_task.execution_wait_times.append(from_memory_comm_time + self.env.now)
                        # end of if (common.shared_memory)
                    # end of for predecessor in task.predecessors:   

                    if (common.INFO_SIM) and (common.PE_to_PE):
                        print('[I] Time %d: Task %d execution ready times due to communication between PEs are'
                              %(self.env.now, ready_task.ID))
                        print('%12s'%(''), ready_task.PE_to_PE_wait_time)

                    if (common.INFO_SIM) and (common.shared_memory):
                        print('[I] Time %d: Task %d execution ready time(s) due to communication between memory and PE-%s are'
                              %(self.env.now, ready_task.ID, ready_task.PE_ID))
                        print('%12s'%(''), ready_task.execution_wait_times)

                    # Populate all ready tasks in executable with a time stamp
                    # which will show when a task is ready for execution
                    common.TaskQueues.executable.list.append(ready_task)
                    remove_from_ready_queue.append(ready_task)
                    if (common.PE_to_PE):
                        common.TaskQueues.executable.list[-1].time_stamp = max(ready_task.PE_to_PE_wait_time)
                    else:
                        common.TaskQueues.executable.list[-1].time_stamp = max(ready_task.execution_wait_times)
                # end of ready_task.base_ID == task.ID:
            # end of i, task in enumerate(self.jobs.list[job_ID].task_list):    
        # end of for ready_task in ready_list:
        
        # Remove the tasks from ready queue that have been moved to executable queue
        for task in remove_from_ready_queue:
            common.TaskQueues.ready.list.remove(task)

        # Reorder tasks based on their job IDs
        common.TaskQueues.executable.list.sort(key=lambda task: task.jobID, reverse=False)
            
    def update_completed_queue(self):
        '''
        This function updates the common.TaskQueues.completed 
        '''  
        ## Be careful about this function when there are diff jobs in the system
        # reorder tasks based on their job IDs
        common.TaskQueues.completed.list.sort(key=lambda x: x.jobID, reverse=False)
        
        first_task_jobID =  common.TaskQueues.completed.list[0].jobID
        last_task_jobID = common.TaskQueues.completed.list[-1].jobID
        
        if ((last_task_jobID - first_task_jobID) > 15):
            for i,task in enumerate(common.TaskQueues.completed.list):
                if (task.jobID == first_task_jobID):
                    del common.TaskQueues.completed.list[i]
            
        
    # Implement the basic run method that will be called periodically
    # in each simulation "tick"
    def run(self):
        '''
        This function takes the next ready tasks and run on the specific PE 
        and update the common.TaskQueues.ready list accordingly.
        '''
        DTPM_module = DTPM.DTPMmodule(self.env, self.resource_matrix, self.PEs)

        for cluster in common.ClusterManager.cluster_list:
            DTPM_policies.initialize_frequency(cluster)

        while (True):                                                           # Continue till the end of the simulation

            if self.env.now % common.sampling_rate == 0:
                #common.results.job_counter_list.append(common.results.job_counter)
                #common.results.sampling_rate_list.append(self.env.now)
                # Evaluate idle PEs, busy PEs will be updated and evaluated from the PE class
                DTPM_module.evaluate_idle_PEs()
            # end of if self.env.now % common.sampling_rate == 0:

            if (common.shared_memory):
                # this section is activated only if shared memory is used

                # Initialize $remove_from_wait_ready which will populate tasks
                # to be removed from the wait ready queue
                remove_from_wait_ready = []

                for i, waiting_task in enumerate(common.TaskQueues.wait_ready.list):
                    if waiting_task.time_stamp <= self.env.now:
                        common.TaskQueues.ready.list.append(waiting_task)
                        remove_from_wait_ready.append(waiting_task)
                # at the end of this loop, all the waiting tasks with a time stamp
                # equal or smaller than the simulation time will be added to
                # the ready queue list
                #end of for i, waiting_task in...

                # Remove the tasks from wait ready queue that have been moved to ready queue
                for task in remove_from_wait_ready:
                    common.TaskQueues.wait_ready.list.remove(task)
            # end of if (common.shared_memory):

            if (common.INFO_SIM) and len(common.TaskQueues.ready.list) > 0:
                print('[I] Time %s: DASH-Sim ticks with %d task ready for being assigned to a PE'
                      % (self.env.now, len(common.TaskQueues.ready.list)))

            if (not len(common.TaskQueues.ready.list) == 0):
                # give all tasks in ready_list to the chosen scheduler
                # and scheduler will assign the tasks to a PE
                if self.scheduler.name == 'CPU_only':
                    self.scheduler.CPU_only(common.TaskQueues.ready.list)
                elif self.scheduler.name == 'ILP_5TX_FPGA':
                    self.scheduler.ILP_ONE(common.TaskQueues.ready.list)
                elif self.scheduler.name == 'ILP_5RX_FPGA':
                    self.scheduler.ILP_ONE(common.TaskQueues.ready.list)
                elif self.scheduler.name == 'ILP_5X_FPGA':
                    self.scheduler.ILP_TWO(common.TaskQueues.ready.list)
                elif self.scheduler.name == 'ILP_5TX_BAL':
                    self.scheduler.ILP_ONE(common.TaskQueues.ready.list)
                elif self.scheduler.name == 'ILP_5RX_BAL':
                    self.scheduler.ILP_ONE(common.TaskQueues.ready.list)
                elif self.scheduler.name == 'ILP_5X_BAL':
                    self.scheduler.ILP_TWO(common.TaskQueues.ready.list)
                elif self.scheduler.name == 'ILP_5TX_BIG':
                    self.scheduler.ILP_ONE(common.TaskQueues.ready.list)
                elif self.scheduler.name == 'ILP_5RX_BIG':
                    self.scheduler.ILP_ONE(common.TaskQueues.ready.list)
                elif self.scheduler.name == 'ILP_5X_BIG':
                    self.scheduler.ILP_TWO(common.TaskQueues.ready.list)
                elif self.scheduler.name == 'MET':
                    self.scheduler.MET(common.TaskQueues.ready.list)
                elif self.scheduler.name == 'EFT':
                    self.scheduler.EFT(common.TaskQueues.ready.list)
                elif self.scheduler.name == 'ILP':
                    self.scheduler.ILP(common.TaskQueues.ready.list)
                elif self.scheduler.name == 'ILP_TX':
                    self.scheduler.ILP_TX(common.TaskQueues.ready.list)
                elif self.scheduler.name == 'STF':
                    self.scheduler.STF(common.TaskQueues.ready.list)
                elif self.scheduler.name == 'ETF':
                    self.scheduler.ETF(common.TaskQueues.ready.list)
                elif self.scheduler.name == 'ETF_LB':
                    self.scheduler.ETF_LB(common.TaskQueues.ready.list)
                elif self.scheduler.name == 'ILP_MULTI':
                    self.scheduler.ILP_FOUR(common.TaskQueues.ready.list)
                else:
                    print('[E] Could not find the requested scheduler')
                    print('[E] Please check "config_file.ini" and enter a proper name')
                    print('[E] or check "scheduler.py" if the scheduler exist')
                    sys.exit()
                # end of if self.scheduler.name


                self.update_execution_queue(common.TaskQueues.ready.list)       # Update the execution queue based on task's info
            # end of if not len(common.TaskQueues.ready.list) == 0:

            # Initialize $remove_from_executable which will populate tasks
            # to be removed from the executable queue
            remove_from_executable = []

            # Go over each task in the executable queue
            if len(common.TaskQueues.executable.list) is not 0:
                for i, executable_task in enumerate(common.TaskQueues.executable.list):
                    is_time_to_execute = (executable_task.time_stamp <= self.env.now)
                    PE_has_capacity = (len(self.PEs[executable_task.PE_ID].queue) < self.PEs[executable_task.PE_ID].capacity)
                    task_has_assignment = (executable_task.PE_ID != -1)

                    dynamic_dependencies_met = True

                    dependencies_completed = []
                    for dynamic_dependency in executable_task.dynamic_dependencies:
                        dependencies_completed = dependencies_completed + list(filter(lambda completed_task: completed_task.ID == dynamic_dependency, common.TaskQueues.completed.list))
                    if len(dependencies_completed) != len(executable_task.dynamic_dependencies):
                        dynamic_dependencies_met = False

                    if is_time_to_execute and PE_has_capacity and dynamic_dependencies_met and task_has_assignment:
                        self.PEs[executable_task.PE_ID].queue.append(executable_task)

                        if (common.INFO_SIM):
                            print('[I] Time %s: Task %s is ready for execution by PE-%s'
                                  % (self.env.now, executable_task.ID, executable_task.PE_ID))

                        current_resource = self.resource_matrix.list[executable_task.PE_ID]
                        self.env.process(self.PEs[executable_task.PE_ID].run(  # Send the current task and a handle for this simulation manager (self)
                            self, executable_task, current_resource, DTPM_module))  # This handle is used by the PE to call the update_ready_queue function

                        # Since the execution started for the executable task
                        # we should add it to the running queue
                        common.TaskQueues.running.list.append(executable_task)
                        remove_from_executable.append(executable_task)
                    # end of if is_time_to_execute and PE_has_capacity and dynamic_dependencies_met
                # end of for i, executable_task in...
            # end of if not len(common.TaskQueues.executable.list) == 0:

            # Remove the tasks from executable queue that have been executed by a resource
            for task in remove_from_executable:
                common.TaskQueues.executable.list.remove(task)

            # If DRL scheduler is active, tha tasks waiting in the exectuable queue will be redirected to the ready queue
            if (len(common.TaskQueues.executable.list)):
                if (self.scheduler.name == 'DRL'):
                    #print('ILP' in self.scheduler.name)
                    while len(common.TaskQueues.executable.list) > 0:
                        task = common.TaskQueues.executable.list.pop(-1)
                        common.TaskQueues.ready.list.append(task)
                        
            # The simulation tick is completed. Wait till the next interval
            yield self.env.timeout(common.simulation_clk)

            if self.env.now > common.simulation_length:
                self.sim_done.succeed()
        #end while (True)
