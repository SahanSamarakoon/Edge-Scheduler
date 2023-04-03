#!/usr/bin/env python3

import json
import time
import concurrent.futures
from kubernetes.client.rest import ApiException
import latency_labeler
from kubernetes import client, watch
from scheduler import CustomScheduler
from handler import Handler
from latency_labeler import LatencyLabeler

latency_matrix = {}

def update_latency_matrix():
    
    latency_labeller_ob = LatencyLabeler()
    while(True):
        time.sleep(5)
        latency_matrix = latency_labeller_ob.labeling()
    # with open('data.txt') as f:
    #     lines=[line.strip() for line in f.readlines()]
    
    # node_names = lines[0].split(",")
    # iot_services = lines[1].split(",")
    # latency_matrix = {}

    # for i, service in enumerate(iot_services):
    #     temp_dict = {}
    #     temp_ping_list = lines[i+2].split(",")
    #     for j in range (len(node_names)):
    #         temp_dict[node_names[j]] = int(temp_ping_list[j])
    #     latency_matrix[service] = temp_dict
        print("Latency Matrix Updated")

def schedule():
    print("Custom Scheduler is starting...")
    scheduler = CustomScheduler()
    w = watch.Watch()
    for event in w.stream(scheduler.v1.list_namespaced_pod, "default"):
        scheduler.set_latency_matrix(latency_matrix)
        print("Event Occured...")
        if event['object'].status.phase == "Pending" and event['type'] == "ADDED" and \
           event['object'].spec.scheduler_name == scheduler.scheduler_name:
            print("Scheduler Event Occured ...")
            try:
                print("Creating pod - named {} - request received".format(event['object'].metadata.name))
                res = scheduler.schedule(event['object'])
            except client.rest.ApiException as e:
                print(json.loads(e.body)['message'])
                
def handler():
    print("Handler is starting...")
    handler_ob = Handler()
    while(True):        
        handler_ob.set_latency_matrix(latency_matrix)
        handler_ob.check_violations()
        print("Handler - Wait for 15s...")
        time.sleep(5)

if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor() as executor: 
        latency_labeler = excutor.submit(update_latency_matrix)
        scheduler_thread = executor.submit(schedule)   
        handler_thread = executor.submit(handler)
        


#            master-m02,   master-m03,   master-m04
# 
# iot_service_01   20,        15,                25
# iot_service_02   5,        20,                 5
# iot_service_03   25,        10,                15