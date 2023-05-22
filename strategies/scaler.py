import time
from kubernetes import client


class Scaler(object):

    def __init__(self):
        self.v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()

    def scale(self, pod, namespace="default"):
        print("Scaler - Up-scaling {}".format(pod.metadata.name))
        current_scaling = self.apps_v1.read_namespaced_deployment_scale(name=pod.metadata.name.split("-")[0],
                                                                        namespace=namespace)
        current_scaling = current_scaling.status.replicas
        self.apps_v1.patch_namespaced_deployment(name=pod.metadata.name.split("-")[0], namespace=namespace,
                                                 body={"spec": {"replicas": current_scaling + 1}})
        print("Scaler - Sleeping for 30s")
        time.sleep(5)
        print("Scaler - Downscaling {}".format(pod.metadata.name))
        self.v1.delete_namespaced_pod(name=pod.metadata.name, namespace=namespace, grace_period_seconds=0)
        self.apps_v1.patch_namespaced_deployment(name=pod.metadata.name.split("-")[0], namespace=namespace,
                                                 body={"spec": {"replicas": current_scaling}})
