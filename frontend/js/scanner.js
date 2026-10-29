/**
 * Document Scanner & Camera Module.
 * Real camera streaming (getUserMedia), frame capture to canvas,
 * device image upload, validation, and retake/replace management.
 */

/**
 * One reliable quality check used by both camera and upload paths.
 * 1. Corrects EXIF rotation
 * 2. Scales fixed copy with long edge = 640 px
 * 3. Measures sharpness as Laplacian variance over 8x8 grid tiles (75th percentile)
 * 4. Measures mean brightness (0-255)
 * 5. Measures glare (% of near-white saturated pixels > 250)
 * Thresholds come from window.QUALITY_CONFIG, with defaults.
 * Never fails silently: returns ok: null on failure.
 */
export async function assessImageQuality(imageOrCanvas) {
  try {
    if (!imageOrCanvas) {
      return { ok: null, blur_score: 0, brightness: 0, glare_pct: 0, issues: ['Could not check this photo, retake if unsure'] };
    }

    let sourceWidth = 0;
    let sourceHeight = 0;
    let sourceElement = imageOrCanvas;

    if (imageOrCanvas instanceof Blob) {
      try {
        sourceElement = await createImageBitmap(imageOrCanvas, { imageOrientation: 'from-image' });
        sourceWidth = sourceElement.width;
        sourceHeight = sourceElement.height;
      } catch (e) {
        const img = new Image();
        const url = URL.createObjectURL(imageOrCanvas);
        await new Promise((res, rej) => {
          img.onload = () => { URL.revokeObjectURL(url); res(); };
          img.onerror = () => { URL.revokeObjectURL(url); rej(new Error('Failed to load image blob')); };
          img.src = url;
        });
        sourceElement = img;
        sourceWidth = img.width;
        sourceHeight = img.height;
      }
    } else if (imageOrCanvas instanceof HTMLVideoElement) {
      sourceWidth = imageOrCanvas.videoWidth || 1280;
      sourceHeight = imageOrCanvas.videoHeight || 720;
    } else {
      sourceWidth = imageOrCanvas.width || 640;
      sourceHeight = imageOrCanvas.height || 480;
    }

    if (sourceWidth < 4 || sourceHeight < 4) {
      return { ok: null, blur_score: 0, brightness: 0, glare_pct: 0, issues: ['Could not check this photo, retake if unsure'] };
    }

    // Scale to fixed copy with long edge = 640 px
    let newW, newH;
    if (sourceWidth >= sourceHeight) {
      newW = 640;
      newH = Math.max(1, Math.round((640 * sourceHeight) / sourceWidth));
    } else {
      newH = 640;
      newW = Math.max(1, Math.round((640 * sourceWidth) / sourceHeight));
    }

    const canvas = document.createElement('canvas');
    canvas.width = newW;
    canvas.height = newH;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) {
      return { ok: null, blur_score: 0, brightness: 0, glare_pct: 0, issues: ['Could not check this photo, retake if unsure'] };
    }

    ctx.drawImage(sourceElement, 0, 0, newW, newH);
    const imgData = ctx.getImageData(0, 0, newW, newH);
    const data = imgData.data;
    const totalPixels = newW * newH;

    // Grayscale luminance array & Brightness & Glare
    const gray = new Float32Array(totalPixels);
    let lumSum = 0;
    let glareCount = 0;

    for (let i = 0, j = 0; i < data.length; i += 4, j++) {
      const y = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
      gray[j] = y;
      lumSum += y;
      if (y > 250) glareCount++;
    }

    const brightness = lumSum / totalPixels;
    const glarePct = (glareCount / totalPixels) * 100.0;

    // Sharpness: 8x8 Grid Tile Laplacian Variance (using high 75th percentile)
    const gridDim = 8;
    const tileW = Math.max(2, Math.floor(newW / gridDim));
    const tileH = Math.max(2, Math.floor(newH / gridDim));
    const tileVars = [];

    for (let tr = 0; tr < gridDim; tr++) {
      const rStart = Math.max(1, tr * tileH);
      const rEnd = (tr === gridDim - 1) ? newH - 1 : (tr + 1) * tileH;
      for (let tc = 0; tc < gridDim; tc++) {
        const cStart = Math.max(1, tc * tileW);
        const cEnd = (tc === gridDim - 1) ? newW - 1 : (tc + 1) * tileW;

        let lapSum = 0;
        let lapSqSum = 0;
        let count = 0;

        for (let r = rStart; r < rEnd; r++) {
          const rowOffset = r * newW;
          const upOffset = (r - 1) * newW;
          const downOffset = (r + 1) * newW;

          for (let c = cStart; c < cEnd; c++) {
            const val = gray[upOffset + c] + gray[downOffset + c] + gray[rowOffset + c - 1] + gray[rowOffset + c + 1] - 4 * gray[rowOffset + c];
            lapSum += val;
            lapSqSum += val * val;
            count++;
          }
        }

        if (count > 4) {
          const mean = lapSum / count;
          const variance = (lapSqSum / count) - (mean * mean);
          tileVars.push(variance);
        }
      }
    }

    // 75th percentile of tile variances
    tileVars.sort((a, b) => a - b);
    let blurScore = 0;
    if (tileVars.length > 0) {
      const pIndex = Math.min(tileVars.length - 1, Math.floor(tileVars.length * 0.75));
      blurScore = tileVars[pIndex];
    }

    // Config thresholds from window.QUALITY_CONFIG with defaults
    const cfg = window.QUALITY_CONFIG || { blur_min: 80.0, dark_max: 50.0, glare_max: 12.0 };
    const blurMin = typeof cfg.blur_min === 'number' ? cfg.blur_min : 80.0;
    const darkMax = typeof cfg.dark_max === 'number' ? cfg.dark_max : 50.0;
    const glareMax = typeof cfg.glare_max === 'number' ? cfg.glare_max : 12.0;

    const issues = [];
    if (brightness < darkMax) issues.push('Too dark / underexposed');
    if (glarePct > glareMax) issues.push('Severe glare detected');
    if (blurScore < blurMin) issues.push('Blurry document');

    return {
      ok: issues.length === 0,
      blur_score: Math.round(blurScore * 10) / 10,
      brightness: Math.round(brightness * 10) / 10,
      glare_pct: Math.round(glarePct * 10) / 10,
      avgLum: Math.round(brightness),
      blurScore: Math.round(blurScore * 10) / 10,
      issues
    };
  } catch (err) {
    console.warn('Image quality assessment error:', err);
    return {
      ok: null,
      blur_score: 0,
      brightness: 0,
      glare_pct: 0,
      issues: ['Could not check this photo, retake if unsure']
    };
  }
}

