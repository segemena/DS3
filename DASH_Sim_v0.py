'''
Description: This file is the main() function which should be run to get the stimulation results.
'''
import simpy
import configparser
import argparse
import matplotlib.pyplot as plt                                                 
import random                                                                  
import numpy as np
import sys
import os
import pandas as pd
import networkx as nx
from shutil import copyfile
import pickle
import csv


import job_generator                                                            # Dynamic job generation is handled by job_generator.py
import common                                                                   # The common parameters used in DASH-Sim are defined in common.py
import DASH_SoC_parser                                                          # The resource parameters used in DASH-Sim are obtained from
                                                                                # Resource initialization file(DASH.SoC.**.txt), parsed by DASH_SoC_parser.py
import job_parser                                                               # The parameters in a job used in DASH-Sim are obtained from
                                                                                # Job initialization file (job_**.txt), parsed by job_parser.py
import processing_element                                                       # Define the processing element class
import DASH_Sim_core                                                            # The core of the simulation engine (SimulationManager) is defined DASH_Sim_core.py
import scheduler                                                                # The DASH-Sim uses the scheduler defined in scheduler.py
import DASH_Sim_utils
import DTPM_utils

def run_simulator():
    readme_file = open("readme.txt", "r", encoding = "utf-8").read()                # The following lines are to create a readme/help file
    parser = argparse.ArgumentParser(
            formatter_class=argparse.RawDescriptionHelpFormatter,description=readme_file)
    args = parser.parse_args()                                                      # when user want to run the simulation on the command line
                                                                                    # type in command line python DASH_Sim_v0 -h

    plt.close('all')                                                                # close all existing plots before the new simulation
    if (common.CLEAN_TRACES):
        DASH_Sim_utils.clean_traces()

    #common.clear_screen()                                                           # Clear IPthon Console screen at the beginning of each simulation
    print('%59s'%('**** Welcome to DASH_Sim.v0 ****'))
    print('%65s'%('**** \xa9 2018 eLab ASU ALL RIGHTS RESERVED ****'))


    # Instantiate the ResourceManager object that contains all the resources
    # in the target DSSoC
    resource_matrix = common.ResourceManager()                                      # This line generates an empty resource matrix
    config = configparser.ConfigParser()
    config.read('config_file.ini')
    resource_file = config['DEFAULT']['resource_file']
    DASH_SoC_parser.resource_parse(resource_matrix, resource_file)    # Parse the input configuration file to populate the resource matrix

    for cluster in common.ClusterManager.cluster_list:
        if cluster.DVFS != 'none':
            if len(cluster.trip_freq) != len(common.trip_temperature) or len(cluster.trip_freq) != len(common.trip_hysteresis):
                print("[E] The trip points must match in size:")
                print("[E] Trip frequency (SoC file):      {} (Cluster {})".format(len(cluster.trip_freq), cluster.ID))
                print("[E] Trip temperature (config file): {}".format(len(common.trip_temperature)))
                print("[E] Trip hysteresis (config file):  {}".format(len(common.trip_hysteresis)))
                sys.exit()
            if len(cluster.power_profile) != len(cluster.PG_profile):
                print("[E] The power and PG profiles must match in size, please check the SoC file")
                print("[E] Cluster ID: {}, Num power points: {}, PG power points: {}".format(cluster.ID, len(cluster.power_profile), len(cluster.PG_profile)))
                sys.exit()

    # Instantiate the ApplicationManager object that contains all the jobs
    # in the target DSSoC
    jobs = common.ApplicationManager()                                              # This line generates an empty list for all jobs
    job_files_list = common.str_to_list(config['DEFAULT']['task_file'])
    for job_file in job_files_list:
        job_parser.job_parse(jobs, job_file)                                        # Parse the input job file to populate the job list

    # Initialize config variables
    common.snippet_start_time = common.warmup_period
    common.snippet_ID_inj = -1
    common.snippet_ID_exec = 0
    common.snippet_throttle = -1
    common.snippet_temp_list = []
    common.current_temperature_vector = [common.T_ambient,  # Indicate the current PE temperature for each hotspot
                                         common.T_ambient,
                                         common.T_ambient,
                                         common.T_ambient,
                                         common.T_ambient]
    common.B_model = []
    common.job_counter_list = [0]*len(common.current_job_list)
    common.throttling_state = -1
    if len(common.job_list) > 0:
        common.max_num_jobs = int(config['SIMULATION MODE']['jobs']) * len(common.job_list)
    else:
        common.max_num_jobs = int(config['SIMULATION MODE']['jobs'])

    scheduler_name = config['DEFAULT']['scheduler']                       # Assign the requested scheduler name to a variable

    dataset = pd.read_csv('ILP_data.csv')
    if (scheduler_name == 'ILP'):
        common.table = list(zip(dataset.iloc[:, 0], dataset.iloc[:, 1]))
    elif (scheduler_name == 'ILP_2'):
        common.table = list(zip(dataset.iloc[:, 2], dataset.iloc[:, 3]))
    elif (scheduler_name == 'ILP_3'):
        common.table = list(zip(dataset.iloc[:, 4], dataset.iloc[:, 5]))
    elif (scheduler_name == 'ILP_TX'):
        common.table = list(zip(dataset.iloc[:, 6], dataset.iloc[:, 7]))
    elif (scheduler_name == 'ILP_5TX_FPGA'):
        common.table = list(zip(dataset.iloc[:, 12], dataset.iloc[:, 13]))
    elif (scheduler_name == 'ILP_5RX_FPGA'):
        common.table = list(zip(dataset.iloc[:, 14], dataset.iloc[:, 15]))
    elif (scheduler_name == 'ILP_5X_FPGA'):
        common.table = list(zip(dataset.iloc[:, 14], dataset.iloc[:, 15]))
        common.table_2 = list(zip(dataset.iloc[:, 12], dataset.iloc[:, 13]))
    elif (scheduler_name == 'ILP_5TX_BAL'):
        common.table = list(zip(dataset.iloc[:, 20], dataset.iloc[:, 21]))
    elif (scheduler_name == 'ILP_5RX_BAL'):
        common.table = list(zip(dataset.iloc[:, 22], dataset.iloc[:, 23]))
    elif (scheduler_name == 'ILP_5X_BAL'):
        common.table = list(zip(dataset.iloc[:, 22], dataset.iloc[:, 23]))
        common.table_2 = list(zip(dataset.iloc[:, 20], dataset.iloc[:, 21]))
    elif (scheduler_name == 'ILP_5TX_BIG'):
        common.table = list(zip(dataset.iloc[:, 28], dataset.iloc[:, 29]))
    elif (scheduler_name == 'ILP_5RX_BIG'):
        common.table = list(zip(dataset.iloc[:, 30], dataset.iloc[:, 31]))
    elif (scheduler_name == 'ILP_5X_BIG'):
        common.table = list(zip(dataset.iloc[:, 30], dataset.iloc[:, 31]))
        common.table_2 = list(zip(dataset.iloc[:, 28], dataset.iloc[:, 29]))
    elif (scheduler_name == 'ILP_MULTI'):
        common.table = list(zip(dataset.iloc[:,32],dataset.iloc[:,33]))
        common.table_2 = list(zip(dataset.iloc[:,34],dataset.iloc[:,35]))
        common.table_3 = list(zip(dataset.iloc[:,22],dataset.iloc[:,23]))
        common.table_4 =  list(zip(dataset.iloc[:,20],dataset.iloc[:,21]))


    # Check whether the resource_matrix and task list are initialized correctly
    if (common.DEBUG_CONFIG):
        print('\n[D] Starting DASH-Sim in DEBUG Mode ...')
        print("[D] Read the resource_matrix and write its contents")
        num_of_resources = len(resource_matrix.list)
        num_of_jobs = len(jobs.list)

        for i in range(num_of_resources):
            curr_resource = resource_matrix.list[i]
            print("[D] Adding a new resource: Type: %s, Name: %s, ID: %d, Capacity: %d" 
                  %(curr_resource.type, curr_resource.name, int(curr_resource.ID), int(curr_resource.capacity))) 
            print("[D] It supports the following %d functionalities"
                  %(curr_resource.num_of_functionalities))
    
            for ii in range(curr_resource.num_of_functionalities):
                print ('%4s'%('')+curr_resource.supported_functionalities[ii],
                       curr_resource.performance[ii])
        print('\nCommunication Bandwidth matrix between Resources is\n', resource_matrix.comm_band)
            # end for ii
        # end for i

        print("\n[D] Read each application and write its components")
        for ii in range(num_of_jobs):
            curr_job = jobs.list[ii]
            num_of_tasks = len(curr_job.task_list)
            print('\n%10s'%('')+'Now reading application %s' %(ii+1))
            print('Application name: %s, Number of tasks in the application: %s'%(curr_job.name, num_of_tasks))
            
            for task in jobs.list[ii].task_list:
                print("Task name: %s, Task ID: %s, Task Predecessor(s) %s"
                      %(task.name, task.ID, task.predecessors))
            print('Communication Volume matrix between Tasks is\n', jobs.list[ii].comm_vol)
        print(' ')
        # end for ii

        print('[D] Read the scheduler name')
        print('Scheduler name: %s' % scheduler_name)
        print('')
    # end if (DEBUG)


    if (common.simulation_mode == 'validation'):
        '''
        Start the simulation in VALIDATION MODE
        '''
        # Provide the value of the seed for the random variables
        random.seed(common.seed)  # user can regenerate the same results by assigning a value to $random_seed in configuration file

        # Instantiate the PerfStatics object that contains all the performance statics
        common.results = common.PerfStatics()

        # Set up the Python Simulation (simpy) environment
        env = simpy.Environment(initial_time=0)
        sim_done = env.event()

        # Construct the processing elements in the target DSSoC
        DASH_resources = []

        for i,resource in enumerate(resource_matrix.list):
            # Define the PEs (resources) in simpy environment
            new_PE = processing_element.PE(env, resource.type, resource.name,
                                           resource.ID, resource.cluster_ID, resource.capacity) # Generate a new PE with this generic process
            DASH_resources.append(new_PE)
        # end for

        # Construct the scheduler
        DASH_scheduler = scheduler.Scheduler(env, resource_matrix, scheduler_name,
                                             DASH_resources, jobs)

        # Check whether PEs are initialized correctly
        if (common.DEBUG_CONFIG):
            print('[D] There are %d simpy resources.' % len(DASH_resources))
            print('[D] Completed building and debugging the DASH model.\n')


        # Start the simulation engine
        print('[I] Starting the simulation under VALIDATION MODE...')

        job_gen = job_generator.JobGenerator(env, resource_matrix, jobs, DASH_scheduler, DASH_resources)

        sim_core = DASH_Sim_core.SimulationManager(env, sim_done, job_gen, DASH_scheduler, DASH_resources,
                                                  jobs, resource_matrix)


        env.run(until = common.simulation_length)

        print('[I] Completed Simulation ...')
        for job in common.Validation.generated_jobs:
            if job in common.Validation.completed_jobs:
                continue
            else:
              print('[E] Not all generated jobs are completed')
              sys.exit()
        print('[I] And, simulation is validated, successfully.')
        print('\nSimulation Parameters')
        print("-"*55)
        print("%-30s : %-20s"%("SoC config file",resource_file))
        print("%-30s : %-20s"%("Job config files",' '.join(job_files_list)))
        print("%-30s : %-20s"%("Scheduler",scheduler_name))
        print("%-30s : %-20s"%("Clock period(us)",common.simulation_clk))
        print("%-30s : %-20d"%("Simulation length(us)",common.simulation_length))
        print('\nSimulation Statitics')
        print("-"*55)
        print("%-30s : %-20s" % ("Execution time(us)", round(common.results.execution_time, 2)))
        print("%-30s : %-20s" % ("Total energy consumption(uJ)",
                                 round(common.results.energy_consumption, 2)))
        print("%-30s : %-20s" % ("EDP",
                                 round(common.results.execution_time * common.results.energy_consumption, 2)))
        DASH_Sim_utils.trace_system()
        # End of simpy simulation

        plot_gantt_chart = True
        if plot_gantt_chart:
            # Creating a text based Gantt chart to visualize the simulation
            job_ID = -1
            ilen = len(resource_matrix.list) - 1  # since the last PE is the memory
            pos = np.arange(0.5, ilen * 0.5 + 0.5, 0.5)
            fig = plt.figure(figsize=(10, 6))
            # fig = plt.figure(figsize=(10,3.5))
            ax = fig.add_subplot(111)
            color_choices = ['red', 'blue', 'green', 'cyan', 'magenta']
            for i in range(len(resource_matrix.list)):
                for ii, task in enumerate(common.TaskQueues.completed.list):
                    if (i == task.PE_ID):
                        end_time = task.finish_time
                        start_time = task.start_time
                        ax.barh((i * 0.5) + 0.5, end_time - start_time, left=start_time,
                                height=0.3, align='center', edgecolor='black', color='white', alpha=0.95)
                        # Retrieve the job ID which the current task belongs to
                        for iii, job in enumerate(jobs.list):
                            if (job.name == task.jobname):
                                job_ID = iii
                        ax.text(0.5 * (start_time + end_time - len(str(task.ID)) - 0.25), (i * 0.5) + 0.5 - 0.03125,
                                task.ID, color=color_choices[(task.jobID) % 5], fontweight='bold', fontsize=18, alpha=0.75)
            # color_choices[(task.jobID)% 5]
            # color_choices[job_ID]
            # locsy, labelsy = plt.yticks(pos, ['P0','P1','P2']) #
            locsy, labelsy = plt.yticks(pos, range(len(resource_matrix.list)))
            plt.ylabel('Processing Element', fontsize=18)
            plt.xlabel('Time', fontsize=18)
            plt.tick_params(labelsize=16)
            # plt.title('DASH-Sim - %s' %(scheduler_name), fontsize =18)
            plt.setp(labelsy, fontsize=18)
            ax.set_ylim(bottom=-0.1, top=ilen * 0.5 + 0.5)
            ax.set_xlim(left=-5)
            ax.grid(color='g', linestyle=':', alpha=0.5)
            plt.show()
    # end of if (common.simulation_mode == 'validation'):

    if (common.simulation_mode == 'performance'):
        '''
        Start the simulation in PERFORMANCE MODE
        '''
        ave_job_injection_rate = [0]*len(common.scale_values_list)                  # The list contains the mean of the lambda injection value corresponding each lambda value 
                                                                                    # based on the number of jobs put into ready queue list
        ave_job_execution_time = [0]*len(common.scale_values_list)                  # The list contains the mean job duration for each lambda value
        ave_job_completion_rate = [0]*len(common.scale_values_list)                 # The list contains the mean job completion rate for each lambda value
        lamd_values_list = [0]*len(common.scale_values_list)                        # The list of lambda values which will determine the job arrival rate

        for (ind,scale) in enumerate(common.scale_values_list):
            common.scale = scale  # Assign each value in $scale_values_list to common.scale
            lamd_values_list[ind] = 1 / scale

            if (common.INFO_JOB):
                print('%10s'%('')+'[I] Simulation starts for scale value %s' %(scale))

            # Iterate over a fixed number of iterations
            job_execution_time  = 0.0
            job_injection_rate  = 0.0
            job_completion_rate = 0.0

            for iteration in range(common.num_of_iterations):                       # Repeat the simulation for a given number of numbers for each lambda value
                random.seed(iteration)                                              # user can regenerate the same results by assigning a value to $random_seed in configuration file
                #np.random.seed(iteration)

                # Instantiate the PerfStatics object that contains all the performance statics
                common.results = common.PerfStatics()
                common.computation_dict = {}
                common.current_dag = nx.DiGraph()

                # Set up the Python Simulation (simpy) environment
                env = simpy.Environment(initial_time=0)
                sim_done = env.event()

                # Construct the processing elements in the target DSSoC
                DASH_resources = []
                for i,resource in enumerate(resource_matrix.list):
                    # Define the PEs (resources) in simpy environment
                    new_PE = processing_element.PE(env, resource.type, resource.name,
                                                   resource.ID, resource.cluster_ID, resource.capacity) # Generate a new PE with this generic process
                    DASH_resources.append(new_PE)
                # end for

                # Construct the scheduler
                DASH_scheduler = scheduler.Scheduler(env, resource_matrix, scheduler_name,
                                                     DASH_resources, jobs)

                if (common.INFO_JOB):
                    print('[I] Starting iteration: %d' %(iteration+1))

                job_gen = job_generator.JobGenerator(env, resource_matrix, jobs, DASH_scheduler, DASH_resources)

                sim_core = DASH_Sim_core.SimulationManager(env, sim_done, job_gen, DASH_scheduler, DASH_resources,
                                                           jobs, resource_matrix)

                if common.sim_early_stop is False:
                    env.run(until = common.simulation_length)
                else:
                    env.run(until = sim_done)

                # Now, the simulation has completed
                # Next, process the results
                if (common.INFO_JOB):
                    print('[I] Completed iteration: %d' %(iteration+1))
                    print('[I] Number of injected jobs: %d' %(common.results.injected_jobs))
                    print('[I] Number of completed jobs: %d' %(common.results.completed_jobs))
                    try:
                        print('[I] Ave latency: %f'
                        %(common.results.cumulative_exe_time/common.results.completed_jobs))
                    except ZeroDivisionError:
                        print('[I] No completed jobs')
                    print("[I] %-30s : %-20s" % ("Execution time(us)", round(common.results.execution_time - common.warmup_period, 2)))
                    print("[I] %-30s : %-20s" % ("Cumulative Execution time(us)", round(common.results.cumulative_exe_time, 2)))
                    print("[I] %-30s : %-20s" % ("Total energy consumption(J)",
                                                 round(common.results.cumulative_energy_consumption, 6)))
                    print("[I] %-30s : %-20s" % ("EDP",
                                                 round((common.results.execution_time - common.warmup_period) * common.results.cumulative_energy_consumption, 2)))
                    print("[I] %-30s : %-20s" % ("Cumulative EDP",
                                                 round(common.results.cumulative_exe_time * common.results.cumulative_energy_consumption, 2)))
                    result_exec_time = common.results.execution_time - common.warmup_period
                    result_energy_cons = common.results.cumulative_energy_consumption
                    result_EDP = result_exec_time * result_energy_cons
                    header_list = ['Execution time(us)', 'Total energy consumption(J)', 'EDP']
                    result_list = [result_exec_time, result_energy_cons, result_EDP]
                    DASH_Sim_utils.trace_system()
                    if not common.generate_complete_trace:
                        if not os.path.exists(common.RESULTS):
                            with open(common.RESULTS, 'w', newline='') as csvfile:
                                result_file = csv.writer(csvfile, delimiter=',')
                                result_file.writerow(header_list)
                        with open(common.RESULTS, 'a', newline='') as csvfile:
                            result_file = csv.writer(csvfile, delimiter=',')
                            result_file.writerow(result_list)

                try:
                    job_execution_time += common.results.cumulative_exe_time / common.results.completed_jobs                    # find the mean job duration value for this iteration
                except ZeroDivisionError:
                    job_execution_time += 0
                job_injection_rate += common.results.injected_jobs / (common.simulation_length - common.warmup_period)      # find the average injection rate
                job_completion_rate += common.results.completed_jobs / (common.simulation_length - common.warmup_period)    # find the average injection rate
            # end of for iteration in range(common.num_of_iterations):

            ave_job_execution_time[ind] = job_execution_time / common.num_of_iterations
            ave_job_injection_rate[ind] = job_injection_rate / common.num_of_iterations
            ave_job_completion_rate[ind] = job_completion_rate / common.num_of_iterations

            if (common.INFO_JOB):
                print('[I] Completed all %d iterations for scale = %d,'
                      %(common.num_of_iterations,scale), end='')
                print(' injection rate:%f, completion rate:%f, ave_execution_time:%f'
                      % (ave_job_injection_rate[ind], ave_job_completion_rate[ind], ave_job_execution_time[ind]))
        # end of for (ind,scale) in enumerate(common.scale_values_list):



        # Plot or save important results when needed
    # =============================================================================
    #     c = 'y'
    #     plt.figure(1)
    #     plt.plot(common.results.sampling_rate_list,common.results.job_counter_list, marker='x', color=c)
    #     plt.xlabel('time')
    #     plt.ylabel('')
    #     plt.grid(True)
    #     plt.show()
    #
    #     plt.figure(2)
    #     plt.plot(ave_job_injection_rate, ave_job_execution_time, marker='s', color=c)
    #     plt.xlabel('Job Injection Rate (job/ms)', fontsize =16)
    #     plt.ylabel('Average Job Execution Time ($\mu$s)', fontsize=16)
    #     plt.tick_params(labelsize=12)
    #     #plt.xticks([0,0.005,0.01,0.015,0.02], [0,5,10,15,20])
    #     #plt.xticks([0.002,0.004,0.006,0.008,0.01,0.012], [2,4,6,8,10,12])
    #     plt.grid(True)
    #
    #     plt.figure(3)
    #     plt.plot(lamd_values_list, ave_job_execution_time, marker='s', color=c)
    #     plt.xlabel('lamd_values_list')
    #     plt.ylabel('Average Job Execution Time ($\mu$s)')
    #     plt.grid(True)
    #
    #     plt.figure(4)
    #     plt.plot(ave_job_injection_rate,ave_job_completion_rate , marker='x', color=c)
    #     plt.xlabel('ave_job_injection_rate')
    #     plt.ylabel('ave_job_completion_rate')
    #     plt.grid(True)
    #     plt.show()
    # =============================================================================

        fieldnames = ['injection_rate', 'execution']
        rows = zip(ave_job_injection_rate,ave_job_execution_time)
        with open('output.csv', 'w') as f:
            writer = csv.DictWriter(f, lineterminator='\n', fieldnames = fieldnames)
            writer.writeheader()
            writer = csv.writer(f, lineterminator='\n', )
            for row in rows:
                writer.writerow(row)

if __name__ == '__main__':
    run_simulator()
