import time
import random
import json
from kubernetes.client.rest import ApiException
from kubernetes import client, config
from placeholder import Placeholder

class Destroyer(object):

    def __init__(self, latency_matrix):
        self.load_config()
        self.v1 = client.CoreV1Api()
        self.latency_matrix = latency_matrix

    @staticmethod
    def load_config():
        try:
            config.load_kube_config()
        except FileNotFoundError as e:
            # print("WARNING %s\n" % e)
            config.load_incluster_config()
    
    def nodes_available(self):
        ready_nodes = []
        for n in self.v1.list_node().items:
            for status in n.status.conditions:
                if status.status == "True" and status.type == "Ready":
                    ready_nodes.append(n.metadata.name)
        return ready_nodes
    
    def get_pods_on_node(self, node_name, kube_system=False):
        if not kube_system:
            return [x for x in self.v1.list_pod_for_all_namespaces(watch=False).items if
                    x.metadata.namespace != 'kube-system' and x.spec.node_name == node_name]
        else:
            return [x for x in self.v1.list_pod_for_all_namespaces(watch=False).items if x.spec.node_name == node_name]

    def check_destroyble():
        available_nodes = self.nodes_available()
        for node in available_nodes:
            pod_list_in_node = get_pods_on_node(node.metadata.name)


    def destroy(pod, namespace="default"):
        self.v1.delete_namespaced_pod(name=pod.metadata.name, namespace=namespace)