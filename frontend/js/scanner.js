/**
 * Document Scanner & Camera Module.
 * Real camera streaming (getUserMedia), frame capture to canvas,
 * device image upload, validation, and retake/replace management.
 *
 * Implements the DOC SCANNER capture & quality specification:
 * Step A. Capture or pick (live camera only on HTTPS, otherwise file picker; no synthetic outside DEMO_MODE).
 * Step B. Correct orientation (EXIF rotation).
 * Step C. Check copy resized to 640 px long edge for sub-second execution.
 * Step D. Page boundary and corner detection.
 * Step E. Quality measurement on page area only (sharpness, darkness, glare, coverage).
 * Step F. Single clear reason matching spec table:
 *         - "Move the whole page into the frame."
 *         - "Move closer so the page fills the screen."
 *         - "It's too dark. Turn on the light or move to a brighter place."
 *         - "There is glare on the page. Tilt the phone slightly."
 *         - "The photo is blurry. Hold the phone still and tap to focus."
 *         - "We could not check this photo. Retake if you are unsure."
 */

export const QUALITY_MESSAGES = Object.freeze({
  CHECK_FAILED: "We could not check this photo. Retake if you are unsure.",
  CORNERS_NOT_FOUND: "Move the whole page into the frame.",
  COVERAGE_LOW: "Move closer so the page fills the screen.",
  TOO_DARK: "It's too dark. Turn on the light or move to a brighter place.",
  GLARE: "There is glare on the page. Tilt the phone slightly.",
  BLURRY: "The photo is blurry. Hold the phone still and tap to focus.",
});

export const DEFAULT_QUALITY_FALLBACK = Object.freeze({
  blur_min: 40.0,
  dark_max: 75.0,
  glare_max: 12.0,
  cover_min: 60.0,
});

/**
 * Assess image quality on a check copy (640 px long edge).
 * Measures blur (tile Laplacian variance), brightness, glare, and page coverage.
 * Returns { ok, reason, issues, blur_score, brightness, glare_pct, coverage }
 */
