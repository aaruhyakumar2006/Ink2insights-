/**
 * API Service for Doc Scanner - Minimal Clinic Demo MVP.
 * Handles all HTTP communications with the Flask backend.
 * Offline-capable: extractPages() enqueues encrypted blobs when offline.
 */

import { offlineQueue, registerOfflineSupport } from './offline-queue.js';
export { offlineQueue, registerOfflineSupport };

const API_BASE = (window.location.origin && window.location.origin.startsWith('http'))
  ? '' 
  : 'http://localhost:5001';

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const opts = { ...options };
  const headers = opts.headers ? { ...opts.headers } : {};

  // Supabase / JWT Auth Token Header
  const authToken = localStorage.getItem('auth_token') || localStorage.getItem('supabase_access_token');
  if (authToken && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${authToken.trim()}`;
  }

  const customKey = localStorage.getItem('i2i_ai_api_key');
  if (customKey && !headers['X-AI-API-Key']) {
    headers['X-AI-API-Key'] = customKey.trim();
  }
  const customProvider = localStorage.getItem('i2i_ai_provider');
  if (customProvider && !headers['X-AI-Provider']) {
    headers['X-AI-Provider'] = customProvider.trim();
  }
  const customModel = localStorage.getItem('i2i_ai_model');
  if (customModel && !headers['X-AI-Model']) {
    headers['X-AI-Model'] = customModel.trim();
  }
  opts.headers = headers;
  try {
    const res = await fetch(url, opts);
    const contentType = res.headers.get('content-type') || '';
    let data;
    if (contentType.includes('application/json')) {
      data = await res.json();
    } else {
      data = await res.text();
    }
    
    if (!res.ok) {
      if (res.status === 401) {
        // Return to login screen on 401 Unauthorized
        // BUT: Don't redirect if we're on landing page (unauthenticated is expected there)
        localStorage.removeItem('auth_token');
        localStorage.removeItem('supabase_access_token');
        
        // Only redirect to login if we're NOT on landing or splash screens
        if (window.app && typeof window.app.go === 'function') {
          const currentScreen = window.app.state?.currentScreen || '';
          if (currentScreen !== 'landing' && currentScreen !== 'splash' && currentScreen !== 'login') {
            window.app.go('login');
          }
        }
      }
      const errMsg = (data && data.error) ? data.error : `Request failed (${res.status})`;
      const errorObj = new Error(errMsg);
      errorObj.status = res.status;
      errorObj.data = data;
      throw errorObj;
    }
    return data;
  } catch (err) {
    if (err.message && err.message.includes('Failed to fetch')) {
      throw new Error('Could not connect to Doc Scanner server. Please ensure the backend is running on port 5001.');
    }
    throw err;
  }
}

// Cache for blob URLs to avoid redundant network requests
const blobUrlCache = new Map();

/**
 * Rule 10.3: Authenticated file loader for <img> tags and document previews.
 * Fetches private files with Authorization header and resolves to a browser blob URL.
 */
export async function getFileBlobUrl(urlOrPath) {
  if (!urlOrPath) return '';
  if (urlOrPath.startsWith('data:') || urlOrPath.startsWith('blob:')) {
    return urlOrPath;
  }
  if (blobUrlCache.has(urlOrPath)) {
    return blobUrlCache.get(urlOrPath);
  }

  const targetUrl = urlOrPath.startsWith('http') ? urlOrPath : `${API_BASE}${urlOrPath}`;
  const authToken = localStorage.getItem('auth_token') || localStorage.getItem('supabase_access_token');
  const headers = {};
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken.trim()}`;
  }

  try {
    const res = await fetch(targetUrl, { headers });
    if (!res.ok) {
      return urlOrPath;
    }
    const blob = await res.blob();
    const objectUrl = URL.createObjectURL(blob);
    blobUrlCache.set(urlOrPath, objectUrl);
    return objectUrl;
  } catch (err) {
    console.warn('Could not load file via authenticated blob:', err);
    return urlOrPath;
  }
}

