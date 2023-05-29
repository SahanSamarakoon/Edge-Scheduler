#!/usr/bin/env python3

import time
import random
import yaml
from kubernetes import client, config
from placeholder import Placeholder


class CustomScheduler(object):

    def __init__(self, scheduler_name="custom-scheduler"):
        self.load_config()
        self.v1 = client.CoreV1Api()
        self.scheduler_name = scheduler_name
        self.placeholders = []
        self.rescedules = dict()
        self.latency_matrix = dict()
        self.bandwidth_matrix = dict()
        self.configs = ""

    @staticmethod
    def load_config(self):
        try:
            config.load_kube_config()
            with open('config.yaml') as f:
                self.configs = yaml.safe_load(f)
        except FileNotFoundError as e:
            # print("WARNING %s\n" % e)
            config.load_incluster_config()

    @staticmethod
    def convert_to_int(resource_string):
        if 'Ki' in resource_string:
            return int(resource_string.split('K')[0]) * 1024
        elif 'Mi' in resource_string:
            return int(resource_string.split('M')[0]) * (1024 ** 2)
        elif 'Gi' in resource_string:
            return int(resource_string.split('G')[0]) * (1024 ** 3)

    def set_latency_matrix(self, new_latency_matrix):
        self.latency_matrix = new_latency_matrix
        print("Scheduler - Latency Matrix Updated")

    def set_bandwidth_matrix(self, new_bandwidth_matrix):
        self.bandwidth_matrix = new_bandwidth_matrix
        print("Scheduler - Bandwidth Matrix Updated")

    def get_pods_on_node(self, node_name, kube_system=False):
        if not kube_system:
            return [x for x in self.v1.list_pod_for_all_namespaces(watch=False).items if
                    x.metadata.namespace != 'kube-system' and x.spec.node_name == node_name]
        else:
            return [x for x in self.v1.list_pod_for_all_namespaces(watch=False).items if x.spec.node_name == node_name]

    def get_node_from_name(self, node_name):
        return next(x for x in self.v1.list_node().items if x.metadata.name == node_name)

    def nodes_available(self, iot_device_area):
        ready_nodes = []
        nodes = [node for node in (self.v1.list_node(watch=False)).items if "master" != node.metadata.name]
        for n in nodes:
            if n.metadata.labels['area'] == iot_device_area:
                for status in n.status.conditions:
                    if status.status == "True" and status.type == "Ready":
                        ready_nodes.append(n.metadata.name)
        return ready_nodes

    def get_nodes_in_radius(self, pod_name, iot_device_area, required_delay, required_bandwidth):
        available_nodes = self.nodes_available(iot_device_area)
        latency_list = self.latency_matrix.get(pod_name)
        bandwidth_list = self.bandwidth_matrix.get(pod_name)

        if pod_name not in self.latency_matrix:
            latency_list = {}
            for node in available_nodes:
                latency_list[str(node)] = 0

        if pod_name not in self.bandwidth_matrix:
            bandwidth_list = {}
            for node in available_nodes:
                bandwidth_list[str(node)] = 1000

        priority = self.configs.get("priority")

        matrices = []
        for priority_name in list(priority.keys()):
            matrices.append(latency_list if priority_name == "latency" else bandwidth_list)

        node_names_array = set()
        for matrix in matrices:
            node_names_scoped = set()
            for edge, status in matrix.items():
                requirement = required_delay if list(priority.keys())[0] == "latency" else required_bandwidth
                if status <= requirement:
                    node_names_scoped.add(edge)
            node_names_array.add(node_names_scoped)

        # Find common nodes
        intersection = set()

        for set in node_names_array:
            intersection.update(set)

        # Return common nodes if they exist, else return nodes from matrix_first
        if intersection:
            node_names = intersection
        else:
            return node_names_array[0]

        return [self.get_node_from_name(x) for x in node_names if x in available_nodes]

    def narrow_nodes_by_capacity(self, pod, node_list):
        return_list = []
        for n in node_list:
            if self.calculate_available_memory(n) > self.get_pod_memory_request(pod):
                return_list.append(n)
        return return_list

    def calculate_available_memory(self, node):
        pods_on_node = self.get_pods_on_node(node.metadata.name)
        sum_reserved_memory = sum([self.get_pod_memory_request(y) for y in pods_on_node])
        allocatable_memory = self.convert_to_int(node.status.allocatable['memory'])
        try:
            sum_reserved_memory += next(x.required_memory for x in self.placeholders if x.node == node.metadata.name)
        except StopIteration:
            pass
        return allocatable_memory - sum_reserved_memory

    def reschedule_pod(self, new_pod, new_nodes_in_radius):
        new_memory_request = self.get_pod_memory_request(new_pod)
        for n in new_nodes_in_radius:
            any_reschedulable, old_pod, reschedule_node = self.get_reschedulable(n, new_memory_request)
            if any_reschedulable:
                self.do_reschedule(old_pod, reschedule_node)
                return old_pod.metadata.name
        return None

    def get_pod_memory_request(self, pod):
        return sum([self.convert_to_int(x.resources.requests['memory']) for x in pod.spec.containers if
                    x.resources.requests is not None])

    def get_reschedulable(self, node, new_memory_request):
        pods_on_node = self.get_pods_on_node(node.metadata.name)
        for old_pod in pods_on_node:
            old_memory_request = self.get_pod_memory_request(old_pod)
            if old_memory_request >= new_memory_request:
                old_service_name = next(x for x in old_pod.metadata.labels.keys() if 'app' in x)
                old_required_delay = int(old_pod.metadata.labels['qos_latency'])
                old_required_bandwidth = int(old_pod.metadata.labels['qos_bandwidth'])
                old_service_area = old_pod.metadata.labels['area']
                old_nodes_in_radius = self.narrow_nodes_by_capacity(old_pod,
                                                                    self.get_nodes_in_radius(old_service_name,
                                                                                             old_service_area,
                                                                                             old_required_delay,
                                                                                             old_required_bandwidth))
                old_placeholder = self.get_placeholder_by_pod(old_pod)
                if len([x for x in old_nodes_in_radius if x.metadata.name != old_placeholder.node]) > 0:
                    return True, old_pod, \
                        random.choice([x for x in old_nodes_in_radius if x.metadata.name != old_placeholder.node])
        return False, None, None

    def get_placeholder_by_pod(self, pod):
        try:
            return next(x for x in self.placeholders if pod.metadata.name.split('-')[0] in x.pods)
        except StopIteration:
            return None

    def do_reschedule(self, old_pod, reschedule_node):
        self.patch_pod(old_pod, reschedule_node.metadata.name)

    def patch_pod(self, pod, node, namespace="default"):
        # FIXME: '-' character assumed as splitting character
        self.rescedules[pod.metadata.name.split('-')[0]] = node
        self.v1.delete_namespaced_pod(name=pod.metadata.name, namespace=namespace)

    def bind(self, pod, node, namespace="default"):
        target = client.V1ObjectReference(api_version='v1', kind='Node', name=node)
        meta = client.V1ObjectMeta()
        meta.name = pod.metadata.name

        body = client.V1Binding(target=target, metadata=meta)

        try:
            print("INFO Pod: %s placed on: %s" % (pod.metadata.name, node))
            api_response = self.v1.create_namespaced_pod_binding(name=pod.metadata.name, namespace=namespace, body=body)
            return api_response
        except Exception as e:
            # print("Warning when calling CoreV1Api->create_namespaced_pod_binding: %s\n" % e)
            pass

    def reused_placeholder_used_pod_node(self, placeholder, pod, nodes_enough_resource):
        placeholder_memory_matrix = self.get_memory_matrix(placeholder, nodes_enough_resource)
        if any(placeholder_memory_matrix[x] + self.get_pod_memory_request(pod) <= placeholder.required_memory
               for x in placeholder_memory_matrix.keys()):
            return True, next(x for x in nodes_enough_resource if x.metadata.name in placeholder_memory_matrix.keys()
                              and placeholder_memory_matrix[x.metadata.name] +
                              self.get_pod_memory_request(pod) <= placeholder.required_memory)
        return False, None

    def assign_placeholder(self, pod, nodes_less_resource, nodes_enough_resource):

        # len(nodes_enough_resource) + len(nodes_less_resource) is always greater than 1!
        node_names_in_rad = [x.metadata.name for x in nodes_less_resource]
        node_names_in_rad += [x.metadata.name for x in nodes_enough_resource]
        placeholders_in_rad = self.narrow_placeholders_in_rad(node_names_in_rad)

        for placeholder in placeholders_in_rad:
            is_any_usable, excluded_list = self.reused_placeholder_unused_pod_node(placeholder, nodes_enough_resource)
            if is_any_usable:
                self.add_pod_to_placeholder(pod, placeholder)
                return [x.metadata.name not in excluded_list for x in nodes_enough_resource]

        for placeholder in placeholders_in_rad:
            is_any_usable, chosen_node = self.reused_placeholder_used_pod_node(placeholder, pod, nodes_enough_resource)
            if is_any_usable:
                self.add_pod_to_placeholder(pod, placeholder)
                return [chosen_node]

        # TODO: Another option, when we have to increase the placeholder's size
        #  for assigning the pod somewhere in the radius

        if len(nodes_enough_resource) > 1:
            placeholder = self.create_new_placeholder(nodes_enough_resource)
            self.add_pod_to_placeholder(pod, placeholder, self.get_pod_memory_request(pod))
            return [x for x in nodes_enough_resource if x.metadata.name != placeholder.node]
        else:
            print("WARNING Can not create placeholder for this pod!")
            return nodes_enough_resource

    def narrow_placeholders_in_rad(self, node_names_in_rad):
        placeholders_in_rad = []
        for placeholder in self.placeholders:
            if placeholder.node in node_names_in_rad:
                placeholders_in_rad.append(placeholder)
        return placeholders_in_rad

    def get_node_from_podname_or_nodename(self, previous_element_name):
        if previous_element_name in [x.metadata.name for x in self.v1.list_node().items]:
            return self.get_node_from_name(previous_element_name)
        else:
            return self.get_node_from_name(next(x for x in self.v1.list_pod_for_all_namespaces(watch=False).items if
                                                previous_element_name in x.metadata.name).spec.node_name)

    def reused_placeholder_unused_pod_node(self, placeholder, nodes_enough_resource):
        covered_nodes = [self.get_node_from_podname_or_nodename(x) for x in placeholder.pods]
        covered_node_names = [y.metadata.name for y in covered_nodes]
        if any(x.metadata.name not in covered_node_names + [placeholder.node] for x in nodes_enough_resource):
            return True, covered_node_names + [placeholder.node]
        return False, None

    def add_pod_to_placeholder(self, pod, placeholder, extra_memory=0):
        placeholder.pods.add(pod.metadata.name.split('-')[0])
        placeholder.required_memory += extra_memory

    def create_new_placeholder(self, nodes_enough_resource):
        placeholder = Placeholder()
        placeholder.node = random.choice(nodes_enough_resource).metadata.name
        # placeholder.node = nodes_enough_resource[-1].metadata.name
        # placeholder.node = next(x for x in nodes_enough_resource if x.metadata.name == 'edge-3').metadata.name
        self.placeholders.append(placeholder)
        return placeholder

    def check_destroyed(self, pod, node):
        iot_device_servicename = pod.metadata.labels['app']
        latency = int(self.latency_matrix.get(iot_device_servicename).get(node.metadata.name))
        bandwidth = int(self.bandwidth_matrix.get(iot_device_servicename).get(node.metadata.name))
        required_delay = int(pod.metadata.labels['qos_latency'])
        required_bandwidth = int(pod.metadata.labels['qos_bandwidth'])
        if latency <= required_delay:
            return True
        if bandwidth <= required_bandwidth:
            return True
        return False

    def pod_has_placeholder(self, pod):
        try:
            # FIXME: '-' character assumed as splitting character
            return True, next(ph for ph in self.placeholders if pod.metadata.name.split('-')[0] in ph.pods)
        except StopIteration:
            return False, None

    def new_pod(self, pod, namespace="default"):
        # New Pod request
        # Get the delay constraint value from the labels

        iot_device_area = pod.metadata.labels['area']
        required_delay = int(pod.metadata.labels['qos_latency'])
        required_bandwidth = int(pod.metadata.labels['qos_bandwidth'])

        # Getting all the nodes inside the delay radius
        all_nodes_in_radius = self.get_nodes_in_radius(pod.metadata.name, iot_device_area, required_delay,
                                                       required_bandwidth)
        nodes_enough_resource_in_rad = self.narrow_nodes_by_capacity(pod, all_nodes_in_radius)

        # There is no node with available resource
        if len(nodes_enough_resource_in_rad) == 0:

            # Try to reschedule some previously deployed Pod
            old_pod_name = self.reschedule_pod(pod, all_nodes_in_radius)
            # We have to wait, while the pod get successfully rescheduled
            if old_pod_name is not None:
                # FIXME: '-' character assumed as splitting character
                # FIXME: We are waiting till only 1 instance remain. There can be more on purpose!
                time.sleep(5)
                print("INFO Waiting for rescheduling.", end="")
                while len([x.metadata.name for x in self.get_all_pods() if
                           old_pod_name.split('-')[0] in x.metadata.name]) > 1:
                    print(".", end="")
                    time.sleep(2)
                print("\n")

            # Recalculate the nodes with the computational resources
            nodes_enough_resource_in_rad = self.narrow_nodes_by_capacity(pod, all_nodes_in_radius)
        if len(all_nodes_in_radius) > 1:
            nodes_enough_resource_in_rad = self.assign_placeholder(
                pod, [x for x in all_nodes_in_radius if x not in nodes_enough_resource_in_rad],
                nodes_enough_resource_in_rad)
            for ph in self.placeholders:
                print("INFO Placeholder on node: %s ;assigned Pods: %s" % (ph.node, str(ph.pods)))
        elif len(all_nodes_in_radius) == 1:
            print("WARNING No placeholder will be assigned to this Pod!")
        node = nodes_enough_resource_in_rad[0]
        self.bind(pod, node.metadata.name, namespace)

    def schedule(self, pod, namespace="default"):
        print("Scheduling Started ...")
        # self.update_latency_matrix()

        if pod.metadata.name.split('-')[0] in self.rescedules.keys():
            print("Rescheduling Pod")
            node = self.rescedules[pod.metadata.name.split('-')[0]]
            del self.rescedules[pod.metadata.name.split('-')[0]]
            self.bind(pod, node)
            return

        any_assigned_placeholder, placeholder = self.pod_has_placeholder(pod)
        if any_assigned_placeholder:
            # Check for destroyed pods by destroyer
            if (self.check_destroyed(pod, placeholder.node)):
                print("Destroyed Pod Detected")
                self.placeholders.remove(placeholder)
                self.new_pod(pod)
            else:
                # The Pod has already an assigned placeholder so probably a node failure occurred, we need to restart
                # the pod
                print("Placeholder Pod Detected")
                self.patch_pod(pod, placeholder.node)
        else:
            print("New Pod Detected")
            self.new_pod(pod)
