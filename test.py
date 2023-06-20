import yaml

with open('rule_collection.yaml') as f:
    data = yaml.safe_load(f)
    priority=data.get("priority").get("iotservice01")
    # matrix_first = list(priority.keys())[0]
    # matrix_second = list(priority.keys())[1]
    # m_test = "hi" if list(priority.keys())[1]=="latency" else "bye"
    print(priority)

for key,value in priority.items():
    print(key)
    print(value)
    # for subkey in key():
    #     print(subkey)