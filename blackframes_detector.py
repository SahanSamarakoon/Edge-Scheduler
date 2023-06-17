#!/usr/bin/env python3

from kubernetes import client, config
from kubernetes.stream import stream
import time
import itertools
import numpy as np

class BlackframesDetector(object):

    def __init__(self):
        self.load_config()
        self.api = client.CoreV1Api()
        self.kube_client = client.AppsV1Api()
        self.nodes = self.get_worker_node_names()
        self.black_frames_monitoring_pod_list = ["black-frames-monitoring-pod{}".format(i) for i in range(1, len(self.nodes) + 1)]
        self.pod_nodes_mapping = {self.black_frames_monitoring_pod_list[i]: self.nodes[i] for i in range(len(self.black_frames_monitoring_pod_list))}
        self.pod_IPs = {self.black_frames_monitoring_pod_list[i]: None for i in range(len(self.black_frames_monitoring_pod_list))}
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
    
    def get_label_value_of(self,key,pod_name):
        ret = self.api.list_pod_for_all_namespaces(watch=False)
        for pod in ret.items:
            if (str(pod.metadata.name) == pod_name):
                for label,label_value in pod.metadata.labels.items():
                    if key in label:
                        return label_value

    def create_pod_template(self,pod_name, node_name):
        # Configureate Pod template container
        container = client.V1Container(
            name=pod_name,
            image='nishanjay98/blackframes_monitor:1.0.0',
            command=['sleep','infinity'],
            image_pull_policy='IfNotPresent')

        # Create and configurate a spec section
        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(name=pod_name),
            spec=client.V1PodSpec(containers=[container], node_selector={"kubernetes.io/hostname": node_name}))
        print("--- Pod template created")
        return template


    def deploy(self,pod_IPs, pod_node_mapping):
        for pod, pod_ip in pod_IPs.items():
            if pod_ip == None:
                template = self.create_pod_template(pod, pod_node_mapping[pod])
                api_instance = client.CoreV1Api()
                namespace = 'default'
                body = client.V1Pod(metadata=template.metadata, spec=template.spec)
                api_response = api_instance.create_namespaced_pod(namespace, body)
                print("--- {} is deployed in {}".format(str(pod),str(pod_node_mapping[pod])))

    def check_deployment(self,black_frames_monitoring_pods):
        for pod in black_frames_monitoring_pods:
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


    def get_black_frames_monitoring_pod_IPs(self,black_frames_monitoring_pods, pod_IPs):
        ret = self.api.list_pod_for_all_namespaces(watch=False)
        for i in ret.items:
            if str(i.metadata.name) in black_frames_monitoring_pods:
                pod_IPs[i.metadata.name] = i.status.pod_ip

        return pod_IPs

    def get_pods_esp32_map(self):
        pods_esp32_map = {}
        ret = self.api.list_pod_for_all_namespaces(watch=False)
        for i in ret.items:
            pod_name = i.metadata.name
            if "iot" in str(pod_name):
                pods_esp32_map[pod_name] = {}
                pods_esp32_map[pod_name]["ip"] = self.get_label_value_of("esp32_ip",pod_name)
                pods_esp32_map[pod_name]["port"] = self.get_label_value_of("port",pod_name)
        return pods_esp32_map

    def check_black_frames(self,pod_from, esp32_ip,port):
        namespace = 'default'
        python_command = f'python blackframes_monitor.py --url "http://{esp32_ip}:{port}/videofeed?username=&password=" --intensity 10 --count 30'

        exec_command = ['/bin/sh', '-c', python_command]

        resp = stream(self.api.connect_get_namespaced_pod_exec, pod_from, namespace,
                    command=exec_command,
                    stderr=True, stdin=False,
                    stdout=True, tty=False)
        black_frames_detections = []
        for line in resp.split('\n'):
                if(line!=""):
                    black_frame_detected = int(line)
                    black_frames_detections.append(black_frame_detected)
        black_frames_count = black_frames_detections.count(0)
        if (black_frames_count > len(black_frames_detections)/4):
            return 0
        return 1

    def is_iot_pod_available_on_node(self,node_name):
        # Get the list of pods in the cluster
        pods = self.api.list_pod_for_all_namespaces().items
        iot_pod_available = False

        for pod in pods:
            if ("iot" in str(pod.metadata.name) and pod.spec.node_name == node_name):
                iot_pod_available = True
                break
        return iot_pod_available

    def do_measuring(self,pods_esp32_map, pod_nodes_mapping):
        if (len(self.permutations)==0):
            self.permutations = list(itertools.product(list(pods_esp32_map.keys()),list(pod_nodes_mapping.values())))
        black_frames_availability_matrix = {i: {j:np.inf for (i, j) in self.permutations } for (i, j) in self.permutations}
        for i, j in self.permutations:
            iot_pod_available = self.is_iot_pod_available_on_node(j)
            # deployment_name = i.split('-')[0]
            if (iot_pod_available and black_frames_availability_matrix[i][j] == np.inf):
                for pod in pod_nodes_mapping:
                    if pod_nodes_mapping[pod]==j:
                        pod_name = pod
                        break
                print("\tChecking Black Frames {} <-> {}".format(pod_name, pods_esp32_map[i]["ip"]))
                black_frames_availability_matrix[i][j] = self.check_black_frames(pod_name, pods_esp32_map[i]["ip"] , pods_esp32_map[i]["port"])
        return black_frames_availability_matrix


    def generate_blackframes_availability_matrix(self):
        print("--- --- Start detecting black frames")
        self.pod_IPs = self.get_black_frames_monitoring_pod_IPs(self.black_frames_monitoring_pod_list, self.pod_IPs)
        
        # Deploy bandwidth measurement pods
        self.deploy(self.pod_IPs, self.pod_nodes_mapping)
        self.check_deployment(self.black_frames_monitoring_pod_list)

        self.pod_IPs = self.get_black_frames_monitoring_pod_IPs(self.black_frames_monitoring_pod_list, self.pod_IPs)

        # Measure latency
        pods_esp32_map = self.get_pods_esp32_map()
        black_frames_availability_matrix = self.do_measuring(pods_esp32_map, self.pod_nodes_mapping)
        print("BLACK FRAMES AVAILABILITY MATRIX:")
        print(black_frames_availability_matrix)

        return black_frames_availability_matrix

    # To create IoT Service Pods:
    # kubectl create deployment iot-service --image=busybox --replicas=2 -- sleep infinity

    # To check pod ips
    # kubectl get pods --output=wide

    # command to run python file
    # python main.py --url "http://192.168.219.185:6677/videofeed?username=\&password=" --count 15
    # python main.py --url "http://192.168.128.235" --quality "5"