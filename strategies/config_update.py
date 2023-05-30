from kubernetes import client, config
from kubernetes.stream import stream


class ConfigUpdate(object):

    def __init__(self):
        self.load_config()
        self.api = client.CoreV1Api()

    @staticmethod
    def load_config():
        try:
            config.load_kube_config()
        except FileNotFoundError as e:
            print("WARNING %s\n" % e)
            config.load_incluster_config()

    def config_selector(self, available_bandwidth):
        if available_bandwidth >= 90:
            return 9
        elif available_bandwidth >= 80:
            return 8
        elif available_bandwidth >= 70:
            return 7
        elif available_bandwidth >= 60:
            return 6
        elif available_bandwidth >= 50:
            return 5
        elif available_bandwidth >= 40:
            return 4
        else:
            return 1

    def update_config(self, pod, node, bandwidth_matrix):
        namespace = 'default'

        available_bandwidth = int(bandwidth_matrix.get(pod.metadata.name).get(node))
        quality = self.config_selector(available_bandwidth)

        url = "https://"+pod.metadata.labels['device_ip']+"/mjpeg"
        exec_command = ['/bin/sh', '-c', 'python main.py --url {} --quality {}'.format(url, quality)]

        resp = stream(self.api.connect_get_namespaced_pod_exec, pod.metadata.name, namespace,
                      command=exec_command,
                      stderr=True, stdin=False,
                      stdout=True, tty=False)
        print("Response: " + resp)
