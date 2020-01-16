'''
Description: This file contains the code to parse DASH-SoC given in config_file.ini file.
'''
import sys
import platform
import numpy as np

import common                                                                   # The common parameters used in DASH-Sim are defined in common_parameters.py
import clusters


def resource_parse(resource_matrix, file_name):
    '''
	In case of running platform is windows,opening and reading a file
    requires encoding = 'utf-8'
	In mac no need to specify encoding techique.
    '''
    try:
        current_platform = platform.system()                                    # Find the platform
        if 'windows' in current_platform.lower():
            input_file = open(file_name, "r", encoding = "utf-8")               # Read the configuration file
        elif 'darwin' in current_platform.lower():
            input_file = open(file_name, 'r')                                   # Read the configuration file
        elif 'linux' in current_platform.lower():
            input_file = open(file_name, 'r')                                   # Read the configuration file


    except IOError:
        print("[E] Could not read configuration file that contains available resources in DASH-SoC")
        print("[E] Please check if the file 'config_file.ini' has the correct file name")
        sys.exit()                                                              # Print an error message, if the input file cannot be opened

    # Now, the file is open. Read the input lines one by one

    found_new_resource = False                                                  # The input lines do not correspond to a particular resource
                                                                                # unless found_new_resource = = true;
                                                                                # This variable shows the number of functionalities supported for a given resource
    # num_functionality_read = 0                                                  # No new functionality has been read initially
    resource_list = []
    
    capacity = 1
    last_PE_ID = 0
    each_PE_functionality = 0
    cluster_ID = 0

    common.ClusterManager.cluster_list = []
    
    for line in input_file:
        input_line = line.strip("\n\r ")                                        # Remove the end of line character
        current_line = input_line.split(" ")                                   # Split the input line into variables sepearated a space: " "
        if ( (len(input_line) == 0) or (current_line[0] == "#") or
            '#' in current_line[0]):                                            # Ignore the lines that are empty or comments (start with #)
            continue

        if not(found_new_resource):
            #new_resource = common.Resource()
            if (current_line[0] == 'add_new_resource'):                         # The key word "add_new_resource" implies that the config file defines a new resource
                
                if int(current_line[4]) > 1:
                    capacity = int(current_line[4])
                else:
                    capacity = 1

                if common.generate_complete_trace:
                    type = current_line[1]
                    if type == "LTL":
                        capacity = common.gen_trace_capacity_little
                    elif type == "BIG":
                        capacity = common.gen_trace_capacity_big
                    
                new_cluster = clusters.Cluster(current_line[2], current_line[3], current_line[1])
                cluster_ID = int(current_line[3])
                
                for i in range(capacity):
                    new_resource = common.Resource()
                    
                    # print("Reading a new resource: ", current_line[1])
                    new_resource.type = current_line[1]
    
                    # print("The name of the new resource: ", current_line[2])
                    new_resource.name = current_line[2]
                    
                    #print("The ID of the new resource: ",i + last_PE_ID)
                    new_resource.ID = i + last_PE_ID
                    new_resource.cluster_ID = cluster_ID
                    
                    new_resource.capacity = 1

                    # print("Number of functionalities supported by this resource: ",current_line[5])
                    new_resource.num_of_functionalities = int(current_line[5])      # Converting the input string to integer
                    each_PE_functionality = int(current_line[5])

                    #resource_list.append(new_resource.ID)
                    resource_list.append(last_PE_ID)
                    resource_matrix.list.append(new_resource)
                    new_cluster.PE_list.append(new_resource.ID)
                
                common.ResourceManager.comm_band = np.ones((len(resource_list),
                                                             len(resource_list))) # Initialize the communication volume matrix

                if common.generate_complete_trace is False:
                    new_cluster.DVFS = current_line[6]  # Obtain the DVFS mode for the given PE
                else:
                    if len(common.ClusterManager.cluster_list) < common.num_PEs_TRACE:
                        new_cluster.DVFS = common.DVFS_cfg_list[len(common.ClusterManager.cluster_list)]
                    else:
                        new_cluster.DVFS = current_line[6]

                found_new_resource = True                                       # Set the flag to indicate that the following lines define the funtionalities
                last_PE_ID += capacity
                common.ClusterManager.cluster_list.append(new_cluster)
                
            elif current_line[0] == 'comm_band':
                # The key word "comm_band" implies that config file defines
                # an element of communication bandwidth matrix
                # TODO: Needs to to unrolled according to the SoC resources
                if int(current_line[1]) < len(resource_list) and int(current_line[2]) < len(resource_list):
                    common.ResourceManager.comm_band[int(current_line[1]),int(current_line[2])] = int(current_line[3])
                    common.ResourceManager.comm_band[int(current_line[2]),int(current_line[1])] = int(current_line[3])
                
            else:
                print("[E] Cannot recognize the input line in resource file:", input_line )
                sys.exit()

        # end of: if not(found_new_resource)

        else: # if not(found_new_resource) (i.e., found a new resource)

            if current_line[0] == 'opp':
                # print("Reading a new OPP tuple for resource ID {0}: <{1},{2}>".format(new_resource.ID, current_line[1], current_line[2]))
                # new_resource.OPP.append((int(current_line[1]), int(current_line[2])))
                # print("Reading a new OPP tuple for resource ID {0}: <{1},{2}>".format(common.ClusterManager.cluster_list[cluster_ID].ID, current_line[1], current_line[2]))
                common.ClusterManager.cluster_list[cluster_ID].OPP.append((int(current_line[1]), int(current_line[2])))
            elif current_line[0] == 'trip_freq':
                for i, freq in enumerate(current_line):
                    if i != 0:
                        # new_resource.trip_freq.append(int(freq))
                        common.ClusterManager.cluster_list[cluster_ID].trip_freq.append(int(freq))

            elif current_line[0] == 'power_profile':
                power_profile_list = []
                frequency_threshold = 0
                for i, val in enumerate(current_line):
                    if i == 1:
                        frequency_threshold = int(val)
                    if i > 1:
                        power_profile_list.append(float(val))
                # new_resource.power_profile.update({frequency_threshold : power_profile_list})
                common.ClusterManager.cluster_list[cluster_ID].power_profile.update({frequency_threshold: power_profile_list})
            elif current_line[0] == 'PG_profile':
                power_profile_list = []
                frequency_threshold = 0
                for i, val in enumerate(current_line):
                    if i == 1:
                        frequency_threshold = int(val)
                    if i > 1:
                        power_profile_list.append(float(val))
                # new_resource.PG_profile.update({frequency_threshold : power_profile_list})
                common.ClusterManager.cluster_list[cluster_ID].PG_profile.update({frequency_threshold: power_profile_list})
            else:
                for ii in range(capacity):

                    length = len(resource_matrix.list)
                    ind_PE = length-1-ii

                    #elif (num_functionality_read < new_resource.num_of_functionalities):
                    if (each_PE_functionality > len(resource_matrix.list[ind_PE].supported_functionalities)):
                        #print("Reading a new functionality: ", current_line[0])
                        #new_resource.supported_functionalities.append(current_line[0])
                        resource_matrix.list[ind_PE].supported_functionalities.append(current_line[0])

                        #print("The runtime for this functionality: ", current_line[1])
                        #new_resource.performance.append(float(current_line[1]))
                        resource_matrix.list[ind_PE].performance.append(float(current_line[1]))

                        #num_functionality_read += 1                                     # Increment the number functionalities read so far
                        #print("number of functionality read: ", num_functionality_read)

                        # Reset these variables, since we completed reading the current resource
                        #if (num_functionality_read == new_resource.num_of_functionalities):
                        #if (num_functionality_read == resource_matrix.list[ind].num_of_functionalities):
                        if (each_PE_functionality == len(resource_matrix.list[ind_PE].supported_functionalities) and ii == (capacity-1)):
                            found_new_resource = False
                            # num_functionality_read = 0
                            each_PE_functionality = 0
                            #new_resource.OPP = sorted(new_resource.OPP)
                            common.ClusterManager.cluster_list[cluster_ID].OPP = sorted(common.ClusterManager.cluster_list[cluster_ID].OPP)
                            common.ClusterManager.cluster_list[cluster_ID].num_active_cores = len(common.ClusterManager.cluster_list[cluster_ID].PE_list)
                            #resource_matrix.list.append(new_resource)
                        
        # end of else: # if not(found_new_resource)

    # Number of resources, ignore the memory
    common.num_PEs_TRACE = len(common.ClusterManager.cluster_list) - 1


