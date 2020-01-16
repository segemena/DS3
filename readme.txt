*************************************************************************
   	© Copyright 2018 ASU All rights reserved.
      This file contains confidential and proprietary
 	    information of DASH-SoC Project.
*************************************************************************
1.Installation Guide :

	In order to install required software, please refer to installation_guide.py file.

2.How to Run the program ?
	- Create a configuration file which contains file names for DASH-SoC resources (DASH.SoC.txt) and tasks (job_singlecarrier.txt)
	  and scheduler name (e.g., min_execution_time). Please refer to config_file.ini file for more information about the format.

	- Create a Task list in a text file (singlecarrier.task.txt) using the key word add_new_tasks followed by the task list.
			The format: add_new_tasks $num_of_tasks (int)
           			    $task_name (string) $task_id (int) $task_predecessors (list)
			Example: The following lines add a new task with ID=0, and predecessor for this task is task with ID=2
    				 (empty list means there is no dependency)

    				add_new_tasks 1
    				scrambler 0 2

	- Create a Resource list in a text file (DASH.SoC.txt) using the key word add_new_resource followed by the resource.
            The format: add_new_resource $resource_type (string)  $resource_name (string) $resource_id (int) $capacity (int) $num_of_supported_functionality (int) $DVFS_mode (string)
                $functionality_name (string) $execution_time (float)
                    opp $frequency (int - MHz) $voltage (int - mV), defines the Operating Performance Points (OPPs) with frequency and voltage tuples
                    trip_freq $trip_1 $trip_2 $trip_3 ..., defines the frequencies that are set at each trip point if throttling is enabled. "-1" means that the frequency is not modified
                    power_profile $frequency $power_1 $power_2 $power_3 ... $power_max_capacity
                    PG_profile $frequency $power_1 $power_2 $power_3 ... $power_max_capacity
            Example: The following lines add a new CPU with name=P1, ID=0, capacity=1 and that can run 3 different tasks using "performance" DVFS mode

                add_new_resource CPU P1 0 1 3 performance
                opp 1000 1150
                trip_freq -1 -1 -1
                power_profile 1000 0.1
                PG_profile 1000 0.1
                scrambler 12
                reed_solomon_encoder 15
                bpsk_modulation 18

	- Finally, run DASH_Sim_v0.py to start the simulation. 
	  Please be sure that all the files listed below are in your file directory

3.File Structure
├── DASH_Sim_v0.py               : This file contains the executable code which should be run to get the stimulation results.
│   ├── common.py                : This file contains all the common parameters used in DASH_Sim.
│   ├── config_file.ini          : This file contains all the file names and variables to initialize the DASH_Sim
│   ├── scheduler.py             : This file contains the code for scheduler class which contains different types of scheduler.
│   ├── DASH_Sim_core.py         : This file contains the simulation core that handles the simulation events.
│   ├── DASH_Sim_utils.py        : This file contains functions that are used by DASH_Sim.
│   ├── DTPM.py                  : This file contains the code for the DTPM module.
│   ├── DTPM_policies.py         : This file contains the DVFS policies.
│   ├── DTPM_power_models.py     : This file contains functions that are used by the DVFS mechanism and PEs to get performance, power, and thermal values.
│   ├── DTPM_utils.py            : This file contains functions that are used by the DTPM module.
│   ├── processing_element.py    : This file contains the process elements and their attributes.
│   ├── DASH.SoC.*.txt           : These files are the configuration files of the Resources available in DASH-SoC.
│   ├── DASH_SoC_parser.py       : This file contains the code to parse DASH-SoC given in config_file.ini file.
│   ├── job_*.txt                : These files are the configuration files of the Tasks.
│   ├── job_generator.py         : This file contains the code for the job generator.
│   └── job_parser.py            : This file contains the code to parse Tasks given in config_file.ini file.
├── generate_traces.py           : This file contains the script to generate the traces of several configurations at once.
└── ...
