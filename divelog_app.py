#!/usr/bin/env python3
"""
Arrowcrab Dive Studio - Windows GUI with embedded dashboard viewer.

Uses pywebview (Edge WebView2 on Windows) so the full HTML+Chart.js
dashboard renders inside the app — no external browser needed.
"""

import webview
import json
import sys
import os
import base64
import io
import tempfile
import threading

from generate_dive_dashboard import (
    extract_dive_data,
    get_computer_info,
    calculate_trip_stats,
    generate_html,
)

# ── Asset path (dev vs PyInstaller) ──────────────────────────────────────
if getattr(sys, "frozen", False):
    ASSET_DIR = sys._MEIPASS
    APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(sys.executable)))
else:
    ASSET_DIR = os.path.dirname(os.path.abspath(__file__))
    APP_DIR = ASSET_DIR


def _logo_data_uri():
    """Return arrowcrab.png as a compact base64 data-URI."""
    path = os.path.join(ASSET_DIR, "arrowcrab.png")
    if not os.path.exists(path):
        return ""
    try:
        from PIL import Image

        img = Image.open(path).resize((64, 64), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    except ImportError:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
    return "data:image/png;base64," + b64


# ── Python ↔ JavaScript API ─────────────────────────────────────────────
class Api:
    def __init__(self):
        self.window = None

    def choose_file(self):
        result = self.window.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=("Database Files (*.db)", "All Files (*.*)"),
        )
        if result and len(result) > 0:
            return result[0]
        return None

    def choose_image_file(self):
        result = self.window.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=("Image Files (*.png;*.jpg;*.jpeg)", "All Files (*.*)"),
        )
        if result and len(result) > 0:
            return result[0]
        return None

    def save_dropped_file(self, filename, b64_data):
        """Persist a file received from HTML5 drag-and-drop (base64)."""
        try:
            data = base64.b64decode(b64_data)
            tmp = os.path.join(tempfile.gettempdir(), "mydivelog_drop")
            os.makedirs(tmp, exist_ok=True)
            out = os.path.join(tmp, filename)
            with open(out, "wb") as f:
                f.write(data)
            return out
        except Exception:
            return None

    def convert_raw(self, b64_data):
        """Convert a RAW image (base64) to JPG via rawpy, return data-URI."""
        try:
            import rawpy
            from PIL import Image

            raw_bytes = base64.b64decode(b64_data)
            tmp = os.path.join(tempfile.gettempdir(), "mydivelog_raw_tmp")
            os.makedirs(tmp, exist_ok=True)
            tmp_file = os.path.join(tmp, "convert.orf")
            with open(tmp_file, "wb") as f:
                f.write(raw_bytes)

            raw = rawpy.imread(tmp_file)
            rgb = raw.postprocess()
            raw.close()
            os.unlink(tmp_file)

            img = Image.fromarray(rgb)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            b64_jpg = base64.b64encode(buf.getvalue()).decode("ascii")
            return "data:image/jpeg;base64," + b64_jpg
        except Exception:
            return ""

    def convert_raw_underwater(self, b64_data):
        """Convert a RAW image with underwater white balance correction."""
        try:
            import rawpy
            from PIL import Image, ImageEnhance
            import numpy as np

            raw_bytes = base64.b64decode(b64_data)
            tmp = os.path.join(tempfile.gettempdir(), "mydivelog_raw_tmp")
            os.makedirs(tmp, exist_ok=True)
            tmp_file = os.path.join(tmp, "convert_uw.orf")
            with open(tmp_file, "wb") as f:
                f.write(raw_bytes)

            raw = rawpy.imread(tmp_file)
            # Underwater white balance: boost red, reduce blue
            rgb = raw.postprocess(
                use_camera_wb=False,
                use_auto_wb=False,
                user_wb=[2.2, 1.0, 0.75, 1.0],
                no_auto_bright=False,
            )
            raw.close()
            os.unlink(tmp_file)

            img = Image.fromarray(rgb)
            # Adaptive channel correction based on actual color cast
            arr = np.array(img, dtype=np.float32)
            r_avg = arr[:, :, 0].mean()
            g_avg = arr[:, :, 1].mean()
            b_avg = arr[:, :, 2].mean()
            target = max(r_avg, g_avg, b_avg)
            if r_avg > 0:
                r_boost = min(target / r_avg, 2.0)
                arr[:, :, 0] = np.clip(arr[:, :, 0] * r_boost, 0, 255)
            if b_avg > g_avg * 1.1:
                b_reduce = max(g_avg / b_avg, 0.7)
                arr[:, :, 2] = np.clip(arr[:, :, 2] * b_reduce, 0, 255)
            img = Image.fromarray(arr.astype(np.uint8))
            img = ImageEnhance.Contrast(img).enhance(1.15)
            img = ImageEnhance.Color(img).enhance(1.25)

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=90)
            b64_jpg = base64.b64encode(buf.getvalue()).decode("ascii")
            return "data:image/jpeg;base64," + b64_jpg
        except Exception:
            return ""

    def correct_underwater(self, b64_data):
        """Apply underwater color correction to any image (JPG/PNG/data-URI)."""
        try:
            from PIL import Image, ImageEnhance
            import numpy as np

            if b64_data.startswith("data:"):
                b64_data = b64_data.split(",", 1)[1]
            img_bytes = base64.b64decode(b64_data)
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

            arr = np.array(img, dtype=np.float32)
            r_avg = arr[:, :, 0].mean()
            g_avg = arr[:, :, 1].mean()
            b_avg = arr[:, :, 2].mean()

            # Adaptive correction: bring red up toward the dominant channel
            target = max(r_avg, g_avg, b_avg)
            if r_avg > 0 and r_avg < target:
                r_factor = min(target / r_avg, 2.5)
                arr[:, :, 0] = np.clip(arr[:, :, 0] * r_factor, 0, 255)
            # Reduce blue if it dominates green
            if b_avg > g_avg * 1.1:
                b_factor = max(g_avg / b_avg, 0.65)
                arr[:, :, 2] = np.clip(arr[:, :, 2] * b_factor, 0, 255)
            # Slight green reduction if it dominates corrected red
            new_r = arr[:, :, 0].mean()
            if g_avg > new_r * 1.15:
                g_factor = max(new_r / g_avg, 0.8)
                arr[:, :, 1] = np.clip(arr[:, :, 1] * g_factor, 0, 255)

            img = Image.fromarray(arr.astype(np.uint8))
            img = ImageEnhance.Contrast(img).enhance(1.2)
            img = ImageEnhance.Color(img).enhance(1.3)

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=90)
            b64_jpg = base64.b64encode(buf.getvalue()).decode("ascii")
            return "data:image/jpeg;base64," + b64_jpg
        except Exception:
            return ""

    # ── Marine Life Identification (Claude Vision API) ──────────────────
    def _api_key_path(self):
        return os.path.join(APP_DIR, "api_config.json")

    def _get_api_key(self):
        try:
            with open(self._api_key_path(), "r") as f:
                cfg = json.load(f)
            return cfg.get("anthropic_api_key", "")
        except Exception:
            return ""

    def get_has_api_key(self):
        return "yes" if self._get_api_key() else "no"

    def save_api_key(self, key):
        try:
            with open(self._api_key_path(), "w") as f:
                json.dump({"anthropic_api_key": key.strip()}, f)
            return "ok"
        except Exception:
            return ""

    def identify_marine_life(self, b64_data, media_type="image/jpeg"):
        """Send image to Claude API for marine life identification."""
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError, URLError

        api_key = self._get_api_key()
        if not api_key:
            return json.dumps({"error": "No API key configured."})

        try:
            payload = json.dumps({
                "model": "claude-sonnet-4-5-20250929",
                "max_tokens": 1024,
                "messages": [{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64_data,
                            }
                        },
                        {
                            "type": "text",
                            "text": "Identify all marine life visible in this underwater photograph. "
                                    "For each species, provide the common name, scientific name, and "
                                    "a brief description. If no marine life is visible, say so."
                        }
                    ]
                }]
            }).encode("utf-8")

            req = Request(
                "https://api.anthropic.com/v1/messages",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
                method="POST",
            )

            with urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))

            # Extract text from response
            text = ""
            for block in body.get("content", []):
                if block.get("type") == "text":
                    text += block.get("text", "")

            return json.dumps({"result": text})

        except HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")[:300]
            return json.dumps({"error": f"API error ({e.code}): {err_body}"})
        except URLError as e:
            return json.dumps({"error": f"Connection error: {e.reason}"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def save_share_image(self, b64_data, default_name="share.png"):
        """Prompt user for save location and write a PNG image."""
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            if not os.path.isdir(desktop):
                desktop = os.path.expanduser("~")
            result = self.window.create_file_dialog(
                webview.SAVE_DIALOG,
                directory=desktop,
                file_types=("PNG Image (*.png)",),
                save_filename=default_name,
            )
            if not result:
                return ""
            path = result if isinstance(result, str) else result[0] if result else ""
            if not path:
                return ""
            if not path.lower().endswith(".png"):
                path += ".png"
            img_bytes = base64.b64decode(b64_data)
            with open(path, "wb") as f:
                f.write(img_bytes)
            return path
        except Exception:
            return ""

    def save_slideshow(self, html_content, default_name="trip_slideshow.html"):
        """Prompt user for save location and write slideshow HTML."""
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            if not os.path.isdir(desktop):
                desktop = os.path.expanduser("~")
            result = self.window.create_file_dialog(
                webview.SAVE_DIALOG,
                directory=desktop,
                file_types=("HTML Files (*.html)",),
                save_filename=default_name,
            )
            if not result:
                return ""
            path = result if isinstance(result, str) else result[0] if result else ""
            if not path:
                return ""
            if not path.lower().endswith(".html"):
                path += ".html"
            with open(path, "w", encoding="utf-8") as f:
                f.write(html_content)
            return path
        except Exception:
            return ""


    def launch_slideshow(self, file_path):
        """Open a saved slideshow HTML in a new pywebview window (allows autoplay)."""
        try:
            if not os.path.isfile(file_path):
                return ""
            url = "file:///" + file_path.replace("\\", "/")
            webview.create_window(
                "Slideshow",
                url=url,
                width=1280,
                height=800,
            )
            return "ok"
        except Exception:
            return ""

    # ── Sound file picker ─────────────────────────────────────────────
    def _sounds_dir(self):
        """Return the sounds folder path, creating it if needed."""
        d = os.path.join(APP_DIR, "sounds")
        os.makedirs(d, exist_ok=True)
        return d

    def list_sound_files(self):
        """Return list of {name, path} for sound files in the sounds dir."""
        d = self._sounds_dir()
        exts = ('.wav', '.mp3', '.ogg', '.m4a', '.aac')
        files = []
        try:
            for fn in sorted(os.listdir(d)):
                if fn.lower().endswith(exts):
                    files.append({"name": fn, "path": os.path.join(d, fn)})
        except Exception:
            pass
        return files

    def pick_sound_file(self):
        """Open a file picker for sound files, defaulting to sounds dir."""
        try:
            d = self._sounds_dir()
            result = self.window.create_file_dialog(
                webview.OPEN_DIALOG,
                directory=d,
                file_types=("Audio Files (*.wav;*.mp3;*.ogg;*.m4a;*.aac)",),
            )
            if result and len(result) > 0:
                return result[0]
            return ""
        except Exception:
            return ""

    def read_sound_base64(self, file_path):
        """Read a sound file and return as base64 data URI."""
        try:
            if not os.path.isfile(file_path):
                return ""
            ext = os.path.splitext(file_path)[1].lower()
            mime_map = {
                '.wav': 'audio/wav', '.mp3': 'audio/mpeg',
                '.ogg': 'audio/ogg', '.m4a': 'audio/mp4',
                '.aac': 'audio/aac',
            }
            mime = mime_map.get(ext, 'audio/wav')
            with open(file_path, "rb") as f:
                data = f.read()
            b64 = base64.b64encode(data).decode("ascii")
            return f"data:{mime};base64,{b64}"
        except Exception:
            return ""

    # ── Video concatenation ──────────────────────────────────────────
    def save_video_blob(self, b64_data, dest_path):
        """Write base64-encoded video data to dest_path. Returns 'ok' or ''."""
        try:
            video_bytes = base64.b64decode(b64_data)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, "wb") as f:
                f.write(video_bytes)
            return "ok"
        except Exception:
            return ""

    def delete_file(self, file_path):
        """Delete a file from disk. Returns 'ok' or ''."""
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
                return "ok"
            return ""
        except Exception:
            return ""

    def _find_ffmpeg(self):
        """Locate ffmpeg executable. Returns path or None."""
        import shutil
        import glob as glob_mod
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            pattern = os.path.join(
                os.path.expanduser("~"),
                "AppData", "Local", "Microsoft", "WinGet", "Packages",
                "Gyan.FFmpeg*", "ffmpeg-*", "bin", "ffmpeg.exe",
            )
            matches = glob_mod.glob(pattern)
            if matches:
                ffmpeg = matches[0]
        return ffmpeg

    def concatenate_videos(self, file_paths, output_path):
        """Concatenate video files using ffmpeg. Returns output path or error."""
        import subprocess
        ffmpeg = self._find_ffmpeg()
        if not ffmpeg:
            return json.dumps({"error": "ffmpeg not found. Please install ffmpeg and add it to your PATH."})
        try:
            list_path = output_path + ".txt"
            with open(list_path, "w", encoding="utf-8") as f:
                for p in file_paths:
                    escaped = p.replace("'", "'\\''")
                    f.write(f"file '{escaped}'\n")
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0
            result = subprocess.run(
                [ffmpeg, "-y", "-f", "concat", "-safe", "0",
                 "-i", list_path, "-c", "copy", output_path],
                capture_output=True, text=True, timeout=600,
                startupinfo=si, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            try:
                os.remove(list_path)
            except Exception:
                pass
            if result.returncode != 0:
                return json.dumps({"error": result.stderr[-500:] if result.stderr else "ffmpeg failed"})
            return json.dumps({"success": True, "path": output_path})
        except subprocess.TimeoutExpired:
            return json.dumps({"error": "ffmpeg timed out"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def create_mp4_slideshow(self, images_json, opts_json, default_name="slideshow.mp4"):
        """Prepare MP4 slideshow: save dialog, decode images, start ffmpeg in background."""
        import subprocess

        ffmpeg = self._find_ffmpeg()
        if not ffmpeg:
            return json.dumps({"error": "ffmpeg not found. Please install ffmpeg and add it to your PATH."})

        try:
            images = json.loads(images_json)
            opts = json.loads(opts_json)
        except Exception:
            return json.dumps({"error": "Invalid input data"})

        if not images:
            return json.dumps({"error": "No images provided"})

        interval_sec = max(1, (opts.get("interval_ms", 5000)) // 1000)
        title_duration = opts.get("titleDuration", 0)
        sound_path = opts.get("soundPath", "")

        # Prompt for save location (synchronous — fast)
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            if not os.path.isdir(desktop):
                desktop = os.path.expanduser("~")
            result = self.window.create_file_dialog(
                webview.SAVE_DIALOG,
                directory=desktop,
                file_types=("MP4 Video (*.mp4)",),
                save_filename=default_name,
            )
            if not result:
                return json.dumps({"error": "Save cancelled"})
            output_path = result if isinstance(result, str) else result[0] if result else ""
            if not output_path:
                return json.dumps({"error": "Save cancelled"})
            if not output_path.lower().endswith(".mp4"):
                output_path += ".mp4"
        except Exception as e:
            return json.dumps({"error": f"Save dialog error: {e}"})

        # Decode images to temp dir (synchronous — fast)
        # Normalize all to JPEG for consistent ffmpeg concat
        tmp_dir = tempfile.mkdtemp(prefix="arrowcrab_ss_")
        img_paths = []
        for i, img in enumerate(images):
            try:
                src = img.get("src", "")
                if not src or not src.startswith("data:"):
                    continue
                header, b64data = src.split(",", 1)
                img_data = base64.b64decode(b64data)
                is_png = "png" in header
                if is_png:
                    # Convert PNG to JPEG for consistent pixel format
                    try:
                        from PIL import Image as PILImage
                        pil_img = PILImage.open(io.BytesIO(img_data)).convert("RGB")
                        buf = io.BytesIO()
                        pil_img.save(buf, format="JPEG", quality=92)
                        img_data = buf.getvalue()
                    except ImportError:
                        pass  # If PIL unavailable, use PNG as-is
                img_file = os.path.join(tmp_dir, f"img_{i:04d}.jpg")
                with open(img_file, "wb") as f:
                    f.write(img_data)
                img_paths.append(img_file)
            except Exception:
                continue

        if not img_paths:
            import shutil as shutil_mod
            shutil_mod.rmtree(tmp_dir, ignore_errors=True)
            return json.dumps({"error": "No valid images to process"})

        # Create concat demuxer file
        concat_file = os.path.join(tmp_dir, "concat.txt")
        total_duration = 0
        with open(concat_file, "w", encoding="utf-8") as f:
            for idx, p in enumerate(img_paths):
                escaped = p.replace("\\", "/").replace("'", "'\\''")
                dur = title_duration if (idx == 0 and title_duration > 0) else interval_sec
                f.write(f"file '{escaped}'\n")
                f.write(f"duration {dur}\n")
                total_duration += dur
            escaped = img_paths[-1].replace("\\", "/").replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")

        # Build ffmpeg command
        has_audio = sound_path and os.path.isfile(sound_path)
        cmd = [ffmpeg, "-y"]
        if has_audio:
            cmd.extend(["-stream_loop", "-1", "-i", sound_path])
        cmd.extend(["-f", "concat", "-safe", "0", "-i", concat_file])
        vf = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black"
        if has_audio:
            cmd.extend(["-map", "1:v", "-map", "0:a"])
        cmd.extend(["-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30"])
        if has_audio:
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])
        else:
            cmd.extend(["-an"])
        cmd.extend(["-t", str(total_duration)])
        cmd.append(output_path)

        # Start ffmpeg in background thread so UI stays responsive
        self._mp4_status = {"state": "encoding", "output_path": output_path, "num_images": len(img_paths)}

        def run_ffmpeg():
            try:
                # Hide console window on Windows
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = 0  # SW_HIDE
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=600,
                    startupinfo=si, creationflags=subprocess.CREATE_NO_WINDOW,
                )
                if os.path.isfile(output_path) and os.path.getsize(output_path) > 0:
                    self._mp4_status = {"state": "done", "path": output_path}
                else:
                    err = proc.stderr[-500:] if proc.stderr else "ffmpeg failed"
                    self._mp4_status = {"state": "error", "error": err}
            except subprocess.TimeoutExpired:
                self._mp4_status = {"state": "error", "error": "ffmpeg timed out (video may be too large)"}
            except Exception as e:
                self._mp4_status = {"state": "error", "error": str(e)}
            finally:
                try:
                    import shutil as shutil_mod
                    shutil_mod.rmtree(tmp_dir, ignore_errors=True)
                except Exception:
                    pass

        threading.Thread(target=run_ffmpeg, daemon=True).start()
        return json.dumps({"status": "encoding", "num_images": len(img_paths)})

    def get_mp4_status(self):
        """Poll the status of a background MP4 slideshow encoding."""
        return json.dumps(getattr(self, "_mp4_status", {"state": "idle"}))

    # ── Collection export ──────────────────────────────────────────────
    def choose_folder(self):
        """Open a folder-picker dialog and return the chosen path."""
        try:
            result = self.window.create_file_dialog(
                webview.FOLDER_DIALOG,
            )
            if result and len(result) > 0:
                return result[0]
            return ""
        except Exception:
            return ""

    def create_directory(self, dir_path):
        """Create a directory (and parents) if it doesn't exist."""
        try:
            os.makedirs(dir_path, exist_ok=True)
            return "ok"
        except Exception:
            return ""

    def save_collection_file(self, b64_data, dest_path):
        """Write base64-encoded image data to dest_path."""
        try:
            img_bytes = base64.b64decode(b64_data)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, "wb") as f:
                f.write(img_bytes)
            return "ok"
        except Exception:
            return ""

    # ── Background images ────────────────────────────────────────────────
    def _bg_images_dir(self):
        """Return the background images folder, creating it if needed."""
        d = os.path.join(APP_DIR, "background_images")
        os.makedirs(d, exist_ok=True)
        return d

    def _bg_config_path(self):
        return os.path.join(APP_DIR, "background_config.json")

    def save_background_image(self, b64_data, filename):
        """Save a background image to background_images/ and persist config."""
        try:
            bg_dir = self._bg_images_dir()
            # Decode the data URI
            if b64_data.startswith("data:"):
                b64_data = b64_data.split(",", 1)[1]
            img_bytes = base64.b64decode(b64_data)
            path = os.path.join(bg_dir, filename)
            with open(path, "wb") as f:
                f.write(img_bytes)
            # Save config so app remembers the background on next launch
            with open(self._bg_config_path(), "w", encoding="utf-8") as f:
                json.dump({"path": path}, f)
            return path
        except Exception:
            return ""

    def get_default_background(self):
        """Return the saved default background as a data URI, or empty."""
        try:
            cfg_path = self._bg_config_path()
            if not os.path.exists(cfg_path):
                return ""
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            img_path = cfg.get("path", "")
            if not img_path or not os.path.exists(img_path):
                return ""
            ext = os.path.splitext(img_path)[1].lower()
            mime = "image/png" if ext == ".png" else "image/jpeg"
            with open(img_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            return f"data:{mime};base64," + b64
        except Exception:
            return ""

    def clear_background_config(self):
        """Remove the saved background config."""
        try:
            cfg_path = self._bg_config_path()
            if os.path.exists(cfg_path):
                os.remove(cfg_path)
            return "ok"
        except Exception:
            return ""

    # ── Default project config ───────────────────────────────────────────
    def _default_project_config_path(self):
        return os.path.join(APP_DIR, "default_project_config.json")

    def set_default_project(self, path):
        """Save the given project path as the default to auto-load on startup."""
        try:
            with open(self._default_project_config_path(), "w", encoding="utf-8") as f:
                json.dump({"path": path}, f)
            return "ok"
        except Exception:
            return ""

    def get_default_project(self):
        """Return the default project path, or empty string if none set."""
        try:
            cfg_path = self._default_project_config_path()
            if not os.path.exists(cfg_path):
                return ""
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            path = cfg.get("path", "")
            if path and os.path.isfile(path):
                return path
            return ""
        except Exception:
            return ""

    def clear_default_project(self):
        """Remove the default project setting."""
        try:
            cfg_path = self._default_project_config_path()
            if os.path.exists(cfg_path):
                os.remove(cfg_path)
            return "ok"
        except Exception:
            return ""

    # ── Save / Load project ─────────────────────────────────────────────
    def _projects_dir(self):
        """Return the default projects folder, creating it if needed."""
        d = os.path.join(APP_DIR, "projects")
        os.makedirs(d, exist_ok=True)
        return d

    def save_project_json(self, json_str):
        """Prompt for save location and write project JSON."""
        try:
            result = self.window.create_file_dialog(
                webview.SAVE_DIALOG,
                directory=self._projects_dir(),
                file_types=("Dive Studio Projects (*.json)",),
                save_filename="dive_project.json",
            )
            if not result:
                return ""
            path = result if isinstance(result, str) else result[0] if result else ""
            if not path:
                return ""
            if not path.lower().endswith(".json"):
                path += ".json"
            with open(path, "w", encoding="utf-8") as f:
                f.write(json_str)
            # Ask user if this should be the default project (native dialog)
            try:
                import ctypes
                MB_YESNO = 0x04
                MB_ICONQUESTION = 0x20
                IDYES = 6
                MB_TOPMOST = 0x40000
                hwnd = 0
                try:
                    hwnd = ctypes.windll.user32.GetForegroundWindow()
                except Exception:
                    pass
                resp = ctypes.windll.user32.MessageBoxW(
                    hwnd,
                    "Set this as the default project?\n\n"
                    "If set, this project will load automatically "
                    "when the app starts.",
                    "Default Project",
                    MB_YESNO | MB_ICONQUESTION | MB_TOPMOST,
                )
                if resp == IDYES:
                    self.set_default_project(path)
            except Exception:
                pass
            return path
        except Exception:
            return ""

    def load_project(self):
        """Open a .json project file, return dashboard HTML + picture manifest."""
        try:
            result = self.window.create_file_dialog(
                webview.OPEN_DIALOG,
                directory=self._projects_dir(),
                file_types=(
                    "Dive Studio Projects (*.json)",
                    "All Files (*.*)",
                ),
            )
            if not result or len(result) == 0:
                return json.dumps({"error": "cancelled"})
            path = result[0]
            with open(path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            dashboard_html = generate_html(
                meta["dives"], meta["computerInfo"], meta["trips"]
            )
            resp = {
                "success": True,
                "html": dashboard_html,
                "pictures": meta.get("pictures", {}),
                "captions": meta.get("captions", {}),
                "marineIds": meta.get("marineIds", {}),
                "collections": meta.get("collections", {}),
            }
            if meta.get("backgroundPath"):
                resp["backgroundPath"] = meta["backgroundPath"]
            if meta.get("background"):
                resp["background"] = meta["background"]
            return json.dumps(resp)
        except Exception as e:
            import traceback
            return json.dumps({"error": str(e), "traceback": traceback.format_exc()})

    def load_project_from_path(self, path):
        """Load a project from a known path (used for default project auto-load)."""
        try:
            if not path or not os.path.isfile(path):
                return json.dumps({"error": "File not found"})
            with open(path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            dashboard_html = generate_html(
                meta["dives"], meta["computerInfo"], meta["trips"]
            )
            resp = {
                "success": True,
                "html": dashboard_html,
                "pictures": meta.get("pictures", {}),
                "captions": meta.get("captions", {}),
                "marineIds": meta.get("marineIds", {}),
                "collections": meta.get("collections", {}),
            }
            if meta.get("backgroundPath"):
                resp["backgroundPath"] = meta["backgroundPath"]
            if meta.get("background"):
                resp["background"] = meta["background"]
            return json.dumps(resp)
        except Exception as e:
            import traceback
            return json.dumps({"error": str(e), "traceback": traceback.format_exc()})

    def load_pic_file(self, filepath):
        """Read a picture file from disk and return base64."""
        try:
            if not os.path.exists(filepath):
                return ""
            with open(filepath, "rb") as f:
                return base64.b64encode(f.read()).decode("ascii")
        except Exception:
            return ""

    def resolve_folder(self, folder_name):
        """Find the absolute path to a folder by searching common locations.

        Used to resolve webkitRelativePath (e.g. 'FolderName/file.jpg')
        by finding where FolderName actually lives on disk.
        Returns the absolute path to the folder, or empty string.
        """
        try:
            home = os.path.expanduser("~")
            # Search common locations (shallow), then drives (one level deep)
            search_dirs = [home]
            for d in ["Pictures", "Desktop", "Downloads", "Documents",
                       "Videos", "OneDrive", "OneDrive\\Pictures"]:
                p = os.path.join(home, d)
                if os.path.isdir(p):
                    search_dirs.append(p)
            # Add drive roots and their immediate children
            for drive in ["C:\\", "D:\\", "E:\\", "F:\\"]:
                if os.path.isdir(drive):
                    search_dirs.append(drive)
                    try:
                        for entry in os.scandir(drive):
                            if entry.is_dir():
                                search_dirs.append(entry.path)
                    except PermissionError:
                        pass
            for search in search_dirs:
                candidate = os.path.join(search, folder_name)
                if os.path.isdir(candidate):
                    return candidate
            return ""
        except Exception:
            return ""

    def generate_empty_dashboard(self):
        """Generate an empty dashboard for a new project."""
        try:
            dashboard_html = generate_html([], {"serial": "N/A"}, [])
            return json.dumps({"success": True, "html": dashboard_html})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def extract_dives_json(self, db_path):
        """Extract dives and trips from a .db file, return as JSON (no HTML)."""
        try:
            if not os.path.isfile(db_path):
                return json.dumps({"error": f"File not found: {db_path}"})
            dives = extract_dive_data(db_path)
            computer_info = get_computer_info(db_path)
            trips = calculate_trip_stats(dives)
            return json.dumps({
                "success": True,
                "dives": dives,
                "trips": trips,
                "computerInfo": computer_info,
            })
        except Exception as e:
            import traceback
            return json.dumps({"error": str(e), "traceback": traceback.format_exc()})

    def generate_dashboard(self, db_path):
        try:
            if not os.path.isfile(db_path):
                return json.dumps({"error": f"File not found: {db_path}"})

            dives = extract_dive_data(db_path)
            computer_info = get_computer_info(db_path)
            trips = calculate_trip_stats(dives)
            dashboard_html = generate_html(dives, computer_info, trips)

            return json.dumps(
                {
                    "success": True,
                    "diveCount": len(dives),
                    "tripCount": len(trips),
                    "serial": computer_info["serial"],
                    "html": dashboard_html,
                }
            )
        except Exception as e:
            import traceback

            return json.dumps(
                {"error": str(e), "traceback": traceback.format_exc()}
            )


# ── HTML template ────────────────────────────────────────────────────────
def _build_app_html():
    logo = _logo_data_uri()

    # Build the welcome page that shows before any dive log is imported
    logo_tag = (
        '<img style="width:80px;height:80px;border-radius:16px;margin-bottom:20px" '
        f'src="{logo}" alt="">' if logo else ''
    )
    welcome = (
        '<!DOCTYPE html><html><head><style>'
        '*{margin:0;padding:0;box-sizing:border-box}'
        "body{background:linear-gradient(135deg,#1e3a5f 0%,#0c4a6e 50%,#164e63 100%);"
        "display:flex;align-items:center;justify-content:center;min-height:100vh;"
        "font-family:'Segoe UI',sans-serif;color:white}"
        '.btn{padding:14px 32px;border-radius:10px;border:none;background:#06b6d4;'
        'color:#0f1923;font-size:1rem;font-weight:600;cursor:pointer;'
        "font-family:inherit;transition:background .15s}"
        '.btn:hover{background:#22d3ee}'
        '</style></head><body>'
        '<div style="text-align:center;position:relative;z-index:1">'
        f'{logo_tag}'
        '<h1 style="font-size:2rem;margin-bottom:8px">Arrowcrab Dive Studio</h1>'
        '<p style="color:#94a3b8;margin-bottom:30px">'
        'Import a Shearwater dive log to get started</p>'
        '<div style="display:flex;gap:12px;justify-content:center;flex-wrap:wrap">'
        '<button class="btn" onclick="parent.doNewProject()">New Project</button>'
        '<button class="btn" onclick="parent.doImport()">Import Dive Log</button>'
        '<button class="btn" onclick="parent.doLoadProject()">Load Project</button>'
        '</div></div></body></html>'
    )
    welcome_js = json.dumps(welcome)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{height:100%;overflow:hidden}}
body{{background:#0f1923}}
iframe{{width:100%;height:100%;border:none}}
</style>
</head>
<body>
<iframe id="dash"></iframe>
<script>
var dash=document.getElementById('dash');
dash.srcdoc={welcome_js};

/* Check for default project, otherwise apply saved background to welcome */
(function(){{
  var n=0;
  function tryStartup(){{
    if(n++>50) return;
    if(typeof pywebview==='undefined'||!pywebview.api||!pywebview.api.get_default_background){{
      setTimeout(tryStartup,100); return;
    }}
    /* Check for a default project to auto-load */
    pywebview.api.get_default_project().then(function(projPath){{
      if(projPath){{
        loadDefaultProject(projPath);
      }}else{{
        /* No default project — apply background to welcome screen */
        pywebview.api.get_default_background().then(function(uri){{
          if(!uri) return;
          var win=dash.contentWindow;
          if(!win||!win.document||!win.document.body) return;
          var b=win.document.body;
          b.style.background='none';
          b.style.backgroundImage='linear-gradient(rgba(15,25,35,0.75),rgba(15,25,35,0.75)),url('+uri+')';
          b.style.backgroundSize='cover';
          b.style.backgroundPosition='center';
          b.style.backgroundAttachment='fixed';
        }});
      }}
    }});
  }}
  setTimeout(tryStartup,150);
}})();

function loadDefaultProject(projPath){{
  pywebview.api.load_project_from_path(projPath).then(function(raw){{
    var r=JSON.parse(raw);
    if(r.error){{
      /* Default project failed to load — show welcome screen instead */
      pywebview.api.get_default_background().then(function(uri){{
        if(!uri) return;
        var win=dash.contentWindow;
        if(!win||!win.document||!win.document.body) return;
        var b=win.document.body;
        b.style.background='none';
        b.style.backgroundImage='linear-gradient(rgba(15,25,35,0.75),rgba(15,25,35,0.75)),url('+uri+')';
        b.style.backgroundSize='cover';
        b.style.backgroundPosition='center';
        b.style.backgroundAttachment='fixed';
      }});
      return;
    }}
    var pics=r.pictures;
    var captions=r.captions||{{}};
    var mids=r.marineIds||{{}};
    var collections=r.collections||{{}};
    var bg=r.background||'';
    var bgPath=r.backgroundPath||'';
    var hasPics=pics && Object.keys(pics).length>0;
    dash.onload=function(){{
      var win=dash.contentWindow;
      var t=setInterval(function(){{
        if(typeof win.injectPic==='function'){{
          clearInterval(t);
          if(typeof win.loadCaptions==='function') win.loadCaptions(captions);
          if(typeof win.loadMarineIds==='function') win.loadMarineIds(mids);
          if(hasPics) injectAll(win,pics,collections,bg,bgPath);
          else if(bg && typeof win.applyLoadedBackground==='function') win.applyLoadedBackground(bg,bgPath);
        }}
      }},100);
    }};
    dash.srcdoc=r.html;
  }});
}}

/* Apply saved default background once dashboard iframe is ready */
function applyDefaultBg(){{
  pywebview.api.get_default_background().then(function(uri){{
    if(!uri) return;
    var win=dash.contentWindow;
    var t=setInterval(function(){{
      if(win && typeof win.applyLoadedBackground==='function'){{
        clearInterval(t);
        win.applyLoadedBackground(uri);
      }}
    }},100);
  }});
}}

function doNewProject(){{
  pywebview.api.generate_empty_dashboard().then(function(raw){{
    var r=JSON.parse(raw);
    if(r.error){{ alert('Error: '+r.error); return; }}
    dash.onload=function(){{ applyDefaultBg(); }};
    dash.srcdoc=r.html;
  }});
}}

function doImport(){{
  pywebview.api.choose_file().then(function(p){{
    if(!p) return;
    /* Check if a dashboard is already loaded with mergeNewDives */
    var win=dash.contentWindow;
    if(win && typeof win.mergeNewDives==='function'){{
      /* Merge into existing dashboard */
      pywebview.api.extract_dives_json(p).then(function(raw){{
        var r=JSON.parse(raw);
        if(r.error){{ alert('Error: '+r.error); return; }}
        var added=win.mergeNewDives(r.dives, r.trips);
        if(added===0) alert('No new dives found to import.');
      }});
    }}else{{
      /* First import — create full dashboard */
      pywebview.api.generate_dashboard(p).then(function(raw){{
        var r=JSON.parse(raw);
        if(r.error){{ alert('Error: '+r.error); return; }}
        dash.onload=function(){{ applyDefaultBg(); }};
        dash.srcdoc=r.html;
      }});
    }}
  }});
}}

function doLoadProject(){{
  pywebview.api.load_project().then(function(raw){{
    var r=JSON.parse(raw);
    if(r.error){{
      if(r.error!=='cancelled') alert('Error: '+r.error);
      return;
    }}
    var pics=r.pictures;
    var captions=r.captions||{{}};
    var mids=r.marineIds||{{}};
    var collections=r.collections||{{}};
    var bg=r.background||'';
    var bgPath=r.backgroundPath||'';
    var hasPics=pics && Object.keys(pics).length>0;
    dash.onload=function(){{
      var win=dash.contentWindow;
      var t=setInterval(function(){{
        if(typeof win.injectPic==='function'){{
          clearInterval(t);
          if(typeof win.loadCaptions==='function') win.loadCaptions(captions);
          if(typeof win.loadMarineIds==='function') win.loadMarineIds(mids);
          if(hasPics) injectAll(win,pics,collections,bg,bgPath);
          else if(bg && typeof win.applyLoadedBackground==='function') win.applyLoadedBackground(bg,bgPath);
        }}
      }},100);
    }};
    dash.srcdoc=r.html;
  }});
}}

function injectAll(win,pics,collections,bg,bgPath){{
  /* Count total files for progress */
  var tripIdxs=Object.keys(pics);
  var totalFiles=0;
  tripIdxs.forEach(function(idx){{ totalFiles+=pics[idx].length; }});
  var loaded=0;
  if(totalFiles>0 && typeof win.showPicLoading==='function') win.showPicLoading(totalFiles);
  var ti=0;
  function nextTrip(){{
    if(ti>=tripIdxs.length){{
      if(typeof win.loadCollections==='function') win.loadCollections(collections);
      win.finishPicInjection();
      if(bg && typeof win.applyLoadedBackground==='function') win.applyLoadedBackground(bg,bgPath);
      /* Force re-render after DOM settles from cross-frame calls */
      setTimeout(function(){{
        if(typeof win.renderTrips==='function') win.renderTrips();
      }},300);
      setTimeout(function(){{
        if(typeof win.renderTrips==='function') win.renderTrips();
      }},1000);
      return;
    }}
    var idx=tripIdxs[ti];
    var files=pics[idx];
    var fi=0;
    function nextFile(){{
      if(fi>=files.length){{ ti++; setTimeout(nextTrip,10); return; }}
      var p=files[fi];
      var filePath=p.path||'';
      if(filePath){{
        pywebview.api.load_pic_file(filePath).then(function(b64){{
          if(b64) win.injectPic(parseInt(idx),p.name,p.lastModified,filePath,b64,p.caption||'');
          loaded++;
          if(typeof win.updatePicLoading==='function') win.updatePicLoading(loaded,totalFiles);
          fi++; setTimeout(nextFile,5);
        }});
      }}else{{
        loaded++;
        if(typeof win.updatePicLoading==='function') win.updatePicLoading(loaded,totalFiles);
        fi++; setTimeout(nextFile,5);
      }}
    }}
    setTimeout(nextFile,5);
  }}
  nextTrip();
}}
</script>
</body>
</html>'''

    return html


# ── Entry point ──────────────────────────────────────────────────────────
def main():
    api = Api()
    window = webview.create_window(
        "Arrowcrab Dive Studio",
        html=_build_app_html(),
        js_api=api,
        width=1050,
        height=750,
        min_size=(750, 550),
    )
    api.window = window
    webview.start()


if __name__ == "__main__":
    # Suppress pywebview .NET AccessibilityObject recursion spam on stderr
    import logging
    logging.disable(logging.CRITICAL)
    sys.stderr = open(os.devnull, "w")
    main()
