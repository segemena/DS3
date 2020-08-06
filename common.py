'''!
@brief This file contains all the common parameters used in DASH_Sim.
'''
import configparser
import sys
import os
import ast
import networkx as nx
import pickle
import numpy as np

#time_at_sim_termination = -1

def str_to_list(x):
    # function to return a list based on a formatted string
    result = []
    if '[' in x:
        result = ast.literal_eval(x)
    else:
        for part in x.split(','):
            if ('-' in part):
                a, b, c = part.split('-')
                a, b, c = int(a), int(b), int(c)
                result.extend(range(a, b, c))
            elif ('txt' in part):
                result.append(part)
            else:
                a = int(part)
                result.append(a)
    return result
# end of def str_to_list(x)


config = configparser.ConfigParser()
config.read('config_file.ini')

# Assign debug variable to be true to check the flow of the program
DEBUG_CONFIG    = config.getboolean('DEBUG', 'debug_config')                    # Debug variable to check the DASH-Sim configuration related debug messages
DEBUG_SIM       = config.getboolean('DEBUG', 'debug_sim')                       # Debug variable to check the Simulation core related debug messages
DEBUG_JOB       = config.getboolean('DEBUG', 'debug_job')                       # Debug variable to check the Job generator related debug messages
DEBUG_SCH       = config.getboolean('DEBUG', 'debug_sch')                       # Debug variable to check the Scheduler related debug messages

# Assign info variable to be true to get the information about the flow of the program
INFO_SIM        = config.getboolean('INFO', 'info_sim')                         # Info variable to check the Simulation core related info messages
INFO_JOB        = config.getboolean('INFO', 'info_job')                         # Info variable to check the job generator related info messages
INFO_SCH        = config.getboolean('INFO', 'info_sch')                         # Info variable to check the Scheduler related info messages

## DEFAULT
scheduler               = config['DEFAULT']['scheduler']                        # Assign scheduler name variable
seed                    = int(config['DEFAULT']['random_seed'])                 # Specify a seed value for the random number generator
simulation_clk          = int(config['DEFAULT']['clock'])                       # The core simulation engine tick with simulation_clk
simulation_length       = int(config['DEFAULT']['simulation_length'])           # The length of the simulation (in us)
standard_deviation      = float(config['DEFAULT']['standard_deviation'])        # Standard deviation for randomization of execution time
job_probabilities       = str_to_list(config['DEFAULT']['job_probabilities'])   # Probability of each app for being selected as the new job
inject_jobs_ASAP        = config.getboolean('DEFAULT', 'inject_jobs_asap')
fixed_injection_rate    = config.getboolean('DEFAULT', 'fixed_injection_rate')
max_jobs_in_parallel    = int(config['DEFAULT']['max_jobs_in_parallel'])

job_list = str_to_list(config['DEFAULT']['job_list'])                           # List containing the number of jobs that should be executed for each application
if len(job_list) > 0:
    current_job_list = job_list[0]
    snippet_size = sum(job_list[0])
    max_num_jobs = snippet_size*len(job_list)
    inject_fixed_num_jobs = True
else:
    current_job_list = []
    max_num_jobs = int(config['DEFAULT']['max_jobs'])
    snippet_size = max_num_jobs
    inject_fixed_num_jobs = config.getboolean('DEFAULT', 'inject_fixed_num_jobs')
job_counter_list = [0] * len(current_job_list)                                  # List to count the number of injected jobs for each application

