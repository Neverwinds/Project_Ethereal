import torch
print(torch.cuda.is_available())  # 应该输出 True
print(torch.cuda.get_device_name(0))  # 应该输出 "NVIDIA GeForce RTX 5080"
print(torch.version.cuda) # 应该输出 "12.4"