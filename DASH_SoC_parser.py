'''!
@brief This file contains the code to parse DASH-SoC given in config_file.ini file.
'''
import sys
import platform
import numpy as np

import common                                                                   # The common parameters used in DASH-Sim are defined in common_parameters.py
import clusters


def resource_parse(resource_matrix, file_name):
    '''!
    Read and parse the SoC configuration.
    @param resource_matrix: Object to the resource matrix
    @param file_name: SoC file name, as specified in the config_file.ini
    '''
    # In case of running platform is windows,opening and reading a file
    # requires encoding = 'utf-8'
    # In mac no need to specify encoding techique.

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
    resource_list = []
    
    capacity = 1
    last_PE_ID = 0
    each_PE_functionality = 0
    cluster_ID = 0
    comm_band_self = 1

    common.ClusterManager.cluster_list = []
    
    for line in input_file:
        input_line = line.strip("\n\r ")                                        # Remove the end of line character
        current_line = input_line.split(" ")                                   # Split the input line into variables sepearated a space: " "
        if ( (len(input_line) == 0) or (current_line[0] == "#") or
            '#' in current_line[0]):                                            # Ignore the lines that are empty or comments (start with #)
            continue

        if not(found_new_resource):
            if (current_line[0] == 'add_new_resource'):                         # The key word "add_new_resource" implies that the config file defines a new resource
                
                if int(current_line[8]) > 1:
                    capacity = int(current_line[8])
                else:
                    capacity = 1
                    
                new_cluster = clusters.Cluster(current_line[4], int(current_line[6]), current_line[2])
                cluster_ID = int(current_line[6])
                
                for i in range(capacity):
                    new_resource = common.Resource()
                    
                    # print("Reading a new resource: ", current_line[1])
                    new_resource.type = current_line[2]
    
                    # print("The name of the new resource: ", current_line[2])
                    new_resource.name = current_line[4]+'_'+str(i + last_PE_ID)
                    
                    #print("The ID of the new resource: ",i + last_PE_ID)
                    new_resource.ID = i + last_PE_ID
                    new_resource.cluster_ID = cluster_ID
                    
                    new_resource.capacity = 1

                    # print("Number of functionalities supported by this resource: ",current_line[5])
                    new_resource.num_of_functionalities = int(current_line[10])      # Converting the input string to integer
                    each_PE_functionality = int(current_line[10])

                    resource_list.append(last_PE_ID)
                    resource_matrix.list.append(new_resource)
                    new_cluster.PE_list.append(new_resource.ID)
                
                common.ResourceManager.comm_band = np.ones((len(resource_list),
                                                             len(resource_list))) # Initialize the communication volume matrix

                new_cluster.DVFS = current_line[12]  # Obtain the DVFS mode for the given PE

                found_new_resource = True                                       # Set the flag to indicate that the following lines define the funtionalities
                last_PE_ID += capacity
                common.ClusterManager.cluster_list.append(new_cluster)

            elif current_line[0] == 'comm_band_self':
                comm_band_self = current_line[1]

            elif current_line[0] == 'comm_band':
                # The key word "comm_band" implies that config file defines
                # an element of communication bandwidth matrix
                if int(current_line[1]) < len(resource_list) and int(current_line[2]) < len(resource_list):
                    cluster_source  = int(current_line[1])
                    cluster_dest    = int(current_line[2])
                    comm_band_value = int(current_line[3])

                    comm_band_index_source = 0
                    comm_band_index_dest = 0
                    source_index_updated = False
                    dest_index_updated = False
                    for cluster in common.ClusterManager.cluster_list:
                        if cluster_source != cluster.ID:
                            if not source_index_updated:
                                comm_band_index_source += cluster.num_active_cores
                        else:
                            source_index_updated = True
                            source_cluster_capacity = cluster.num_active_cores

                        if cluster_dest != cluster.ID:
                            if not dest_index_updated:
                                comm_band_index_dest += cluster.num_active_cores
                        else:
                            dest_index_updated = True
                            dest_cluster_capacity = cluster.num_active_cores

                        # Fill the comm_band table with the bandwith values from the SoC config file when both indexes were updated
                        if source_index_updated and dest_index_updated:
                            for core_source in range(source_cluster_capacity):
                                for core_dest in range(dest_cluster_capacity):
                                    if comm_band_index_source + core_source == comm_band_index_dest + core_dest:
                                        comm_value = comm_band_self
                                    else:
                                        comm_value = comm_band_value
                                    common.ResourceManager.comm_band[comm_band_index_source + core_source, comm_band_index_dest + core_dest] = comm_value
                                    common.ResourceManager.comm_band[comm_band_index_dest + core_dest, comm_band_index_source + core_source] = comm_value
                            break
            else:
                print("[E] Cannot recognize the input line in resource file:", input_line )
                sys.exit()

        # end of: if not(found_new_resource)

        else: # if not(found_new_resource) (i.e., found a new resource)

            if current_line[0] == 'opp':
                # print("Reading a new OPP tuple for resource ID {0}: <{1},{2}>".format(common.ClusterManager.cluster_list[cluster_ID].ID, current_line[1], current_line[2]))
                common.ClusterManager.cluster_list[cluster_ID].OPP.append((int(current_line[1]), int(current_line[2])))
            elif current_line[0] == 'trip_freq':
                for i, freq in enumerate(current_line):
                    if i != 0:
                        common.ClusterManager.cluster_list[cluster_ID].trip_freq.append(int(freq))
            elif current_line[0] == 'DTPM_trip_freq':
                for i, freq in enumerate(current_line):
                    if i != 0:
                        common.ClusterManager.cluster_list[cluster_ID].DTPM_trip_freq.append(int(freq))
            elif current_line[0] == 'power_profile':
                power_profile_list = []
                frequency_threshold = 0
                for i, val in enumerate(current_line):
                    if i == 1:
                        frequency_threshold = int(val)
                    if i > 1:
                        power_profile_list.append(float(val))
                common.ClusterManager.cluster_list[cluster_ID].power_profile.update({frequency_threshold: power_profile_list})
            elif current_line[0] == 'PG_profile':
                power_profile_list = []
                frequency_threshold = 0
                for i, val in enumerate(current_line):
                    if i == 1:
                        frequency_threshold = int(val)
                    if i > 1:
                        power_profile_list.append(float(val))
                common.ClusterManager.cluster_list[cluster_ID].PG_profile.update({frequency_threshold: power_profile_list})
            elif (current_line[0] == 'mesh_information'):
                for ii in range(capacity):

                    length = len(resource_matrix.list)
                    ind_PE = length-1-ii
                    # print("Mesh name of the resource: ", current_line[1])
                    resource_matrix.list[ind_PE].mesh_name = current_line[1]

                    # print("Mesh position of the resource", current_line[2])
                    resource_matrix.list[ind_PE].position = current_line[2]

                    # print("Height of the resource: ", current_line[3])
                    resource_matrix.list[ind_PE].height = current_line[3]

                    # print("Width of the resource: ", current_line[4])
                    resource_matrix.list[ind_PE].width = current_line[4]

                    # print("Color of the resource: ", current_line[5])
                    resource_matrix.list[ind_PE].color = current_line[5]
            else:
                for ii in range(capacity):

                    length = len(resource_matrix.list)
                    ind_PE = length-1-ii

                    if (each_PE_functionality > len(resource_matrix.list[ind_PE].supported_functionalities)):
                        #print("Reading a new functionality: ", current_line[0])
                        resource_matrix.list[ind_PE].supported_functionalities.append(current_line[0])

                        #print("The runtime for this functionality: ", current_line[1])
                        resource_matrix.list[ind_PE].performance.append(float(current_line[1]))

                        #print("number of functionality read: ", num_functionality_read)

                        # Reset these variables, since we completed reading the current resource
                        if (each_PE_functionality == len(resource_matrix.list[ind_PE].supported_functionalities) and ii == (capacity-1)):
                            found_new_resource = False
                            each_PE_functionality = 0
                            common.ClusterManager.cluster_list[cluster_ID].OPP = sorted(common.ClusterManager.cluster_list[cluster_ID].OPP)
                            common.ClusterManager.cluster_list[cluster_ID].num_active_cores = len(common.ClusterManager.cluster_list[cluster_ID].PE_list)
                            common.ClusterManager.cluster_list[cluster_ID].num_total_cores = len(common.ClusterManager.cluster_list[cluster_ID].PE_list)

        # end of else: # if not(found_new_resource)

    # Number of resources, ignore the memory
    common.num_PEs_TRACE = len(common.ClusterManager.cluster_list) - 1


