#!/usr/bin/env python3

from os import path

from kubernetes import client, config, utils
from kubernetes.client.apis import core_v1_api
from kubernetes.client.rest import ApiException
from kubernetes.stream import stream
import time
import itertools
import numpy as np

class LatencyCalculator(object):

    def __init__(self):
        self.load_config()
        self.api = client.CoreV1Api()
        self.kube_client = client.AppsV1Api()
        self.permutations = []

    @staticmethod
    def load_config():
        try:
            config.load_kube_config()
        except FileNotFoundError as e:
            # print("WARNING %s\n" % e)
            config.load_incluster_config()

    def get_worker_node_names(self):
        return [node.metadata.name for node in (self.api.list_node(watch=False)).items if "master" != node.metadata.name]


    def create_pod_template(self,pod_name, node_name):
        # Configureate Pod template container
        container = client.V1Container(
            name=pod_name,
            image='busybox',
            command=['sleep','infinity'],
            image_pull_policy='IfNotPresent')

        # Create and configurate a spec section
        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(name=pod_name),
            spec=client.V1PodSpec(containers=[container], node_selector={"kubernetes.io/hostname": node_name}))

        return template


    def deploy_rtt_deployment(self,pod_IPs, pod_node_mapping):
        for pod, pod_ip in pod_IPs.items():
            if pod_ip == None:
                template = self.create_pod_template(pod, pod_node_mapping[pod])
                api_instance = client.CoreV1Api()
                namespace = 'default'
                body = client.V1Pod(metadata=template.metadata, spec=template.spec)
                api_response = api_instance.create_namespaced_pod(namespace, body)


    def check_rtt_deployment(self,ping_pods):
        for pod in ping_pods:
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


    def get_ping_pod_IPs(self,ping_pods, pod_IPs):
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
                deployment_ip_mapping[i.metadata.name] = '192.168.4.1'
        return deployment_ip_mapping

    def measure_latency(self,pod_from, end_device_IP):
        namespace = 'default'

        exec_command = ['/bin/sh', '-c', 'ping -c 10 {}'.format(end_device_IP)]

        resp = stream(self.api.connect_get_namespaced_pod_exec, pod_from, namespace,
                    command=exec_command,
                    stderr=True, stdin=False,
                    stdout=True, tty=False)
        rtt_times = []
        for line in resp.split('\n'):
            if 'time=' in line:
                rtt_time = float(line.split('=')[-1][:-3])
                rtt_times.append(rtt_time)
        np_rtt_times = np.array(rtt_times)
        rtt_value = np.percentile(np_rtt_times, 95)
        return rtt_value


    def get_rtt_labels_of_node(self,node, rtt_matrix, ping_pods, POD_NODES_MAP):
        # FIXME: Currently we handle RTTs in millisec
        rtt_list = {}

        for i in ping_pods:
            if i != node:
                rtt = rtt_matrix[(node, i)]
                rtt_ms = int(round(rtt))
                try:
                    rtt_list["rtt-{}".format(rtt_ms)].append(POD_NODES_MAP[i])
                except:
                    rtt_list["rtt-{}".format(rtt_ms)] = [POD_NODES_MAP[i]]

        return rtt_list

    def get_zone_label_of_node(self,node_name):
        ret = self.api.list_node(watch=False)
        for node in ret.items:
            if (node.metadata.name == node_name):
                for label,label_value in node.metadata.labels.items():
                    if "area" in label:
                            return label_value

    def get_zone_label_of_service(self,pod_name):
        ret = self.api.list_pod_for_all_namespaces(watch=False)
        for pod in ret.items:
            if (str(pod.metadata.name) == pod_name):
                for label,label_value in pod.metadata.labels.items():
                    if "area" in label:
                            return label_value

    def do_labeling(self,node_name, labels):
        # FIXME: This method could be stucked into a unvalid state: if we already delete the old rtt labels,
        #        but due to a failure, the new labels are not saved

        # Get old labels
        old_labels = []
        ret = self.api.list_node(watch=False)
        for node in ret.items:
            for label in node.metadata.labels:
                if "rtt" in label:
                    if label not in old_labels:
                        old_labels.append(label)

        # Delete old labels
        old_labels_dict = {label: None for label in old_labels}
        api_instance = client.CoreV1Api()
        body = {
            "metadata": {
                "labels": old_labels_dict
            }
        }
        api_response = api_instance.patch_node(node_name, body)

        # Upload new labels
        for key, value in labels.items():
            api_instance = client.CoreV1Api()
            label_value = "_".join(value)
            body = {
                "metadata": {
                    "labels": {
                        key: label_value
                    }
                }
            }
            api_response = api_instance.patch_node(node_name, body)


    def do_measuring(self,deployment_ip_mapping, pod_nodes_mapping):
        if (len(self.permutations)==0):
            self.permutations = list(itertools.product(list(deployment_ip_mapping.keys()),list(pod_nodes_mapping.values())))
        rtt_matrix = {i: {j:np.inf for (i, j) in self.permutations } for (i, j) in self.permutations}
        for i, j in self.permutations:
            # deployment_name = i.split('-')[0]
            end_device_zone = self.get_zone_label_of_service(i)
            edge_node_zone = self.get_zone_label_of_node(j)
            if (end_device_zone==edge_node_zone and rtt_matrix[i][j] == np.inf):
                for pod in pod_nodes_mapping:
                    if pod_nodes_mapping[pod]==j:
                        pod_name = pod
                        break
                print("\tMeasuring {} <-> {}".format(pod_name, deployment_ip_mapping[i]))
                rtt_matrix[i][j] = self.measure_latency(pod_name, deployment_ip_mapping[i])
        return rtt_matrix


    def labeling(self):
        nodes = self.get_worker_node_names()
        ping_pod_list = ["ping-pod{}".format(i) for i in range(1, len(nodes) + 1)]
        pod_nodes_mapping = {ping_pod_list[i]: nodes[i] for i in range(len(ping_pod_list))}
        pod_IPs = {ping_pod_list[i]: None for i in range(len(ping_pod_list))}
        pod_IPs = self.get_ping_pod_IPs(ping_pod_list, pod_IPs)

        # Deploy latency measurement pods
        self.deploy_rtt_deployment(pod_IPs, pod_nodes_mapping)
        self.check_rtt_deployment(ping_pod_list)

        pod_IPs = self.get_ping_pod_IPs(ping_pod_list, pod_IPs)

        # Measure latency
        # rtt_matrix = do_measuring(pod_IPs, ping_pod_list)
        deployment_ip_mapping = self.get_deployment_ip_mapping()
        rtt_matrix = self.do_measuring(deployment_ip_mapping, pod_nodes_mapping)
        print("RTT MATRIX:")
        print(rtt_matrix)
        print("DONE")
        # Do labeling
        # for pod in ping_pod_list:
        #     labels = get_rtt_labels_of_node(pod, rtt_matrix, ping_pod_list, pod_nodes_mapping)
        #     do_labeling(pod_nodes_mapping[pod], labels)

        return rtt_matrix

    # def main(self):
    #     print("Start labeling...")
    #     rtt_matrix = labeling()
    #     print("RTT MATRIX:")
    #     print(rtt_matrix)
    #     print("DONE")


    # if __name__ == '__main__':
    #     main()

    # To create IoT Service Pods:
    # kubectl create deployment iot-service --image=busybox --replicas=2 -- sleep infinity

    # To check pod ips
    # kubectl get pods --output=wide