// Automatic token refresh helper (Rule 0.4)
export async function refreshAuthSession() {
  const currentToken = localStorage.getItem('auth_token') || localStorage.getItem('supabase_access_token');
  if (!currentToken) return null;

  try {
    const res = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${currentToken.trim()}`,
        'Content-Type': 'application/json'
      }
    });
    if (res.ok) {
      const data = await res.json();
      if (data && data.access_token) {
        localStorage.setItem('auth_token', data.access_token);
        return data.access_token;
      }
    }
  } catch (e) {
    console.warn('Flask session refresh error, checking supabase fallback:', e);
  }

  if (window.supabase && typeof window.supabase.createClient === 'function') {
    const supabaseUrl = localStorage.getItem('supabase_url');
    const supabaseAnonKey = localStorage.getItem('supabase_anon_key');
    if (supabaseUrl && supabaseAnonKey && !window.supabaseClient) {
      window.supabaseClient = window.supabase.createClient(supabaseUrl, supabaseAnonKey);
    }
    if (window.supabaseClient?.auth) {
      try {
        const { data } = await window.supabaseClient.auth.getSession();
        if (data?.session?.access_token) {
          localStorage.setItem('supabase_access_token', data.session.access_token);
          return data.session.access_token;
        }
      } catch (e) {
        console.warn('Auto refresh error:', e);
      }
    }
  }
  return localStorage.getItem('auth_token');
}

// Refresh token periodically (every 10 minutes)
if (typeof window !== 'undefined') {
  setInterval(refreshAuthSession, 10 * 60 * 1000);
}

export const api = {
  async getStatus() {
    return request('/api/status');
  },

  async getQualityConfig() {
    return request('/api/config/quality');
  },

  async checkQuality(imageBlob) {
    const formData = new FormData();
    formData.append('image', imageBlob);
    return request('/api/quality-check', {
      method: 'POST',
      body: formData
    });
  },

  async getStats() {
    return request('/api/stats');
  },

  async sendOtp(phone) {
    return request('/api/auth/send-otp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone })
    });
  },

  async login(payload) {
    return request('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  },

  async loginDemo() {
    return request('/api/auth/demo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
  },

  async verifyCommunity(code) {
    return request('/api/community/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code })
    });
  },

  async createCommunity(data) {
    return request('/api/community/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
  },

  async getCamps() {
    return request('/api/camps');
  },

  async createCamp(name, expectedRecords = 100, dateStr = 'Today') {
    return request('/api/camps', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, expected_records: expectedRecords, date_str: dateStr })
    });
  },

  async getRecords(campId = null, status = null) {
    const params = new URLSearchParams();
    if (campId) params.append('camp_id', campId);
    if (status) params.append('status', status);
    const qs = params.toString() ? `?${params.toString()}` : '';
    return request(`/api/records${qs}`);
  },

  async getRecord(recordId) {
    return request(`/api/records/${encodeURIComponent(recordId)}`);
  },

  async extractPages(page1Blob, page2Blob, campId = null, qualityBypassed = false, templateIds = null) {
    // ── Offline path: encrypt + enqueue ────────────────────────────────────
    if (!navigator.onLine) {
      const uploadId = `upl_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
      const apiHeaders = { 'X-Upload-ID': uploadId };
      const customKey = localStorage.getItem('i2i_ai_api_key');
      if (customKey) apiHeaders['X-AI-API-Key'] = customKey.trim();
      const customProvider = localStorage.getItem('i2i_ai_provider');
      if (customProvider) apiHeaders['X-AI-Provider'] = customProvider.trim();
      const customModel = localStorage.getItem('i2i_ai_model');
      if (customModel) apiHeaders['X-AI-Model'] = customModel.trim();
      if (qualityBypassed) apiHeaders['X-Quality-Bypassed'] = '1';

      // Compress images before offline queueing
      let p1Compressed = page1Blob;
      let p2Compressed = page2Blob;
      try {
        const { compressImageBlob } = await import('./scanner.js');
        [p1Compressed, p2Compressed] = await Promise.all([
          compressImageBlob(page1Blob, 1568, 0.8),
          compressImageBlob(page2Blob, 1568, 0.8)
        ]);
      } catch (e) {
        console.warn('Pre-queue compression fallback:', e);
      }

      const id = await offlineQueue.enqueue(p1Compressed, p2Compressed, { campId, uploadId, apiHeaders, templateIds });
      const queueLength = await offlineQueue.length();
      // Return a sentinel so callers can distinguish queued from real response
      return {
        _offline_queued: true,
        queue_id: id,
        upload_id: uploadId,
        queue_length: queueLength,
        message: `📵 No network — scan saved to encrypted offline queue (#${id}). Will sync automatically once connected.`,
      };
    }

    // ── Online path: normal upload ──────────────────────────────────────────
    const formData = new FormData();
    formData.append('page1', page1Blob, 'page1.jpg');
    formData.append('page2', page2Blob, 'page2.jpg');
    if (campId) formData.append('camp_id', campId);
    if (qualityBypassed) formData.append('quality_bypassed', '1');
    if (templateIds) {
      const tIds = Array.isArray(templateIds) ? templateIds.join(',') : templateIds;
      formData.append('template_ids', tIds);
    }

    return request('/api/extract', {
      method: 'POST',
      body: formData,
      headers: qualityBypassed ? { 'X-Quality-Bypassed': '1' } : {}
    });
  },

  /**
   * Direct extract function for internal queue-drain usage.
   * Always makes the live HTTP call (no offline check).
   */
  async extractPagesDirect(page1Blob, page2Blob, extraHeaders = {}) {
    const formData = new FormData();
    formData.append('page1', page1Blob, 'page1.jpg');
    formData.append('page2', page2Blob, 'page2.jpg');
    return request('/api/extract', {
      method: 'POST',
      body: formData,
      headers: extraHeaders,
    });
  },

  async saveRecord(recordData) {
    return request('/api/records', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(recordData)
    });
  },

  async reviewRecord(recordId, updateData, reviewer = 'Attending Physician') {
    return request(`/api/records/${encodeURIComponent(recordId)}/review`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...updateData, reviewed_by: reviewer })
    });
  },

  async clearAllData() {
    return request('/api/clear-data', {
      method: 'POST'
    });
  },

  async resetDemoData() {
    return this.clearAllData();
  },

  async getCampAnalytics(campId = null) {
    const qs = campId ? `?camp_id=${encodeURIComponent(campId)}` : '';
    return request(`/api/analytics${qs}`);
  },

  async eraseRecord(recordId) {
    return request(`/api/records/${encodeURIComponent(recordId)}/erase`, {
      method: 'POST'
    });
  },

  async getDoctorProfile(doctorId = null) {
    const qs = doctorId ? `?doctor_id=${encodeURIComponent(doctorId)}` : '';
    return request(`/api/doctor/profile${qs}`);
  },

  async updateDoctorProfile(payload) {
    return request('/api/doctor/profile', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  },

  async getCommunityMembers(communityId = null) {
    const qs = communityId ? `?community_id=${encodeURIComponent(communityId)}` : '';
    return request(`/api/community/members${qs}`);
  },

  async inviteDoctorToCommunity(email, role = 'doctor', expiresHours = 72) {
    return request('/api/community/invite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, role, expires_hours: expiresHours })
    });
  },

  async rotateCommunityCode(communityId, newCode = null) {
    return request('/api/community/rotate-code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ community_id: communityId, new_code: newCode })
    });
  },

  async revokeCommunityMember(communityId, doctorId) {
    return request('/api/community/members/revoke', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ community_id: communityId, doctor_id: doctorId })
    });
  },

  async calculatePaediatricScreening(payload) {
    return request('/api/paediatric/screen', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  },

  async checkDuplicate(campId, personName, phone = '', excludeId = null) {
    return request('/api/records/check-duplicate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        camp_id: campId,
        person_name: personName,
        phone,
        exclude_id: excludeId
      })
    });
  },

  async syncSupabase() {
    return request('/api/sync/supabase', {
      method: 'POST'
    });
  },

  async getAdminBilling() {
    return request('/api/admin/billing');
  },

  async lockRecord(recordId, doctorName = 'Attending Physician') {
    return request(`/api/records/${encodeURIComponent(recordId)}/lock`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ doctor_name: doctorName })
    });
  },

  async unlockRecord(recordId, doctorName = 'Attending Physician') {
    return request(`/api/records/${encodeURIComponent(recordId)}/unlock`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ doctor_name: doctorName })
    });
  },

  async approveRecord(recordId, approvedBy = 'Attending Physician') {
    return request(`/api/records/${encodeURIComponent(recordId)}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approved_by: approvedBy })
    });
  },

  async getUsage() {
    return request('/api/usage', {
      headers: { 'X-Admin-Key': 'admin_secret_key' }
    });
  },

  async getUsageLedger(page = 1, limit = 50) {
    return request(`/api/usage/ledger?page=${page}&limit=${limit}`, {
      headers: { 'X-Admin-Key': 'admin_secret_key' }
    });
  },

  async createBillingOrder(papers = 1000) {
    return request('/api/billing/order', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ papers })
    });
  },

  async getInvoices() {
    return request('/api/billing/invoices');
  },

  getInvoiceDownloadUrl(invoiceNumber) {
    return `${API_BASE}/api/billing/invoices/${encodeURIComponent(invoiceNumber)}/download`;
  },

  async setAiPause(orgId = null, paused = true) {
    return request('/api/admin/ai-pause', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Admin-Key': 'admin_secret_key' },
      body: JSON.stringify({ org_id: orgId, paused })
    });
  },

  async cleanupExpiredReservations(expiryDays = 7) {
    return request('/api/admin/cleanup-expired-reservations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Admin-Key': 'admin_secret_key' },
      body: JSON.stringify({ expiry_days: expiryDays })
    });
  },

  getExportUrl(campId = null, onlyReviewed = false, format = 'xlsx', formType = null) {
    const params = new URLSearchParams();
    if (campId) params.append('camp_id', campId);
    if (onlyReviewed) params.append('only_reviewed', 'true');
    if (formType) params.append('type', formType);
    params.append('format', format);
    const qs = params.toString() ? `?${params.toString()}` : '';
    return `${API_BASE}/api/export${qs}`;
  },

  getAdultExportUrl(campId = null, onlyReviewed = false) {
    const params = new URLSearchParams();
    if (campId) params.append('camp_id', campId);
    if (onlyReviewed) params.append('only_reviewed', 'true');
    const qs = params.toString() ? `?${params.toString()}` : '';
    return `${API_BASE}/api/export/adult/excel${qs}`;
  },

  getPaediatricExportUrl(campId = null, onlyReviewed = false) {
    const params = new URLSearchParams();
    if (campId) params.append('camp_id', campId);
    if (onlyReviewed) params.append('only_reviewed', 'true');
    const qs = params.toString() ? `?${params.toString()}` : '';
    return `${API_BASE}/api/export/paediatric/excel${qs}`;
  },

  getCampExportUrl(campId, format = 'xlsx', formType = null) {
    const params = new URLSearchParams();
    params.append('format', format);
    if (formType) params.append('type', formType);
    return `${API_BASE}/api/camps/${encodeURIComponent(campId)}/export?${params.toString()}`;
  },

  async getForms() {
    return request('/api/forms');
  },

  async getFormStructure(formId) {
    return request(`/api/forms/${encodeURIComponent(formId)}`);
  },

  async getFormAttributes(formId) {
    return request(`/api/forms/${encodeURIComponent(formId)}/attributes`);
  },

  async getFormSchema(formId) {
    return request(`/api/forms/${encodeURIComponent(formId)}/schema`);
  },

  async getAIStatus() {
    return request('/api/ai/status');
  },

  async classifyTemplate(footerCode, headerText = null) {
    return request('/api/templates/classify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ footer_code: footerCode, header_text: headerText })
    });
  },

  async pairCase(historyPage, examPage, sessionId = null) {
    return request('/api/cases/pair', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        history_page: historyPage,
        exam_page: examPage,
        session_id: sessionId
      })
    });
  },

  async getTemplate(templateId, uiSchema = false) {
    const qs = uiSchema ? '?ui_schema=true' : '';
    return request(`/api/templates/${encodeURIComponent(templateId)}${qs}`);
  },

  async listTemplates() {
    return request('/api/templates');
  }
};

