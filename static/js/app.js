/* ================================================================
   Facebook Automation — app.js  v15
   Full suite: YouTube Clipper + Video Merger + AI Video Generator
   ================================================================ */
'use strict';


const mapLang = (l) => {
    if(l==='Urdu') return 'ur-PK';
    if(l==='Hindi') return 'hi-IN';
    if(l==='English') return 'en-US';
    return l;
};

const state = {
    statsFiles: 0,
    statsClips: 0,
    statsAI: 0,
    voiceData: null,  // { voices, voice_styles, mood_labels, age_presets }
};

function $(id)   { return document.getElementById(id); }
function $q(sel) { return document.querySelector(sel); }

function showToast(msg, type = 'success', duration = 3500) {
    const t = $('toast');
    if (!t) return;
    t.textContent = msg;
    t.className = `toast ${type} show`;
    setTimeout(() => t.classList.remove('show'), duration);
}

function animateCount(el, target) {
    if (!el) return;
    const start = parseInt(el.textContent) || 0;
    const diff  = target - start;
    if (diff === 0) return;
    const step  = Math.ceil(Math.abs(diff) / 10) || 1;
    const dir   = diff > 0 ? 1 : -1;
    let cur = start;
    const iv = setInterval(() => {
        cur += dir * step;
        if ((dir > 0 && cur >= target) || (dir < 0 && cur <= target)) {
            cur = target;
            clearInterval(iv);
        }
        el.textContent = cur;
    }, 30);
}

// ─────────────────────────────────────────────────────────────────
// MAIN TAB NAVIGATION
// ─────────────────────────────────────────────────────────────────
function initMainTabs() {
    const tabBtns = document.querySelectorAll('.main-tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.dataset.tab;
            // Deactivate all
            tabBtns.forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
            // Activate target
            btn.classList.add('active');
            const panel = $(`tab-${tabId}`);
            if (panel) panel.classList.add('active');
        });
    });
}

// ─────────────────────────────────────────────────────────────────
// GALLERY / LIBRARY
// ─────────────────────────────────────────────────────────────────
async function loadGallery() {
    const container = $('gallery-container');
    if (!container) return;

    const searchVal = ($('library-search')?.value || '').toLowerCase();

    try {
        const res  = await fetch('/api/outputs');
        const data = await res.json();

        const filtered = searchVal
            ? data.filter(f => f.filename.toLowerCase().includes(searchVal))
            : data;

        if (!filtered.length) {
            container.innerHTML = `
                <div class="empty-library">
                    <div class="empty-art">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                            <rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"/>
                            <line x1="7" y1="2" x2="7" y2="22"/>
                            <line x1="17" y1="2" x2="17" y2="22"/>
                            <line x1="2" y1="12" x2="22" y2="12"/>
                        </svg>
                    </div>
                    <p class="empty-title">${searchVal ? 'No results found' : 'No exported clips'}</p>
                    <p class="empty-desc">${searchVal ? 'Try a different search term.' : 'Run a clipping operation to begin.'}</p>
                </div>`;
            animateCount($('stat-files'), 0);
            return;
        }

        state.statsFiles = data.length;
        animateCount($('stat-files'), data.length);

        container.innerHTML = filtered.map(file => {
            const isClip  = file.filename.includes('clip_');
            const isAI    = file.filename.includes('ai_video_');
            const isMerge = file.filename.includes('merged_');
            let iconSvg;
            if (isAI) {
                iconSvg = `<svg class="card-file-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
            } else if (isMerge) {
                iconSvg = `<svg class="card-file-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"/><line x1="7" y1="2" x2="7" y2="22"/></svg>`;
            } else {
                iconSvg = `<svg class="card-file-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 10a4 4 0 108 0 4 4 0 00-8 0zm0 0V6a4 4 0 018 0v4m-8 0h8" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
            }
            return `
            <div class="video-card" data-fn="${file.filename}">
                <div class="video-card-info">
                    <span class="video-card-title">${iconSvg} ${file.filename}</span>
                    <span class="video-card-meta">${file.duration} &nbsp;·&nbsp; ${file.size}</span>
                </div>
                <div class="video-card-actions">
                    <button class="action-btn play-action" data-fn="${file.filename}">
                        <svg viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                        Play
                    </button>
                    <button class="action-btn download-action" data-fn="${file.filename}">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4m4-5l5 5 5-5m-5 5V3" stroke-linecap="round" stroke-linejoin="round"/></svg>
                    </button>
                </div>
            </div>`;
        }).join('');

        // Wire up play / download
        container.querySelectorAll('.play-action').forEach(btn => {
            btn.addEventListener('click', () => openVideoModal(btn.dataset.fn));
        });
        container.querySelectorAll('.download-action').forEach(btn => {
            btn.addEventListener('click', () => {
                const a = document.createElement('a');
                a.href = `/api/outputs/${btn.dataset.fn}`;
                a.download = btn.dataset.fn;
                a.click();
            });
        });

    } catch (e) {
        console.error('Error loading library:', e);
        container.innerHTML = `<div class="empty-library"><p class="empty-desc">Failed to load library.</p></div>`;
    }
}

// ─────────────────────────────────────────────────────────────────
// CLEAR LIBRARY
// ─────────────────────────────────────────────────────────────────
async function clearLibrary() {
    const confirmed = confirm('🗑️ Delete ALL exported files from disk?\n\nThis cannot be undone.');
    if (!confirmed) return;

    const btn = $('clear-library-btn');
    if (btn) btn.disabled = true;

    try {
        const res  = await fetch('/api/clear-library', { method: 'POST' });
        const data = await res.json();
        showToast(`✅ Cleared ${data.deleted} file${data.deleted !== 1 ? 's' : ''} from library`, 'success');
        animateCount($('stat-files'), 0);
        animateCount($('stat-clips'), 0);
        animateCount($('stat-ai'), 0);
        await loadGallery();
    } catch (e) {
        showToast('❌ Failed to clear library', 'error');
    } finally {
        if (btn) btn.disabled = false;
    }
}

// ─────────────────────────────────────────────────────────────────
// VIDEO PLAYER MODAL
// ─────────────────────────────────────────────────────────────────
function openVideoModal(filename) {
    $('modal-title').textContent = `▶ ${filename}`;
    $('modal-player').src = `/api/outputs/${filename}`;
    $('video-modal').classList.add('active');
    $('modal-player').play();
}
function closeVideoModal() {
    $('modal-player').pause();
    $('modal-player').src = '';
    $('video-modal').classList.remove('active');
}

