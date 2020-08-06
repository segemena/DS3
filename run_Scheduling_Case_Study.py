import shutil
import os
import matplotlib.pyplot as plt

# Some variable initialization
color_list = ['b','r']
markers = ["o", "^"]
result_list = [[],[]]

# Get a configuration file satisfying the needs of the scheduling study
shutil.copyfile("config_Files/config_file_scheduling.ini", "config_file.ini")

import configparser
import common
import DASH_Sim_v0

# read the initial configuration file to make modification on the parameters needed for different simulations
config = configparser.ConfigParser()
config.read('config_file.ini')

common.simulation_length = 100000

# Dynamic config parameters
scale_list = [2000,300,200,150,125,100,80,60,50]                                # Different injection rates (data  points) to run simulations 
scheduler_list = ['MET','ETF']                                                  # Each of above injection rates will be simulated with different schedulers   

# Run simulation with each scheduler and each selected scale value (frame or injection rate)
for i, scheduler in enumerate(scheduler_list):
    config['DEFAULT']['scheduler'] = scheduler
    for rate in scale_list:
        config['SIMULATION MODE']['scale_values'] = "["+str(rate)+"]"
        with open('config_file.ini', 'w') as configfile:
            config.write(configfile)
        DASH_Sim_v0.run_simulator()
        # Only average execution time results recored for these simulations
        ave_exec = common.results.cumulative_exe_time/common.results.completed_jobs        
        injection_rate = common.results.injected_jobs / (common.results.execution_time - common.warmup_period)
        result_list[i].append((injection_rate, ave_exec))

# Plot the results (average execution time)
plt.figure(figsize=(5,3))
for i, result in enumerate(result_list):
    
    plt.plot([x[0] for x in result],[x[1] for x in result],label=scheduler_list[i],color = color_list[i], marker = markers[i])
    
#plt.ylim(100,260)
plt.yticks(fontsize=12)
plt.xticks([0,0.004,0.008,0.012,0.016,0.020], [0,4,8,12,16,20],fontsize=12)
plt.xlabel('Job Injection Rate (job/ms)', fontsize = 12)
plt.ylabel('Avg. Execution Time ($\mu$s)', fontsize = 12)
plt.grid()
plt.legend()
plt.tight_layout()
plt.show()

# Finally, reset the configuratin file to DEFAULT values
shutil.copyfile("./config_Files/config_file.ini", "./config_file.ini")
