'''!
@brief This file contains the code for dynamic scheduling with Constraint Programming.

CP is one of the schedulers develop in DS3. 
The Constraint Programming model is executed after every frame (job) is generated. 
The obtained schedule is stored in a table and then used as the tasks become ready for execution.
'''
import matplotlib.pyplot as plt
import csv
from docplex.cp.model import *
import docplex.cp.utils_visu as visu
from docplex.cp.config import context
import docplex.cp.parameters as params
import common

def CP(env_time, P_elems, resource_matrix, domain_applications, generated_jobs):
    '''!
    Creates a schedule using the Constraint Programming model
    @param env_time: Current time of the simulation environment
    @param P_elems: Instances of processing elements in the SoC configuration generated in the simulation environment
    @param resource_matrix: All processing elements in the SoC configuration 
    @param domain_applications: Applications under consideration for workload generation
    @param generated_jobs: Instances of applications (jobs) currently being executed in the system
    '''
    ###### Step 1 - Initialize variable and parameters
    plt.close('all')
    
    # Set docplex related parameters
    context.solver.trace_log = False
    #params.CpoParameters.OptimalityTolerance = 2
    #params.CpoParameters.RelativeOptimalityTolerance= 2
    
    Dags = []
    Dags_2 = {}
    # Get the task in Outstanding and Ready Queues
    # Since tasks in Completed Queue are already done, they will not be considered
    for task in common.TaskQueues.outstanding.list:
        if task.jobID not in Dags:
            Dags.append(task.jobID)
            for i in range(len(domain_applications.list)):
                name = domain_applications.list[i].name
                if name == task.jobname:
                    Dags_2[task.jobID] = {}
                    Dags_2[task.jobID]['selection'] = i
    for task in common.TaskQueues.ready.list:
        if task.jobID not in Dags:
            Dags.append(task.jobID)
            for i in range(len(domain_applications.list)):
                name = domain_applications.list[i].name
                if name == task.jobname:
                    Dags_2[task.jobID] = {}
                    Dags_2[task.jobID]['selection'] = i
    #Dags.sort()

    common.ilp_job_list = [(key,Dags_2[key]['selection']) for key in Dags_2.keys()]
    #print(Dags_2)
    
    
    NbDags = len(Dags)                                                      # Current number of jobs in the system
    PEs = []                                                                # List of PE element in the given SoC configuration                                                

    print('[I] Time %d: There is %d job(s) in the system' %(env_time, NbDags)   )
    print('[D] Time %d: ID of the jobs in the system are' %(env_time),Dags)
   
    ###### Step 2 - Prepare Data 
    
    # First, check if there are any tasks currently being executed on a PE
    # if yes, retrieve remaining time of execution on that PE and
    # do not assign a task during ILP solution
    for i, PE in enumerate(P_elems):
        if (PE.type == 'MEM') or (PE.type == 'CAC') :                       # Do not consider Memory ond Cache
            continue
        PEs.append(PE.name)                                                 # Populate the name of the PEs in the SoC
    #print(PEs)
    
    for ID in Dags_2.keys():
        Dags_2[ID]['Tasks'] = []                                            # list of tasks that CPLEX will return a schedule for
        Dags_2[ID]['Functionality'] = []                                    # list of task-PE relationship
        Dags_2[ID]['Con_Precedence'] = []                                    # list of task dependencies

        app_id = Dags_2[ID]['selection']        
        #print(len(Dags), len(self.generated_job_list))
        num_of_tasks = len(domain_applications.list[app_id].task_list)
        
        for task in domain_applications.list[app_id].task_list:
            Dags_2[ID]['Tasks'].append(task.base_ID)
            
            # Next, gather the information about which PE can run which Tasks 
            # and if so, the expected execution time
            for resource in resource_matrix.list:
                if (resource.type == 'MEM') or (resource.type == 'CAC') :        # Do not consider Memory ond Cache
                    continue
                else:
                    if task.name in resource.supported_functionalities:
                        ind = resource.supported_functionalities.index(task.name)
                        #Functionality.append((resource.name, task.base_ID, resource.performance[ind]))
                        Dags_2[ID]['Functionality'].append((resource.name, task.base_ID, resource.performance[ind]))
            
            # Finally, gather dependency information between tasks
            
            for i,predecessor in enumerate(task.predecessors):
                #print(task.ID, predecessor, num_of_tasks, last_ID, task.base_ID)

                for resource in resource_matrix.list:
                    if (resource.type == 'MEM') or (resource.type == 'CAC') :
                        continue
                    else:
                        #pred_name = self.generated_job_list[job_ind].task_list[predecessor-last_ID].name
                        pred_name = domain_applications.list[app_id].task_list[ predecessor- (task.ID - task.base_ID) ].name
                        if (pred_name in resource.supported_functionalities):
                            c_vol = domain_applications.list[app_id].comm_vol[predecessor - (task.ID - task.base_ID), task.base_ID]
                            Dags_2[ID]['Con_Precedence'].append((resource.name,Dags_2[ID]['Tasks'][predecessor - (task.ID - task.base_ID)], task.base_ID, c_vol))

    #print(Dags_2[ID]['Tasks'])
    #print(len(Dags_2[ID]['Functionality']))
    #print(Dags_2[ID]['Con_Precedence'])
    

    
    ###### Step 3 - Create the model
    mdl = CpoModel()
    
    # Create dag interval variables
    dags = { d : mdl.interval_var(name="dag"+str(d)) for d in Dags_2.keys()}
    #print(dags)
    
    # Create tasks interval variables and pe_tasks interval variables
    # pe_tasks are optional and only one of them will be mapped to the corresponding
    # tasks interval variable
    # For example, task_1 has 3 pe_tasks (i.e.,P1-task_1, P2-task_1, P3, task_1)
    # only of these will be selected. If the first one is selected, it means that task_1 will be executed in P1
    tasks_2 = {}
    pe_tasks_2 = {}
    task_names_ids_2 = {}
    last_ID = 0
    for d in Dags_2.keys():
        num_of_tasks = len(generated_jobs[d].task_list)
        for t in Dags_2[d]['Tasks']:
            tasks_2[(d,t)] = mdl.interval_var(name = str(d)+"_"+str(t))
        for f in Dags_2[d]['Functionality']:
            #print(f)
            name = str(d)+"_"+str(f[1])+'-'+str(f[0])
            if len(common.TaskQueues.running.list) == 0 and len(common.TaskQueues.completed.list) == 0:
                pe_tasks_2[(d,f)] = mdl.interval_var(optional=True, size =int(f[2]), name = name )
                task_names_ids_2[name] = last_ID+f[1]
            else:
                for ii, running_task in enumerate(common.TaskQueues.running.list):
                    if (d == running_task.jobID) and (f[1] == running_task.base_ID) and (f[0] == P_elems[running_task.PE_ID].name):

                        ind = resource_matrix.list[running_task.PE_ID].supported_functionalities.index(running_task.name)
                        exec_time = resource_matrix.list[running_task.PE_ID].performance[ind]
                        free_time = int(running_task.start_time + exec_time - env_time)
                        #print(free_time)    
                        pe_tasks_2[(d,f)] = mdl.interval_var(optional=True, start=0, end=free_time,name = name )
                        task_names_ids_2[name] = last_ID+f[1]
                        break
                    elif (d == running_task.jobID) and (f[1] == running_task.base_ID):
                        pe_tasks_2[(d,f)] = mdl.interval_var(optional=True, size =INTERVAL_MAX, name = name )
                        task_names_ids_2[name] = last_ID+f[1]
                        break
                else:
                    pe_tasks_2[(d,f)] = mdl.interval_var(optional=True, size =int(f[2]), name = name )
                    task_names_ids_2[name] = last_ID+f[1]
                
                for iii, completed_task in enumerate(common.TaskQueues.completed.list):
                    if (d == completed_task.jobID) and (f[1] == completed_task.base_ID) and (f[0] == P_elems[completed_task.PE_ID].name):
                        #print(completed_task.name)
                        #pe_tasks[(d,f)] = mdl.interval_var(optional=True, size =0, name = name )
                        pe_tasks_2[(d,f)] = mdl.interval_var(optional=True, start=0, end=0, name = name )
                        task_names_ids_2[name] = last_ID+f[1]
                    elif (d == completed_task.jobID) and (f[1] == completed_task.base_ID):
                        pe_tasks_2[(d,f)] = mdl.interval_var(optional=True, size =INTERVAL_MAX, name = name )
                        task_names_ids_2[name] = last_ID+f[1]
                #print('3',pe_tasks[(d,f)])
                  
        last_ID += num_of_tasks
    #print(tasks_2)
    #print(task_names_ids_2)
    
    # Add the temporal constraints            
    for d in Dags_2.keys():
        for c in Dags_2[d]['Con_Precedence']:
            for (p1, task1, d1) in Dags_2[d]['Functionality']:
                if p1 == c[0] and task1 == c[1]:
                    p1_id = PEs.index(p1)
                    for (p2, task2, d2) in Dags_2[d]['Functionality']:
                        if p2 == c[0] and task2 == c[2]:
                            mdl.add( mdl.end_before_start(pe_tasks_2[d,(p1,task1,d1)], pe_tasks_2[d,(p2,task2,d2)], 0) )
                        elif p2 != c[0] and task2 == c[2]:
                            p2_id = PEs.index(p2)
                            #print(p2_id)
                            bandwidth = common.ResourceManager.comm_band[p1_id,p2_id]
                            comm_time = int( (c[3])/bandwidth )
                            for ii, completed_task in enumerate(common.TaskQueues.completed.list):
                                if ((d == completed_task.jobID) and (task1 == completed_task.base_ID) and (p1 == P_elems[completed_task.PE_ID].name)):
                                    mdl.add( mdl.end_before_start(pe_tasks_2[d,(p1,task1,d1)], pe_tasks_2[d,(p2,task2,d2)], max(0,comm_time+completed_task.finish_time-env_time)  ))
                                    #print (d, p1,p2, task1,task2, max(0,int(c[3])+completed_task.finish_time-self.env.now) )
                                    break
                            else:
                                #print(d, p1,p2, task1,task2, c[3])
                                mdl.add( mdl.end_before_start(pe_tasks_2[d,(p1,task1,d1)], pe_tasks_2[d,(p2,task2,d2)], comm_time ) )
                

    # Add the span constraints
    # This constraint enables to identify tasks in a dag            
    for d in Dags_2.keys():
        mdl.add( mdl.span(dags[d], [tasks_2[(d,t)] for t in Dags_2[d]['Tasks'] ] ) )
        
    
    # Add the alternative constraints
    # This constraint ensures that only one PE is chosen to execute a particular task                
    for d in Dags_2.keys():
        for t in Dags_2[d]['Tasks']:
            mdl.add( mdl.alternative(tasks_2[d,t], [pe_tasks_2[d,f] for f in Dags_2[d]['Functionality'] if f[1]==t]) )
            
    
    # Add the no overlap constraints
    # This constraint ensures that there will be no overlap for the task being executed on the same PE        
    for p in PEs:
        b_list = [pe_tasks_2[d,f] for d in Dags_2.keys() for f in Dags_2[d]['Functionality'] if f[0]==p]
        if b_list:
            mdl.add( mdl.no_overlap([pe_tasks_2[d,f] for d in Dags_2.keys() for f in Dags_2[d]['Functionality'] if f[0]==p]))
        else:
            continue     
    
    # Add the objective
    mdl.add(mdl.minimize(mdl.sum([mdl.end_of(dags[d]) for i,d in enumerate(Dags)])))
    #mdl.add(mdl.minimize(mdl.max([mdl.end_of(pe_tasks_2[(d,f)]) for i,d in enumerate(Dags) for f in Dags_2[d]['Functionality'] ])))
    #mdl.add(mdl.minimize(mdl.max(mdl.end_of(dags[d]) for i,d in enumerate(Dags))))
    
    ###### Step 4 - Solve the model and print some results
    # Solve the model
    print("\nSolving CP model....")
    msol = mdl.solve(TimeLimit = 60)
    #msol = mdl.solve()
    #print("Completed")

    #print(msol.print_solution())
    #print(msol.is_solution_optimal())
    print(msol.get_objective_gaps())
    print(msol.get_objective_values()[0])
    
    
    tem_list = []
    for d in Dags:
        #for f in Functionality:
        for f in Dags_2[d]['Functionality']:
            #solution = msol.get_var_solution(pe_tasks[(d,f)])
            solution = msol.get_var_solution(pe_tasks_2[(d,f)])
            if solution.is_present():
                #ID = task_names_ids[solution.get_name()]
                ID = task_names_ids_2[solution.get_name()]
                tem_list.append( (ID, f[0], solution.get_start(), solution.get_end()) )
    tem_list.sort(key=lambda x: x[2], reverse=False)
    #print(tem_list)
    
    actual_schedule = []
    for i,p in enumerate(PEs):
        count = 0      
        for item in tem_list:
            if item[1] == p:
                actual_schedule.append( (item[0],i,count+1))
                count += 1
    actual_schedule.sort(key=lambda x: x[0], reverse=False)
    #print(actual_schedule)
    
    common.table = []
    for element in actual_schedule:
        common.table.append((element[1],element[2]))
    #print(common.table)    
    #print(len(common.table))
    
    
    if (common.simulation_mode == 'validation'):
        colors = ['salmon','turquoise', 'lime' , 'coral', 'lightpink']
        PEs.reverse()                     
        for i,p in enumerate(PEs):
            #visu.panel()
            #visu.pause(PE_busy_times[p])
            visu.sequence(name=p)

            for ii,d in enumerate(Dags):
                #for f in Functionality: 
                for f in Dags_2[d]['Functionality']:
                    #wt = msol.get_var_solution(pe_tasks[(d,f)])
                    wt = msol.get_var_solution(pe_tasks_2[(d,f)])
                    if wt.is_present() and p == f[0]:
                        color = colors[ii%len(colors)]
                        #visu.interval(wt, color, str(task_names_ids[wt.get_name()]))
                        visu.interval(wt, color, str(task_names_ids_2[wt.get_name()]))          
        visu.show()
    

    for d in Dags:
        for task in generated_jobs[d].task_list:

            task_sched_ID = 0
            task.dynamic_dependencies.clear()                                  # Clear dependencies from previosu ILP run
           
            ind = Dags.index(d)
            for i in range(ind):
                selection = Dags_2[Dags[i]]['selection']
                task_sched_ID += len(domain_applications.list[selection].task_list)
            task_sched_ID += task.base_ID
            
            task_order = common.table[task_sched_ID][1]
           
            for k in Dags:

                for dyn_depend in generated_jobs[k].task_list:
                    dyn_depend_sched_ID = 0
                   
                    ind_k = Dags.index(k)
                    for ii in range(ind_k):
                        selection = Dags_2[Dags[ii]]['selection']
                        dyn_depend_sched_ID += len(domain_applications.list[selection].task_list)
                    dyn_depend_sched_ID += dyn_depend.base_ID    
                       
                    if ( (common.table[dyn_depend_sched_ID][0] == common.table[task_sched_ID][0]) and 
                        (common.table[dyn_depend_sched_ID][1] == task_order-1) and 
                        (dyn_depend.ID not in task.predecessors) and 
                        (dyn_depend.ID not in task.dynamic_dependencies) ):
                        
                        task.dynamic_dependencies.append(dyn_depend.ID)
                #print(task.ID, task.dynamic_dependencies)

# end of CP_Multi(......

###########################################################################################################################
###########################################################################################################################


