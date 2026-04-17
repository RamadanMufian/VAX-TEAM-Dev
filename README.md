
# AI Text-to-Video Generator (Ref by LTX-Video)

This system is an AI-based Text-to-Video web application specifically designed to run locally on PCs/Laptops with limited VRAM (such as Nvidia RTX 3050 4GB).

This application uses the **LTX-Video (Lightricks 2B)** model which runs on top of the **FastAPI** (Backend) and **Vanilla HTML/CSS/JS** (Frontend) frameworks.

## Feature
- *VRAM Optimization (4GB)**: Uses CPU Offloading, VAE Slicing, VAE Tiling, and the `bfloat16` data type to enable the model to run without Out of Memory (OOM).
- **Text-to-Video**: Capable of generating short videos (~1 second / 25 frames) at 320x240 resolution with fast inference.
- **Web Dashboard**: An intuitive local user interface (UI) for entering prompts and monitoring video generation status in real-time.
- **Local Server**: Runs 100% offline locally after the model is successfully downloaded.
- **Automated Scripts**: Comes with various ready-to-use `.bat` scripts for Windows (`setup.bat`, `start_server.bat`, `download_model.bat`).
  
## Project Structure
```text
📦 model 
 ┣ 📂 backend/ # FastAPI server logic & Text-to-Video pipeline
 ┣ 📂 frontend/ # Web dashboard (UI)
 ┣ 📂 models/ # Cache for HuggingFace models
 ┣ 📂 outputs/ # Generated video outputs (.mp4)
 ┣ 📂 venv/ # Python virtual environment (created during installation)
 ┣ 📜 .env # Configure local environment variables
 ┣ 📜 INSTALL_GUIDE.txt # Complete manual installation instructions
 ┣ 📜 download_model.bat # Script to download the model manually (if needed)
 ┣ 📜 requirements.txt # List of Python dependencies
 ┣ 📜 setup.bat # Script for automatic initial setup
 ┣ 📜 start_server.bat # Script to start the web server & frontend
 ┗ 📜 test_gpu.py # Script to check GPU usage and detect
```

## Troubleshooting & Tips for 4GB VRAM (Continued)

If you experience a **CUDA Out of Memory (OOM)** error:
- Reduce the resolution in `backend/config.py` from `320x240` to something lower (e.g., `256x192` or `224x160`).
- Reduce the `DEFAULT_NUM_FRAMES` option to a range of `8-16` only (shorter videos consume less VRAM).
- Make sure no other heavy applications (Games, Rendering, Browsers with many tabs) are consuming VRAM when pressing "Generate".
- The bitsandbytes library sometimes has issues on pure Windows OS. If the library fails to load, read the `INSTALL_GUIDE.txt` file about reinstalling the Windows version of bitsandbytes.
- Try enabling `CPU_OFFLOAD=true` in the `.env` configuration file to shift some model layers to system RAM.
- Set `VAE_TILING_ENABLED=true` and `VAE_TILE_SIZE=128` in the backend configuration to process the VAE in smaller chunks.

### Common Error Messages & Solutions

| Error Message | Solution |
|---------------|----------|
| `CUDA out of memory` | Reduce resolution, reduce frame count, or close other VRAM-heavy applications |
| `No module named 'torch'` | Virtual environment not activated properly. Run `venv\Scripts\activate` manually |
| `bitsandbytes.dll not found` | Follow Windows-specific bitsandbytes installation in `INSTALL_GUIDE.txt` |
| `Model not found` | Run `download_model.bat` to manually download the VAX model |
| `Port 8000 already in use` | Change port in `start_server.bat` from `8000` to another port like `8001` |

## Performance Expectations (RTX 3050 4GB)

With the optimized settings, you can expect:

| Configuration | Generation Time | VRAM Usage |
|---------------|----------------|-------------|
| 320x240, 25 frames | ~15-25 seconds | 3.5-3.8 GB |
| 256x192, 16 frames | ~8-12 seconds | 3.0-3.3 GB |
| 224x160, 8 frames | ~4-7 seconds | 2.5-2.8 GB |

> **Note**: First generation after startup may be slower due to model loading into memory. Subsequent generations will be faster.

## Custom Configuration

You can modify the `.env` file or `backend/config.py` to adjust:

```python
# Resolution settings (width x height)
DEFAULT_WIDTH = 320
DEFAULT_HEIGHT = 240

# Video length settings
DEFAULT_NUM_FRAMES = 25  # ~1 second at 25 fps
DEFAULT_FPS = 25

# VRAM optimization flags
CPU_OFFLOAD = True
VAE_SLICING = True
VAE_TILING = True
USE_BFLOAT16 = True

# Generation settings
GUIDANCE_SCALE = 7.5
NUM_INFERENCE_STEPS = 30
=======
# VAX-TEAM-Dev
>>>>>>> upstream/main