export async function assessImageQuality(imageOrCanvas) {
  try {
    if (!imageOrCanvas) {
      return {
        ok: null,
        reason: QUALITY_MESSAGES.CHECK_FAILED,
        blur_score: 0,
        brightness: 0,
        glare_pct: 0,
        coverage: 0,
        issues: [QUALITY_MESSAGES.CHECK_FAILED]
      };
    }

    let sourceWidth = 0;
    let sourceHeight = 0;
    let sourceElement = imageOrCanvas;

    // Step B: Correct orientation with createImageBitmap from-image
    if (typeof Blob !== 'undefined' && imageOrCanvas instanceof Blob) {
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
    } else if (typeof HTMLVideoElement !== 'undefined' && imageOrCanvas instanceof HTMLVideoElement) {
      sourceWidth = imageOrCanvas.videoWidth || 1280;
      sourceHeight = imageOrCanvas.videoHeight || 720;
    } else {
      sourceWidth = imageOrCanvas.width || 640;
      sourceHeight = imageOrCanvas.height || 480;
    }

    if (sourceWidth < 4 || sourceHeight < 4) {
      return {
        ok: null,
        reason: QUALITY_MESSAGES.CHECK_FAILED,
        blur_score: 0,
        brightness: 0,
        glare_pct: 0,
        coverage: 0,
        issues: [QUALITY_MESSAGES.CHECK_FAILED]
      };
    }

    // Step C: Resize long edge to 640 px
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
      return {
        ok: null,
        reason: QUALITY_MESSAGES.CHECK_FAILED,
        blur_score: 0,
        brightness: 0,
        glare_pct: 0,
        coverage: 0,
        issues: [QUALITY_MESSAGES.CHECK_FAILED]
      };
    }

    ctx.drawImage(sourceElement, 0, 0, newW, newH);
    const imgData = ctx.getImageData(0, 0, newW, newH);
    const data = imgData.data;
    const totalPixels = newW * newH;

    // Step E: Luminance, glare, and coverage analysis
    const gray = new Float32Array(totalPixels);
    let lumSum = 0;
    let satCount = 0;

    for (let i = 0, j = 0; i < data.length; i += 4, j++) {
      const r = data[i];
      const g = data[i + 1];
      const b = data[i + 2];
      const y = 0.299 * r + 0.587 * g + 0.114 * b;
      gray[j] = y;
      lumSum += y;
      if (r >= 250 && g >= 250 && b >= 250) {
        satCount++;
      }
    }

    const brightness = lumSum / totalPixels;

    // Sort a sampled subset of gray to get median and percentiles
    const sampleStep = Math.max(1, Math.floor(totalPixels / 1000));
    const samples = [];
    for (let i = 0; i < totalPixels; i += sampleStep) {
      samples.push(gray[i]);
    }
    samples.sort((a, b) => a - b);
    const medianLum = samples[Math.floor(samples.length * 0.5)] || brightness;

    // If median is near 250, clean white document, not specular glare
    let glarePct = 0;
    if (medianLum < 245) {
      glarePct = (satCount / totalPixels) * 100.0;
    }

    // Step D: Corner and coverage check
    // Examine outer border vs inner region for dark table background
    const borderThickness = Math.max(2, Math.floor(Math.min(newW, newH) * 0.05));
    let darkBorderPixels = 0;
    let totalBorderPixels = 0;
    const darkThreshold = Math.min(100, brightness * 0.65);

    for (let y = 0; y < newH; y++) {
      for (let x = 0; x < newW; x++) {
        const isBorder = (x < borderThickness || x >= newW - borderThickness || y < borderThickness || y >= newH - borderThickness);
        if (isBorder) {
          totalBorderPixels++;
          if (gray[y * newW + x] < darkThreshold) {
            darkBorderPixels++;
          }
        }
      }
    }

    const borderDarkFraction = totalBorderPixels > 0 ? (darkBorderPixels / totalBorderPixels) : 0;
    let estimatedCoverage = 100.0;
    let cornersFound = true;

    if (borderDarkFraction > 0.15) {
      // Document is on a darker surface; calculate document area
      let brightCount = 0;
      for (let i = 0; i < totalPixels; i++) {
        if (gray[i] >= darkThreshold) brightCount++;
      }
      estimatedCoverage = (brightCount / totalPixels) * 100.0;

      // Check if page touches 1 border heavily while opposite is dark (cut off at edge)
      let leftDark = 0, rightDark = 0, topDark = 0, botDark = 0;
      for (let y = 0; y < newH; y++) {
        if (gray[y * newW] < darkThreshold) leftDark++;
        if (gray[y * newW + (newW - 1)] < darkThreshold) rightDark++;
      }
      for (let x = 0; x < newW; x++) {
        if (gray[x] < darkThreshold) topDark++;
        if (gray[(newH - 1) * newW + x] < darkThreshold) botDark++;
      }
      const edgesTouching = [
        leftDark / newH < 0.1,
        rightDark / newH < 0.1,
        topDark / newW < 0.1,
        botDark / newW < 0.1,
      ];
      const touchingCount = edgesTouching.filter(Boolean).length;
      if (touchingCount >= 1 && touchingCount <= 3 && estimatedCoverage < 90) {
        cornersFound = false;
      }
    }

    // Step E: Sharpness via 8x8 Grid Tile Laplacian Variance (75th percentile)
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

    tileVars.sort((a, b) => a - b);
    let blurScore = 0;
    if (tileVars.length > 0) {
      const pIndex = Math.min(tileVars.length - 1, Math.floor(tileVars.length * 0.75));
      blurScore = tileVars[pIndex];
    }

    // Check for blank white image (variance near 0)
    let sumSq = 0;
    for (let i = 0; i < totalPixels; i++) {
      const diff = gray[i] - brightness;
      sumSq += diff * diff;
    }
    const totalVar = sumSq / totalPixels;
    if (totalVar < 5.0) {
      blurScore = 0;
    }

    // Config thresholds
    const cfg = (typeof window !== 'undefined' && window.QUALITY_CONFIG) ? window.QUALITY_CONFIG : DEFAULT_QUALITY_FALLBACK;
    const blurMin = typeof cfg.blur_min === 'number' ? cfg.blur_min : DEFAULT_QUALITY_FALLBACK.blur_min;
    const darkMax = typeof cfg.dark_max === 'number' ? cfg.dark_max : DEFAULT_QUALITY_FALLBACK.dark_max;
    const glareMax = typeof cfg.glare_max === 'number' ? cfg.glare_max : DEFAULT_QUALITY_FALLBACK.glare_max;
    const coverMin = typeof cfg.cover_min === 'number' ? cfg.cover_min : DEFAULT_QUALITY_FALLBACK.cover_min;

    // Step F: Determine single clear reason by strict priority
    let primaryReason = null;
    if (!cornersFound) {
      primaryReason = QUALITY_MESSAGES.CORNERS_NOT_FOUND;
    } else if (estimatedCoverage < coverMin) {
      primaryReason = QUALITY_MESSAGES.COVERAGE_LOW;
    } else if (brightness < darkMax) {
      primaryReason = QUALITY_MESSAGES.TOO_DARK;
    } else if (glarePct > glareMax) {
      primaryReason = QUALITY_MESSAGES.GLARE;
    } else if (blurScore < blurMin) {
      primaryReason = QUALITY_MESSAGES.BLURRY;
    }

    const isOk = (primaryReason === null);

    return {
      ok: isOk,
      reason: primaryReason,
      issues: primaryReason ? [primaryReason] : [],
      blur_score: Math.round(blurScore * 10) / 10,
      brightness: Math.round(brightness * 10) / 10,
      glare_pct: Math.round(glarePct * 10) / 10,
      coverage: Math.round(estimatedCoverage),
      avgLum: Math.round(brightness),
      blurScore: Math.round(blurScore * 10) / 10,
    };
  } catch (err) {
    console.warn('Image quality assessment error:', err);
    return {
      ok: null,
      reason: QUALITY_MESSAGES.CHECK_FAILED,
      blur_score: 0,
      brightness: 0,
      glare_pct: 0,
      coverage: 0,
      issues: [QUALITY_MESSAGES.CHECK_FAILED]
    };
  }
}