// ─────────────────────────────────────────────────────────────────
// SLICING TOGGLE (YouTube Clipper)
// ─────────────────────────────────────────────────────────────────
function initAudioToggle() {
    const clipToggles = document.querySelectorAll('.segment-tab-btn');
    clipToggles.forEach(btn => {
        btn.addEventListener('click', () => {
            clipToggles.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const type = btn.dataset.type;
            $('full-clip-panel')?.classList.toggle('active', type === 'full');
            $('auto-clip-panel')?.classList.toggle('active', type === 'auto');
            $('timestamps-clip-panel')?.classList.toggle('active', type === 'timestamps');
        });
    });
}

function startProgress(fillId, pctId, stepId, steps, onDone) {
    const fill = $(fillId);
    const pct  = $(pctId);
    const step = $(stepId);
    if (!fill) return null;

    let idx = 0;
    let cur = 0;

    const iv = setInterval(() => {
        if (idx >= steps.length) { clearInterval(iv); onDone?.(); return; }
        const { pct: target, label, dur } = steps[idx];
        step.textContent = label;

        const speed = (target - cur) / (dur / 120);
        const inner = setInterval(() => {
            cur = Math.min(cur + speed, target);
            fill.style.width = `${cur}%`;
            pct.textContent  = `${Math.round(cur)}%`;
            if (cur >= target) { clearInterval(inner); idx++; }
        }, 120);
    }, 0);

    return iv;
}

function showProgress(progressId) {
    $(progressId)?.classList.add('visible');
}
function hideProgress(progressId) {
    $(progressId)?.classList.remove('visible');
}

// ─────────────────────────────────────────────────────────────────
// CLIP FORM SUBMISSION (YouTube Clipper)
// ─────────────────────────────────────────────────────────────────
function initClipForm() {
    const form = $('clip-form');
    if (!form) return;

    form.addEventListener('submit', async e => {
        e.preventDefault();
        const url = $('url')?.value.trim();
        const isValidUrl = url && (url.includes('youtube.com') || url.includes('youtu.be') || url.includes('tiktok.com') || url.includes('instagram.com'));
        if (!isValidUrl) {
            showToast('⚠️ Please enter a valid YouTube, TikTok, or Instagram URL', 'error'); return;
        }

        const btn = $('clip-submit-btn');
        btn.disabled = true; btn.classList.add('loading');
        showProgress('clip-progress');

        const steps = [
            { pct: 20, label: '⬇️ Downloading video…',        dur: 3000 },
            { pct: 50, label: '✂️ Slicing into clips…',         dur: 2500 },
            { pct: 75, label: '🎨 Applying safety filters…',   dur: 2000 },
            { pct: 90, label: '💾 Saving clips to library…',   dur: 1200 },
            { pct: 99, label: '📦 Cleaning up temp files…',    dur: 600  },
        ];
        startProgress('clip-fill', 'clip-pct', 'clip-step', steps);

        try {
            const fd  = new FormData(form);
            const activeMethodBtn = $q('.segment-tab-btn.active');
            if (activeMethodBtn) {
                fd.set('slicing_method', activeMethodBtn.dataset.type);
            }
            
            const res = await fetch('/api/clip', { method: 'POST', body: fd });
            const data = await res.json();

            $('clip-fill').style.width = '100%';
            $('clip-pct').textContent  = '100%';
            $('clip-step').textContent = '✅ Done!';

            if (data.success) {
                showToast(`✅ ${data.message}`, 'success', 5000);
                state.statsClips += data.filenames?.length || 0;
                animateCount($('stat-clips'), state.statsClips);
                await loadGallery();
            } else {
                showToast(`❌ ${data.error}`, 'error', 7000);
            }
        } catch (err) {
            showToast('❌ Network error — check server logs', 'error');
        } finally {
            btn.disabled = false; btn.classList.remove('loading');
            setTimeout(() => hideProgress('clip-progress'), 2000);
        }
    });
}

// ─────────────────────────────────────────────────────────────────
// VOICE DATA LOADING
// ─────────────────────────────────────────────────────────────────
async function loadVoiceData() {
    try {
        const res = await fetch('/api/voices');
        state.voiceData = await res.json();
        // Populate both merge and AI voice dropdowns
        populateLanguageDropdown('merge-language', 'merge-voice', 'merge-style');
        populateLanguageDropdown('ai-language', 'ai-voice', null);
        populateLanguageDropdown('dub-language', 'dub-voice', null);
        populateLanguageDropdown('cartoon-language', 'cartoon-voice', null);
        

        if (document.getElementById('autodraft-lang')) {
            populateVoiceDropdown('autodraft-voice', mapLang(document.getElementById('autodraft-lang').value), null);
        }

    } catch (e) {
        console.error('Failed to load voice data:', e);
    }
}

function populateLanguageDropdown(langSelectId, voiceSelectId, styleSelectId) {
    const langSel = $(langSelectId);
    if (!langSel || !state.voiceData) return;

    const voices = state.voiceData.voices;
    langSel.innerHTML = '';

    Object.keys(voices).forEach((lang, i) => {
        const opt = document.createElement('option');
        opt.value = lang;
        opt.textContent = lang;
        if (i === 0) opt.selected = true;
        langSel.appendChild(opt);
    });

    // Update voices on language change
    const updateVoices = () => {
        const lang = langSel.value;
        populateVoiceDropdown(voiceSelectId, lang, styleSelectId);
    };

    langSel.addEventListener('change', updateVoices);
    updateVoices(); // initial populate
}

function populateVoiceDropdown(voiceSelectId, lang, styleSelectId) {
    const voiceSel = $(voiceSelectId);
    if (!voiceSel || !state.voiceData) return;

    const voices = state.voiceData.voices[lang] || {};
    voiceSel.innerHTML = '';

    Object.entries(voices).forEach(([label, id], i) => {
        const opt = document.createElement('option');
        opt.value = id;
        opt.textContent = label;
        if (i === 0) opt.selected = true;
        voiceSel.appendChild(opt);
    });

    // Update styles on voice change
    const updateStyles = () => {
        if (styleSelectId) {
            populateStyleDropdown(styleSelectId, voiceSel.value);
        }
    };

    voiceSel.addEventListener('change', updateStyles);
    updateStyles(); // initial populate
}

