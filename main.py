#!/usr/bin/env python3

import json
import time
import concurrent.futures
from kubernetes.client.rest import ApiException
from kubernetes import client, watch
from scheduler import CustomScheduler
from handler import Handler
from latency_calculator import LatencyCalculator
from bandwidth_calculator import BandwidthCalculator

latency_matrix = {}
bandwidth_matrix = {}


def update_latency_matrix():
    latency_calculator_ob = LatencyCalculator()
    while (True):
        time.sleep(5)
        global latency_matrix
        latency_matrix_cpy = latency_calculator_ob.labeling()
        latency_matrix = latency_matrix_cpy
        print("Latency Matrix Updated")


def update_bandwidth_matrix():
    bandwidth_calculator_ob = BandwidthCalculator()
    while (True):
        time.sleep(5)
        global bandwidth_matrix
        bandwidth_matrix_cpy = bandwidth_calculator_ob.labeling()
        bandwidth_matrix = bandwidth_matrix_cpy
        print("Bandwidth Matrix Updated")


def schedule():
    print("Custom Scheduler is starting...")
    scheduler = CustomScheduler()
    w = watch.Watch()
    for event in w.stream(scheduler.v1.list_namespaced_pod, "default"):
        scheduler.set_latency_matrix(latency_matrix)
        scheduler.set_bandwidth_matrix(bandwidth_matrix)
        print("Event Occurred...")
        if event['object'].status.phase == "Pending" and event['type'] == "ADDED" and \
                event['object'].spec.scheduler_name == scheduler.scheduler_name:
            print("Scheduler Event Occurred ...")
            try:
                print("Creating pod - named {} - request received".format(event['object'].metadata.name))
                res = scheduler.schedule(event['object'])
            except client.rest.ApiException as e:
                print(json.loads(e.body)['message'])


def handler():
    print("Handler is starting...")
    handler_ob = Handler()
    while (True):
        handler_ob.set_latency_matrix(latency_matrix)
        handler_ob.set_bandwidth_matrix(bandwidth_matrix)
        handler_ob.check_violations()
        print("Handler - Wait for 15s...")
        time.sleep(5)


if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor() as executor:
        latency_labeler = executor.submit(update_latency_matrix)
        bandwidth_labeler = executor.submit(update_bandwidth_matrix)
        scheduler_thread = executor.submit(schedule)
        handler_thread = executor.submit(handler)