export class DocumentScanner {
  constructor(options = {}) {
    this.videoEl = options.videoEl;
    this.canvasEl = options.canvasEl;
    this.onThumbnailsUpdated = options.onThumbnailsUpdated || (() => {});
    this.onStateChanged = options.onStateChanged || (() => {});

    this.stream = null;
    this.facingMode = 'environment'; // Back camera default for documents
    this.currentPage = 0; // 0 for Page 1, 1 for Page 2
    this.pages = [null, null]; // [ { blob, url, name }, { blob, url, name } ]
    this.isCameraActive = false;
    this.torchOn = false;
  }

  async isTorchSupported() {
    if (!this.stream) return false;
    const track = this.stream.getVideoTracks()[0];
    if (!track || !track.getCapabilities) return false;
    const caps = track.getCapabilities();
    return Boolean(caps && caps.torch);
  }

  async toggleTorch(forceState = null) {
    if (!this.stream) return false;
    const track = this.stream.getVideoTracks()[0];
    if (!track || !track.getCapabilities) return false;
    const caps = track.getCapabilities();
    if (!caps || !caps.torch) return false;
    this.torchOn = forceState !== null ? forceState : !this.torchOn;
    try {
      await track.applyConstraints({ advanced: [{ torch: this.torchOn }] });
      this.onStateChanged({ torchOn: this.torchOn });
      return this.torchOn;
    } catch (err) {
      console.warn('Torch constraint error:', err);
      return false;
    }
  }

  async checkImageQuality(canvasOrImg) {
    return assessImageQuality(canvasOrImg);
  }