## TRACE
# Assign trace variable to be true to save traces from the execution
CLEAN_TRACES                        = config.getboolean('TRACE', 'clean_traces')              # Flag used to clear previous traces
TRACE_TASKS                         = config.getboolean('TRACE', 'trace_tasks')               # Trace information from each task
TRACE_SYSTEM                        = config.getboolean('TRACE', 'trace_system')              # Trace information from the whole system
TRACE_FREQUENCY                     = config.getboolean('TRACE', 'trace_frequency')           # Trace frequency variation information
TRACE_PES                           = config.getboolean('TRACE', 'trace_PEs')                 # Trace information from each PE
TRACE_IL_PREDICTIONS                = config.getboolean('TRACE', 'trace_IL_predictions')      # Trace the predictions of the IL policy
TRACE_TEMPERATURE                   = config.getboolean('TRACE', 'trace_temperature')         # Trace temperature information
TRACE_LOAD                          = config.getboolean('TRACE', 'trace_load')                # Trace system load information
CREATE_DATASET_DTPM                 = config.getboolean('TRACE', 'create_dataset_DTPM')       # Create dataset for the ML algorithm
TRACE_FILE_TASKS                    = config['TRACE']['trace_file_tasks']                     # Trace file name for the task trace
TRACE_FILE_SYSTEM                   = config['TRACE']['trace_file_system']                    # Trace file name for the system trace
TRACE_FILE_FREQUENCY                = config['TRACE']['trace_file_frequency']                 # Trace file name for the frequency trace
TRACE_FILE_PES                      = config['TRACE']['trace_file_PEs']                       # Trace file name for the PE trace
TRACE_FILE_TEMPERATURE              = config['TRACE']['trace_file_temperature']               # Trace file name for the temperature trace
TRACE_FILE_TEMPERATURE_WORKLOAD     = config['TRACE']['trace_file_temperature_workload']      # Trace file name for the temperature trace (workload)
TRACE_FILE_LOAD                     = config['TRACE']['trace_file_load']                      # Trace file name for the load trace
RESULTS                             = config['TRACE']['results']                              # Trace file name for the results of the simulation, including exec time, energy, etc.

## POWER MANAGEMENT
sampling_rate                   = int(config['POWER MANAGEMENT']['sampling_rate'])                      # Specify the sampling rate for the DVFS mechanism
sampling_rate_temperature       = int(config['POWER MANAGEMENT']['sampling_rate_temperature'])          # Specify the sampling rate for the temperature update
util_high_threshold             = float(config['POWER MANAGEMENT']['util_high_threshold'])              # Specify the high threshold (ondemand mode)
util_low_threshold              = float(config['POWER MANAGEMENT']['util_low_threshold'])               # Specify the low threshold  (ondemand mode)
enable_throttling               = config.getboolean('POWER MANAGEMENT', 'enable_throttling')            # Flag to enable the thermal throttling
enable_DTPM_throttling          = config.getboolean('POWER MANAGEMENT', 'enable_DTPM_throttling')       # Flag to enable the thermal throttling for the custom DTPM policies
C1                              = float(config['POWER MANAGEMENT']['C1'])                               # Coefficient for the leakage model
C2                              = int(config['POWER MANAGEMENT']['C2'])                                 # Coefficient for the leakage model
Igate                           = float(config['POWER MANAGEMENT']['Igate'])                            # Coefficient for the leakage model
T_ambient                       = float(config['POWER MANAGEMENT']['T_ambient'])                        # Ambient temperature

trip_temperature                = str_to_list(config['POWER MANAGEMENT']['trip_temperature'])           # List of temperature trip points
trip_hysteresis                 = str_to_list(config['POWER MANAGEMENT']['trip_hysteresis'])            # List of hysteresis trip points
DTPM_trip_temperature           = str_to_list(config['POWER MANAGEMENT']['DTPM_trip_temperature'])      # List of temperature trip points for the custom DTPM policies

## SIMULATION MODE
simulation_mode = config['SIMULATION MODE']['simulation_mode']                  # Defines under which mode, the simulation will be run

if simulation_mode not in ('validation','performance') :
    print('[E] Please choose a valid simulation mode')
    print(simulation_mode)
    sys.exit()

# variables used under performance mode
warmup_period       = int(config['SIMULATION MODE']['warmup_period'])                   # is the time period till which no result will be recorded
num_of_iterations   = int(config['SIMULATION MODE']['num_of_iterations'])               # The number of iteration at each job injection rate
config_scale_values = config['SIMULATION MODE']['scale_values']
scale_values_list = str_to_list(config_scale_values)                                    # List of scale values which will determine the job arrival rate under performance mode

# variables used under validation mode
scale = int(config['SIMULATION MODE']['scale'])                                 # The variable used to adjust the mean value of the job inter-arrival time
if (simulation_mode == 'validation'):
    warmup_period = 0                                                           # Warmup period is zero under validation mode