function populateStyleDropdown(styleSelectId, voiceId) {
    const styleSel = $(styleSelectId);
    if (!styleSel || !state.voiceData) return;

    const styles = state.voiceData.voice_styles[voiceId] || [];
    const labels = state.voiceData.mood_labels || {};

    styleSel.innerHTML = '<option value="">🎙️ Default Style</option>';

    styles.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s;
        opt.textContent = labels[s] || s;
        styleSel.appendChild(opt);
    });
}

// ─────────────────────────────────────────────────────────────────
// VOICE PREVIEW
// ─────────────────────────────────────────────────────────────────
function initVoicePreview(previewBtnId, langSelectId, voiceSelectId, styleSelectId, rateSelectId, pitchSelectId) {
    const btn = $(previewBtnId);
    if (!btn) return;

    btn.addEventListener('click', async () => {
        const audio = $('preview-audio');
        
        // If already playing this preview, toggle pause/play
        if (btn.classList.contains('playing')) {
            if (!audio.paused) {
                audio.pause();
                btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="5 3 19 12 5 21 5 3"/></svg> Paused`;
            } else {
                audio.play();
                btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="10" y1="15" x2="10" y2="9"/><line x1="14" y1="15" x2="14" y2="9"/></svg> Playing…`;
            }
            return;
        }

        // Otherwise start a new preview
        const voice = $(voiceSelectId)?.value;
        const lang  = $(langSelectId)?.value;
        const style = styleSelectId ? ($(styleSelectId)?.value || '') : '';
        const rate  = $(rateSelectId)?.value || '+0%';
        const pitch = $(pitchSelectId)?.value || '+0Hz';

        if (!voice) { showToast('⚠️ Select a voice first', 'error'); return; }

        btn.classList.add('playing');
        btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="10" y1="15" x2="10" y2="9"/><line x1="14" y1="15" x2="14" y2="9"/></svg> Playing…`;

        try {
            const fd = new FormData();
            fd.append('voice', voice);
            fd.append('lang', lang);
            fd.append('style', style);
            fd.append('rate', rate);
            fd.append('pitch', pitch);

            const res = await fetch('/api/preview-voice', { method: 'POST', body: fd });
            if (!res.ok) throw new Error('Preview failed');

            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            audio.src = url;
            audio.play();

            audio.onended = () => {
                btn.classList.remove('playing');
                btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="5 3 19 12 5 21 5 3"/></svg> Preview Voice`;
                URL.revokeObjectURL(url);
            };
        } catch (e) {
            showToast('❌ Voice preview failed', 'error');
            btn.classList.remove('playing');
            btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="5 3 19 12 5 21 5 3"/></svg> Preview Voice`;
        }
    });
}

// ─────────────────────────────────────────────────────────────────
// AGE PRESETS
// ─────────────────────────────────────────────────────────────────
function initAgePresets(containerId, rateSelectId, pitchSelectId) {
    const container = $(containerId);
    if (!container) return;

    container.querySelectorAll('.age-preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            // Update active state
            container.querySelectorAll('.age-preset-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Set rate & pitch
            const rate = btn.dataset.rate;
            const pitch = btn.dataset.pitch;
            const rateSel = $(rateSelectId);
            const pitchSel = $(pitchSelectId);

            if (rateSel) {
                // Find matching option or add it
                let found = false;
                for (const opt of rateSel.options) {
                    if (opt.value === rate) { opt.selected = true; found = true; break; }
                }
                if (!found) {
                    const opt = document.createElement('option');
                    opt.value = rate; opt.textContent = rate; opt.selected = true;
                    rateSel.appendChild(opt);
                }
            }
            if (pitchSel) {
                let found = false;
                for (const opt of pitchSel.options) {
                    if (opt.value === pitch) { opt.selected = true; found = true; break; }
                }
                if (!found) {
                    const opt = document.createElement('option');
                    opt.value = pitch; opt.textContent = pitch; opt.selected = true;
                    pitchSel.appendChild(opt);
                }
            }
        });
    });
}

// ─────────────────────────────────────────────────────────────────
// AUDIO SOURCE TABS (Video Merger)
// ─────────────────────────────────────────────────────────────────
function initAudioSourceTabs() {
    const btns = document.querySelectorAll('.audio-src-btn');
    btns.forEach(btn => {
        btn.addEventListener('click', () => {
            btns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            const src = btn.dataset.src;
            $('merge-audio-script')?.classList.toggle('active', src === 'script');
            $('merge-audio-upload')?.classList.toggle('active', src === 'upload');
            $('merge-audio-none')?.classList.toggle('active', src === 'none');
        });
    });
}

// ─────────────────────────────────────────────────────────────────
// FILE UPLOAD DROP ZONE + FILE LIST
// ─────────────────────────────────────────────────────────────────
function initDropZone(zoneId, inputId, listId) {
    const zone = $(zoneId);
    const input = $(inputId);
    const list = $(listId);
    if (!zone || !input) return;

    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', e => {
        e.preventDefault();
        zone.classList.remove('drag-over');
        if (e.dataTransfer.files.length) {
            input.files = e.dataTransfer.files;
            updateFileList(input, list);
        }
    });

    input.addEventListener('change', () => updateFileList(input, list));
}

function updateFileList(input, listEl) {
    if (!listEl) return;
    const files = input.files;
    if (!files || !files.length) {
        listEl.innerHTML = '';
        return;
    }
    listEl.innerHTML = Array.from(files).map(f => `
        <div class="upload-file-item">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
            ${f.name} <span style="color:var(--text-muted);margin-left:auto;">${(f.size / 1024 / 1024).toFixed(1)} MB</span>
        </div>
    `).join('');
}

// ─────────────────────────────────────────────────────────────────
// VIDEO MERGER FORM SUBMISSION
// ─────────────────────────────────────────────────────────────────
function initMergeForm() {
    const form = $('merge-form');
    if (!form) return;

    form.addEventListener('submit', async e => {
        e.preventDefault();

        const videoInput = $('merge-videos-input');
        if (!videoInput?.files?.length) {
            showToast('⚠️ Please upload at least one video file', 'error');
            return;
        }

        const btn = $('merge-submit-btn');
        btn.disabled = true; btn.classList.add('loading');
        showProgress('merge-progress');

        const steps = [
            { pct: 25, label: '🎬 Merging video clips…',       dur: 3000 },
            { pct: 50, label: '🎙️ Generating voiceover…',       dur: 2500 },
            { pct: 75, label: '🎵 Mixing audio tracks…',        dur: 2000 },
            { pct: 90, label: '💾 Encoding final video…',       dur: 1500 },
            { pct: 99, label: '📦 Cleaning up…',                dur: 500  },
        ];
        startProgress('merge-fill', 'merge-pct', 'merge-step', steps);

        try {
            const fd = new FormData();

            // Videos
            for (const f of videoInput.files) {
                fd.append('videos', f);
            }

            // Aspect ratio
            const ar = form.querySelector('input[name="merge_aspect_ratio"]:checked');
            fd.append('aspect_ratio', ar?.value || 'vertical');

            // Audio source
            const activeAudioSrc = $q('.audio-src-btn.active')?.dataset.src || 'script';
            fd.append('audio_source', activeAudioSrc);

            if (activeAudioSrc === 'script') {
                fd.append('script_text', $('merge-script')?.value || '');
                fd.append('language', $('merge-language')?.value || 'en-US');
                fd.append('voice', $('merge-voice')?.value || 'en-US-EmmaMultilingualNeural');
                fd.append('style', $('merge-style')?.value || '');
                fd.append('rate', $('merge-rate')?.value || '+0%');
                fd.append('pitch', $('merge-pitch')?.value || '+0Hz');
            } else if (activeAudioSrc === 'upload') {
                const audioFile = $('merge-audio-file')?.files?.[0];
                if (audioFile) fd.append('audio_file', audioFile);
            }

            // Background music
            const bgMusic = $('merge-bg-music')?.files?.[0];
            if (bgMusic) fd.append('bg_music_file', bgMusic);

            // Trim audio
            const trim = form.querySelector('input[name="trim_audio"]');
            fd.append('trim_audio', trim?.checked ? 'true' : 'false');

            const res = await fetch('/api/merge', { method: 'POST', body: fd });
            const data = await res.json();

            $('merge-fill').style.width = '100%';
            $('merge-pct').textContent  = '100%';
            $('merge-step').textContent = '✅ Done!';

            if (data.success) {
                showToast(`✅ ${data.message}`, 'success', 5000);
                await loadGallery();
            } else {
                showToast(`❌ ${data.error}`, 'error', 7000);
            }
        } catch (err) {
            showToast('❌ Network error — check server logs', 'error');
        } finally {
            btn.disabled = false; btn.classList.remove('loading');
            setTimeout(() => hideProgress('merge-progress'), 2000);
        }
    });
}

// ─────────────────────────────────────────────────────────────────
// AI VIDEO GENERATOR FORM SUBMISSION
// ─────────────────────────────────────────────────────────────────
function initAIVideoForm() {
    const form = $('ai-video-form');
    if (!form) return;

    form.addEventListener('submit', async e => {
        e.preventDefault();

        const script = $('ai-script')?.value.trim();
        if (!script) {
            showToast('⚠️ Please enter a script for the video', 'error');
            return;
        }

        const btn = $('ai-submit-btn');
        btn.disabled = true; btn.classList.add('loading');
        showProgress('ai-progress');

        const steps = [
            { pct: 15, label: '📝 Processing script…',          dur: 1500 },
            { pct: 35, label: '🎙️ Generating narration…',        dur: 3000 },
            { pct: 55, label: '🖼️ Fetching stock media…',        dur: 4000 },
            { pct: 75, label: '🎬 Compositing slides…',          dur: 5000 },
            { pct: 90, label: '🎵 Mixing final audio…',          dur: 2000 },
            { pct: 99, label: '💾 Encoding video…',              dur: 2000 },
        ];
        startProgress('ai-fill', 'ai-pct', 'ai-step', steps);

        try {
            const fd = new FormData();
            fd.append('script_text', script);
            fd.append('theme', form.querySelector('input[name="theme"]:checked')?.value || 'auto');
            fd.append('aspect_ratio', form.querySelector('input[name="ai_aspect_ratio"]:checked')?.value || 'vertical');
            fd.append('voice', $('ai-voice')?.value || 'en-US-EmmaMultilingualNeural');
            fd.append('rate', $('ai-rate')?.value || '+0%');
            fd.append('pitch', $('ai-pitch')?.value || '+0Hz');

            // Trim audio
            const trim = form.querySelector('input[name="ai_trim_audio"]');
            fd.append('trim_audio', trim?.checked ? 'true' : 'false');

            // Background music
            const bgMusic = $('ai-bg-music')?.files?.[0];
            if (bgMusic) fd.append('bg_music_file', bgMusic);

            const res = await fetch('/api/generate-video', { method: 'POST', body: fd });
            const data = await res.json();

            $('ai-fill').style.width = '100%';
            $('ai-pct').textContent  = '100%';
            $('ai-step').textContent = '✅ Done!';

            if (data.success) {
                showToast(`✅ ${data.message}`, 'success', 5000);
                state.statsAI += 1;
                animateCount($('stat-ai'), state.statsAI);
                await loadGallery();
            } else {
                showToast(`❌ ${data.error}`, 'error', 7000);
            }
        } catch (err) {
            showToast('❌ Network error — check server logs', 'error');
        } finally {
            btn.disabled = false; btn.classList.remove('loading');
            setTimeout(() => hideProgress('ai-progress'), 2000);
        }
    });
}

// ─────────────────────────────────────────────────────────────────
// THEME SWITCHER
// ─────────────────────────────────────────────────────────────────
function initThemeSwitcher() {
    const toggleBtn = $('theme-toggle');
    if (!toggleBtn) return;

    const sunIcon = toggleBtn.querySelector('.sun-icon');
    const moonIcon = toggleBtn.querySelector('.moon-icon');

    // Load initial theme from localStorage
    const savedTheme = localStorage.getItem('theme') || 'dark';
    if (savedTheme === 'light') {
        document.body.classList.add('light-theme');
        if (sunIcon) sunIcon.style.display = 'none';
        if (moonIcon) moonIcon.style.display = 'block';
    }

    toggleBtn.addEventListener('click', () => {
        const isLight = document.body.classList.toggle('light-theme');
        localStorage.setItem('theme', isLight ? 'light' : 'dark');

        if (isLight) {
            if (sunIcon) sunIcon.style.display = 'none';
            if (moonIcon) moonIcon.style.display = 'block';
            showToast('☀️ Switched to Light theme', 'success', 2000);
        } else {
            if (sunIcon) sunIcon.style.display = 'block';
            if (moonIcon) moonIcon.style.display = 'none';
            showToast('🌙 Switched to Dark theme', 'success', 2000);
        }
    });
}

// ─────────────────────────────────────────────────────────────────
// GENERIC: Aspect Card + Theme Card Selection Visuals
// ─────────────────────────────────────────────────────────────────
function initRadioCardSelections() {
    // Aspect ratio cards (all forms)
    document.querySelectorAll('.aspect-card input[type=radio]').forEach(radio => {
        radio.addEventListener('change', () => {
            const grid = radio.closest('.aspect-ratio-grid');
            grid?.querySelectorAll('.aspect-card').forEach(c => c.classList.remove('selected'));
            radio.closest('.aspect-card').classList.add('selected');
        });
        if (radio.checked) radio.closest('.aspect-card').classList.add('selected');
    });

    // Theme cards (AI Video)
    document.querySelectorAll('.theme-card input[type=radio]').forEach(radio => {
        radio.addEventListener('change', () => {
            document.querySelectorAll('.theme-card').forEach(c => c.classList.remove('selected'));
            radio.closest('.theme-card').classList.add('selected');
        });
        if (radio.checked) radio.closest('.theme-card').classList.add('selected');
    });
}

// ─────────────────────────────────────────────────────────────────
// AI DUBBER FORM
// ─────────────────────────────────────────────────────────────────
function initDubberForm() {
    const form = $('ai-dubber-form');
    if (!form) return;

    // Handle input method tabs
    const radios = form.querySelectorAll('input[name="dub_input_method"]');
    const urlGroup = $('dub-url-group');
    const uploadGroup = $('dub-upload-group');
    const libraryGroup = $('dub-library-group');

    radios.forEach(radio => {
        radio.addEventListener('change', () => {
            // Update UI visual tabs
            const grid = radio.closest('.audio-source-tabs');
            grid?.querySelectorAll('.source-tab').forEach(c => c.classList.remove('active'));
            radio.closest('.source-tab').classList.add('active');

            // Toggle visibility
            urlGroup.style.display = 'none';
            uploadGroup.style.display = 'none';
            libraryGroup.style.display = 'none';
            
            $('dub-source-url').required = false;
            $('dub-source-upload').required = false;
            $('dub-source-file').required = false;

            if (radio.value === 'url') {
                urlGroup.style.display = 'block';
                $('dub-source-url').required = true;
            } else if (radio.value === 'upload') {
                uploadGroup.style.display = 'block';
                $('dub-source-upload').required = true;
            } else {
                libraryGroup.style.display = 'block';
                $('dub-source-file').required = true;
            }
        });
    });

    // Show filename when selected
    const uploadInput = $('dub-source-upload');
    if (uploadInput) {
        uploadInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                showToast(`📁 Selected: ${file.name}`, 'success');
            }
        });
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const method = form.querySelector('input[name="dub_input_method"]:checked').value;
        if (method === 'url' && !$('dub-source-url').value.trim()) {
            showToast('❌ Please enter a video URL', 'error');
            return;
        }
        if (method === 'upload' && !$('dub-source-upload').files.length) {
            showToast('❌ Please select a video file to upload', 'error');
            return;
        }
        if (method === 'library' && !$('dub-source-file').value.trim()) {
            showToast('❌ Please enter a source video filename from the library', 'error');
            return;
        }

        const btn = $('dub-submit-btn');
        btn.disabled = true;
        btn.classList.add('loading');
        
        $('dub-progress').style.display = 'block';

        try {
            const fd = new FormData(form);
            const res = await fetch('/api/dub-video', { method: 'POST', body: fd });
            const data = await res.json();

            if (data.success) {
                showToast(`✅ ${data.message}`, 'success', 5000);
                await loadGallery();
            } else {
                showToast(`❌ ${data.error}`, 'error', 7000);
            }
        } catch (err) {
            showToast('❌ Network error — check server logs', 'error');
        } finally {
            btn.disabled = false; 
            btn.classList.remove('loading');
            $('dub-progress').style.display = 'none';
        }
    });
}

// ─────────────────────────────────────────────────────────────────
// 2D CARTOON MAKER FORM
// ─────────────────────────────────────────────────────────────────
function initCartoonMakerForm() {
    const form = $('cartoon-form');
    if (!form) return;

    const generateBtn = $('generate-script-btn');
    if (generateBtn) {
        // Prevent enter key submitting the form directly
        $('cartoon-prompt').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                $('generate-script-btn').click();
            }
        });
        
        generateBtn.addEventListener('click', async () => {
            const prompt = $('cartoon-prompt').value.trim();
            if (!prompt) {
                showToast('❌ Please enter a story topic first', 'error');
                return;
            }

            generateBtn.disabled = true;
            generateBtn.querySelector('.btn-spinner').style.display = 'inline-block';
            // Hide the right panel elements to show automation
            $('cartoon-submit-btn').style.display = 'none';
            $('cartoon-submit-btn').disabled = true;
            
            try {
                const res = await fetch('/api/generate-script', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: new URLSearchParams({ topic: prompt })
                });
                
                const data = await res.json();
                if (data.success) {
                    const d = data.studio_data;
                    
                    // Render Story Outline
                    $('studio-story-info').innerHTML = `
                        <p style="margin-bottom:5px;"><strong>Title:</strong> ${d.story.title}</p>
                        <p style="margin-bottom:5px; font-size:0.9rem;"><strong>Genre:</strong> ${d.story.genre} | <strong>Target:</strong> ${d.story.target_age}</p>
                        <p style="margin-bottom:5px; font-size:0.9rem;"><strong>Summary:</strong> ${d.story.summary}</p>
                        <p style="margin-bottom:0; font-size:0.9rem;"><strong>Moral:</strong> ${d.story.moral}</p>
                    `;
                    
                    // Render Characters
                    let charHtml = "";
                    (d.characters || []).forEach(c => {
                        charHtml += `
                        <div style="background:rgba(255,255,255,0.05); padding:10px; margin-bottom:10px; border-radius:5px;">
                            <h5 style="color:#00ffcc; margin-top:0; margin-bottom:5px;">${c.name} (Age: ${c.age})</h5>
                            <p style="font-size:0.85rem; margin-bottom:5px;"><strong>Appearance:</strong> ${c.appearance}</p>
                            <p style="font-size:0.85rem; margin-bottom:0;"><strong>Voice/Personality:</strong> ${c.voice_style}</p>
                        </div>`;
                    });
                    $('studio-characters').innerHTML = charHtml;
                    
                    // Render Scenes and Build Script for Compiler
                    let sceneHtml = "";
                    let hiddenScript = "";
                    let scenesArray = d.scenes || [];
                    
                    if (scenesArray.length === 0) {
                        scenesArray = [{
                            scene_number: 1, location: "Unknown", time_of_day: "Day", mood: "Neutral",
                            image_prompt: "Beautiful 2D flat cartoon scene matching the story",
                            script: [{ type: "narration", text: d.story.summary || "Once upon a time..." }]
                        }];
                    }
                    
                    scenesArray.forEach(s => {
                        sceneHtml += `
                        <div style="background:rgba(255,255,255,0.05); padding:10px; margin-bottom:10px; border-radius:5px; border-left: 3px solid #b366ff;">
                            <h5 style="color:#b366ff; margin-top:0; margin-bottom:5px;">Scene ${s.scene_number || 1}: ${s.location || 'Location'}</h5>
                            <p style="font-size:0.85rem; color:#aaa; margin-bottom:5px;">${s.time_of_day || 'Day'} | ${s.mood || 'Neutral'}</p>
                            <p style="font-size:0.85rem; margin-bottom:5px;"><strong>Visuals:</strong> ${s.image_prompt || ''}</p>
                            <ul style="font-size:0.85rem; margin-bottom:0; padding-left: 15px;">`;
                            
                        hiddenScript += `\n[Scene: ${s.image_prompt || 'Beautiful 2D cartoon scene'}]\n`;
                        
                        (s.script || []).forEach(line => {
                            if (line.type === 'narration') {
                                sceneHtml += `<li style="margin-bottom:3px;"><em>Narration: ${line.text || ''}</em></li>`;
                                hiddenScript += `${line.text || ''}\n`;
                            } else {
                                sceneHtml += `<li style="margin-bottom:3px;"><strong>${line.speaker || 'Character'}:</strong> ${line.text || ''}</li>`;
                                hiddenScript += `${line.speaker || 'Character'}: ${line.text || ''}\n`;
                            }
                        });
                        sceneHtml += `</ul></div>`;
                    });
                    
                    $('studio-scenes').innerHTML = sceneHtml;
                    $('cartoon-script-text').value = hiddenScript.trim();
                    $('studio-dashboard').style.display = 'block';
                    
                    showToast('✅ Production Document Generated! Please select your options and click Compile.', 'success');
                    
                    $('cartoon-submit-btn').style.display = 'flex';
                    $('cartoon-submit-btn').disabled = false;
                    
                } else {
                    showToast(`❌ Error: ${data.error}`, 'error');
                    $('cartoon-submit-btn').style.display = 'flex';
                    $('cartoon-submit-btn').disabled = false;
                }
            } catch (err) {
                console.error("Frontend Exception:", err);
                showToast(`❌ Network error: ${err.message}`, 'error');
                $('cartoon-submit-btn').style.display = 'flex';
                $('cartoon-submit-btn').disabled = false;
            } finally {
                generateBtn.disabled = false;
                generateBtn.querySelector('.btn-spinner').style.display = 'none';
            }
        });
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const scriptText = $('cartoon-script-text').value.trim();
        if (!scriptText) {
            // Prevent infinite loop if script generation returns empty JSON
            showToast('❌ Failed to extract script. Please try a different topic.', 'error');
            return;
        }

        const btn = $('cartoon-submit-btn');
        btn.disabled = true;
        btn.classList.add('loading');
        
        showProgress('cartoon-progress');

        let steps = [
            { pct: 15, label: '📝 Parsing script & scenes…', dur: 2000 },
            { pct: 40, label: '🎨 AI drawing scenes…',       dur: 8000 },
            { pct: 60, label: '🎙️ Generating voiceovers…',    dur: 6000 },
            { pct: 85, label: '🎬 Rendering HD Video…',      dur: 6000 },
            { pct: 99, label: '✨ Finalizing animation…',    dur: 3000 },
        ];

        const isProMotion = $('cartoon-pro-motion') && $('cartoon-pro-motion').checked;
        if (isProMotion) {
            steps = [
                { pct: 10, label: '📝 Parsing script & characters…', dur: 2000 },
                { pct: 40, label: '🎨 FLUX AI generating HD images (Queue)…', dur: 45000 },
                { pct: 80, label: '🎥 SVD generating True Motion Video (Long Queue)…', dur: 180000 },
                { pct: 90, label: '🎙️ Syncing Audio & Dialogues…', dur: 10000 },
                { pct: 99, label: '🎬 Finalizing HD Motion Video…', dur: 10000 },
            ];
            showToast('⏳ Pro Motion Mode enabled. This may take 15-20 minutes depending on HuggingFace queues.', 'info', 8000);
        }
        
        startProgress('cartoon-fill', 'cartoon-pct', 'cartoon-step', steps);

        try {
            const fd = new FormData(form);
            const res = await fetch('/api/generate-cartoon-video', { method: 'POST', body: fd });
            const data = await res.json();

            $('cartoon-fill').style.width = '100%';
            $('cartoon-pct').textContent  = '100%';
            $('cartoon-step').textContent = '✅ Done!';

            if (data.success) {
                showToast(`✅ Cartoon generated!`, 'success', 5000);
                
                if (data.images && data.images.length > 0) {
                    let sbHtml = '<h3 style="margin-bottom:10px;">Storyboard Preview</h3><div style="display:flex;gap:10px;overflow-x:auto;padding-bottom:10px;">';
                    data.images.forEach(img => {
                        sbHtml += `<img src="/api/outputs/${img}" style="height:120px; border-radius:8px; border:2px solid #b366ff; object-fit:cover;">`;
                    });
                    sbHtml += '</div>';
                    $('cartoon-storyboard').innerHTML = sbHtml;
                }
                
                await loadGallery();
            } else {
                showToast(`❌ ${data.error}`, 'error', 7000);
            }
        } catch (err) {
            showToast('❌ Network error — check server logs', 'error');
        } finally {
            btn.disabled = false; 
            btn.classList.remove('loading');
            $('cartoon-progress').style.display = 'none';
        }
    });
}

function setDbStepStatus(id, status, type) {
    const el = $(id);
    if (!el) return;
    el.className = 'dashboard-step'; // reset
    if (type) el.classList.add(`db-${type}`);
    
    const statusEl = el.querySelector('.db-status');
    const iconEl = el.querySelector('.db-icon');
    if (statusEl) statusEl.textContent = status;
    
    if (type === 'active') iconEl.textContent = '🔄';
    else if (type === 'done') iconEl.textContent = '✅';
    else iconEl.textContent = '⏳';
}

function initAutoDraftMode() {
    const langSelect = $('autodraft-lang');
    if (langSelect) {
        langSelect.addEventListener('change', () => {
            populateVoiceDropdown('autodraft-voice', mapLang(langSelect.value), null);
        });

    }

    const btn = $('autodraft-submit-btn');
    if (!btn) return;

    btn.addEventListener('click', async () => {
        const topic = $('autodraft-topic').value.trim();
        const style = $('autodraft-style').value;
        const duration = $('autodraft-duration').value;
        const lang = $('autodraft-lang').value;
        
        if (!topic) {
            showToast('Please enter a story topic first.', 'error');
            return;
        }

        btn.disabled = true;
        btn.classList.add('loading');
        
        // Show Dashboard
        const db = $('autodraft-dashboard');
        db.style.display = 'block';
        
        // Reset Dashboard
        ['db-story', 'db-char', 'db-scene', 'db-image', 'db-anim', 'db-voice', 'db-render'].forEach(id => setDbStepStatus(id, 'Waiting', ''));
        
        setDbStepStatus('db-story', 'Writing...', 'active');
        setDbStepStatus('db-char', 'Designing...', 'active');
        
        try {
            const fd = new FormData();
            fd.append('topic', topic);
            fd.append('style', style);
            fd.append('duration', duration);
            fd.append('language', lang);
            
            const res = await fetch('/api/autodraft-script', { method: 'POST', body: fd });
            const data = await res.json();
            
            if (data.success && data.script) {
                setDbStepStatus('db-story', 'Complete', 'done');
                setDbStepStatus('db-char', 'Complete', 'done');
                setDbStepStatus('db-scene', 'Complete', 'done');
                
                // Populate the Master Script Editor with the generated script
                $('cartoon-script-text').value = data.script;
                
                
                // Ensure Pro Motion Mode is enabled
                const proCheck = cartoon-pro-motion;
                if (proCheck) proCheck.checked = true;
                
                // Copy selected voice to the legacy compiler
                const voiceSelect = cartoon-voice;
                const autoVoice = autodraft-voice;
                if (voiceSelect && autoVoice) {
                    const opt = document.createElement('option');
                    opt.value = autoVoice.value;
                    opt.textContent = autoVoice.options[autoVoice.selectedIndex]?.text || autoVoice.value;
                    voiceSelect.appendChild(opt);
                    voiceSelect.value = autoVoice.value;
                }

                // Copy format
                const formatVal = $('autodraft-format').value;
                const formatRadios = document.getElementsByName('cartoon_aspect_ratio');
                for (let r of formatRadios) {
                    if (r.value === formatVal) { r.checked = true; break; }
                }
                
                setDbStepStatus('db-image', 'Generating...', 'active');
                setDbStepStatus('db-anim', 'Queued...', 'active');
                
                // We hook into the global fetch to update our dashboard when the cartoon generation finishes
                // For a seamless UI experience, we simulate the dashboard updates while the real progress bar runs
                let simInterval = setInterval(() => {
                    const stepTxt = $('cartoon-step')?.textContent || '';
                    if (stepTxt.includes('SVD') || stepTxt.includes('Motion')) {
                        setDbStepStatus('db-image', 'Complete', 'done');
                        setDbStepStatus('db-anim', 'Rendering...', 'active');
                    } else if (stepTxt.includes('Audio') || stepTxt.includes('Syncing')) {
                        setDbStepStatus('db-anim', 'Complete', 'done');
                        setDbStepStatus('db-voice', 'Mixing...', 'active');
                    } else if (stepTxt.includes('Finalizing')) {
                        setDbStepStatus('db-voice', 'Complete', 'done');
                        setDbStepStatus('db-render', 'Encoding...', 'active');
                    } else if (stepTxt.includes('Done')) {
                        setDbStepStatus('db-render', 'Complete', 'done');
                        clearInterval(simInterval);
                    }
                }, 2000);
                
                // Automatically click the Compile button
                setTimeout(() => {
                    $('cartoon-submit-btn').click();
                }, 1000);
                
            } else {
                setDbStepStatus('db-story', 'Failed', '');
                setDbStepStatus('db-char', 'Failed', '');
                showToast(`❌ AutoDraft Failed: ${data.error}`, 'error');
            }
        } catch (err) {
            setDbStepStatus('db-story', 'Error', '');
            showToast('❌ AutoDraft network error', 'error');
        } finally {
            btn.disabled = false;
            btn.classList.remove('loading');
        }
    });
}


function initAutoUploaderForm() {
    const form = $('auto-upload-form');
    if (!form) return;

    // Load saved credentials from localStorage
    const instaUserField = form.querySelector('[name="insta_username"]');
    const instaPassField = form.querySelector('[name="insta_password"]');
    const instaSessionField = form.querySelector('[name="insta_session_id"]');
    const tiktokSessionField = form.querySelector('[name="tiktok_session_id"]');
    
    if (instaUserField) instaUserField.value = localStorage.getItem('au_insta_user') || '';
    if (instaPassField) instaPassField.value = localStorage.getItem('au_insta_pass') || '';
    if (instaSessionField) instaSessionField.value = localStorage.getItem('au_insta_session') || '';
    if (tiktokSessionField) tiktokSessionField.value = localStorage.getItem('au_tiktok_session') || '';

    // Setup Dropzone for auto-uploader video
    initDropZone('au-video-zone', 'au-video-file', 'au-video-list');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const btn = $('au-submit-btn');
        const statusCont = $('au-status-container');
        const statusText = $('au-status-text');
        
        if (!$('au-video-file').files.length) {
            showToast('⚠️ Please select a video file.', 'error');
            return;
        }

        btn.disabled = true;
        btn.classList.add('loading');
        statusCont.style.display = 'block';
        statusText.innerHTML = '🚀 Processing... Generating SEO & Uploading in background.';

        // Save credentials for next time
        if (instaUserField) localStorage.setItem('au_insta_user', instaUserField.value);
        if (instaPassField) localStorage.setItem('au_insta_pass', instaPassField.value);
        if (instaSessionField) localStorage.setItem('au_insta_session', instaSessionField.value);
        if (tiktokSessionField) localStorage.setItem('au_tiktok_session', tiktokSessionField.value);

        try {
            const fd = new FormData(form);
            const res = await fetch('/api/auto-upload', { method: 'POST', body: fd });
            const data = await res.json();

            if (data.success) {
                showToast('✅ Uploads completed successfully!', 'success', 5000);
                alert('✅ Uploads completed successfully!\n\nTitle: ' + data.seo_generated.title);
                statusText.innerHTML = `
                    <b>Success!</b><br>
                    <b>Generated SEO:</b><br>
                    Title: ${data.seo_generated.title}<br>
                    Tags: ${data.seo_generated.hashtags}<br>
                    <br>
                    <b>Upload Results:</b><br>
                    YouTube: ${data.upload_results.youtube?.success ? '✅ OK' : '❌ ' + (data.upload_results.youtube?.error || 'Failed')}<br>
                    Instagram: ${data.upload_results.instagram?.success ? '✅ OK' : '❌ ' + (data.upload_results.instagram?.error || 'Failed')}<br>
                    TikTok: ${data.upload_results.tiktok?.success ? '✅ OK' : '❌ ' + (data.upload_results.tiktok?.error || 'Failed')}
                `;
            } else {
                showToast(`❌ ${data.error}`, 'error', 7000);
                alert('❌ Upload Failed:\n' + data.error);
                statusText.innerHTML = `❌ Error: ${data.error}`;
            }
        } catch (err) {
            showToast('❌ Network error — check server logs', 'error');
            statusText.innerHTML = '❌ Network Error.';
        } finally {
            btn.disabled = false;
            btn.classList.remove('loading');
        }
    });
}

// ─────────────────────────────────────────────────────────────────
// INITIALIZATION
// ─────────────────────────────────────────────────────────────────
function initAIStudioForm() {
    const typeBtns = document.querySelectorAll('#ai-studio-type-image, #ai-studio-type-video');
    const typeInput = $('ai-studio-media-type');
    const modelSelect = $('ai-studio-model');
    const durationGroup = $('ai-studio-duration-group');
    const styleGroup = $('ai-studio-style').closest('.form-group');
    
    // Toggling Image/Video
    typeBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            typeBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const isVideo = btn.dataset.type === 'video';
            typeInput.value = isVideo ? 'video' : 'image';
            
            if (isVideo) {
                modelSelect.innerHTML = `
                    <option value="google_vids">Google Vids (Extension)</option>
                    <option value="cogvideox">CogVideoX-5B (Free Open-Source)</option>
                    <option value="zoom">Cinematic Zoom (Fast & Free)</option>
                `;
                durationGroup.style.display = 'block';
                styleGroup.style.display = 'none';
            } else {
                modelSelect.innerHTML = `
                    <option value="flux-dev">Flux Dev (Image)</option>
                    <option value="midjourney">Midjourney v7 (Image)</option>
                    <option value="gpt4o">GPT-4o (Image)</option>
                    <option value="seedream">Seedream (Image)</option>
                `;
                durationGroup.style.display = 'none';
                styleGroup.style.display = 'block';
            }
        });
    });
    
    initDropZone('ai-studio-ref-zone', 'ai-studio-ref-file', 'ai-studio-ref-list');
    
    const form = $('ai-studio-form');
    if (!form) return;
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = $('ai-studio-submit-btn');
        const progress = $('ai-studio-progress');
        const step = $('ai-studio-step');
        const fill = $('ai-studio-fill');
        
        btn.disabled = true;
        btn.classList.add('loading');
        progress.style.display = 'block';
        step.textContent = 'Uploading Reference & Generating Media...';
        fill.style.width = '50%';
        
        try {
            const fd = new FormData(form);
            const res = await fetch('/api/muapi-generate', { method: 'POST', body: fd });
            const data = await res.json();
            
            if (data.success) {
                fill.style.width = '100%';
                step.textContent = '✅ Generated 1 file!';
                showToast('✅ Generation Complete!', 'success', 5000);
                
                // Show the media right below the form
                const resultsContainer = $('ai-studio-results');
                const mediaContainer = $('ai-studio-media-container');
                if (resultsContainer && mediaContainer && data.filename) {
                    resultsContainer.style.display = 'block';
                    mediaContainer.innerHTML = ''; // Clear previous
                    
                    const filename = data.filename;
                    let el;
                    if (filename.endsWith('.mp4')) {
                        el = `<video src="/api/outputs/${filename}" controls autoplay style="width:100%; max-height:400px; display:block;"></video>`;
                    } else {
                        el = `<img src="/api/outputs/${filename}" style="width:100%; max-height:400px; display:block; object-fit:contain;">`;
                    }
                    mediaContainer.innerHTML = el;
                }
                
                await loadGallery();
            } else {
                showToast('❌ ' + data.error, 'error');
                step.textContent = '❌ Failed';
            }
        } catch(err) {
            showToast('❌ Network error', 'error');
            step.textContent = '❌ Error';
        } finally {
            btn.disabled = false;
            btn.classList.remove('loading');
            setTimeout(() => { progress.style.display = 'none'; }, 5000);
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initThemeSwitcher();
    initMainTabs();
    initAudioToggle();
    initClipForm();
    initAudioSourceTabs();
    initMergeForm();
    initAIVideoForm();
    initDubberForm();
    initCartoonMakerForm();
    initAutoDraftMode();
    initRadioCardSelections();
    initAutoUploaderForm();
    initAIStudioForm();

    // Drop zone for video merger
    initDropZone('merge-video-zone', 'merge-videos-input', 'merge-video-list');

    // Voice data & preview
    loadVoiceData().then(() => {
        initVoicePreview('merge-preview-btn', 'merge-language', 'merge-voice', 'merge-style', 'merge-rate', 'merge-pitch');
        initVoicePreview('ai-preview-btn', 'ai-language', 'ai-voice', null, 'ai-rate', 'ai-pitch');
        initVoicePreview('dub-preview-btn', 'dub-language', 'dub-voice', null, null, null);
        initVoicePreview('cartoon-preview-btn', 'cartoon-language', 'cartoon-voice', null, 'cartoon-rate', 'cartoon-pitch');
        initAgePresets('merge-age-presets', 'merge-rate', 'merge-pitch');
    });

    // Modal
    $('modal-close')?.addEventListener('click', closeVideoModal);
    $('modal-close-btn')?.addEventListener('click', closeVideoModal);
    document.addEventListener('keydown', e => { if (e.key === 'Escape') closeVideoModal(); });

    // Gallery
    $('refresh-gallery')?.addEventListener('click', loadGallery);
    $('clear-library-btn')?.addEventListener('click', clearLibrary);
    $('library-search')?.addEventListener('input', loadGallery);

    loadGallery();

    // Auto-refresh gallery list every 30 seconds
    setInterval(loadGallery, 30000);
});
