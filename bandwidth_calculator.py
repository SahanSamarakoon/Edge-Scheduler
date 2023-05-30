#!/usr/bin/env python3

from os import path

from kubernetes import client, config, utils
from kubernetes.client.apis import core_v1_api
from kubernetes.client.rest import ApiException
from kubernetes.stream import stream
import time
import itertools
import numpy as np


class BandwidthCalculator(object):

    def __init__(self):
        self.load_config()
        self.api = client.CoreV1Api()
        self.kube_client = client.AppsV1Api()
        self.nodes = self.get_worker_node_names()
        self.bandwidth_pod_list = ["bandwidth-pod{}".format(i) for i in range(1, len(self.nodes) + 1)]
        self.pod_nodes_mapping = {self.bandwidth_pod_list[i]: self.nodes[i] for i in
                                  range(len(self.bandwidth_pod_list))}
        self.pod_IPs = {self.bandwidth_pod_list[i]: None for i in range(len(self.bandwidth_pod_list))}
        self.permutations = []

    @staticmethod
    def load_config():
        try:
            config.load_kube_config()
        except FileNotFoundError as e:
            # print("WARNING %s\n" % e)
            config.load_incluster_config()

    def get_worker_node_names(self):
        worker_nodes = []
        for node in (self.api.list_node(watch=False)).items:
            if "master" != node.metadata.name:
                worker_nodes.append(node.metadata.name)
        print("--- {} worker nodes found.".format(str(len(worker_nodes))))
        print(worker_nodes)
        worker_nodes.sort()
        return worker_nodes

    def create_pod_template(self, pod_name, node_name):
        # Configureate Pod template container
        container = client.V1Container(
            name=pod_name,
            image='nishanjay98/bandwidth-monitor',
            command=['sleep', 'infinity'],
            image_pull_policy='IfNotPresent')

        # Create and configurate a spec section
        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(name=pod_name),
            spec=client.V1PodSpec(containers=[container], node_selector={"kubernetes.io/hostname": node_name}))
        print("--- Pod template created")
        return template

    def deploy(self, pod_IPs, pod_node_mapping):
        for pod, pod_ip in pod_IPs.items():
            if pod_ip == None:
                template = self.create_pod_template(pod, pod_node_mapping[pod])
                api_instance = client.CoreV1Api()
                namespace = 'default'
                body = client.V1Pod(metadata=template.metadata, spec=template.spec)
                api_response = api_instance.create_namespaced_pod(namespace, body)
                print("--- {} is deployed in {}".format(str(pod), str(pod_node_mapping[pod])))

    def check_deployment(self, bandwidth_pods):
        for pod in bandwidth_pods:
            running = False
            time_out = 120
            cur_time = 0
            while cur_time < time_out:
                resp = self.api.read_namespaced_pod(name=pod, namespace='default')
                if resp.status.phase == 'Running':
                    running = True
                    break
                time.sleep(1)
                cur_time += 1
            if not running:
                raise Exception("TIMEOUT: Pod {} is not running".format(pod))

    def get_bandwidth_pod_IPs(self, ping_pods, pod_IPs):
        ret = self.api.list_pod_for_all_namespaces(watch=False)
        for i in ret.items:
            if str(i.metadata.name) in ping_pods:
                pod_IPs[i.metadata.name] = i.status.pod_ip

        return pod_IPs

    def get_deployment_ip_mapping(self):
        deployment_ip_mapping = {}
        ret = self.api.list_pod_for_all_namespaces(watch=False)
        for i in ret.items:
            if "iot" in str(i.metadata.name):
                deployment_ip_mapping[i.metadata.name] = '192.168.190.85'
                # deployment_ip_mapping[i.metadata.name] = i.status.pod_ip
        return deployment_ip_mapping

    def measure_bandwidth(self, pod_from, end_device_IP):
        namespace = 'default'

        exec_command = ['/bin/sh', '-c', 'python main.py']

        resp = stream(self.api.connect_get_namespaced_pod_exec, pod_from, namespace,
                      command=exec_command,
                      stderr=True, stdin=False,
                      stdout=True, tty=False)
        bandwidth_measurements = []
        for line in resp.split('\n'):
            if (line != ""):
                print(line)
                bandwidth = float(line)
                bandwidth_measurements.append(bandwidth)
        np_rtt_times = np.array(bandwidth_measurements)
        rtt_value = np.percentile(np_rtt_times, 95)
        return rtt_value

    def get_zone_label_of_node(self, node_name):
        ret = self.api.list_node(watch=False)
        for node in ret.items:
            if (node.metadata.name == node_name):
                for label, label_value in node.metadata.labels.items():
                    if "area" in label:
                        return label_value

    def get_zone_label_of_service(self, pod_name):
        ret = self.api.list_pod_for_all_namespaces(watch=False)
        for pod in ret.items:
            if (str(pod.metadata.name) == pod_name):
                for label, label_value in pod.metadata.labels.items():
                    if "area" in label:
                        return label_value

    def do_measuring(self, deployment_ip_mapping, pod_nodes_mapping):
        if (len(self.permutations) == 0):
            self.permutations = list(
                itertools.product(list(deployment_ip_mapping.keys()), list(pod_nodes_mapping.values())))
        rtt_matrix = {i: {j: np.inf for (i, j) in self.permutations} for (i, j) in self.permutations}
        for i, j in self.permutations:
            # deployment_name = i.split('-')[0]
            end_device_zone = self.get_zone_label_of_service(i)
            edge_node_zone = self.get_zone_label_of_node(j)
            if (end_device_zone == edge_node_zone and rtt_matrix[i][j] == np.inf):
                for pod in pod_nodes_mapping:
                    if pod_nodes_mapping[pod] == j:
                        pod_name = pod
                        break
                print("\tMeasuring Bandwidth {} <-> {}".format(pod_name, deployment_ip_mapping[i]))
                rtt_matrix[i][j] = self.measure_bandwidth(pod_name, deployment_ip_mapping[i])
        return rtt_matrix

    def generate_bandwidth_matrix(self):
        print("--- --- Start generating bandwidth matrix")
        self.pod_IPs = self.get_bandwidth_pod_IPs(self.bandwidth_pod_list, self.pod_IPs)

        # Deploy bandwidth measurement pods
        self.deploy(self.pod_IPs, self.pod_nodes_mapping)
        self.check_deployment(self.bandwidth_pod_list)

        self.pod_IPs = self.get_bandwidth_pod_IPs(self.bandwidth_pod_list, self.pod_IPs)

        # Measure latency
        deployment_ip_mapping = self.get_deployment_ip_mapping()
        rtt_matrix = self.do_measuring(deployment_ip_mapping, self.pod_nodes_mapping)
        print("RTT MATRIX:")
        print(rtt_matrix)

        return rtt_matrix

    # To create IoT Service Pods:
    # kubectl create deployment iot-service --image=busybox --replicas=2 -- sleep infinity

    # To check pod ips
    # kubectl get pods --output=wide
