'''
Description: This file contains the code for the job generator
'''
import random 
import common
import copy
import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
import sys
import simpy

import numpy as np
import os
import DASH_Sim_utils
           
class JobGenerator:
    '''
    Define the JobGenerator class to handle dynamic job generation
    '''
    def __init__(self, env, resource_matrix, jobs, scheduler, PE_list):
        '''
        env: Pointer to the current simulation environment
        resource_matrix: The data structure that defines power/performance
            characteristics of the PEs for each supported task
        jobs: The list of all jobs given to DASH-Sim
        scheduler: Pointer to the DASH_scheduler
        PE_list: The PEs available in the current SoCs
        '''
        self.env = env
        self.resource_matrix = resource_matrix
        self.jobs = jobs
        self.scheduler = scheduler
        self.PEs = PE_list
        
        
        # Initially none of the tasks are outstanding
        common.TaskQueues.outstanding = common.TaskManager()                    # List of *all* tasks waiting to be processed

        # Initially none of the tasks are completed
        common.TaskQueues.completed = common.TaskManager()                      # List of completed tasks

        # Initially none of the tasks are running on the PEs
        common.TaskQueues.running = common.TaskManager()                        # List of currently running tasks
        
        # Initially none of the tasks are completed
        common.TaskQueues.ready = common.TaskManager()                          # List of tasks that are ready for processing
        
        # Initially none of the tasks are in wait ready queue
        common.TaskQueues.wait_ready = common.TaskManager()                     # List of tasks that are waiting for being ready for processing
        
        # Initially none of the tasks are executable
        common.TaskQueues.executable = common.TaskManager()                     # List of tasks that are ready for execution
        
        self.generate_job = True                                                # Initially $generate_job is True so that as soon as run function is called
                                                                                #   it will start generating jobs
        self.max_num_jobs = common.max_num_jobs                                 # Number of jobs to be created
        self.job = []                                                           # List of all jobs that are generated
        self.offset = 0                                                         # This value will be used to assign correct ID numbers for incoming tasks

        self.action = env.process(self.run())                                   # Starts the run() method as a SimPy process

    def run(self):
        i = 0  # Initialize the iteration variable
        num_jobs = 0
        np.random.seed(0)

        if len(DASH_Sim_utils.get_current_job_list()) != len(self.jobs.list) and DASH_Sim_utils.get_current_job_list() != []:
            print('[E] Time %s: Job_list and task_file configs have different lengths, please check DASH.SoC.**.txt file'
                  % (self.env.now))
            sys.exit()

        while (self.generate_job):  # Continue generating jobs till #generate_job is False

            if (common.results.job_counter >= common.max_jobs_in_parallel or (common.job_list != [] and common.snippet_ID_inj == common.snippet_ID_exec)):
                # yield self.env.timeout(self.wait_time)                          # new job addition will be after this wait time
                try:
                    yield self.env.timeout(common.simulation_clk)
                except simpy.exceptions.Interrupt:
                    pass
            else:
                # selection = np.random.choice([0, 1], 1, p=[0.34, 0.66])
                # self.job.append(copy.deepcopy(self.jobs.list[int(selection)]))
                # print('selected job id is',selection)

                valid_jobs = []
                common.current_job_list = DASH_Sim_utils.get_current_job_list()
                for index, job_counter in enumerate(common.job_counter_list):
                    if job_counter < common.current_job_list[index]:
                        valid_jobs.append(index)
                
                if valid_jobs != []:
                    selection = np.random.choice(valid_jobs)
                else:
                    selection = 0

                self.job.append(copy.deepcopy(self.jobs.list[selection]))               # Create each job as a deep copy of the job chosen from job list
                common.results.job_counter += 1

                if (common.DEBUG_JOB):
                    print('[D] Time %d: Job generator added job %d' % (self.env.now, i + 1))

                if (common.simulation_mode == 'validation'):
                    common.Validation.generated_jobs.append(i)

                for ii in range(len(self.job[i].task_list)):                    # Go over each task in the job
                    next_task = self.job[i].task_list[ii]
                    next_task.jobID = i                                         # assign job id to the next task
                    next_task.base_ID = ii                                      # also record the original ID of the next task
                    next_task.ID = ii + self.offset                             # and change the ID of the task accordingly

                    if next_task.head:
                        next_task.job_start = self.env.now                      # When a new job is generated, its execution is also started

                    for k in range(len(next_task.predecessors)):
                        next_task.predecessors[k] += self.offset                # also change the predecessors of the newly added task, accordingly

                    if len(next_task.predecessors) > 0:
                        common.TaskQueues.outstanding.list.append(next_task)    # Add the task to the outstanding queue since it has predecessors
                        # Next, print debug messages
                        if (common.DEBUG_SIM):
                            print('[D] Time %d: Adding task %d to the outstanding queue,'
                                  % (self.env.now, next_task.ID), end='')
                            print(' task %d has predecessors:'
                                  % (next_task.ID), next_task.predecessors)
                    else:
                        common.TaskQueues.ready.list.append(next_task)          # Add the task to the ready queue since it has no predecessors
                        if (common.DEBUG_SIM):
                            print('[D] Time %s: Task %s is pushed to the ready queue list'
                                  % (self.env.now, next_task.ID), end='')
                            print(', the ready queue list has %s tasks'
                                  % (len(common.TaskQueues.ready.list)))
                self.offset += len(self.job[i].task_list)
                # end of for ii in range(len(self.job[i].list))

                if self.scheduler.name == 'ILP_CPLEX':
                    self.get_ILP()

                # Update the job ID
                i += 1
                if self.env.now > common.warmup_period or common.simulation_mode == 'validation':
                    num_jobs += 1
                    if common.job_counter_list != []:
                        common.job_counter_list[selection] += 1
                        count_complete_jobs = 0
                        # Check if all jobs for the current snippet were injected
                        common.current_job_list = DASH_Sim_utils.get_current_job_list()
                        for index, job_counter in enumerate(common.job_counter_list):
                            if job_counter == common.current_job_list[index]:
                                count_complete_jobs += 1
                        if count_complete_jobs == len(common.job_counter_list) and num_jobs < common.max_num_jobs:
                            # Get the next snippet's job list
                            common.snippet_ID_inj += 1
                            np.random.seed(0)
                            common.job_counter_list = [0]*len(common.current_job_list)

                if (common.simulation_mode == 'validation' or common.sim_early_stop):
                    if (num_jobs >= self.max_num_jobs):                                 # check if max number of jobs, given in config file, are created
                        self.generate_job = False                                       # if yes, no more jobs will be added to simulation
                
                #a_list = [82, 16, 480, 497, 55, 398, 212, 241, 748, 336]
                
                # print ('lambda value is: %.2f' %(1/common.scale))
                if common.fixed_injection_rate:
                    self.wait_time = common.scale
                else:
                    self.wait_time = int(random.expovariate(1 / common.scale))      # assign an exponentially distributed random variable to $wait_time
                try:
                    yield self.env.timeout(self.wait_time)                          # new job addition will be after this wait time
                    #yield self.env.timeout(a_list[i%len(a_list)])
                except simpy.exceptions.Interrupt:
                    pass
            # end of while (self.generate_job):