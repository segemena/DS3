'''
Descrption: This file contains the code for scheduler class 
which contains different types of scheduler. 
'''
import networkx as nx
import numpy as np
import copy

import common                                                                   # The common parameters used in DASH-Sim are defined in common_parameters.py
import DTPM_power_models

class Scheduler:
    def __init__(self, env, resource_matrix, name, PE_list, jobs):
        '''
        env: Pointer to the current simulation environment
        resource_matrix: The data structure that defines power/performance
    		  characteristics of the PEs for each supported task
        name : The name of the requested scheduler
        PE_list: The PEs available in the current SoCs
        jobs: The list of all jobs given to DASH-Sim
        '''
        self.env = env
        self.resource_matrix = resource_matrix
        self.name = name
        self.PEs = PE_list
        self.jobs = jobs
        self.assigned = [0] * (len(self.PEs))

        # At the end of this function, the scheduler class has a copy of the
        # the power/performance characteristics of the resource matrix and
        # name of the requested scheduler name


    # end  def __init__(self, env, resource_matrix, scheduler_name)

    # Specific scheduler instances can be defined below
    def CPU_only(self, list_of_ready):
        '''
        This scheduler always select the resource with ID 0 (CPU) to
        execute all outstanding tasks without any comparison between
        available resources
        '''
        for task in list_of_ready:
            task.PE_ID = 0

    # end def CPU_only(list_of_ready):


    def ILP_ONE(self, list_of_ready):
        '''
        This scheduler utilizes a look-up table for scheduling tasks
        to a particular processor
        '''
        for task in list_of_ready:
            for i, schedule in enumerate(common.table):
                if (task.base_ID == i):
                    task.PE_ID = int(schedule[0])
                    task.order = schedule[1]
