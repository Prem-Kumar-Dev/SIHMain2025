# Install PyTorch Geometric on Windows (CPU)

PyTorch Geometric (PyG) isn’t bundled by default. For CPU-only Windows setups:

1) Install a matching PyTorch (CPU) first:
```
pip install torch==2.3.1+cpu torchvision==0.18.1+cpu torchaudio==2.3.1+cpu -f https://download.pytorch.org/whl/cpu
```

2) Install PyG core packages (pick wheels compatible with your torch/cpu):
```
pip install pyg-lib torch-scatter torch-sparse torch-cluster torch-spline-conv torch-geometric -f https://data.pyg.org/whl/torch-2.3.1+cpu.html
```

Notes:
- If versions mismatch, check the latest wheel index at https://data.pyg.org/whl/
- For GPU/CUDA, use the CUDA-specific PyTorch and corresponding PyG wheel index.
- In corporate networks, you may need to configure `pip` proxies.