  async startCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error('Camera is not supported on this device/browser. Please use the Upload button.');
    }

    this.stopCamera();

    try {
      const constraints = {
        video: {
          facingMode: { ideal: this.facingMode },
          width: { ideal: 1920 },
          height: { ideal: 1080 }
        },
        audio: false
      };

      this.stream = await navigator.mediaDevices.getUserMedia(constraints);
      if (this.videoEl) {
        this.videoEl.srcObject = this.stream;
        await this.videoEl.play();
      }
      this.isCameraActive = true;
      const torchAvail = await this.isTorchSupported();
      this.onStateChanged({ cameraActive: true, torchSupported: torchAvail });
    } catch (err) {
      this.isCameraActive = false;
      this.onStateChanged({ cameraActive: false, error: err.message });
      // If environment camera fails, try any available video device
      if (this.facingMode === 'environment') {
        this.facingMode = 'user';
        return this.startCamera();
      }
      throw new Error('Camera access was denied or is unavailable. You can upload document photos instead.');
    }
  }

  stopCamera() {
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this.stream = null;
    }
    if (this.videoEl) {
      this.videoEl.srcObject = null;
    }
    this.isCameraActive = false;
    this.torchOn = false;
    this.onStateChanged({ cameraActive: false, torchOn: false });
  }

  async switchCamera() {
    this.facingMode = (this.facingMode === 'environment') ? 'user' : 'environment';
    await this.startCamera();
  }

  async captureCurrentFrame() {
    if (!this.isCameraActive || !this.videoEl) {
      throw new Error('Camera is not active. Please start camera or upload an image.');
    }

    const video = this.videoEl;
    const canvas = this.canvasEl || document.createElement('canvas');
    
    // Use actual video feed resolution
    const width = video.videoWidth || 1280;
    const height = video.videoHeight || 720;
    canvas.width = width;
    canvas.height = height;

    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, width, height);

    // One reliable pre-flight image quality check
    const quality = await assessImageQuality(canvas);

    return new Promise((resolve, reject) => {
      canvas.toBlob(blob => {
        if (!blob) {
          reject(new Error('Failed to create image from camera frame.'));
          return;
        }
        const url = URL.createObjectURL(blob);
        this.setPageImage(this.currentPage, blob, url, `camera_page${this.currentPage + 1}.jpg`);
        resolve({ blob, url, quality });
      }, 'image/jpeg', 0.92);
    });
  }

  async handleFileUpload(file) {
    if (!file) return;

    const validMimes = [
      'image/jpeg', 'image/png', 'image/webp', 'image/jpg',
      'image/heic', 'image/heif', 'image/heic-sequence', 'image/heif-sequence'
    ];
    const isHeic = file.name && /\.(heic|heif)$/i.test(file.name);
    if (!validMimes.includes(file.type) && !isHeic) {
      throw new Error('Please select a valid image file (JPEG, PNG, WebP, or iPhone HEIC).');
    }

    const maxSize = 20 * 1024 * 1024; // 20MB
    if (file.size > maxSize) {
      throw new Error('File size exceeds the 20 MB limit.');
    }

    try {
      // Use the exact same assessImageQuality check for uploaded images
      const quality = await assessImageQuality(file);
      const url = URL.createObjectURL(file);
      this.setPageImage(this.currentPage, file, url, file.name);
      return { blob: file, url, quality };
    } catch (err) {
      const url = URL.createObjectURL(file);
      this.setPageImage(this.currentPage, file, url, file.name);
      return {
        blob: file,
        url,
        quality: { ok: null, blur_score: 0, brightness: 0, glare_pct: 0, issues: ['Could not check this photo, retake if unsure'] }
      };
    }
  }

  _resizeAndAnalyzeImage(fileOrBlob, maxDim = 1600) {
    return new Promise((resolve) => {
      const img = new Image();
      const objUrl = URL.createObjectURL(fileOrBlob);
      img.onload = () => {
        URL.revokeObjectURL(objUrl);
        let width = img.width;
        let height = img.height;
        if (width > maxDim || height > maxDim) {
          if (width > height) {
            height = Math.round((height * maxDim) / width);
            width = maxDim;
          } else {
            width = Math.round((width * maxDim) / height);
            height = maxDim;
          }
        }
        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, width, height);

        const quality = this.checkImageQuality(canvas);

        canvas.toBlob(blob => {
          resolve({ optimizedBlob: blob || fileOrBlob, quality });
        }, 'image/jpeg', 0.88);
      };
      img.onerror = () => {
        URL.revokeObjectURL(objUrl);
        resolve({ optimizedBlob: fileOrBlob, quality: { ok: true } });
      };
      img.src = objUrl;
    });
  }

  setPageImage(pageIndex, blob, url, name = '') {
    // Revoke previous URL if present to prevent memory leaks
    if (this.pages[pageIndex] && this.pages[pageIndex].url) {
      URL.revokeObjectURL(this.pages[pageIndex].url);
    }

    this.pages[pageIndex] = { blob, url, name };
    this.onThumbnailsUpdated(this.pages);
  }

  removePage(pageIndex) {
    if (this.pages[pageIndex] && this.pages[pageIndex].url) {
      URL.revokeObjectURL(this.pages[pageIndex].url);
    }
    this.pages[pageIndex] = null;
    this.onThumbnailsUpdated(this.pages);
  }

  resetAllPages() {
    this.pages.forEach((p, idx) => {
      if (p && p.url) URL.revokeObjectURL(p.url);
      this.pages[idx] = null;
    });
    this.currentPage = 0;
    this.onThumbnailsUpdated(this.pages);
  }

  hasBothPages() {
    return Boolean(this.pages[0] && this.pages[1]);
  }

  getPageBlobs() {
    if (!this.hasBothPages()) {
      throw new Error('Both Page 1 and Page 2 are required.');
    }
    return {
      page1: this.pages[0].blob,
      page2: this.pages[1].blob
    };
  }

  async loadActualFixtureSample() {
    throw new Error('Demo sample fixtures are disabled in production. Please capture or upload real clinic intake forms.');
  }

  async loadSyntheticSample() {
    throw new Error('Synthetic sample generation is disabled in production. Please capture or upload real clinic intake forms.');
  }
}