# =============================================================================
#                     if (not self.PEs[int(schedule[0])].idle):
#                         for PE in self.PEs:
#                             if ((PE.type == self.PEs[int(schedule[0])].type) and (PE.idle) and
#                                 (task.name in self.resource_matrix.list[PE.ID].supported_functionalities)):
#                                 #print(PE.type ,self.PEs[int(schedule[0])].type )
#                                 task.PE_ID = PE.ID
# =============================================================================

        list_of_ready.sort(key=lambda x: x.order, reverse=False)
    # def ILP_5RX_FPGA(self, list_of_ready):

    def ILP_TWO(self, list_of_ready):
        '''
        This scheduler utilizes a look-up table for scheduling tasks
        to a particular processor
        '''
        for task in list_of_ready:
            if ('Receiver' in task.jobname):
                for i, schedule in enumerate(common.table):
                    if (task.base_ID == i):
                        task.PE_ID = int(schedule[0])
                        task.order = schedule[1]
            else:
                for i, schedule in enumerate(common.table_2):
                    if (task.base_ID == i):
                        task.PE_ID = int(schedule[0])
                        task.order = schedule[1]


        list_of_ready.sort(key=lambda x: x.order, reverse=False)
    # def ILP_5X_FPGA(self, list_of_ready):

    def ILP(self, list_of_ready):
        '''
        This scheduler utilizes a look-up table for scheduling tasks
        to a particular processor
        '''
        for task in list_of_ready:
            for i, schedule in enumerate(common.table):
                if (task.base_ID == i):
                    task.PE_ID = int(schedule[0])
                    task.order = schedule[1]

        list_of_ready.sort(key=lambda x: x.order, reverse=False)
    # def ILP(self, list_of_ready):


    def ILP_TX(self, list_of_ready):
        '''
        This scheduler utilizes a look-up table for scheduling tasks
        to a particular processor
        '''
        for task in list_of_ready:
            for i, schedule in enumerate(common.table):
                if (task.base_ID == i):
                    task.PE_ID = schedule[0]
                    task.order = schedule[1]

        list_of_ready.sort(key=lambda x: x.order, reverse=False)

    # def ILP_TX(self, list_of_ready):

    def ILP_FOUR(self, list_of_ready):
        '''
        This scheduler utilizes a look-up table for scheduling tasks
        to a particular processor
        '''
        for task in list_of_ready:
            if ('lag' in task.jobname):
                for i, schedule in enumerate(common.table):
                    if (task.base_ID == i):
                        task.PE_ID = int(schedule[0])
                        task.order = schedule[1]
            elif ('pulse' in task.jobname):
                for i, schedule in enumerate(common.table_2):
                    if (task.base_ID == i):
                        task.PE_ID = int(schedule[0])
                        task.order = schedule[1]
            elif ('Receiver' in task.jobname):
                for i, schedule in enumerate(common.table_3):
                    if (task.base_ID == i):
                        task.PE_ID = int(schedule[0])
                        task.order = schedule[1]
            else:
                for i, schedule in enumerate(common.table_4):
                    if (task.base_ID == i):
                        task.PE_ID = int(schedule[0])
                        task.order = schedule[1]

        list_of_ready.sort(key=lambda x: x.order, reverse=False)
    # def ILP_FOUR(self, list_of_ready):

    def MET(self, list_of_ready):
        '''
        This scheduler compares the execution times of the current
        task for available resources and returns the ID of the resource
        with minimum execution time for the current task.
        '''
        # Initialize a list to record number of assigned tasks to a PE
        # for every scheduling instance
        assigned = [0]*(len(self.PEs))

        # go over all ready tasks for scheduling and make a decision
        for task in list_of_ready:

            exec_times = [np.inf]*(len(self.PEs))                                             # Initialize a list to keep execution times of task for each PE

            for i in range(len(self.resource_matrix.list)):
                if self.PEs[i].enabled:
                    if (task.name in self.resource_matrix.list[i].supported_functionalities):

                        ind = self.resource_matrix.list[i].supported_functionalities.index(task.name)
                        exec_times[i] = self.resource_matrix.list[i].performance[ind]

            min_of_exec_times = min(exec_times)                                                 # $min_of_exec_times is the minimum of execution time of the task among all PEs
            count_minimum = exec_times.count(min_of_exec_times)                                 # also, record how many times $min_of_exec_times is seen in the list
            #print(count_minimum)

            # if there are two or more PEs satisfying minimum execution
            # then we should try to utilize all those PEs
            if (count_minimum > 1):

                # if there are tow or more PEs satisfying minimum execution
                # populate the IDs of those PEs into a list
                min_PE_IDs = [i for i, x in enumerate(exec_times) if x == min_of_exec_times]

                # then check whether those PEs are busy or idle
                PE_check_list = [True if not self.PEs[index].idle else False for i, index in enumerate(min_PE_IDs)]

                # assign tasks to the idle PEs instead of the ones that are currently busy
                if (True in PE_check_list) and (False in PE_check_list):
                    for PE in PE_check_list:
                        # if a PE is currently busy remove that PE from $min_PE_IDs list
                        # to schedule the task to a idle PE
                        if (PE == True):
                            min_PE_IDs.remove(min_PE_IDs[PE_check_list.index(PE)])

                # then compare the number of the assigned tasks to remaining PEs
                # and choose the one with the lowest number of assigned tasks
                assigned_tasks = [assigned[x] for i, x in enumerate(min_PE_IDs)]
                PE_ID_index = assigned_tasks.index(min(assigned_tasks))

                # finally, choose the best available PE for the task
                task.PE_ID = min_PE_IDs[PE_ID_index]

