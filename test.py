available_nodes = ['master', 'master-m02', 'master-m03', 'master-m04']
print(available_nodes)
for node in available_nodes:
    print(node.metadata.name)