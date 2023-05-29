import time
import yaml
from strategies.scaler import Scaler
from kubernetes import client, config
from strategies.config_update import ConfigUpdate


class Handler(object):

    def __init__(self):
        self.load_config()
        self.v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        self.latency_matrix = dict()
        self.bandwidth_matrix = dict()
        self.configs = ""
        self.scaler = Scaler()
        self.config_updater = ConfigUpdate()
        # Create an instance of the Scaler class

    @staticmethod
    def load_config(self):
        try:
            config.load_kube_config()
            with open('config.yaml') as f:
                self.configs = yaml.safe_load(f)
        except FileNotFoundError as e:
            # print("WARNING %s\n" % e)
            config.load_incluster_config()

    def set_latency_matrix(self, new_latency_matrix):
        self.latency_matrix = new_latency_matrix
        print("Handler - Latency Matrix Updated")

    def set_bandwidth_matrix(self, new_bandwidth_matrix):
        self.bandwidth_matrix = new_bandwidth_matrix
        print("Handler - Bandwidth Matrix Updated")

    def nodes_available(self):
        ready_nodes = []
        for n in self.v1.list_node().items:
            for status in n.status.conditions:
                if status.status == "True" and status.type == "Ready" and n.metadata.name != "master":
                    ready_nodes.append(n.metadata.name)
        return ready_nodes

    def get_pods_on_node(self, node_name, kube_system=False):
        if not kube_system:
            return [x for x in self.v1.list_pod_for_all_namespaces(watch=False).items if
                    (
                                x.metadata.namespace != 'kube-system' and x.metadata.namespace != 'kubernetes-dashboard') and x.spec.node_name == node_name and "ping-pod" not in x.metadata.name]
        else:
            return [x for x in self.v1.list_pod_for_all_namespaces(watch=False).items if x.spec.node_name == node_name]

    def check_pod(self, pod, node):
        priority = self.configs.get("priority")
        for key in priority.items():
            print("Handler - Checking", key, "between pod and node")
            match key:
                case "latency":
                    if pod.metadata.name not in self.latency_matrix:
                        print("Handler - No latency Violations")
                    else:
                        latency = int(self.latency_matrix.get(pod.metadata.name).get(node))
                        required_delay = int(pod.metadata.labels['qos_latency'])
                        if latency >= required_delay:
                            return "latency"
                    print("Handler - No latency Violations")

                case "bandwidth":
                    if pod.metadata.name not in self.bandwidth_matrix:
                        print("Handler - No bandwidth Violations")
                    else:
                        bandwidth = int(self.bandwidth_matrix.get(pod.metadata.name).get(node))
                        required_bandwidth = int(pod.metadata.labels['qos_bandwidth'])
                        if bandwidth >= required_bandwidth:
                            return "bandwidth"
                    print("Handler - No bandwidth Violations")
                case default:
                    return "none"

    def check_violations(self):
        print("Handler - Checking for Violations...")
        available_nodes = self.nodes_available()
        for node in available_nodes:
            pod_list_in_node = self.get_pods_on_node(node)
            for pod in pod_list_in_node:
                check = self.check_pod(pod, node)
                if check != "none":
                    print("Handler - ", check, "Violation Found")
                    priority = self.configs.get("priority")
                    values = priority.get(check)
                    values = values.split(",")
                    for value in values:
                        if check != "none":
                            match value:
                                case "migration":
                                    self.scaler.scale(pod)  # Call the scaler method from the Scaler instance
                                    time.sleep(60)
                                    check = self.check_pod(pod, node)
                                case "ota":
                                    ##TO_DO
                                    check = self.check_pod(pod, node)
                                case "config_update":
                                    self.config_updater.update_config(pod, node, self.bandwidth_matrix)
                                    check = self.check_pod(pod, node)
                        else:
                            break
