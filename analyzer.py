import time
import yaml
from strategies.migration import Migration
from kubernetes import client, config
from strategies.config_handler import ConfigHandler


class Analyzer(object):

    def __init__(self):
        self.load_config()
        self.v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        self.latency_matrix = dict()
        self.bandwidth_matrix = dict()
        self.rules = {}
        self.scaler = Migration()
        self.config_updater = ConfigHandler()

    @staticmethod
    def load_config(self):
        try:
            config.load_kube_config()
            with open('rule_collection.yaml') as f:
                self.rules = yaml.safe_load(f)
        except FileNotFoundError as e:
            print("WARNING %s\n" % e)
            config.load_incluster_config()

    def set_latency_matrix(self, new_latency_matrix):
        self.latency_matrix = new_latency_matrix
        print("Analyzer - Latency Matrix Updated")

    def set_bandwidth_matrix(self, new_bandwidth_matrix):
        self.bandwidth_matrix = new_bandwidth_matrix
        print("Analyzer - Bandwidth Matrix Updated")

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
                    (x.metadata.namespace != 'kube-system' and x.metadata.namespace != 'kubernetes-dashboard') and x.spec.node_name == node_name and "ping-pod" not in x.metadata.name]
        else:
            return [x for x in self.v1.list_pod_for_all_namespaces(watch=False).items if x.spec.node_name == node_name]

    def check_pod(self, pod, node):
        priority = self.rules.get("priority").get(pod.metadata.labels['app'])
        for key in priority.items():
            print("Analyzer - Checking", key, "between pod and node")
            match key:
                case "latency":
                    if pod.metadata.name not in self.latency_matrix:
                        print("Analyzer - No latency Violations")
                    else:
                        latency = int(self.latency_matrix.get(pod.metadata.name).get(node))
                        required_delay = int(pod.metadata.labels['qos_latency'])
                        if latency >= required_delay:
                            return "latency"

                case "bandwidth":
                    if pod.metadata.name not in self.bandwidth_matrix:
                        print("Analyzer - No bandwidth Violations")
                    else:
                        bandwidth = int(self.bandwidth_matrix.get(pod.metadata.name).get(node))
                        required_bandwidth = int(pod.metadata.labels['qos_bandwidth'])
                        if bandwidth >= required_bandwidth:
                            return "bandwidth"

                case "distortion":
                    if pod.metadata.name not in self.bandwidth_matrix:
                        print("Analyzer - No distortion Violations")
                    else:
                        bandwidth = int(self.bandwidth_matrix.get(pod.metadata.name).get(node))
                        required_bandwidth = int(pod.metadata.labels['qos_bandwidth'])
                        if bandwidth >= required_bandwidth:
                            return "distortion"

                case default:
                    return "none"

    def check_violations(self):
        print("Analyzer - Checking for Violations...")
        available_nodes = self.nodes_available()
        for node in available_nodes:
            pod_list_in_node = self.get_pods_on_node(node)
            for pod in pod_list_in_node:
                check = self.check_pod(pod, node)
                if check != "none":
                    print("Analyzer - ", check, " Violation Found")
                    priority = self.rules.get("priority").get(pod.metadata.labels['app'])
                    values = priority.get(check)
                    values = values.split(",")
                    for value in values:
                        if check != "none":
                            match value:
                                case "migration":
                                    self.scaler.scale(pod)  # Call the scaler method from the Migration instance
                                    time.sleep(60)
                                    check = self.check_pod(pod, node)
                                case "firmware":
                                    ##TO_DO
                                    time.sleep(60)
                                    check = self.check_pod(pod, node)
                                case "reconfiguration":
                                    available_bandwidth = int(self.bandwidth_matrix.get(pod.metadata.name).get(node))
                                    self.config_updater.update_config(pod, available_bandwidth)
                                    time.sleep(60)
                                    check = self.check_pod(pod, node)
                        else:
                            break