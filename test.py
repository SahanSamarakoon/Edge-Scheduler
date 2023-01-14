with open('data.txt') as f:
    lines=[line.strip() for line in f.readlines()]

node_names = lines[0].split(",")
iot_services = lines[1].split(",")

latency_matrix = {}

for i, service in enumerate(iot_services):
    temp_dict = {}
    temp_ping_list = lines[i+2].split(",")
    for j in range (len(node_names)):
        temp_dict[node_names[j]] = int(temp_ping_list[j])
    latency_matrix[service] = temp_dict

print(latency_matrix)