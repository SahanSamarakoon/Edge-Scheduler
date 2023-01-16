#!/usr/bin/env python3

import json
import time
import concurrent.futures
from kubernetes.client.rest import ApiException
import latency_labeler
from kubernetes import client, watch
from scheduler import CustomScheduler
from destroyer import Destroyer

def get_latency_matrix():
    with open('data.txt') as f:
        lines=[line.strip() for line in f.readlines()]
    
    node_names = lines[0].split(",")
    iot_services = lines[1].split(",")
    latency_matrix = {}

    for i, service in enumerate(iot_services):
        temp_dict = {}
        temp_ping_list = lines[i+2].split(",")
        for j in range (len(node_names)):
            temp_dict[node_names[j]] = int(temp_ping_list[j])
        latency_matrix[service] = temp_dict
    print("Latency Matrix Updated from the text file")
    return latency_matrix

def schedule():
    print("Custom Scheduler is starting...")
    scheduler = CustomScheduler()
    w = watch.Watch()
    # FIXME: API BUG: https://github.com/kubernetes-client/python/issues/547 -> we assume all scheduling will be OK
    for event in w.stream(scheduler.v1.list_namespaced_pod, "default"):
        print("Event Occured...")
        if event['object'].status.phase == "Pending" and event['type'] == "ADDED" and \
           event['object'].spec.scheduler_name == scheduler.scheduler_name:
            print("Scheduler Event Occured ...")
            try:
                print("Creating pod - named {} - request received".format(event['object'].metadata.name))
                res = scheduler.schedule(event['object'])
            except client.rest.ApiException as e:
                print(json.loads(e.body)['message'])

def destroyer():
    print("Destroyer is starting...")
    destroyer_ob = Destroyer()
    while(True):        
        latency_matrix = get_latency_matrix()
        destroyer_ob.set_latency_matrix(latency_matrix)
        destroyer_ob.check_destroyble()
        print("Wait for 15s...")
        time.sleep(5)

if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor() as executor:   
        scheduler_thread = executor.submit(schedule)   
        destroyer_thread = executor.submit(destroyer)


#            master-m02,   master-m03,   master-m04
# 
# iot_service_01   20,        15,                25
# iot_service_02   5,        20,                 5
# iot_service_03   25,        10,                15