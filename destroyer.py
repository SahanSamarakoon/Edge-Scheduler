#!/usr/bin/env python3

import time
import random
import json
from kubernetes.client.rest import ApiException
from kubernetes import client, config
from placeholder import Placeholder

class Destroyer(object):

    def __init__(self):
        self.name = "Name"
        self.load_config()
        self.v1 = client.CoreV1Api()
        self.latency_matrix = dict()

    @staticmethod
    def load_config():
        try:
            config.load_kube_config()
        except FileNotFoundError as e:
            # print("WARNING %s\n" % e)
            config.load_incluster_config()

    def set_latency_matrix(self, new_latency_matrix):
        self.latency_matrix = new_latency_matrix
        print("Destroyer Latency Matrix Updated")
    
    def nodes_available(self):
        ready_nodes = []
        for n in self.v1.list_node().items:
            for status in n.status.conditions:
                if status.status == "True" and status.type == "Ready" and n.metadata.name!="master":
                    ready_nodes.append(n.metadata.name)
        return ready_nodes
    
    def get_pods_on_node(self, node_name, kube_system=False):
        if not kube_system:
            return [x for x in self.v1.list_pod_for_all_namespaces(watch=False).items if
                    x.metadata.namespace != 'kube-system' and x.spec.node_name == node_name]
        else:
            return [x for x in self.v1.list_pod_for_all_namespaces(watch=False).items if x.spec.node_name == node_name]

    def check_pod(self, pod, node):
        print("Checking Latency between pod and node")
        iot_device_servicename = pod.metadata.labels['app']
        latency = int(self.latency_matrix.get(iot_device_servicename).get(node))
        required_delay = int(pod.metadata.labels['qos_latency'])
        if latency >= required_delay:
            return self.check_again(pod, node, iot_device_servicename, required_delay)
        return False

    def check_again(self, pod, node, iot_device_servicename, required_delay):
        print("Again Checking Latency between pod and node after 30s")
        latency = int(self.latency_matrix.get(iot_device_servicename).get(node))
        if latency >= required_delay:
            return True

    def check_destroyble(self):
        print("Checking for Latency Violations...")
        available_nodes = self.nodes_available()
        for node in available_nodes:
            pod_list_in_node = self.get_pods_on_node(node)
            for pod in pod_list_in_node:
                if (self.check_pod(pod, node)):
                    print("Destroying {} in ".format(pod.metadata.name, node))
                    self.destroy(pod)

    def destroy(self, pod, namespace="default"):
        self.v1.delete_namespaced_pod(name=pod.metadata.name, namespace=namespace)
        time.sleep(30)