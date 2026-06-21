import torch
print("CUDA Available:", torch.cuda.is_available())
try:
    print("Device 0:", torch.cuda.get_device_name(0))
except Exception as e:
    print("Failed to get device name:", e)
try:
    test_tensor = torch.tensor([1.0]).cuda() * 2
    print("Tensor test:", test_tensor)
except Exception as e:
    print("Tensor test failed:", e)