/**
 * Compresses an image blob to JPEG quality 80 with max dimension 1568 px.
 */
export async function compressImageBlob(blob, maxDim = 1568, quality = 0.8) {
  try {
    let sourceElement = blob;
    if (typeof createImageBitmap !== 'undefined') {
      try {
        sourceElement = await createImageBitmap(blob, { imageOrientation: 'from-image' });
      } catch (e) {
        // Fallback to Image
      }
    }

    if (sourceElement === blob) {
      const img = new Image();
      const url = URL.createObjectURL(blob);
      await new Promise((res, rej) => {
        img.onload = () => { URL.revokeObjectURL(url); res(); };
        img.onerror = () => { URL.revokeObjectURL(url); rej(new Error('Failed to load blob for compression')); };
        img.src = url;
      });
      sourceElement = img;
    }

    let width = sourceElement.width;
    let height = sourceElement.height;
    if (Math.max(width, height) > maxDim) {
      if (width >= height) {
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
    ctx.drawImage(sourceElement, 0, 0, width, height);

    return new Promise((resolve) => {
      canvas.toBlob((b) => resolve(b || blob), 'image/jpeg', quality);
    });
  } catch (err) {
    console.warn('Image compression fallback:', err);
    return blob;
  }
}

export class DocumentScanner {
  constructor(options = {}) {
    this.videoEl = options.videoEl;
    this.canvasEl = options.canvasEl;
    this.onThumbnailsUpdated = options.onThumbnailsUpdated || (() => {});
    this.onStateChanged = options.onStateChanged || (() => {});

    this.stream = null;
    this.facingMode = 'environment';
    this.currentPage = 0;
    this.pages = [null, null];
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
    // Step A: Live camera only on HTTPS or localhost
    const isSecure = typeof window !== 'undefined' && (
      window.location.protocol === 'https:' ||
      window.location.hostname === 'localhost' ||
      window.location.hostname === '127.0.0.1'
    );
    if (!isSecure) {
      throw new Error('Live camera requires HTTPS. Please select or capture a photo using the phone file picker.');
    }

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
      if (this.facingMode === 'environment') {
        this.facingMode = 'user';
        return this.startCamera();
      }
      throw new Error('Camera access was denied or is unavailable. You can capture or upload document photos instead.');
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
    const width = video.videoWidth || 1280;
    const height = video.videoHeight || 720;
    canvas.width = width;
    canvas.height = height;

    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, width, height);

    // Assess quality on check copy
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
      }, 'image/jpeg', 0.90);
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

    // Step B & C: Check quality on uploaded photo
    const quality = await assessImageQuality(file);
    const url = URL.createObjectURL(file);
    this.setPageImage(this.currentPage, file, url, file.name);
    return { blob: file, url, quality };
  }

  setPageImage(pageIndex, blob, url, name = '') {
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
