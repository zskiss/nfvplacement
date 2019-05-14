#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Dec 03 17:39:52 2018
Written and tested in Python 3.7.1
@author: Zsombor Kiss
"""
import os
import sys
import json
import traceback
import random
import collections
from graph_tool.all import *

#GLOBAL CONSTANTS
WEIGHT_CPU = 1.0
WEIGHT_RAM = 1.0

def help():
    print("Short helper text!")
    print("Why are you seeing this?")
    print("Either there were some problems with the arguments, or you called it with --help.")
    print("Usage: python tester.py $ABSOLUTE_PATH_TO_NETWORK_FILE.gml $ABSOLUTE_PATH_TO_FOLDER_CONTATING_VNFS_json_FILES")
    #no appending folder paths to each other
    print("Above is supposed to be one line.")
    print("JSON files in the folder should only be the ones needed, as all will try to get loaded! The slash at the end of the path does not matter.")
    print("The format requirements are in my thesis, and I wish you the best in your adventures!")
    sys.exit(0)

def load_network(filepath):
    try:
        g = Graph() #empty graph
        g = load_graph(filepath)
    
        if not g:
            #loading failed
            print("Network file loading failed! Exiting!")
            print("Call the file with no arguments to check the helper text!")
            sys.exit(1)
        #Debug prints, ctrl+4 to comment, ctrl+5 to uncomment in spyder
        ####
        print("Is g directed:", g.is_directed())
        print("Graph properties:")
        print(g.list_properties())
        print("Vertices:", g.num_vertices())
        for v in g.vertices():
            print(v)
        print("Edges:", g.num_edges())
        for e in g.edges():
            print(e, "is this edge valid?", e.is_valid())
        print("")
        ####
        
        print("Found graph with", g.num_vertices(), "vertices and", g.num_edges(), "edges")
        
        return g
    except Exception as ex:
        print("Exception occured during loading the network file!")
        traceback.print_tb(ex.__traceback__)
        print("Call the file with no arguments to check the helper text!")
        sys.exit(1)
        
def load_vnfs(folderpath):
    try:
        vnfs_list = [] #empty list
        list_of_files = [f for f in os.listdir(folderpath) if os.path.isfile(os.path.join(folderpath, f))]
        list_of_jsons = [k for k in list_of_files if '.json' in k]
        
        ####
        #print("Filelist: ", list_of_files)
        #print("Jsonlist: ", list_of_jsons)
        ####
        list_of_jsons.sort()
        ####
        #print("Sorted jsons: ", list_of_jsons)
        ####
        
        for j in list_of_jsons:
            ####
            #print(j)
            ####
            j2 = ""
            j2 += folderpath
            if not j2.endswith('/'):
                j2 += "/"
            j2 += j
            ####
            #print(j2)
            ####
            with open(j2, "r") as fp:
                x = json.loads(fp.read())
            print("Found VNF file with", len(x['NFS']) ,"NFs and", len(x['VLINKS']), "links, ID:", x['ID'])
            vnfs_list.append(x)
        if not vnfs_list:
            print("No JSON files were found/loaded! Exiting!")
            print("Call the file with no arguments to check the helper text!")
            sys.exit(2)
        #####
        print("VNF list: ")
        for vnf in vnfs_list:
            print(vnf)
        #####
        return vnfs_list
    except Exception as ex:
        print("Exception occured during loading the VNF files!")
        traceback.print_tb(ex.__traceback__)
        print("Call the file with no arguments to check the helper text!")
        sys.exit(2)
        
def randomplacement(g, vnf, source, target):
    #returns the delay
    #random.randint(0, g.num_vertices()-1): alsó zárt, felső zárt intervallum
    g_backup = Graph(g)
    print("")
    print("Placing VNF ID:", vnf['ID'])
    placements = []
    for nf in vnf['NFS']:
        print("Placing NF:", nf['ID'], "it needs", nf['CPU'], "cpu and", nf['RAM'], "ram")
        placed = False
        #set: unique
        notEnoughCapacity = set()
        while not placed:
            candidate = random.randint(0, g.num_vertices()-1)
            cpu = g.vp["cpu"][candidate]
            ram = g.vp["ram"][candidate]
            print("Looking at vertex:", candidate, "| cpu free:", cpu, "ram free:", ram)
            if cpu >= float(nf['CPU']) and ram >= float(nf['RAM']):
                #it fits!
                placements.append(candidate)
                placed = True
                g.vp["cpu"][candidate] -= float(nf['CPU'])
                g.vp["ram"][candidate] -= float(nf['RAM'])
                print("placed it at", candidate, ", remaining cpu:", g.vp["cpu"][candidate], "ram:", g.vp["ram"][candidate])
            else:
                #it doesn't fit
                notEnoughCapacity.add(candidate)
                print("Current nodes where it didn't fit:", notEnoughCapacity)
                if len(notEnoughCapacity) == g.num_vertices():
                    #it doesn't fit anywhere
                    print("Placing NF ID:", nf['ID'], "failed, rolling back and quitting!")
                    #ROLLBACK
                    j = 0
                    while j < len(placements):
                        node = placements[j]
                        g.vp["cpu"][node] += float(vnf['NFS'][j]['CPU'])
                        g.vp["ram"][node] += float(vnf['NFS'][j]['RAM'])
                        print("ROLLBACK: gave back", vnf['NFS'][j]['CPU'], "cpu and", vnf['NFS'][j]['RAM'], "ram to vertex", node)
                        print("Vertex", node, "now has", g.vp["cpu"][node], "free cpu and", g.vp["ram"][node], "free ram")
                        j += 1
                    print("Completed: failed to place VNF", vnf['ID'], "with RANDOM")
                    return -1
    #NFs are placed, gotta route between them
    
    print("Successfully placed vnf ID", vnf['ID'], "at the following vertices:")
    print(placements)
    
    #handle case where you can't route them: out of link capacity
    #needs a second graph, so that the overloaded links can be deleted without impacting other stuff
    #all the load information is still in the first graph
    #vnf['BW']  
    i = 0
    if placements[0] != source:
        i = -1
    if placements[-1] == target:
        loop_condition = len(vnf['VLINKS'])
    else:
        loop_condition = len(vnf['VLINKS']) + 1
    delays = []
    used_edges = []
    
    print("Calculating path and delays")
    print("Global source:", source, "| Global target:", target)
    while i < loop_condition:
        if i == -1:
            #extra link at the start
            link = vnf['VLINKS'][0]
            print("Routing extra first vlink from", source, "to", link['SRC'])
            print("Finding source and destination")
            src_node = source
            dst_node = -1
            j = 0
            for nf in vnf['NFS']:
                if nf['ID'] == link['SRC']:
                    dst_node = placements[j]
                j += 1
            if src_node == -1:
                print("Source node not found! This should not happen!")
                return -2
            if dst_node == -1:
                print("Destination node not found! This should not happen!")
                return -2
            print("Source set at", src_node, "destination found at", dst_node)
        elif i != len(vnf['VLINKS']):
            link = vnf['VLINKS'][i]
            print("Routing vlink", link['ID'], "from", link['SRC'], "to", link['DST'])
            print("Finding source and destination")
            src_node = -1
            dst_node = -1
            j = 0
            for nf in vnf['NFS']:
                if nf['ID'] == link['SRC']:
                    src_node = placements[j]
                if nf['ID'] == link['DST']:
                    dst_node = placements[j]
                j += 1
            if src_node == -1:
                print("Source node not found! This should not happen!")
                return -2
            if dst_node == -1:
                print("Destination node not found! This should not happen!")
                return -2
            print("Source found at", src_node, "destination found at", dst_node)
        else:
            #extra link at the end
            link = vnf['VLINKS'][i-1]
            print("Routing extra vlink from", link['DST'], "to target node", target)
            print("Finding source")
            src_node = -1
            dst_node = target
            j = 0
            for nf in vnf['NFS']:
                if nf['ID'] == link['DST']:
                    src_node = placements[j]
                j += 1
            if src_node == -1:
                print("Source node not found! This should not happen!")
                return -2
            if dst_node == -1:
                print("Destination node not found! This should not happen!")
                return -2
            print("Source found at", src_node, "destination set at", dst_node)
        
        g_pathfinding = Graph(g)
        placed = False
        while not placed:
            startover = False
            vlist, elist = shortest_path(g_pathfinding, g_pathfinding.vertex(src_node), g_pathfinding.vertex(dst_node), g_pathfinding.ep['delay'])
            print("Current path:")
            print([str(v) for v in vlist])
            print([str(e) for e in elist])
            vlist_rev, elist_rev = shortest_path(g_pathfinding, g_pathfinding.vertex(dst_node), g_pathfinding.vertex(src_node), g_pathfinding.ep['delay'])
            if not elist and src_node != dst_node:
                #THEY HAVE TO BE DIFFERENT NODES
                #no path found, that means that no available paths had enough capacity
                print("No path found between", src_node, "and", dst_node, ", restoring graph to the starting state and quitting!")
                print("Completed: failed to place VNF", vnf['ID'], "with RANDOM")
# =============================================================================
#                 j = 0
#                 while j < len(placements):
#                     node = placements[j]
#                     g.vp["cpu"][node] += float(vnf['NFS'][j]['CPU'])
#                     g.vp["ram"][node] += float(vnf['NFS'][j]['RAM'])
#                     print("ROLLBACK: gave back", vnf['NFS'][j]['CPU'], "cpu and", vnf['NFS'][j]['RAM'], "ram to vertex", node)
#                     print("Vertex", node, "now has", g.vp["cpu"][node], "free cpu and", g.vp["ram"][node], "free ram")
#                     j += 1
# =============================================================================
                #just restore the whole graph
                g = Graph(g_backup)
                return -1
            if link['BIDIR'] == True:
                print("Reversed for the BIDIR stuff:")
                print("Current path:")
                print([str(v) for v in vlist_rev])
                print([str(e) for e in elist_rev])
                print("Reversed:")
                vlist_rev.reverse()
                elist_rev.reverse()
                print([str(v) for v in vlist_rev])
                print([str(e) for e in elist_rev])
            if src_node == dst_node:
                #they are located at the same node
                print("These are at the same node, there is no path!")
                delays.append(0)
                placed = True
            if link['BIDIR'] == True:
                for e, e_rev in zip(elist, elist_rev):
                    if not startover:
                        print("edge source:", e.source())
                        print("edge dest:", e.target())
                        print("edge capacity:", g.ep["capacity"][e])
                        print("edge delay:", g.ep["delay"][e])
                        print("reverse edge source:", e_rev.source())
                        print("reverse edge dest:", e_rev.target())
                        print("reverse edge capacity:", g.ep["capacity"][e_rev])
                        print("reverse edge delay: ", g.ep["delay"][e_rev])
                        if g.ep["capacity"][e] >= float(vnf['BW']) and g.ep["capacity"][e_rev] >= float(vnf['BW']):
                            g.ep["capacity"][e] -= float(vnf['BW'])
                            g.ep["capacity"][e_rev] -= float(vnf['BW'])
                            used_edges.append(e)
                            used_edges.append(e_rev)
                            delays.append(g.ep["delay"][e])
                            print("Placed route between", str(e), "remaining capacity:", g.ep["capacity"][e])
                            print("BIDIR: placed route between", str(e_rev), "remaining capacity:", g.ep["capacity"][e_rev])
                        else:
                            #it doesn't fit, needs more capacity, delete those edges
                            print("Current edges", str(e), "and" , str(e_rev),"have insufficient capacity, removing and starting over with the current link!")
                            g_pathfinding.remove_edge(e)
                            g_pathfinding.remove_edge(e_rev)
                            startover = True
                if not startover:
                    placed = True
            else:
                for e in elist:
                    if not startover:
                        print("edge source:",e.source())
                        print("edge dest:",e.target())
                        print("edge capacity:", g.ep["capacity"][e])
                        print("edge delay: ", g.ep["delay"][e])
                        if g.ep["capacity"][e] >= float(vnf['BW']):
                            g.ep["capacity"][e] -= float(vnf['BW'])
                            delays.append(g.ep["delay"][e])
                            used_edges.append(e)
                            print("Placed route between", str(e), "remaining capacity:", g.ep["capacity"][e])
                        else:
                            #it doesn't fit, needs more capacity, delete that edge
                            print("Current edge", str(e), "has insufficient capacity, removing and starting over with the current link!")
                            g_pathfinding.remove_edge(e)
                            startover = True
                if not startover:
                    placed = True
    
        i += 1
    
    print("All route delays:")
    print(delays)
    
    rounded = round(sum(delays),3)
    
    print("-------------------")
    print("Completed: placed VNF", vnf['ID'], "with RANDOM:", rounded)
    print("Returning sum:", rounded)
    print("-------------------")
    return rounded
    
def greedyplacement(g, vnf, source, target):
    #constants to control which resource is weighed more in the node comparison
    #returns the delay
    #random.randint(0, g.num_vertices()-1): alsó zárt, felső zárt intervallum
    print("")
    print("Placing VNF ID:", vnf['ID'])
    g_backup = Graph(g)
    placements = []
    current_node = source
    i = 1
    for nf in vnf['NFS']:
        #general case
        #check the free resources of the current node, and its neighbors
        #place it in the one that has the most of them
        #if none, then sort all resources globally, pick (one of) the nodes with the most
        print("Placing NF:", nf['ID'], "it needs", nf['CPU'], "cpu and", nf['RAM'], "ram")
        check_local = False
        check_global = False
        placed = False
        while not placed:
            print("Current node:", current_node)
            #check the current node and its out_neighbors for the most free resources
            resources = {}
            #prefer local: if the local node has the same free resources as the first one, then this will be in first place when sorted
            resources.update({current_node: WEIGHT_CPU * g.vp["cpu"][current_node] + WEIGHT_RAM * g.vp["ram"][current_node]})
            for v in g.vertex(current_node).out_neighbors():
                resources.update({int(str(v)): WEIGHT_CPU * g.vp["cpu"][v] + WEIGHT_RAM * g.vp["ram"][v]})
            print("Current node and neighbors with their free resources weighed:", resources)
            sorted_resources_list = sorted(resources.items(), key=lambda kv: kv[1], reverse=True)
            sorted_resources = collections.OrderedDict(sorted_resources_list)
            print("This sorted by free resources:", sorted_resources)
            for key, value in sorted_resources.items():
                if not placed:
                    cpu = g.vp["cpu"][key]
                    ram = g.vp["ram"][key]
                    print("Looking at vertex:", key, "| cpu free:", cpu, "ram free:", ram)
                    if cpu >= float(nf['CPU']) and ram >= float(nf['RAM']):
                        #place it there
                        placements.append(key)
                        placed = True
                        g.vp["cpu"][key] -= float(nf['CPU'])
                        g.vp["ram"][key] -= float(nf['RAM'])
                        current_node = key
                        check_local = True
                        print("placed it at", key, ", remaining cpu:", g.vp["cpu"][key], "ram:", g.vp["ram"][key])
            #no match found in these, search globally
            #if it still doesn't fit then fail, roll back and quit
            #reset resources store
            if not check_local:
                print("No match found locally, searching globally!")
                resources = {}
                for v in g.vertices():
                     resources.update({int(str(v)): WEIGHT_CPU * g.vp["cpu"][v] + WEIGHT_RAM * g.vp["ram"][v]})
                print("Current node and neighbors with their free resources weighed:", resources)
                sorted_resources_list = sorted(resources.items(), key=lambda kv: kv[1], reverse=True)
                sorted_resources = collections.OrderedDict(sorted_resources_list)
                print("This sorted by free resources:", sorted_resources)
                for key, value in sorted_resources.items():
                    if not placed:
                        cpu = g.vp["cpu"][key]
                        ram = g.vp["ram"][key]
                        print("Looking at vertex:", key, "| cpu free:", cpu, "ram free:", ram)
                        if cpu >= float(nf['CPU']) and ram >= float(nf['RAM']):
                            #place it there
                            placements.append(key)
                            placed = True
                            g.vp["cpu"][key] -= float(nf['CPU'])
                            g.vp["ram"][key] -= float(nf['RAM'])
                            current_node = key
                            print("placed it at", key, ", remaining cpu:", g.vp["cpu"][key], "ram:", g.vp["ram"][key])
                            check_global = True
                if not check_global:
                    #nothing matched, ROLLBACK
                    print("Could not placed NF", nf['ID'] , "rolling back and quitting!")
                    j = 0
                    while j < len(placements):
                        node = placements[j]
                        g.vp["cpu"][node] += float(vnf['NFS'][j]['CPU'])
                        g.vp["ram"][node] += float(vnf['NFS'][j]['RAM'])
                        print("ROLLBACK: gave back", vnf['NFS'][j]['CPU'], "cpu and", vnf['NFS'][j]['RAM'], "ram to vertex", node)
                        print("Vertex", node, "now has", g.vp["cpu"][node], "free cpu and", g.vp["ram"][node], "free ram")
                        j += 1
                    print("Completed: failed to place VNF", vnf['ID'], "with GREEDY")
                    return -1
     
    print("Successfully placed vnf ID", vnf['ID'], "at the following vertices:")
    print(placements)
    
    #let's route this
    #in routing it might happen that an additional link is needed from source node to the first NF
    #or an extra link from the last NF to the target node
    #or both
    i = 0
    if placements[0] != source:
        i = -1
    if placements[-1] == target:
        loop_condition = len(vnf['VLINKS'])
    else:
        loop_condition = len(vnf['VLINKS']) + 1
    delays = []
    used_edges = []
    #vnf['BW']  
    print("Calculating path and delays")
    print("Global source:", source, "| Global target:", target)
    while i < loop_condition:
        if i == -1:
            #extra link at the start
            link = vnf['VLINKS'][0]
            print("Routing extra first vlink from", source, "to", link['SRC'])
            print("Finding source and destination")
            src_node = source
            dst_node = -1
            j = 0
            for nf in vnf['NFS']:
                if nf['ID'] == link['SRC']:
                    dst_node = placements[j]
                j += 1
            if src_node == -1:
                print("Source node not found! This should not happen!")
                return -2
            if dst_node == -1:
                print("Destination node not found! This should not happen!")
                return -2
            print("Source set at", src_node, "destination found at", dst_node)
        elif i != len(vnf['VLINKS']):
            link = vnf['VLINKS'][i]
            print("Routing vlink", link['ID'], "from", link['SRC'], "to", link['DST'])
            print("Finding source and destination")
            src_node = -1
            dst_node = -1
            j = 0
            for nf in vnf['NFS']:
                if nf['ID'] == link['SRC']:
                    src_node = placements[j]
                if nf['ID'] == link['DST']:
                    dst_node = placements[j]
                j += 1
            if src_node == -1:
                print("Source node not found! This should not happen!")
                return -2
            if dst_node == -1:
                print("Destination node not found! This should not happen!")
                return -2
            print("Source found at", src_node, "destination found at", dst_node)
        else:
            #extra link at the end
            link = vnf['VLINKS'][i-1]
            print("Routing extra vlink from", link['DST'], "to target node", target)
            print("Finding source")
            src_node = -1
            dst_node = target
            j = 0
            for nf in vnf['NFS']:
                if nf['ID'] == link['DST']:
                    src_node = placements[j]
                j += 1
            if src_node == -1:
                print("Source node not found! This should not happen!")
                return -2
            if dst_node == -1:
                print("Destination node not found! This should not happen!")
                return -2
            print("Source found at", src_node, "destination set at", dst_node)
            
        g_pathfinding = Graph(g)
        placed = False
        while not placed:
            startover = False
            vlist, elist = shortest_path(g_pathfinding, g_pathfinding.vertex(src_node), g_pathfinding.vertex(dst_node), g_pathfinding.ep['delay'])
            print("Current path:")
            print([str(v) for v in vlist])
            print([str(e) for e in elist])
            vlist_rev, elist_rev = shortest_path(g_pathfinding, g_pathfinding.vertex(dst_node), g_pathfinding.vertex(src_node), g_pathfinding.ep['delay'])
            if not elist and src_node != dst_node:
                #THEY HAVE TO BE DIFFERENT NODES
                #no path found, that means that no available paths had enough capacity
                print("No path found between", src_node, "and", dst_node, ", restoring graph to the starting state and quitting!")
                print("Completed: failed to place VNF", vnf['ID'], "with GREEDY")
# =============================================================================
#                 j = 0
#                 while j < len(placements):
#                     node = placements[j]
#                     g.vp["cpu"][node] += float(vnf['NFS'][j]['CPU'])
#                     g.vp["ram"][node] += float(vnf['NFS'][j]['RAM'])
#                     print("ROLLBACK: gave back", vnf['NFS'][j]['CPU'], "cpu and", vnf['NFS'][j]['RAM'], "ram to vertex", node)
#                     print("Vertex", node, "now has", g.vp["cpu"][node], "free cpu and", g.vp["ram"][node], "free ram")
#                     j += 1
# =============================================================================
                #restore the whole graph to the starting position
                g = Graph(g_backup)
                return -1
            if link['BIDIR'] == True:
                print("Reversed for the BIDIR stuff:")
                print("Current path:")
                print([str(v) for v in vlist_rev])
                print([str(e) for e in elist_rev])
                print("Reversed:")
                vlist_rev.reverse()
                elist_rev.reverse()
                print([str(v) for v in vlist_rev])
                print([str(e) for e in elist_rev])
            if src_node == dst_node:
                #they are located at the same node
                print("These are at the same node, there is no path!")
                delays.append(0)
                placed = True
            if link['BIDIR'] == True:
                for e, e_rev in zip(elist, elist_rev):
                    if not startover:
                        print("edge source:", e.source())
                        print("edge dest:", e.target())
                        print("edge capacity:", g.ep["capacity"][e])
                        print("edge delay:", g.ep["delay"][e])
                        print("reverse edge source:", e_rev.source())
                        print("reverse edge dest:", e_rev.target())
                        print("reverse edge capacity:", g.ep["capacity"][e_rev])
                        print("reverse edge delay: ", g.ep["delay"][e_rev])
                        if g.ep["capacity"][e] >= float(vnf['BW']) and g.ep["capacity"][e_rev] >= float(vnf['BW']):
                            g.ep["capacity"][e] -= float(vnf['BW'])
                            g.ep["capacity"][e_rev] -= float(vnf['BW'])
                            used_edges.append(e)
                            used_edges.append(e_rev)
                            delays.append(g.ep["delay"][e])
                            print("Placed route between", str(e), "remaining capacity:", g.ep["capacity"][e])
                            print("BIDIR: placed route between", str(e_rev), "remaining capacity:", g.ep["capacity"][e_rev])
                        else:
                            #it doesn't fit, needs more capacity, delete those edges
                            print("Current edges", str(e), "and" , str(e_rev),"have insufficient capacity, removing and starting over with the current link!")
                            g_pathfinding.remove_edge(e)
                            g_pathfinding.remove_edge(e_rev)
                            startover = True
                if not startover:
                    placed = True
            else:
                for e in elist:
                    if not startover:
                        print("edge source:",e.source())
                        print("edge dest:",e.target())
                        print("edge capacity:", g.ep["capacity"][e])
                        print("edge delay: ", g.ep["delay"][e])
                        if g.ep["capacity"][e] >= float(vnf['BW']):
                            g.ep["capacity"][e] -= float(vnf['BW'])
                            used_edges.append(e)
                            delays.append(g.ep["delay"][e])
                            print("Placed route between", str(e), "remaining capacity:", g.ep["capacity"][e])
                        else:
                            #it doesn't fit, needs more capacity, delete that edge
                            print("Current edge", str(e), "has insufficient capacity, removing and starting over with the current link!")
                            g_pathfinding.remove_edge(e)
                            startover = True
                if not startover:
                    placed = True
        i += 1
          
    
    print("All route delays:")
    print(delays)
    
    rounded = round(sum(delays),3)
    print("-------------------")
    print("Completed: placed VNF", vnf['ID'], "with GREEDY:", rounded)
    print("Returning sum:", rounded)
    print("-------------------")
    return rounded
    

def myplacement(g, vnf, source, target):
    print("")
    print("Placing VNF ID:", vnf['ID'])
    centrals = []
    distances = {}
    for v in g.vertices():
        if g.vp['label'][v] == "central":
            centrals.append(int(str(v)))
    print("Central nodes:", centrals)
    for v in centrals:
        delay1 = 0
        delay2 = 0
        vlist1, elist1 = shortest_path(g, g.vertex(source), g.vertex(v), g.ep['delay'])
        vlist2, elist2 = shortest_path(g, g.vertex(v), g.vertex(target), g.ep['delay'])
        for edge in elist1:
            delay1 += g.ep['delay'][edge]
        for edge in elist2:
            delay2 += g.ep['delay'][edge]
        distances.update({v: delay1 + delay2})
    print("Delays for the routes through central nodes:")
    print(distances)
    sorted_distances_list = sorted(distances.items(), key=lambda kv: kv[1])
    sorted_distances = collections.OrderedDict(sorted_distances_list)
    print("Sorted for the shortest:")
    print(sorted_distances)
    centrals_sorted = []
    for key, value in sorted_distances.items():
        centrals_sorted.append(key)
    print("Only the central nodes sorted:", centrals_sorted)
    
    centralcounter = 0
    done = False
    delays = []
    
    while not done:
        #lets do the shortest route
        print("Running the shortest route variant")
        g_shortest = Graph(g)
        placements_shortest = []
        delays_shortest = []
        failed = False
        vlist, elist = shortest_path(g_shortest, g_shortest.vertex(source), g_shortest.vertex(target), g_shortest.ep['delay'])
        free_resources = {}
        for v in vlist:
            free_resources.update({int(str(v)): WEIGHT_CPU * g.vp["cpu"][v] + WEIGHT_RAM * g.vp["ram"][v]})
        print("Free resources of the nodes along the shortest path:")
        print(free_resources)
        sorted_resources_list = sorted(free_resources.items(), key=lambda kv: kv[1], reverse=True)
        sorted_resources = collections.OrderedDict(sorted_resources_list)
        print("Sorted in descending order:")
        print(sorted_resources)
        onlykeys = []
        for key, value in sorted_resources.items():
            onlykeys.append(key)
        print("onlykeys:", onlykeys)
        #place all you can in the first one, then move on the next one and so on
        resources_index = 0
        for nf in vnf['NFS']:
            placed = False
            if not failed:
                while not placed:
                    print("Placing NF", nf['ID'], "needs", nf['CPU'], "cpu and", nf['RAM'], "ram")
                    cpu = g_shortest.vp['cpu'][onlykeys[resources_index]]
                    ram = g_shortest.vp['ram'][onlykeys[resources_index]]
                    print("Looking at vertex", onlykeys[resources_index], "| has", cpu, "free cpu and", ram, "free ram")
                    if cpu >= float(nf['CPU']) and ram >= float(nf['RAM']):
                        g_shortest.vp['cpu'][onlykeys[resources_index]] -= float(nf['CPU'])
                        g_shortest.vp['ram'][onlykeys[resources_index]] -= float(nf['RAM'])
                        placements_shortest.append(int(onlykeys[resources_index]))
                        placed = True
                        #placednfs.update({"type": "NF", "VNF": vnf['ID'], "location": onlykeys[resources_index], "cpu": nf['CPU'], "ram": nf['RAM']})
                        print("Placed it at", onlykeys[resources_index], "remaining cpu:", g_shortest.vp['cpu'][onlykeys[resources_index]], "ram:", g_shortest.vp['ram'][onlykeys[resources_index]])
                        print("Placements right now:", placements_shortest)
                    else:
                        resources_index += 1
                        if resources_index == len(onlykeys):
                            print("Placement failed, going to the next")
                            failed = True
                    if failed:
                        break
        
        if not failed:
            print("Successfully placed vnf ID", vnf['ID'], "at the following vertices:")
            print(placements_shortest)
            #routing
            i = 0
            if placements_shortest[0] != source:
                i = -1
            if placements_shortest[-1] == target:
                loop_condition = len(vnf['VLINKS'])
            else:
                loop_condition = len(vnf['VLINKS']) + 1
            
            while i < loop_condition:
                if i == -1:
                    #extra link at the start
                    link = vnf['VLINKS'][0]
                    print("Routing extra first vlink from", source, "to", link['SRC'])
                    print("Finding source and destination")
                    src_node = source
                    dst_node = -1
                    j = 0
                    for nf in vnf['NFS']:
                        if nf['ID'] == link['SRC']:
                            dst_node = placements_shortest[j]
                        j += 1
                    if src_node == -1:
                        print("Source node not found! This should not happen!")
                        return -2
                    if dst_node == -1:
                        print("Destination node not found! This should not happen!")
                        return -2
                    print("Source set at", src_node, "destination found at", dst_node)
                elif i != -1 and i != len(vnf['VLINKS']):
                    link = vnf['VLINKS'][i]
                    print("Routing vlink", link['ID'], "from", link['SRC'], "to", link['DST'])
                    print("Finding source and destination")
                    src_node = -1
                    dst_node = -1
                    j = 0
                    for nf in vnf['NFS']:
                        if nf['ID'] == link['SRC']:
                            src_node = placements_shortest[j]
                        if nf['ID'] == link['DST']:
                            dst_node = placements_shortest[j]
                        j += 1
                    if src_node == -1:
                        print("Source node not found! This should not happen!")
                        return -2
                    if dst_node == -1:
                        print("Destination node not found! This should not happen!")
                        return -2
                    print("Source found at", src_node, "destination found at", dst_node)
                else:
                    #extra link at the end
                    link = vnf['VLINKS'][i-1]
                    print("Routing extra vlink from", link['DST'], "to target node", target)
                    print("Finding source")
                    src_node = -1
                    dst_node = target
                    j = 0
                    for nf in vnf['NFS']:
                        if nf['ID'] == link['DST']:
                            src_node = placements_shortest[j]
                        j += 1
                    if src_node == -1:
                        print("Source node not found! This should not happen!")
                        return -2
                    if dst_node == -1:
                        print("Destination node not found! This should not happen!")
                        return -2
                    print("Source found at", src_node, "destination set at", dst_node)
                    
                placed = False
                while not placed:
                    startover = False
                    vlist, elist = shortest_path(g_shortest, g_shortest.vertex(src_node), g_shortest.vertex(dst_node), g_shortest.ep['delay'])
                    print("Current path:")
                    print([str(v) for v in vlist])
                    print([str(e) for e in elist])
                    vlist_rev, elist_rev = shortest_path(g_shortest, g_shortest.vertex(dst_node), g_shortest.vertex(src_node), g_shortest.ep['delay'])
                    if not elist and src_node != dst_node:
                        #THEY HAVE TO BE DIFFERENT NODES
                        #no path found, that means that no available paths had enough capacity
                        print("No path found between", src_node, "and", dst_node, ", moving on to the next round!")
                        #fail it
                        failed = True
                        return -1
                    if link['BIDIR'] == True:
                        print("Reversed for the BIDIR stuff:")
                        print("Current path:")
                        print([str(v) for v in vlist_rev])
                        print([str(e) for e in elist_rev])
                        print("Reversed:")
                        vlist_rev.reverse()
                        elist_rev.reverse()
                        print([str(v) for v in vlist_rev])
                        print([str(e) for e in elist_rev])
                    if src_node == dst_node:
                        #they are located at the same node
                        print("These are at the same node, there is no path!")
                        delays_shortest.append(0)
                        placed = True
                    if link['BIDIR'] == True:
                        for e, e_rev in zip(elist, elist_rev):
                            if not startover:
                                print("edge source:", e.source())
                                print("edge dest:", e.target())
                                print("edge capacity:", g_shortest.ep["capacity"][e])
                                print("edge delay:", g_shortest.ep["delay"][e])
                                print("reverse edge source:", e_rev.source())
                                print("reverse edge dest:", e_rev.target())
                                print("reverse edge capacity:", g_shortest.ep["capacity"][e_rev])
                                print("reverse edge delay: ", g_shortest.ep["delay"][e_rev])
                                if g_shortest.ep["capacity"][e] >= float(vnf['BW']) and g_shortest.ep["capacity"][e_rev] >= float(vnf['BW']):
                                    g_shortest.ep["capacity"][e] -= float(vnf['BW'])
                                    g_shortest.ep["capacity"][e_rev] -= float(vnf['BW'])
                                    delays_shortest.append(g.ep["delay"][e])
                                    print("Placed route between", str(e), "remaining capacity:", g_shortest.ep["capacity"][e])
                                    print("BIDIR: placed route between", str(e_rev), "remaining capacity:", g_shortest.ep["capacity"][e_rev])
                                else:
                                    #it doesn't fit, needs more capacity, delete those edges
                                    print("Current edges", str(e), "and" , str(e_rev),"have insufficient capacity, removing and starting over with the current link!")
                                    g_shortest.remove_edge(e)
                                    g_shortest.remove_edge(e_rev)
                                    startover = True
                        if not startover:
                            placed = True
                    else:
                        for e in elist:
                            if not startover:
                                print("edge source:",e.source())
                                print("edge dest:",e.target())
                                print("edge capacity:", g_shortest.ep["capacity"][e])
                                print("edge delay: ", g_shortest.ep["delay"][e])
                                if g_shortest.ep["capacity"][e] >= float(vnf['BW']):
                                    g_shortest.ep["capacity"][e] -= float(vnf['BW'])
                                    delays_shortest.append(g_shortest.ep["delay"][e])
                                    print("Placed route between", str(e), "remaining capacity:", g_shortest.ep["capacity"][e])
                                else:
                                    #it doesn't fit, needs more capacity, delete that edge
                                    print("Current edge", str(e), "has insufficient capacity, removing and starting over with the current link!")
                                    g_shortest.remove_edge(e)
                                    startover = True
                        if not startover:
                            placed = True
                i += 1
        
        
        if failed:
            print("Failed with the shortest placement of VNF", vnf['ID'])
            delays_shortest = [-1]
        
        #lets do the route through the current central node
        print("Running the central node variant, current central node:", centrals_sorted[centralcounter])
        g_central = Graph(g)
        placements_central = []
        delays_central = []
        failed = False
        free_resources = {}
        print("Source:", source, "target:", centrals_sorted[centralcounter])
        vlist, elist = shortest_path(g_central, g_central.vertex(source), g_central.vertex(centrals_sorted[centralcounter]), g_central.ep['delay'])
        for v in vlist:
            print("Added", int(str(v)))
            free_resources.update({int(str(v)): WEIGHT_CPU * g.vp["cpu"][v] + WEIGHT_RAM * g.vp["ram"][v]})
        #skip the first item, it was included in the previous sort
        first = True
        print("Source:", centrals_sorted[centralcounter], "target:", target)
        vlist, elist = shortest_path(g_central, g_central.vertex(centrals_sorted[centralcounter]), g_central.vertex(target), g_central.ep['delay'])
        for v in vlist:
            print("Added", int(str(v)))
            free_resources.update({int(str(v)): WEIGHT_CPU * g.vp["cpu"][v] + WEIGHT_RAM * g.vp["ram"][v]})
        print("Free resources of the nodes along the shortest path:")
        print(free_resources)
        sorted_resources_list = sorted(free_resources.items(), key=lambda kv: kv[1], reverse=True)
        sorted_resources = collections.OrderedDict(sorted_resources_list)
        print("Sorted in descending order:")
        print(sorted_resources)
        onlykeys = []
        for key, value in sorted_resources.items():
            onlykeys.append(key)
        #place all you can in the first one, then move on the next one and so on
        resources_index = 0
        for nf in vnf['NFS']:
            placed = False
            if not failed:
                while not placed:
                    print("Placing NF", nf['ID'], "needs", nf['CPU'], "cpu and", nf['RAM'], "ram")
                    cpu = g_central.vp['cpu'][onlykeys[resources_index]]
                    ram = g_central.vp['ram'][onlykeys[resources_index]]
                    print("Looking at vertex", onlykeys[resources_index], "| has", cpu, "free cpu and", ram, "free ram")
                    if cpu >= float(nf['CPU']) and ram >= float(nf['RAM']):
                        g_central.vp['cpu'][onlykeys[resources_index]] -= float(nf['CPU'])
                        g_central.vp['ram'][onlykeys[resources_index]] -= float(nf['RAM'])
                        placements_central.append(onlykeys[resources_index])
                        placed = True
                        #placednfs.update({"type": "NF", "VNF": vnf['ID'], "location": onlykeys[resources_index], "cpu": nf['CPU'], "ram": nf['RAM']})
                        print("Placed it at", onlykeys[resources_index], "remaining cpu:", g_central.vp['cpu'][onlykeys[resources_index]], "ram:", g_central.vp['ram'][onlykeys[resources_index]])
                        print("Placements right now:", placements_central)
                    else:
                        resources_index += 1
                        if resources_index == len(onlykeys):
                            print("Placement failed, going to the next")
                            failed = True
                    if failed:
                        break
        
        if not failed:
            print("Successfully placed vnf ID", vnf['ID'], "at the following vertices:")
            print(placements_central)
            
            #routing
            i = 0
            if placements_central[0] != source:
                i = -1
            if placements_central[-1] == target:
                loop_condition = len(vnf['VLINKS'])
            else:
                loop_condition = len(vnf['VLINKS']) + 1
            
            while i < loop_condition:
                if i == -1:
                    #extra link at the start
                    link = vnf['VLINKS'][0]
                    print("Routing extra first vlink from", source, "to", link['SRC'])
                    print("Finding source and destination")
                    src_node = source
                    dst_node = -1
                    j = 0
                    for nf in vnf['NFS']:
                        if nf['ID'] == link['SRC']:
                            dst_node = placements_central[j]
                        j += 1
                    if src_node == -1:
                        print("Source node not found! This should not happen!")
                        return -2
                    if dst_node == -1:
                        print("Destination node not found! This should not happen!")
                        return -2
                    print("Source set at", src_node, "destination found at", dst_node)
                elif i != len(vnf['VLINKS']):
                    link = vnf['VLINKS'][i]
                    print("Routing vlink", link['ID'], "from", link['SRC'], "to", link['DST'])
                    print("Finding source and destination")
                    src_node = -1
                    dst_node = -1
                    j = 0
                    for nf in vnf['NFS']:
                        if nf['ID'] == link['SRC']:
                            src_node = placements_central[j]
                        if nf['ID'] == link['DST']:
                            dst_node = placements_central[j]
                        j += 1
                    if src_node == -1:
                        print("Source node not found! This should not happen!")
                        return -2
                    if dst_node == -1:
                        print("Destination node not found! This should not happen!")
                        return -2
                    print("Source found at", src_node, "destination found at", dst_node)
                else:
                    #extra link at the end
                    link = vnf['VLINKS'][i-1]
                    print("Routing extra vlink from", link['DST'], "to target node", target)
                    print("Finding source")
                    src_node = -1
                    dst_node = target
                    j = 0
                    for nf in vnf['NFS']:
                        if nf['ID'] == link['DST']:
                            src_node = placements_central[j]
                        j += 1
                    if src_node == -1:
                        print("Source node not found! This should not happen!")
                        return -2
                    if dst_node == -1:
                        print("Destination node not found! This should not happen!")
                        return -2
                    print("Source found at", src_node, "destination set at", dst_node)
                    
                placed = False
                while not placed:
                    startover = False
                    vlist, elist = shortest_path(g_central, g_central.vertex(src_node), g_central.vertex(dst_node), g_central.ep['delay'])
                    print("Current path:")
                    print([str(v) for v in vlist])
                    print([str(e) for e in elist])
                    vlist_rev, elist_rev = shortest_path(g_central, g_central.vertex(dst_node), g_central.vertex(src_node), g_central.ep['delay'])
                    if not elist and src_node != dst_node:
                        #THEY HAVE TO BE DIFFERENT NODES
                        #no path found, that means that no available paths had enough capacity
                        print("No path found between", src_node, "and", dst_node, ", moving on to the next round!")
                        #just fail it
                        failed = True
                        return -1
                    if link['BIDIR'] == True:
                        print("Reversed for the BIDIR stuff:")
                        print("Current path:")
                        print([str(v) for v in vlist_rev])
                        print([str(e) for e in elist_rev])
                        print("Reversed:")
                        vlist_rev.reverse()
                        elist_rev.reverse()
                        print([str(v) for v in vlist_rev])
                        print([str(e) for e in elist_rev])
                    if src_node == dst_node:
                        #they are located at the same node
                        print("These are at the same node, there is no path!")
                        delays_central.append(0)
                        placed = True
                    if link['BIDIR'] == True:
                        for e, e_rev in zip(elist, elist_rev):
                            if not startover:
                                print("edge source:", e.source())
                                print("edge dest:", e.target())
                                print("edge capacity:", g_central.ep["capacity"][e])
                                print("edge delay:", g_central.ep["delay"][e])
                                print("reverse edge source:", e_rev.source())
                                print("reverse edge dest:", e_rev.target())
                                print("reverse edge capacity:", g_central.ep["capacity"][e_rev])
                                print("reverse edge delay: ", g_central.ep["delay"][e_rev])
                                if g_central.ep["capacity"][e] >= float(vnf['BW']) and g_central.ep["capacity"][e_rev] >= float(vnf['BW']):
                                    g_central.ep["capacity"][e] -= float(vnf['BW'])
                                    g_central.ep["capacity"][e_rev] -= float(vnf['BW'])
                                    delays_central.append(g.ep["delay"][e])
                                    print("Placed route between", str(e), "remaining capacity:", g_central.ep["capacity"][e])
                                    print("BIDIR: placed route between", str(e_rev), "remaining capacity:", g_central.ep["capacity"][e_rev])
                                else:
                                    #it doesn't fit, needs more capacity, delete those edges
                                    print("Current edges", str(e), "and" , str(e_rev),"have insufficient capacity, removing and starting over with the current link!")
                                    g_central.remove_edge(e)
                                    g_central.remove_edge(e_rev)
                                    startover = True
                        if not startover:
                            placed = True
                    else:
                        for e in elist:
                            if not startover:
                                print("edge source:",e.source())
                                print("edge dest:",e.target())
                                print("edge capacity:", g_central.ep["capacity"][e])
                                print("edge delay: ", g_central.ep["delay"][e])
                                if g_central.ep["capacity"][e] >= float(vnf['BW']):
                                    g_central.ep["capacity"][e] -= float(vnf['BW'])
                                    delays_central.append(g_central.ep["delay"][e])
                                    print("Placed route between", str(e), "remaining capacity:", g_central.ep["capacity"][e])
                                else:
                                    #it doesn't fit, needs more capacity, delete that edge
                                    print("Current edge", str(e), "has insufficient capacity, removing and starting over with the current link!")
                                    g_central.remove_edge(e)
                                    startover = True
                        if not startover:
                            placed = True
                i += 1
        
        if failed:
            print("Failed with the central placement of VNF", vnf['ID'])
            delays_central = [-1]
        
        #compare the results
        #if none of them pass then move on the next central node: the shortest will still fail, but that's okay
        #if one of them pass then compare the results, and use the one with the shorter delay
        print("")
        print("Sum(delays_shortest):", sum(delays_shortest))
        print("Sum(delays_central):", sum(delays_central))
        #both failed
        if sum(delays_shortest) == -1 and sum(delays_central) == -1:
            centralcounter += 1
            print("Both failed, moving on to the next round")
            #both completed, but the central is shorter, pick that
        elif sum(delays_shortest) != -1 and round(sum(delays_shortest),3) > round(sum(delays_central),3):
            placements = placements_central
            delays = delays_central
            g = Graph(g_central)
            done = True
            print("Chose the central variant, through central node:", centrals_sorted[centralcounter])
        #both completed, they are the same, then pick the shortest, this will override the previous one
        elif sum(delays_shortest) != -1 and round(sum(delays_shortest),3) <= round(sum(delays_central),3):
            placements = placements_shortest
            delays = delays_shortest
            g = Graph(g_shortest)
            done = True
            print("Chose the shortest variant")
        #shortest failed, central completed
        elif sum(delays_shortest) == -1 and sum(delays_central) != -1:
            placements = placements_central
            delays = delays_central
            g = Graph(g_central)
            done = True
            print("Chose the central variant, through central node:", centrals_sorted[centralcounter])
        else:
            print("############################")
            print("THIS SHOULD NOT HAPPEN!")
            print("############################")
    
    if not done:
        #FAILURE AT THE END
        print("Completed: failed to place VNF", vnf['ID'], "with CUSTOM")
        return -1, tobereplaced, placednfs, placedlinks
    else:
        print("All route delays:")
        print(delays)
        
        rounded = round(sum(delays),3)
        print("-------------------")
        print("Completed: placed VNF", vnf['ID'], "with CUSTOM:", rounded)
        print("Returning sum:", rounded)
        print("-------------------")
        return rounded


def main(argv):
    if len(argv) == 1: #no parameters
        help()
    elif any("help" in k for k in argv):
        help()
    elif len(argv) != 3:
        help()
    print("Loading network file:", argv[1])
    g = load_network(argv[1])
    print("Network file loaded!")
    print("Loading VNF json file(s) from", argv[2])
    vnfs = load_vnfs(argv[2])
    print("VNF file(s) loaded!")
    
    #mass dump, edit count
# =============================================================================
#     vnf1random = []
#     vnf2random = []
#     vnf3random = []
#     vnf4random = []
#     vnf1greedy = []
#     vnf2greedy = []
#     vnf3greedy = []
#     vnf4greedy = []
#     vnf1custom = []
#     vnf2custom = []
#     vnf3custom = []
#     vnf4custom = []
#     
#     count = 0
#     while count < 100:
#     
#         print("Randomizing sources and targets")
#         targets = []
#         i = 0
#         while i < len(vnfs):
#             source = random.randint(0, g.num_vertices()-1)
#             while not g.vertex(source):
#                 source = random.randint(0, g.num_vertices()-1)
#             target = random.randint(0, g.num_vertices()-1)
#             #don't be the same
#             while target == source or not g.vertex(target):
#                 target = random.randint(0, g.num_vertices()-1)
#             print("randomized for vnf", i, "source:", source, "target:", target)
#             dictionary = {"source" : source, "target": target}
#             targets.append(dictionary)
#             i += 1
#         print("targets:", targets)
#         
#         #graph properties that are modified (cpu, ram amounts) are preserved
#         #through each loop, that's why you need new copies at each placing
#         
#         #random loop for all vnfs
#         g1 = Graph(g)
#         print("")
#         print("-----Starting loop of random placement!-----")
#         i = 0
#         while i < len (vnfs):
#             delay = randomplacement(g1, vnfs[i], targets[i]["source"], targets[i]["target"])
#             print("One way latency:", delay)
#             if i == 0:
#                 if delay != -1:
#                     vnf1random.append(delay)
#                 else:
#                     vnf1random.append("FAIL")
#             if i == 1:
#                 if delay != -1:
#                     vnf2random.append(delay)
#                 else:
#                     vnf2random.append("FAIL")
#             if i == 2:
#                 if delay != -1:
#                     vnf3random.append(delay)
#                 else:
#                     vnf3random.append("FAIL")
#             if i == 3:
#                 if delay != -1:
#                     vnf4random.append(delay)
#                 else:
#                     vnf4random.append("FAIL")
#             i += 1
#         print("")
#         print("-----Finished with random loop!-----")
#         print("")
#         
#         #greedy loop for all vnfs
#         g2 = Graph(g)
#         print("")
#         print("-----Starting loop of greedy placement!-----")
#         i = 0
#         while i < len (vnfs):
#             delay = greedyplacement(g2, vnfs[i], targets[i]["source"], targets[i]["target"])
#             print("One way latency:", delay)
#             if i == 0:
#                 if delay != -1:
#                     vnf1greedy.append(delay)
#                 else:
#                     vnf1greedy.append("FAIL")
#             if i == 1:
#                 if delay != -1:
#                     vnf2greedy.append(delay)
#                 else:
#                     vnf2greedy.append("FAIL")
#             if i == 2:
#                 if delay != -1:
#                     vnf3greedy.append(delay)
#                 else:
#                     vnf3greedy.append("FAIL")
#             if i == 3:
#                 if delay != -1:
#                     vnf4greedy.append(delay)
#                 else:
#                     vnf4greedy.append("FAIL")
#             i += 1
#         print("-----Finished with greedy loop!-----")
#         print("")
#         
#         #myplacement loop for all vnfs
#     
#         g3 = Graph(g)
#         print("")
#         print("-----Starting loop of custom placement!-----")
#         i = 0
#         while i < len (vnfs):
#             delay = myplacement(g3, vnfs[i], targets[i]["source"], targets[i]["target"])
#             print("One way latency:", delay)
#             if i == 0:
#                 if delay != -1:
#                     vnf1custom.append(delay)
#                 else:
#                     vnf1custom.append("FAIL")
#             if i == 1:
#                 if delay != -1:
#                     vnf2custom.append(delay)
#                 else:
#                     vnf2custom.append("FAIL")
#             if i == 2:
#                 if delay != -1:
#                     vnf3custom.append(delay)
#                 else:
#                     vnf3customm.append("FAIL")
#             if i == 3:
#                 if delay != -1:
#                     vnf4custom.append(delay)
#                 else:
#                     vnf4custom.append("FAIL")
#             i += 1
#         print("-----Finished with custom loop!-----")
#         print("")
#         
#         count += 1
#         
#         
#     #dump them to files
#     with open('randomvnf1.txt', 'w') as f:
#         for item in vnf1random:
#             f.write("%s\n" % item)
#     
#     with open('randomvnf2.txt', 'w') as f:
#         for item in vnf2random:
#             f.write("%s\n" % item)
#             
#     with open('randomvnf3.txt', 'w') as f:
#         for item in vnf3random:
#             f.write("%s\n" % item)
#     
#     with open('randomvnf4.txt', 'w') as f:
#         for item in vnf4random:
#             f.write("%s\n" % item)
#     
#     with open('greedyvnf1.txt', 'w') as f:
#         for item in vnf1greedy:
#             f.write("%s\n" % item)
#             
#     with open('greedyvnf2.txt', 'w') as f:
#         for item in vnf2greedy:
#             f.write("%s\n" % item)
#     
#     with open('greedyvnf3.txt', 'w') as f:
#         for item in vnf3greedy:
#             f.write("%s\n" % item)
#     
#     with open('greedyvnf4.txt', 'w') as f:
#         for item in vnf4greedy:
#             f.write("%s\n" % item)
#     
#     with open('customvnf1.txt', 'w') as f:
#         for item in vnf1custom:
#             f.write("%s\n" % item)
#     
#     with open('customvnf2.txt', 'w') as f:
#         for item in vnf2custom:
#             f.write("%s\n" % item)
#     
#     with open('customvnf3.txt', 'w') as f:
#         for item in vnf3custom:
#             f.write("%s\n" % item)
#     
#     with open('customvnf4.txt', 'w') as f:
#         for item in vnf4custom:
#             f.write("%s\n" % item)
# =============================================================================
        
    
    
    #simple run, not for mass dumping
        
    print("Randomizing sources and targets")
    targets = []
    i = 0
    while i < len(vnfs):
        source = random.randint(0, g.num_vertices()-1)
        while not g.vertex(source):
            source = random.randint(0, g.num_vertices()-1)
        target = random.randint(0, g.num_vertices()-1)
        #don't be the same
        while target == source or not g.vertex(target):
            target = random.randint(0, g.num_vertices()-1)
        print("randomized for vnf", i, "source:", source, "target:", target)
        dictionary = {"source" : source, "target": target}
        targets.append(dictionary)
        i += 1
    print("targets:", targets)
    
    #random loop for all vnfs
    g1 = Graph(g)
    print("")
    print("-----Starting loop of random placement!-----")
    i = 0
    while i < len (vnfs):
        delay = randomplacement(g1, vnfs[i], targets[i]["source"], targets[i]["target"])
        print("One way latency:", delay)
        i += 1
    print("")
    print("-----Finished with random loop!-----")
    print("")
    
    #greedy loop for all vnfs
    g2 = Graph(g)
    print("")
    print("-----Starting loop of greedy placement!-----")
    i = 0
    while i < len (vnfs):
        delay = greedyplacement(g2, vnfs[i], targets[i]["source"], targets[i]["target"])
        print("One way latency:", delay)
        i += 1
    print("-----Finished with greedy loop!-----")
    print("")
    
    #myplacement loop for all vnfs

    g3 = Graph(g)
    print("")
    print("-----Starting loop of custom placement!-----")
    i = 0
    while i < len (vnfs):
        delay = myplacement(g3, vnfs[i], targets[i]["source"], targets[i]["target"])
        print("One way latency:", delay)
        i += 1
    print("-----Finished with custom loop!-----")
    print("")

if __name__ == "__main__":
    main(sys.argv)
