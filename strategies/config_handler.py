from kubernetes import client, config
from kubernetes.stream import stream
import yaml


class ConfigHandler(object):

    def __init__(self):
        self.configs = {}
        self.load_config()
        self.api = client.CoreV1Api()

    @staticmethod
    def load_config(self):
        try:
            config.load_kube_config()
            with open('rule_collection.yaml') as f:
                self.rules = yaml.safe_load(f)
        except FileNotFoundError as e:
            print("WARNING %s\n" % e)
            config.load_incluster_config()

    def config_selector(self, pod, available_bandwidth):
        config_dict = pod.metadata.labels['reconfiguration']
        min_difference = float('inf')
        selected_config = None

        for config, required_bandwidth in config_dict.items():
            difference = abs(required_bandwidth - available_bandwidth)
            if difference < min_difference:
                min_difference = difference
                selected_config = config
        return selected_config

    def update_config(self, pod, available_bandwidth):
        namespace = 'default'
        quality = self.config_selector(pod, available_bandwidth)

        url = "https://" + pod.metadata.labels['device_ip'] + "/mjpeg"
        exec_command = ['/bin/sh', '-c', 'python main.py --url {} --quality {}'.format(url, quality)]

        resp = stream(self.api.connect_get_namespaced_pod_exec, pod.metadata.name, namespace,
                      command=exec_command,
                      stderr=True, stdin=False,
                      stdout=True, tty=False)
        print("Response: " + resp)
