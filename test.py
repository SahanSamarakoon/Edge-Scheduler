# import yaml
#
# with open('rule_collection.yaml') as f:
#     data = yaml.safe_load(f)
#     priority=data.get("priority").get("iotservice01")
#     # matrix_first = list(priority.keys())[0]
#     # matrix_second = list(priority.keys())[1]
#     # m_test = "hi" if list(priority.keys())[1]=="latency" else "bye"
#     print(priority)
#
# for key,value in priority.items():
#     print(key)
#     print(value)
#     # for subkey in key():
#     #     print(subkey)
# def select_config(available_bandwidth, config_dict):
#     min_difference = float('inf')
#     selected_config = None
#
#     for config, required_bandwidth in config_dict.items():
#         difference = abs(required_bandwidth - available_bandwidth)
#
#         if difference < min_difference:
#             min_difference = difference
#             selected_config = config
#
#     return selected_config
#
# # Example usage
# config_dict = {
#     'FRAMESIZE_QQVGA': 250,
#     'FRAMESIZE_HQVGA': 400,
#     'FRAMESIZE_QVGA': 700,
#     'FRAMESIZE_CIF': 800,
#     'FRAMESIZE_VGA': 900,
#     'FRAMESIZE_SVGA': 1000,
#     'FRAMESIZE_UXGA': 1100
# }
#
# available_bandwidth = 1000
# selected_config = select_config(available_bandwidth, config_dict)
print(f"Selected config for available bandwidth {available_bandwidth}: {selected_config}")
