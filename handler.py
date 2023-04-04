#!/usr/bin/env python3

import time
import random
import json
from kubernetes.client.rest import ApiException
from kubernetes import client, config

class Handler(object):

    def __init__(self):
        self.load_config()
        self.v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
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
        print("Handler - Latency Matrix Updated")
    
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
                    (x.metadata.namespace != 'kube-system' and x.metadata.namespace != 'kubernetes-dashboard') and x.spec.node_name == node_name and "ping-pod" not in x.metadata.name]
        else:
            return [x for x in self.v1.list_pod_for_all_namespaces(watch=False).items if x.spec.node_name == node_name]

    def check_pod(self, pod, node):
        print("Handler - Checking Latency between pod and node")
        if pod.metadata.name not in self.latency_matrix:
            print("Handler - No Violations")
            return False
        else:    
            latency = int(self.latency_matrix.get(pod.metadata.name).get(node))
        required_delay = int(pod.metadata.labels['qos_latency'])
        if latency >= required_delay:
            return True
        print("Handler - No Violations")
        return False

    def check_violations(self):
        print("Handler - Checking for Latency Violations...")
        available_nodes = self.nodes_available()
        for node in available_nodes:
            pod_list_in_node = self.get_pods_on_node(node)
            for pod in pod_list_in_node:
                if (self.check_pod(pod, node)):
                    print("Handler - Latency Violated")
                    self.scaler(pod)

    def scaler(self, pod, namespace="default"):
        print("Handler - Upscaling {}".format(pod.metadata.name))
        current_scaling = self.apps_v1.read_namespaced_deployment_scale(name=pod.metadata.name.split("-")[0], namespace=namespace)
        current_scaling = current_scaling.status.replicas
        self.apps_v1.patch_namespaced_deployment(name=pod.metadata.name.split("-")[0], namespace=namespace, body={"spec": {"replicas": current_scaling + 1}})
        print("Handler - Sleeping for 30s")
        time.sleep(5)
        print("Handler - Downscaling {}".format(pod.metadata.name))
        self.v1.delete_namespaced_pod(name=pod.metadata.name, namespace=namespace, grace_period_seconds=0)
        self.apps_v1.patch_namespaced_deployment(name=pod.metadata.name.split("-")[0], namespace=namespace, body={"spec": {"replicas": current_scaling}})