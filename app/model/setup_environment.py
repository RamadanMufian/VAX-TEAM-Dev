# ============================================================
# VAX Studio Colab AI Engine v3.3 — SPEED OPTIMIZED (15GB VRAM)
# STRATEGY: SMART PERSISTENCE (Keep model in memory)
# GPU Target  : T4 (15GB VRAM / 12GB RAM)
# ============================================================

import os, nest_asyncio, gc, torch, imageio, numpy as np, uuid, base64, io
from PIL import Image
from typing import Optional, Literal
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
from diffusers import (
    StableDiffusionPipeline,
    StableVideoDiffusionPipeline,
    CogVideoXImageToVideoPipeline,
)
from diffusers.utils import export_to_video

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

from google.colab import drive
drive.mount('/content/drive')
nest_asyncio.apply()

# Persistence: Save models to Drive so they only download ONCE
HF_CACHE = '/content/drive/MyDrive/vax_models_cache'
os.environ["HF_HOME"] = HF_CACHE
os.makedirs(HF_CACHE, exist_ok=True)

BASE_DIR = '/content/drive/MyDrive/AI_Video_Output'
os.makedirs(BASE_DIR, exist_ok=True)

# ── NGROK SETUP ──────────────────────────────────────────────
from pyngrok import ngrok, conf
NGROK_TOKEN = "3ChitPHrdVx5vCS2ObT3PiSmcKT_5VMi8Ms4gZcPA2cp34a4t"
conf.get_default().auth_token = NGROK_TOKEN

app = FastAPI(title="VAX Studio Engine v3.3")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ── GLOBAL STATE ─────────────────────────────────────────────
jobs = {}
current_model_name = None
pipe = None

# ── MEMORY UTILS ─────────────────────────────────────────────
def clear_memory():
    global pipe, current_model_name
    print(f"🧹 Clearing memory (Previous model: {current_model_name})...")
    pipe = None
    current_model_name = None
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()