# =============================================================================
#                 # assign tasks to the idle PEs instead of the ones that are currently busy
#                 if (True in PE_check_list) and (False in PE_check_list):
#                     for PE in PE_check_list:
#                         # if a PE is currently busy remove that PE from $min_PE_IDs list
#                         # to schedule the task to a idle PE
#                         if (PE == True):
#                             min_PE_IDs.remove(min_PE_IDs[PE_check_list.index(PE)])
#
#
#                 # then compare the number of the assigned tasks to remaining PEs
#                 # and choose the one with the lowest number of assigned tasks
#                 assigned_tasks = [assigned[x] for i, x in enumerate(min_PE_IDs)]
#                 PE_ID_index = assigned_tasks.index(min(assigned_tasks))
# =============================================================================


                # finally, choose the best available PE for the task
                task.PE_ID = min_PE_IDs[PE_ID_index]

            else:
                task.PE_ID = exec_times.index(min_of_exec_times)
            # end of if count_minimum >1:
            # since one task is just assigned to a PE, increase the number by 1
            assigned[task.PE_ID] += 1

            if (task.PE_ID == -1):
                print ('[E] Time %s: %s can not be assigned to any resource, please check DASH.SoC.**.txt file'
                       % (self.env.now,task.name))
                print ('[E] or job_**.txt file')
                assert(task.PE_ID >= 0)
            else:
                if (common.INFO_SCH):
                    print ('[I] Time %s: The scheduler assigns the %s task to resource PE-%s: %s'
                           %(self.env.now, task.ID, task.PE_ID,
                             self.resource_matrix.list[task.PE_ID].type))
            # end of if task.PE_ID == -1:
        # end of for task in list_of_ready:
        # At the end of this loop, we should have a valid (non-negative ID)
        # that can run next_task

    # end of MET(list_of_ready)

    def EFT(self, list_of_ready):
        '''
        This scheduler compares the execution times of the current
        task for available resources and also considers if a resource has
        already a task running. it picks the resource which will give the
        earliest finish time for the task
        '''

        for task in list_of_ready:

            comparison = [np.inf]*len(self.PEs)                                     # Initialize the comparison vector
            comm_ready = [0]*len(self.PEs)                                          # A list to store the max communication times for each PE

            if (common.DEBUG_SCH):
                print ('[D] Time %s: The scheduler function is called with task %s'
                       %(self.env.now, task.ID))

            for i in range(len(self.resource_matrix.list)):
                if self.PEs[i].enabled:
                    # if the task is supported by the resource, retrieve the index of the task
                    if (task.name in self.resource_matrix.list[i].supported_functionalities):
                        ind = self.resource_matrix.list[i].supported_functionalities.index(task.name)


                        # $PE_comm_wait_times is a list to store the estimated communication time
                        # (or the remaining communication time) of all predecessors of a task for a PE
                        # As simulation forwards, relevant data is being sent after a task is completed
                        # based on the time instance, one should consider either whole communication
                        # time or the remaining communication time for scheduling
                        PE_comm_wait_times = []

                        # $PE_wait_time is a list to store the estimated wait times for a PE
                        # till that PE is available if the PE is currently running a task
                        PE_wait_time = []

                        job_ID = -1                                                     # Initialize the job ID

                        # Retrieve the job ID which the current task belongs to
                        for ii, job in enumerate(self.jobs.list):
                            if job.name == task.jobname:
                                job_ID = ii

                        for predecessor in self.jobs.list[job_ID].task_list[task.base_ID].predecessors:
                            # data required from the predecessor for $ready_task
                            c_vol = self.jobs.list[job_ID].comm_vol[predecessor, task.base_ID]

                            # retrieve the real ID  of the predecessor based on the job ID
                            real_predecessor_ID = predecessor + task.ID - task.base_ID

                            # Initialize following two variables which will be used if
                            # PE to PE communication is utilized
                            predecessor_PE_ID = -1
                            predecessor_finish_time = -1


                            for completed in common.TaskQueues.completed.list:
                                if completed.ID == real_predecessor_ID:
                                    predecessor_PE_ID = completed.PE_ID
                                    predecessor_finish_time = completed.finish_time
                                    #print(predecessor, predecessor_finish_time, predecessor_PE_ID)

                            if (common.PE_to_PE):
                                # Compute the PE to PE communication time
                                PE_to_PE_band = common.ResourceManager.comm_band[predecessor_PE_ID, i]
                                PE_to_PE_comm_time = int(c_vol/PE_to_PE_band)

                                PE_comm_wait_times.append(max((predecessor_finish_time + PE_to_PE_comm_time - self.env.now), 0))

                                if (common.DEBUG_SCH):
                                    print('[D] Time %s: Estimated communication time between PE %s to PE %s from task %s to task %s is %d'
                                          %(self.env.now, predecessor_PE_ID, i, real_predecessor_ID, task.ID, PE_comm_wait_times[-1]))

                            if (common.shared_memory):
                                # Compute the communication time considering the shared memory
                                # only consider memory to PE communication time
                                # since the task passed the 1st phase (PE to memory communication)
                                # and its status changed to ready

                                #PE_to_memory_band = common.ResourceManager.comm_band[predecessor_PE_ID, -1]
                                memory_to_PE_band = common.ResourceManager.comm_band[self.resource_matrix.list[-1].ID, i]
                                shared_memory_comm_time = int(c_vol/memory_to_PE_band)

                                PE_comm_wait_times.append(shared_memory_comm_time)
                                if (common.DEBUG_SCH):
                                    print('[D] Time %s: Estimated communication time between memory to PE %s from task %s to task %s is %d'
                                          %(self.env.now, i, real_predecessor_ID, task.ID, PE_comm_wait_times[-1]))

                            # $comm_ready contains the estimated communication time
                            # for the resource in consideration for scheduling
                            # maximum value is chosen since it represents the time required for all
                            # data becomes available for the resource.
                            comm_ready[i] = (max(PE_comm_wait_times))
                        # end of for for predecessor in self.jobs.list[job_ID].task_list[ind].predecessors:

                        # if a resource currently is executing a task, then the estimated remaining time
                        # for the task completion should be considered during scheduling
                        PE_wait_time.append(max((self.PEs[i].available_time - self.env.now), 0))


                        # update the comparison vector accordingly
                        comparison[i] = self.resource_matrix.list[i].performance[ind] + max(comm_ready[i], PE_wait_time[-1])
                    # end of if (task.name in...
            # end of for i in range(len(self.resource_matrix.list)):

            # after going over each resource, choose the one which gives the minimum result
            task.PE_ID = comparison.index(min(comparison))

            if task.PE_ID == -1:
                print ('[E] Time %s: %s can not be assigned to any resource, please check DASH.SoC.**.txt file'
                       % (self.env.now,task.ID))
                print ('[E] or job_**.txt file')
                assert(task.PE_ID >= 0)
            else:
                if (common.DEBUG_SCH):
                    print('[D] Time %s: Estimated execution times for each PE with task %s, respectively'
                              %(self.env.now, task.ID))
                    print('%12s'%(''), comparison)
                    print ('[D] Time %s: The scheduler assigns task %s to resource %s: %s'
                           %(self.env.now, task.ID, task.PE_ID, self.resource_matrix.list[task.PE_ID].type))

            # Finally, update the estimated available time of the resource to which
            # a task is just assigned
            self.PEs[task.PE_ID].available_time = self.env.now + comparison[task.PE_ID]

            # At the end of this loop, we should have a valid (non-negative ID)
            # that can run next_task

        # end of for task in list_of_ready:

    #end of EFT(list_of_ready)

    def STF(self, list_of_ready):
        '''
        This scheduler compares the execution times of the current
        task for available resources and returns the ID of the resource
        with minimum execution time for the current task. The only difference
        between STF and MET is the order in which the tasks are scheduled onto resources
        '''

        ready_list = copy.deepcopy(list_of_ready)

        # Iterate through the list of ready tasks until all of them are scheduled
        while (len(ready_list) > 0) :

            shortest_task_exec_time = np.inf
            shortest_task_pe_id     = -1

            for task in ready_list:

                min_time = np.inf                                                                   # Initialize the best performance found so far as a large number

                for i in range(len(self.resource_matrix.list)):
                    if self.PEs[i].enabled:
                        if (task.name in self.resource_matrix.list[i].supported_functionalities):
                            ind = self.resource_matrix.list[i].supported_functionalities.index(task.name)


                            if (self.resource_matrix.list[i].performance[ind] < min_time):              # Found resource with smaller execution time
                                min_time    = self.resource_matrix.list[i].performance[ind]                # Update the best time found so far
                                resource_id = self.resource_matrix.list[i].ID                           # Record the ID of the resource
                                #task.PE_ID = i                                                          # Record the corresponding resource

                #print('[INFO] Task - %d, Resource - %d, Time - %d' %(task.ID, resource_id, min_time))
                # Obtain the ID and resource for the shortest task in the current iteration
                if (min_time < shortest_task_exec_time) :
                    shortest_task_exec_time = min_time
                    shortest_task_pe_id     = resource_id
                    shortest_task           = task
                # end of if (min_time < shortest_task_exec_time)

            # end of for task in list_of_ready:
            # At the end of this loop, we should have the minimum execution time
            # of a task across all resources

            # Assign PE ID of the shortest task
            index = [i for i,x in enumerate(list_of_ready) if x.ID == shortest_task.ID][0]
            list_of_ready[index].PE_ID = shortest_task_pe_id
            shortest_task.PE_ID        = shortest_task_pe_id

            if (common.DEBUG_SCH):
                print ('[I] Time %s: The scheduler function found task %d to be shortest on resource %d with %.1f'
                       %(self.env.now, shortest_task.ID, shortest_task.PE_ID, shortest_task_exec_time))

            if list_of_ready[index].PE_ID == -1:
                print ('[E] Time %s: %s can not be assigned to any resource, please check DASH.SoC.**.txt file'
                       % (self.env.now,shortest_task.name))
                print ('[E] or job_**.txt file')
                assert(shortest_task.PE_ID >= 0)
            else:
                if (common.INFO_SCH):
                    print ('[I] Time %s: The scheduler assigns the %s task to resource PE-%s: %s'
                           %(self.env.now, shortest_task.ID, shortest_task.PE_ID,
                             self.resource_matrix.list[shortest_task.PE_ID].type))
            # end of if shortest_task.PE_ID == -1:

            # Remove the task which got a schedule successfully
            for i, task in enumerate(ready_list) :
                if task.ID == shortest_task.ID :
                    ready_list.remove(task)

        # end of for task in list_of_ready:
        # At the end of this loop, all ready tasks are assigned to the resources
        # on which the execution times are minimum. The tasks will execute
        # in the order of increasing execution times


    # end of STF(list_of_ready)

    def ETF_LB(self, list_of_ready):
        '''
        This scheduler compares the execution times of the current
        task for available resources and also considers if a resource has
        already a task running. it picks the resource which will give the
        earliest finish time for the task. Additionally, the task with the
        lowest earliest finish time  is scheduled first
        '''

        ready_list = copy.deepcopy(list_of_ready)

        task_counter = 0
        assigned = self.assigned

        # Iterate through the list of ready tasks until all of them are scheduled
        while len(ready_list) > 0:

            shortest_task_exec_time = np.inf
            shortest_task_pe_id = -1
            shortest_comparison = [np.inf] * len(self.PEs)

            for task in ready_list:

                comparison = [np.inf] * len(self.PEs)  # Initialize the comparison vector
                comm_ready = [0] * len(self.PEs)  # A list to store the max communication times for each PE

                if (common.DEBUG_SCH):
                    print('[D] Time %s: The scheduler function is called with task %s'
                          % (self.env.now, task.ID))

                for i in range(len(self.resource_matrix.list)):
                    if self.PEs[i].enabled:
                        # if the task is supported by the resource, retrieve the index of the task
                        if (task.name in self.resource_matrix.list[i].supported_functionalities):
                            ind = self.resource_matrix.list[i].supported_functionalities.index(task.name)

                            # $PE_comm_wait_times is a list to store the estimated communication time
                            # (or the remaining communication time) of all predecessors of a task for a PE
                            # As simulation forwards, relevant data is being sent after a task is completed
                            # based on the time instance, one should consider either whole communication
                            # time or the remaining communication time for scheduling
                            PE_comm_wait_times = []

                            # $PE_wait_time is a list to store the estimated wait times for a PE
                            # till that PE is available if the PE is currently running a task
                            PE_wait_time = []

                            job_ID = -1  # Initialize the job ID

                            # Retrieve the job ID which the current task belongs to
                            for ii, job in enumerate(self.jobs.list):
                                if job.name == task.jobname:
                                    job_ID = ii

                            for predecessor in self.jobs.list[job_ID].task_list[task.base_ID].predecessors:
                                # data required from the predecessor for $ready_task
                                c_vol = self.jobs.list[job_ID].comm_vol[predecessor, task.base_ID]

                                # retrieve the real ID  of the predecessor based on the job ID
                                real_predecessor_ID = predecessor + task.ID - task.base_ID

                                # Initialize following two variables which will be used if
                                # PE to PE communication is utilized
                                predecessor_PE_ID = -1
                                predecessor_finish_time = -1

                                for completed in common.TaskQueues.completed.list:
                                    if completed.ID == real_predecessor_ID:
                                        predecessor_PE_ID = completed.PE_ID
                                        predecessor_finish_time = completed.finish_time
                                        # print(predecessor, predecessor_finish_time, predecessor_PE_ID)
                                        break

                                if (common.PE_to_PE):
                                    # Compute the PE to PE communication time
                                    PE_to_PE_band = common.ResourceManager.comm_band[predecessor_PE_ID, i]
                                    PE_to_PE_comm_time = int(c_vol / PE_to_PE_band)

                                    PE_comm_wait_times.append(max((predecessor_finish_time + PE_to_PE_comm_time - self.env.now), 0))

                                    if (common.DEBUG_SCH):
                                        print('[D] Time %s: Estimated communication time between PE-%s to PE-%s from task %s to task %s is %d'
                                              % (self.env.now, predecessor_PE_ID, i, real_predecessor_ID, task.ID, PE_comm_wait_times[-1]))

                                if (common.shared_memory):
                                    # Compute the communication time considering the shared memory
                                    # only consider memory to PE communication time
                                    # since the task passed the 1st phase (PE to memory communication)
                                    # and its status changed to ready

                                    # PE_to_memory_band = common.ResourceManager.comm_band[predecessor_PE_ID, -1]
                                    memory_to_PE_band = common.ResourceManager.comm_band[self.resource_matrix.list[-1].ID, i]
                                    shared_memory_comm_time = int(c_vol / memory_to_PE_band)

                                    PE_comm_wait_times.append(shared_memory_comm_time)
                                    if (common.DEBUG_SCH):
                                        print('[D] Time %s: Estimated communication time between memory to PE-%s from task %s to task %s is %d'
                                              % (self.env.now, i, real_predecessor_ID, task.ID, PE_comm_wait_times[-1]))

                                # $comm_ready contains the estimated communication time
                                # for the resource in consideration for scheduling
                                # maximum value is chosen since it represents the time required for all
                                # data becomes available for the resource.
                                comm_ready[i] = max(PE_comm_wait_times)
                            # end of for for predecessor in self.jobs.list[job_ID].task_list[ind].predecessors:

                            # if a resource currently is executing a task, then the estimated remaining time
                            # for the task completion should be considered during scheduling
                            PE_wait_time.append(max((self.PEs[i].available_time - self.env.now), 0))

                            # update the comparison vector accordingly
                            comparison[i] = self.resource_matrix.list[i].performance[ind] * (1 + DTPM_power_models.compute_DVFS_performance_slowdown(common.ClusterManager.cluster_list[self.PEs[i].cluster_ID])) + max(comm_ready[i], PE_wait_time[-1])
                        # end of if (task.name in...
                # end of for i in range(len(self.resource_matrix.list)):

                if min(comparison) < shortest_task_exec_time:
                    resource_id = comparison.index(min(comparison))
                    shortest_task_exec_time = min(comparison)
                    #                    print(shortest_task_exec_time, comparison)
                    count_minimum = comparison.count(shortest_task_exec_time)  # also, record how many times $min_of_exec_times is seen in the list
                    # if there are two or more PEs satisfying minimum execution
                    # then we should try to utilize all those PEs
                    if (count_minimum > 1):
                        # if there are two or more PEs satisfying minimum execution
                        # populate the IDs of those PEs into a list
                        min_PE_IDs = [i for i, x in enumerate(comparison) if x == shortest_task_exec_time]
                        # then compare the number of the assigned tasks to remaining PEs
                        # and choose the one with the lowest number of assigned tasks
                        assigned_tasks = [assigned[x] for i, x in enumerate(min_PE_IDs)]
                        PE_ID_index = assigned_tasks.index(min(assigned_tasks))

                        # finally, choose the best available PE for the task
                        task.PE_ID = min_PE_IDs[PE_ID_index]
                    #   print(count_minimum, task.PE_ID)
                    else:
                        task.PE_ID = comparison.index(shortest_task_exec_time)
                    # end of if count_minimum >1:

                    # since one task is just assigned to a PE, increase the number by 1
                    assigned[task.PE_ID] += 1

                    resource_id = task.PE_ID
                    shortest_task_pe_id = resource_id
                    shortest_task = task
                    shortest_comparison = copy.deepcopy(comparison)

            # assign PE ID of the shortest task
            index = [i for i, x in enumerate(list_of_ready) if x.ID == shortest_task.ID][0]
            list_of_ready[index].PE_ID = shortest_task_pe_id
            list_of_ready[index], list_of_ready[task_counter] = list_of_ready[task_counter], list_of_ready[index]
            shortest_task.PE_ID = shortest_task_pe_id

            if shortest_task.PE_ID == -1:
                print('[E] Time %s: %s can not be assigned to any resource, please check DASH.SoC.**.txt file'
                      % (self.env.now, shortest_task.ID))
                print('[E] or job_**.txt file')
                assert (task.PE_ID >= 0)
            else:
                if (common.DEBUG_SCH):
                    print('[D] Time %s: Estimated execution times for each PE with task %s, respectively'
                          % (self.env.now, shortest_task.ID))
                    print('%12s' % (''), comparison)
                    print('[D] Time %s: The scheduler assigns task %s to PE-%s: %s'
                          % (self.env.now, shortest_task.ID, shortest_task.PE_ID, self.resource_matrix.list[shortest_task.PE_ID].name))

            # Finally, update the estimated available time of the resource to which
            # a task is just assigned
            index_min_available_time = self.PEs[shortest_task.PE_ID].available_time_list.index(min(self.PEs[shortest_task.PE_ID].available_time_list))
            self.PEs[shortest_task.PE_ID].available_time_list[index_min_available_time] = self.env.now + shortest_comparison[shortest_task.PE_ID]

            self.PEs[shortest_task.PE_ID].available_time = min(self.PEs[shortest_task.PE_ID].available_time_list)

            # Remove the task which got a schedule successfully
            for i, task in enumerate(ready_list):
                if task.ID == shortest_task.ID:
                    ready_list.remove(task)

            task_counter += 1
            # At the end of this loop, we should have a valid (non-negative ID)
            # that can run next_task

        # end of while len(ready_list) > 0 :

    # end of ETF( list_of_ready)

    def ETF(self, list_of_ready):
        '''
        This scheduler compares the execution times of the current
        task for available resources and also considers if a resource has
        already a task running. it picks the resource which will give the
        earliest finish time for the task. Additionally, the task with the
        lowest earliest finish time  is scheduled first
        '''
        ready_list = copy.deepcopy(list_of_ready)
    
        task_counter = 0
    
        # Iterate through the list of ready tasks until all of them are scheduled
        while len(ready_list) > 0 :
    
            shortest_task_exec_time = np.inf
            shortest_task_pe_id     = -1
            shortest_comparison     = [np.inf] * len(self.PEs)
    
            for task in ready_list:
                
                comparison = [np.inf]*len(self.PEs)                                     # Initialize the comparison vector 
                comm_ready = [0]*len(self.PEs)                                          # A list to store the max communication times for each PE
                
                if (common.DEBUG_SCH):
                    print ('[D] Time %s: The scheduler function is called with task %s'
                           %(self.env.now, task.ID))
                    
                for i in range(len(self.resource_matrix.list)):
                    # if the task is supported by the resource, retrieve the index of the task
                    if (task.name in self.resource_matrix.list[i].supported_functionalities):
                        ind = self.resource_matrix.list[i].supported_functionalities.index(task.name)
                        
                            
                        # $PE_comm_wait_times is a list to store the estimated communication time 
                        # (or the remaining communication time) of all predecessors of a task for a PE
                        # As simulation forwards, relevant data is being sent after a task is completed
                        # based on the time instance, one should consider either whole communication
                        # time or the remaining communication time for scheduling
                        PE_comm_wait_times = []
                        
                        # $PE_wait_time is a list to store the estimated wait times for a PE
                        # till that PE is available if the PE is currently running a task
                        PE_wait_time = []
                          
                        job_ID = -1                                                     # Initialize the job ID
                        
                        # Retrieve the job ID which the current task belongs to
                        for ii, job in enumerate(self.jobs.list):
                            if job.name == task.jobname:
                                job_ID = ii
                                
                        for predecessor in self.jobs.list[job_ID].task_list[task.base_ID].predecessors:
                            # data required from the predecessor for $ready_task
                            c_vol = self.jobs.list[job_ID].comm_vol[predecessor, task.base_ID]
                            
                            # retrieve the real ID  of the predecessor based on the job ID
                            real_predecessor_ID = predecessor + task.ID - task.base_ID
                            
                            # Initialize following two variables which will be used if 
                            # PE to PE communication is utilized
                            predecessor_PE_ID = -1
                            predecessor_finish_time = -1
                            
                            
                            for completed in common.TaskQueues.completed.list:
                                if (completed.ID == real_predecessor_ID):
                                    predecessor_PE_ID = completed.PE_ID
                                    predecessor_finish_time = completed.finish_time
                                    #print(predecessor, predecessor_finish_time, predecessor_PE_ID)
                                    
                            
                            if (common.PE_to_PE):
                                # Compute the PE to PE communication time
                                #PE_to_PE_band = self.resource_matrix.comm_band[predecessor_PE_ID, i]
                                PE_to_PE_band = common.ResourceManager.comm_band[predecessor_PE_ID, i]
                                PE_to_PE_comm_time = int(c_vol/PE_to_PE_band)
                                
                                PE_comm_wait_times.append(max((predecessor_finish_time + PE_to_PE_comm_time - self.env.now), 0))
                                
                                if (common.DEBUG_SCH):
                                    print('[D] Time %s: Estimated communication time between PE-%s to PE-%s from task %s to task %s is %d' 
                                          %(self.env.now, predecessor_PE_ID, i, real_predecessor_ID, task.ID, PE_comm_wait_times[-1]))
                                
                            if (common.shared_memory):
                                # Compute the communication time considering the shared memory
                                # only consider memory to PE communication time
                                # since the task passed the 1st phase (PE to memory communication)
                                # and its status changed to ready 
                                
                                #PE_to_memory_band = self.resource_matrix.comm_band[predecessor_PE_ID, -1]
                                memory_to_PE_band = common.ResourceManager.comm_band[self.resource_matrix.list[-1].ID, i]
                                shared_memory_comm_time = int(c_vol/memory_to_PE_band)
                                
                                PE_comm_wait_times.append(shared_memory_comm_time)
                                if (common.DEBUG_SCH):
                                    print('[D] Time %s: Estimated communication time between memory to PE-%s from task %s to task %s is %d' 
                                          %(self.env.now, i, real_predecessor_ID, task.ID, PE_comm_wait_times[-1]))
                            
                            # $comm_ready contains the estimated communication time 
                            # for the resource in consideration for scheduling
                            # maximum value is chosen since it represents the time required for all
                            # data becomes available for the resource. 
                            comm_ready[i] = (max(PE_comm_wait_times))
                            
                        # end of for for predecessor in self.jobs.list[job_ID].task_list[ind].predecessors: 
                        
                        # if a resource currently is executing a task, then the estimated remaining time
                        # for the task completion should be considered during scheduling
                        PE_wait_time.append(max((self.PEs[i].available_time - self.env.now), 0))
                        
                        # update the comparison vector accordingly    
                        comparison[i] = self.resource_matrix.list[i].performance[ind] + max(comm_ready[i], PE_wait_time[-1])
                        
    
                        # after going over each resource, choose the one which gives the minimum result
                        resource_id = comparison.index(min(comparison))
                        #print('aa',comparison)
                    # end of if (task.name in self.resource_matrix.list[i]...
                    
                # obtain the task ID, resource for the task with earliest finish time 
                # based on the computation 
                #print('bb',comparison)
                if min(comparison) < shortest_task_exec_time :
                    shortest_task_exec_time = min(comparison)
                    shortest_task_pe_id     = resource_id
                    shortest_task           = task
                    shortest_comparison     = comparison
    
                    
                # end of for i in range(len(self.resource_matrix.list)):
            # end of for task in ready_list:
            
            # assign PE ID of the shortest task 
            index = [i for i,x in enumerate(list_of_ready) if x.ID == shortest_task.ID][0]
            list_of_ready[index].PE_ID = shortest_task_pe_id
            list_of_ready[index], list_of_ready[task_counter] = list_of_ready[task_counter], list_of_ready[index]
            shortest_task.PE_ID        = shortest_task_pe_id
    
            if shortest_task.PE_ID == -1:
                print ('[E] Time %s: %s can not be assigned to any resource, please check DASH.SoC.**.txt file'
                       % (self.env.now, shortest_task.ID))
                print ('[E] or job_**.txt file')
                assert(task.PE_ID >= 0)           
            else: 
                if (common.DEBUG_SCH):
                    print('[D] Time %s: Estimated execution times for each PE with task %s, respectively' 
                              %(self.env.now, shortest_task.ID))
                    print('%12s'%(''), comparison)
                    print ('[D] Time %s: The scheduler assigns task %s to PE-%s: %s'
                           %(self.env.now, shortest_task.ID, shortest_task.PE_ID, 
                             self.resource_matrix.list[shortest_task.PE_ID].name))
            
            # Finally, update the estimated available time of the resource to which
            # a task is just assigned
            self.PEs[shortest_task.PE_ID].available_time = self.env.now + shortest_comparison[shortest_task.PE_ID]
            
            # Remove the task which got a schedule successfully
            for i, task in enumerate(ready_list) :
                if task.ID == shortest_task.ID :
                    ready_list.remove(task)
            
            
            task_counter += 1
            # At the end of this loop, we should have a valid (non-negative ID)
            # that can run next_task

        # end of while len(ready_list) > 0 :
    #end of ETF( list_of_ready)
    