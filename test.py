import yaml

with open('config.yaml') as f:
    data = yaml.safe_load(f)
    priority=data.get("priority")
    matrix_first = list(priority.keys())[0]
    matrix_second = list(priority.keys())[1]
    m_test = "hi" if list(priority.keys())[1]=="latency" else "bye"
    print(m_test)

# for key,values in priority.items():
#     print(key)
#     print("Handler - Checking", key ,"between pod and node")
#     match key:
#                 case "latency":
#                     print("It's Monday!")
#                 case "bandwith":
#                     print("It's tuesday!")
#     values = values.split(",")
#     for value in values:
#         print(value)
#     # for subkey in key():
#     #     print(subkey)