def show_progress(job_id, step, total, model_name):
    progress = int((step / total) * 100)
    bar = '█' * (progress // 5) + '░' * (20 - progress // 5)
    print(f"\r🚀 [{model_name}] Job: {job_id} |{bar}| {progress}%", end="", flush=True)

# ── AUDIO UTILS ──────────────────────────────────────────────
import subprocess

def merge_audio(video_path, audio_base64, job_id):
    if not audio_base64: return video_path
    print(f"\n🎵 Mixing audio for {job_id}...")
    audio_path = os.path.join(BASE_DIR, f"{job_id}_temp_audio.mp3")
    output_path = os.path.join(BASE_DIR, f"{job_id}_muxed.mp4")
    try:
        with open(audio_path, "wb") as f: f.write(base64.b64decode(audio_base64))
        # ffmpeg: combine video + audio
        cmd = ["ffmpeg", "-y", "-i", video_path, "-i", audio_path, "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0", "-shortest", output_path]
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path
    except Exception as e:
        print(f"⚠️ Audio Muxing failed: {e}")
        return video_path

# ── REQUEST SCHEMAS ──────────────────────────────────────────
class GenerateImageRequest(BaseModel):
    prompt: str
    width: int = 512
    height: int = 512
    num_inference_steps: int = 20
    seed: int = -1

class GenerateVideoRequest(BaseModel):
    image_base64: str
    prompt: str = ""
    model: Literal["svd", "cogvideox"] = "svd"
    num_frames: int = 17
    num_frames_cog: int = 17
    width: int = 480
    height: int = 272
    seed: int = -1
    audio_ref: Optional[str] = None
    video_ref: Optional[str] = None

# ═══════════════════════════════════════════════════════════════
# OPTIMIZED MODEL HANDLERS
# ═══════════════════════════════════════════════════════════════

def run_sd15(job_id, req):
    global pipe, current_model_name
    try:
        if current_model_name != "sd15":
            clear_memory()
            print(f"\n🖼️ Loading SD 1.5 (Persistence Mode)...")
            pipe = StableDiffusionPipeline.from_pretrained(
                "runwayml/stable-diffusion-v1-5", torch_dtype=torch.float16, safety_checker=None
            ).to("cuda")
            current_model_name = "sd15"
        
        seed = req.seed if req.seed != -1 else int(np.random.randint(0, 1000000))
        def cb(pipe, step, t, kwargs):
            jobs[job_id]["progress"] = int((step/req.num_inference_steps)*100)
            show_progress(job_id, step, req.num_inference_steps, "SD 1.5")
            return kwargs

        image = pipe(req.prompt, width=req.width, height=req.height, 
                     num_inference_steps=req.num_inference_steps, generator=torch.manual_seed(seed),
                     callback_on_step_end=cb).images[0]
        
        path = os.path.join(BASE_DIR, f"{job_id}.png")
        image.save(path)
        jobs[job_id].update({"status": "done", "file": path, "progress": 100})
        print(f"\n✅ SD 1.5 Done. Model kept in memory.")
    except Exception as e:
        jobs[job_id].update({"status": "failed", "error": str(e)})
        clear_memory()

def run_svd(job_id, req):
    global pipe, current_model_name
    try:
        if current_model_name != "svd":
            clear_memory()
            print(f"\n🎬 Loading SVD-XT (Persistence Mode)...")
            pipe = StableVideoDiffusionPipeline.from_pretrained(
                "stabilityai/stable-video-diffusion-img2vid-xt", torch_dtype=torch.float16, variant="fp16"
            ).to("cuda")
            # Enable faster decoding & VRAM saving
            pipe.enable_model_cpu_offload()
            current_model_name = "svd"
        
        img_data = base64.b64decode(req.image_base64)
        img = Image.open(io.BytesIO(img_data)).convert("RGB").resize((req.width, req.height))
        seed = req.seed if req.seed != -1 else int(np.random.randint(0, 1000000))
        
        torch.cuda.empty_cache() # Clear cache before inference
        
        def cb(pipe, step, t, kwargs):
            jobs[job_id]["progress"] = int((step/25)*100)
            show_progress(job_id, step, 25, "SVD-XT")
            return kwargs

        frames = pipe(img, decode_chunk_size=2, num_frames=25, 
                      generator=torch.manual_seed(seed), callback_on_step_end=cb).frames[0]
        
        path = os.path.join(BASE_DIR, f"{job_id}.mp4")
        export_to_video(frames, path, fps=7)
        
        # Audio Muxing
        final_path = merge_audio(path, req.audio_ref, job_id)
        
        jobs[job_id].update({"status": "done", "file": final_path, "progress": 100})
        print(f"\n✅ SVD Done. Model kept in memory.")
    except Exception as e:
        jobs[job_id].update({"status": "failed", "error": str(e)})
        clear_memory()

def run_cog(job_id, req):
    global pipe, current_model_name
    try:
        if current_model_name != "cogvideox":
            clear_memory()
            print(f"\n🧠 Loading CogVideoX-5B (Fast Mode)...")
            pipe = CogVideoXImageToVideoPipeline.from_pretrained(
                "THUDM/CogVideoX-5b-I2V", torch_dtype=torch.bfloat16
            )
            # Menggunakan model_cpu_offload + VRAM optimizations
            pipe.enable_model_cpu_offload() 
            pipe.vae.enable_tiling()
            pipe.vae.enable_slicing()
            current_model_name = "cogvideox"
        
        img_data = base64.b64decode(req.image_base64)
        img = Image.open(io.BytesIO(img_data)).convert("RGB").resize((req.width, req.height))
        seed = req.seed if req.seed != -1 else int(np.random.randint(0, 1000000))
        
        torch.cuda.empty_cache() # Clear cache before inference
        
        def cb(pipe, step, t, kwargs):
            jobs[job_id]["progress"] = int((step/30)*100)
            show_progress(job_id, step, 30, "CogVideoX")
            return kwargs

        frames = pipe(prompt=req.prompt or "cinematic motion", image=img, 
                      num_inference_steps=30, num_frames=req.num_frames_cog, 
                      generator=torch.Generator("cpu").manual_seed(seed),
                      callback_on_step_end=cb).frames[0]
        
        path = os.path.join(BASE_DIR, f"{job_id}.mp4")
        export_to_video(frames, path, fps=8)
        
        # Audio Muxing
        final_path = merge_audio(path, req.audio_ref, job_id)
        
        jobs[job_id].update({"status": "done", "file": final_path, "progress": 100})
        print(f"\n✅ CogVideoX Done. Model kept in memory.")
    except Exception as e:
        jobs[job_id].update({"status": "failed", "error": str(e)})
        clear_memory()

# ═══════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.post("/generate_image")
def gen_image(req: GenerateImageRequest, bg: BackgroundTasks):
    job_id = f"img_{uuid.uuid4().hex[:8]}"
    jobs[job_id] = {"status": "processing", "progress": 0}
    bg.add_task(run_sd15, job_id, req)
    return {"success": True, "job_id": job_id}

@app.post("/generate_video")
def gen_video(req: GenerateVideoRequest, bg: BackgroundTasks):
    job_id = f"vid_{uuid.uuid4().hex[:8]}"
    jobs[job_id] = {"status": "processing", "progress": 0}
    if req.model == "svd": bg.add_task(run_svd, job_id, req)
    else: bg.add_task(run_cog, job_id, req)
    return {"success": True, "job_id": job_id}

@app.get("/status/{job_id}")
def get_status(job_id: str): return jobs.get(job_id, {"status": "not_found"})

@app.get("/download/{job_id}")
def download(job_id: str):
    job = jobs.get(job_id)
    if job and job["status"] == "done": return FileResponse(job["file"])
    return JSONResponse(status_code=404, content={"error": "Not ready"})

@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": current_model_name,
        "vram": vram_info() if torch.cuda.is_available() else "N/A"
    }

def vram_info():
    free = torch.cuda.mem_get_info()[0] / 1024**3
    total = torch.cuda.get_device_properties(0).total_memory / 1024**3
    return f"{free:.1f}/{total:.1f} GB"

# ── START ────────────────────────────────────────────────────
public_url = ngrok.connect(8000).public_url
print(f"\n🚀 VAX ENGINE v3.3 ONLINE (SPEED OPTIMIZED)")
print(f"📡 URL: {public_url}\n")

config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="warning")
server = uvicorn.Server(config)
await server.serve()