## COMMUNICATION MODE
packet_size      = int(config['COMMUNICATION MODE']['packet_size'])               # The packet size (in bits)
PE_to_PE         = config.getboolean('COMMUNICATION MODE', 'PE_to_PE')            # The communication mode in which data is sent, directly, from a PE to a PE
shared_memory    = config.getboolean('COMMUNICATION MODE', 'shared_memory')       # The communication mode in which data is sent from a PE to a PE through a shared memory
write_time       = -1
read_time        = -1
PE_to_Cache      = {}

if (PE_to_PE) and (shared_memory):
    print('[E] Please chose only one of the communication modes')
    sys.exit()
elif (not PE_to_PE) and (not shared_memory):
    print('[E] Please chose one of the communication modes')
    sys.exit()

iteration = 0

# The variables used by table-based schedulers
table   = -1
table_2 = -1
table_3 = -1
table_4 = -1
temp_list = []
# Additional variables used by list-based schedulers
current_dag      = nx.DiGraph()
computation_dict = {}
power_dict       = {}

## DTPM
current_temperature_vector  = [T_ambient,                  # Indicate the current PE temperature for each hotspot
                               T_ambient,
                               T_ambient,
                               T_ambient,
                               T_ambient]
B_model = []
throttling_state = -1
trace_file_num = 0
DVFS_cfg_list = []

# Snippet_inj is incremented every time a snippet finishes being injected
snippet_ID_inj                      = -1
# Snippet_exec is incremented every time a snippet finishes being executed
snippet_ID_exec                     = 0
snippet_throttle                    = -1
snippet_temp_list                   = []
snippet_initial_temp                = [T_ambient,
                                       T_ambient,
                                       T_ambient,
                                       T_ambient,
                                       T_ambient]

snippet_start_time                  = 0
## End of DTPM

class PerfStatics:
    '''!
    Define the PerfStatics class to calculate energy consumption and total execution time.
    '''
    def __init__(self):
        self.execution_time = 0.0                   # The total execution time (us)
        self.energy_consumption = 0.0               # The total energy consumption (uJ)
        self.cumulative_exe_time = 0.0              # Sum of the execution time of completed tasks (us)
        self.cumulative_energy_consumption = 0.0    # Sum of the energy consumption of completed tasks (us)
        self.injected_jobs = 0                      # Count the number of jobs that enter the system (i.e. the ready queue)
        self.completed_jobs = 0                     # Count the number of jobs that are completed 
        self.ave_execution_time = 0.0               # Average execution time for the jobs that are finished 
        self.job_counter = 0                        # Indicate the number of jobsin the system at any given time
        self.average_job_number = 0                 # Shows the average number of jobs in the system for a workload
        self.job_counter_list = []
        self.sampling_rate_list = []
# end class PerfStatics

# Instantiate the object that will store the performance statistics
global results

class Validation:
    '''!
    Define the Validation class to compare the generated and completed jobs.
    '''
    start_times = []
    finish_times = []
    generated_jobs = []
    injected_jobs = []
    completed_jobs = []
# end class Validation

class Resource:
    '''!
    Define the Resource class to define a resource.
    It stores properties of the resources.
	'''
    def __init__(self):
        self.type = ''                          # The type of the resource (CPU, FFT_ACC, etc.)
        self.name = ''                          # Name of the resource
        self.ID = -1                            # This is the unique ID of the resource. "-1" means it is not initialized
        self.cluster_ID = -1                    # ID of the cluster this PE belongs to
        self.capacity = 1                       # Number tasks that a resource can run simultaneously. Default value is 1.
        self.num_of_functionalites = 0          # This variable shows how many different task this resource can run
        self.supported_functionalities = []     # List of all tasks can be executed by Resource
        self.performance = []                   # List of runtime (in micro seconds) for each supported task
        self.idle = True                        # initial state of Resource which idle and ready for a task (normalized to the number of instructions)
        self.mesh_name = -1
        self.position = -1
        self.width = -1
        self.height = -1
# end class Resource

class ResourceManager:
    '''!
    Define the ResourceManager class to maintain the list of the resource in our DASH-SoC model.
    '''
    def __init__(self):
        self.list = []                          # List of available resources
        self.comm_band = []                     # This variable represents the communication bandwidth matrix
# end class ResourceManager

class ClusterManager:
    '''!
    Define the ClusterManager class to maintain the list of clusters in our DASH-SoC model.
    '''
    def __init__(self):
        self.cluster_list = []                  # list of available clusters
# end class ClusterManager

class Tasks:
    '''!
    Define the Tasks class to maintain the list of tasks.
    It stores properties of the tasks.
    '''
    def __init__(self):
        self.name = ''                          # The name of the task
        self.ID = -1                            # This is the unique ID of the task. "-1" means it is not initialized
        self.predecessors = []                  # List of all task IDs to identify task dependency
        self.est = -1                           # This variable represents the earliest time that a task can start
        self.deadline = -1                      # This variable represents the deadline for a task
        self.head = False                       # If head is true, this task is the leading (the first) element in a task graph
        self.tail = False                       # If tail is true, this task is the end (the last) element in a task graph
        self.jobID = -1                         # This task belongs to job with this ID
        self.jobname = ''                       # This task belongs to job with this name
        self.base_ID = -1                       # This ID will be used to calculate the data volume from one task to another
        self.PE_ID = -1                         # Holds the PE ID on which the task will be executed
        self.start_time = -1                    # Execution start time of a task
        self.finish_time = -1                   # Execution finish time of a task
        self.order = -1                         # Relative ordering of this task on a particular PE
        self.dynamic_dependencies = []          # List of dynamic dependencies that a scheduler requests are satisfied before task launch
        self.ready_wait_times = []              # List holding wait times for a task for being ready due to communication time from its predecessor
        self.execution_wait_times = []          # List holding wait times for a task for being execution-ready due to communication time between memory and a PE 
        self.PE_to_PE_wait_time = []            # List holding wait times for a task for being execution-ready due to PE to PE communication time
        self.order = -1                         # Execution order if a list based scheduler is used, e.g., ILP
        self.task_elapsed_time_max_freq = 0     # Indicate the current execution time for a given task
        self.job_start = -1                     # Holds the execution start time of a head task (also execution start time for a job)
        self.time_stamp = -1                    # This values used to check whether all data for the task is transferred or not
        self.input_packet_size = -1
        self.output_packet_size = -1
# end class Tasks

class TaskManager:
    '''!
    Define the TaskManager class to maintain the list of the tasks in our DASH-SoC model.
    '''
    def __init__(self):
        self.list = []                          # List of available tasks
# end class TaskManager

class Applications:
    '''!
    Define the Applications class to maintain all information about an application (job)
    '''
    def __init__(self):
        self.name =  ''                         # The name of the application
        self.task_list = []                     # List of all tasks in an application
        self.comm_vol = []                      # This variable represents the communication volume matrix
        # i.e. each entry is data volume should be transferred from one task to another
# end class Applications

class ApplicationManager:
    '''!
    Define the ApplicationManager class to maintain the list of the applications (jobs) in our DASH-SoC model.
    '''
    def __init__(self):
        self.list = []                          # List of all applications
# end class ApplicationManager

class TaskQueues:
    '''!
    Define the TaskQueues class to maintain all task queue lists
    '''
    def __init__(self):
        self.outstanding = []                   # List of *all* tasks waiting to be processed
        self.ready = []                         # List of tasks that are ready for processing
        self.running = []                       # List of currently running tasks
        self.completed = []                     # List of completed tasks
        self.wait_ready = []                    # List of task waiting for being pushed into ready queue because of memory communication time
        self.executable = []                    # List of task waiting for being executed because of memory communication time 
# end class TaskQueues

# =============================================================================
# def clear_screen():
#     '''
#     Define the clear_screen function to
#     clear the screen before the simulation.
#     '''
#     current_platform = platform.system()        # Find the platform
#     if 'windows' in current_platform.lower():
#         get_ipython().magic('clear')
#     elif 'Darwin' in current_platform.lower():
#         get_ipython().magic('clear')
#     elif 'linux' in current_platform.lower():
#         get_ipython().magic('clear')  
# # end of def clear_screen()
# =============================================================================

