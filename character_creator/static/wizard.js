// ================================
// Utility Functions
// ================================

/**
 * Debounce function to limit API calls
 */
function debounce(fn, delay) {
    let timeoutId;
    return function(...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => fn.apply(this, args), delay);
    };
}

/**
 * API helper with error handling
 */
async function api(method, url, body = null) {
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json'
        }
    };
    
    if (body && method !== 'GET') {
        options.body = JSON.stringify(body);
    }
    
    try {
        const response = await fetch(url, options);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || `HTTP ${response.status}`);
        }
        
        return data;
    } catch (error) {
        console.error(`API Error [${method} ${url}]:`, error);
        throw error;
    }
}

/**
 * Show toast notification
 */
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    const icon = {
        success: '✅',
        error: '❌',
        info: 'ℹ️',
        warning: '⚠️'
    }[type] || 'ℹ️';
    
    toast.innerHTML = `<span class="toast-icon">${icon}</span><span class="toast-message">${message}</span>`;
    container.appendChild(toast);
    
    setTimeout(() => toast.classList.add('show'), 10);
    
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ================================
// WizardState Class
// ================================

class WizardState {
    constructor() {
        this.currentStep = 0;
        this.data = {};
        this.restore();
    }
    
    save() {
        const state = {
            currentStep: this.currentStep,
            data: this.data,
            savedAt: new Date().toISOString()
        };
        localStorage.setItem('wizard_state', JSON.stringify(state));
    }
    
    restore() {
        try {
            const saved = localStorage.getItem('wizard_state');
            if (saved) {
                const state = JSON.parse(saved);
                this.currentStep = state.currentStep || 0;
                this.data = state.data || {};
                return true;
            }
        } catch (error) {
            console.error('Failed to restore state:', error);
        }
        return false;
    }
    
    clear() {
        this.currentStep = 0;
        this.data = {};
        localStorage.removeItem('wizard_state');
    }
    
    set(key, value) {
        this.data[key] = value;
        this.save();
    }
    
    get(key, defaultValue = null) {
        return this.data.hasOwnProperty(key) ? this.data[key] : defaultValue;
    }
}

// ================================
// WizardUI Class
// ================================

class WizardUI {
    constructor() {
        this.state = new WizardState();
        this.totalSteps = 7;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.modelConfigDirty = false;
        this.availableModels = [];
        this.edgeVoices = [];
        this.spriteTaskId = null;
        
        // Debounced handlers
        this.debouncedNameLookup = debounce(this.lookupKnownCharacter.bind(this), 500);
    }
    
    init() {
        console.log('Initializing Character Creator Wizard');
        this.bindEvents();
        this.checkForDraft();
        this.initStep0();
    }
    
    bindEvents() {
        // Progress bar clicks
        document.querySelectorAll('.progress-step').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const targetStep = parseInt(btn.dataset.step);
                if (targetStep < this.state.currentStep) {
                    this.goToStep(targetStep);
                }
            });
        });
        
        // Step 0: Identity
        document.querySelectorAll('input[name="char_type"]').forEach(radio => {
            radio.addEventListener('change', () => {
                this.state.set('char_type', radio.value);
            });
        });
        
        const charNameInput = document.getElementById('char-name');
        charNameInput.addEventListener('input', () => {
            const name = charNameInput.value.trim();
            this.state.set('char_name', name);
            if (name && document.querySelector('input[name="char_type"]:checked').value === 'known') {
                this.debouncedNameLookup(name);
            } else {
                this.clearAutoFill();
            }
        });
        
        document.getElementById('display-name').addEventListener('input', (e) => this.state.set('display_name', e.target.value));
        document.getElementById('tagline').addEventListener('input', (e) => this.state.set('tagline', e.target.value));
        document.getElementById('description').addEventListener('input', (e) => this.state.set('description', e.target.value));
        document.getElementById('color-primary').addEventListener('input', (e) => this.state.set('color_primary', e.target.value));
        document.getElementById('color-secondary').addEventListener('input', (e) => this.state.set('color_secondary', e.target.value));
        document.getElementById('color-accent').addEventListener('input', (e) => this.state.set('color_accent', e.target.value));
        document.getElementById('color-text').addEventListener('input', (e) => this.state.set('color_text', e.target.value));
        
        // Step 1: Personality
        document.getElementById('skip-personality').addEventListener('change', (e) => {
            const fields = document.getElementById('personality-fields');
            fields.style.display = e.target.checked ? 'none' : 'block';
            this.state.set('skip_personality', e.target.checked);
        });
        
        document.getElementById('system-prompt').addEventListener('input', (e) => this.state.set('system_prompt', e.target.value));
        
        document.getElementById('accent-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.addTag('accent');
            }
        });
        
        document.getElementById('catchphrase-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.addTag('catchphrase');
            }
        });
        
        // Step 2: Voice
        const audioUploadZone = document.getElementById('audio-upload-zone');
        const audioFileInput = document.getElementById('audio-file-input');
        
        audioUploadZone.addEventListener('click', () => audioFileInput.click());
        audioUploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            audioUploadZone.classList.add('dragover');
        });
        audioUploadZone.addEventListener('dragleave', () => {
            audioUploadZone.classList.remove('dragover');
        });
        audioUploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            audioUploadZone.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                this.handleAudioUpload(e.dataTransfer.files[0]);
            }
        });
        
        audioFileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleAudioUpload(e.target.files[0]);
            }
        });
        
        document.getElementById('voice-gender-filter').addEventListener('change', () => {
            this.filterEdgeVoices();
        });
        
        document.getElementById('edge-voice-select').addEventListener('change', (e) => {
            this.state.set('edge_voice', e.target.value);
        });
        
        document.getElementById('voice-rate').addEventListener('input', (e) => {
            const value = parseInt(e.target.value);
            document.getElementById('voice-rate-display').textContent = `${value >= 0 ? '+' : ''}${value}%`;
            this.state.set('voice_rate', value);
        });
        
        document.getElementById('voice-pitch').addEventListener('input', (e) => {
            const value = parseInt(e.target.value);
            document.getElementById('voice-pitch-display').textContent = `${value >= 0 ? '+' : ''}${value}Hz`;
            this.state.set('voice_pitch', value);
        });
        
        // Step 3: Appearance
        document.querySelectorAll('input[name="sprite_source"]').forEach(radio => {
            radio.addEventListener('change', () => {
                this.toggleSpriteMode(radio.value);
                this.state.set('sprite_source', radio.value);
            });
        });
        
        document.querySelectorAll('.style-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.style-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.state.set('art_style', btn.dataset.style);
            });
        });
        
        document.getElementById('visual-description').addEventListener('input', (e) => {
            this.state.set('visual_description', e.target.value);
        });
        
        // Step 4: Hardware & Models
        document.getElementById('advanced-models-toggle').addEventListener('change', (e) => {
            document.getElementById('dual-model-picker').style.display = e.target.checked ? 'block' : 'none';
            this.state.set('advanced_models', e.target.checked);
        });
    }
    
    // ================================
    // Navigation & State Management
    // ================================
    
    goToStep(n) {
        if (n < 0 || n >= this.totalSteps) return;
        
        // Hide all steps
        document.querySelectorAll('.wizard-step').forEach(step => {
            step.style.display = 'none';
            step.classList.remove('active');
        });
        
        // Show target step
        const targetStep = document.getElementById(`step-${n}`);
        targetStep.style.display = 'block';
        targetStep.classList.add('active');
        
        // Update progress bar
        document.querySelectorAll('.progress-step').forEach((btn, index) => {
            if (index <= n) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
        
        // Update nav buttons
        const btnBack = document.getElementById('btn-back');
        const btnNext = document.getElementById('btn-next');
        const wizardNav = document.getElementById('wizard-nav');
        
        btnBack.style.display = n > 0 ? 'block' : 'none';
        
        if (n === this.totalSteps - 1 || n === 6) {
            wizardNav.style.display = 'none';
        } else {
            wizardNav.style.display = 'flex';
        }
        
        // Update state
        this.state.currentStep = n;
        this.state.save();
        
        // Focus heading
        const heading = document.getElementById(`step-${n}-heading`);
        if (heading) {
            heading.focus();
        }
        
        // Announce step change
        const statusRegion = document.getElementById('status-region');
        statusRegion.textContent = `Navigated to step ${n + 1} of ${this.totalSteps}`;
        
        // Load step-specific data
        this.onStepEnter(n);
    }
    
    async nextStep() {
        const isValid = await this.validateStep(this.state.currentStep);
        if (isValid) {
            this.goToStep(this.state.currentStep + 1);
        }
    }
    
    prevStep() {
        this.goToStep(this.state.currentStep - 1);
    }
    
    async validateStep(step) {
        switch(step) {
            case 0: // Identity
                const charName = document.getElementById('char-name').value.trim();
                if (!charName) {
                    showToast('Please enter a character name', 'error');
                    document.getElementById('char-name').focus();
                    return false;
                }
                return true;
                
            case 1: // Personality (always valid, skippable)
                return true;
                
            case 2: // Voice
                const hasEdgeVoice = this.state.get('edge_voice');
                const hasAudio = this.state.get('audio_path');
                if (!hasEdgeVoice && !hasAudio) {
                    showToast('Please select an Edge TTS voice or upload reference audio', 'warning');
                    return false;
                }
                return true;
                
            case 3: // Appearance (always valid, skippable)
                return true;
                
            case 4: // Hardware & Models
                if (this.availableModels.length === 0) {
                    showToast('No AI models available. Please install Ollama.', 'error');
                    return false;
                }
                return true;
                
            case 5: // Review (always valid)
                return true;
                
            default:
                return true;
        }
    }
    
    onStepEnter(step) {
        switch(step) {
            case 2:
                this.initStep2();
                break;
            case 4:
                this.initStep4();
                break;
            case 5:
                this.initStep5();
                break;
            case 6:
                this.initStep6();
                break;
        }
    }
    
    checkForDraft() {
        const saved = localStorage.getItem('wizard_state');
        if (saved) {
            try {
                const state = JSON.parse(saved);
                const banner = document.getElementById('resume-banner');
                const dateSpan = document.getElementById('draft-date');
                
                const savedDate = new Date(state.savedAt);
                dateSpan.textContent = savedDate.toLocaleString();
                banner.style.display = 'block';
            } catch (error) {
                console.error('Error checking draft:', error);
            }
        }
    }
    
    resumeDraft() {
        document.getElementById('resume-banner').style.display = 'none';
        this.restoreFormValues();
        this.goToStep(this.state.currentStep);
        showToast('Draft restored', 'success');
    }
    
    async startFresh() {
        const charName = this.state.get('char_name');
        if (charName) {
            try {
                await api('DELETE', `/api/upload/draft/${encodeURIComponent(charName)}`);
            } catch (error) {
                console.error('Error deleting draft uploads:', error);
            }
        }
        
        this.state.clear();
        document.getElementById('resume-banner').style.display = 'none';
        this.goToStep(0);
        this.clearAllFields();
        showToast('Starting fresh', 'info');
    }
    
    restoreFormValues() {
        // Step 0: Identity
        const charType = this.state.get('char_type', 'known');
        document.querySelector(`input[name="char_type"][value="${charType}"]`).checked = true;
        
        document.getElementById('char-name').value = this.state.get('char_name', '');
        document.getElementById('display-name').value = this.state.get('display_name', '');
        document.getElementById('tagline').value = this.state.get('tagline', '');
        document.getElementById('description').value = this.state.get('description', '');
        document.getElementById('color-primary').value = this.state.get('color_primary', '#7B2FBE');
        document.getElementById('color-secondary').value = this.state.get('color_secondary', '#1E90FF');
        document.getElementById('color-accent').value = this.state.get('color_accent', '#FFD700');
        document.getElementById('color-text').value = this.state.get('color_text', '#FFFFFF');
        
        // Step 1: Personality
        const skipPersonality = this.state.get('skip_personality', false);
        document.getElementById('skip-personality').checked = skipPersonality;
        document.getElementById('personality-fields').style.display = skipPersonality ? 'none' : 'block';
        document.getElementById('system-prompt').value = this.state.get('system_prompt', '');
        
        this.renderTags('accent', this.state.get('accent_markers', []));
        this.renderTags('catchphrase', this.state.get('catchphrases', []));
        
        // Step 2: Voice
        const voiceRate = this.state.get('voice_rate', 0);
        const voicePitch = this.state.get('voice_pitch', 0);
        document.getElementById('voice-rate').value = voiceRate;
        document.getElementById('voice-pitch').value = voicePitch;
        document.getElementById('voice-rate-display').textContent = `${voiceRate >= 0 ? '+' : ''}${voiceRate}%`;
        document.getElementById('voice-pitch-display').textContent = `${voicePitch >= 0 ? '+' : ''}${voicePitch}Hz`;
        
        // Step 3: Appearance
        const spriteSource = this.state.get('sprite_source', 'generate');
        document.querySelector(`input[name="sprite_source"][value="${spriteSource}"]`).checked = true;
        this.toggleSpriteMode(spriteSource);
        
        document.getElementById('visual-description').value = this.state.get('visual_description', '');
        
        const artStyle = this.state.get('art_style', '3d_figurine');
        document.querySelectorAll('.style-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.style === artStyle);
        });
        
        // Step 4: Hardware & Models
        const advancedModels = this.state.get('advanced_models', false);
        document.getElementById('advanced-models-toggle').checked = advancedModels;
        document.getElementById('dual-model-picker').style.display = advancedModels ? 'block' : 'none';
    }
    
    clearAllFields() {
        document.getElementById('char-name').value = '';
        document.getElementById('display-name').value = '';
        document.getElementById('tagline').value = '';
        document.getElementById('description').value = '';
        document.getElementById('system-prompt').value = '';
        document.getElementById('visual-description').value = '';
        this.renderTags('accent', []);
        this.renderTags('catchphrase', []);
    }
    
    // ================================
    // Step 0: Identity
    // ================================
    
    initStep0() {
        // Set initial values from state
        const charType = this.state.get('char_type', 'known');
        document.querySelector(`input[name="char_type"][value="${charType}"]`).checked = true;
    }
    
    async lookupKnownCharacter(name) {
        const nameStatus = document.getElementById('name-status');
        nameStatus.textContent = '🔍 Searching...';
        nameStatus.className = 'help-text searching';
        
        try {
            const data = await api('GET', `/api/known-character/${encodeURIComponent(name)}`);
            
            if (data.found && data.data) {
                this.autoFillCharacter(data.data);
                nameStatus.textContent = `✨ Found "${name}"! Auto-filled details below.`;
                nameStatus.className = 'help-text success';
            } else {
                this.clearAutoFill();
                nameStatus.textContent = `Not in our database — you're creating something new!`;
                nameStatus.className = 'help-text info';
            }
        } catch (error) {
            console.error('Lookup error:', error);
            nameStatus.textContent = 'Search failed. Creating as original character.';
            nameStatus.className = 'help-text error';
        }
    }
    
    autoFillCharacter(data) {
        // Display name
        if (data.display_name) {
            document.getElementById('display-name').value = data.display_name;
            this.state.set('display_name', data.display_name);
            document.getElementById('display-name-badge').style.display = 'inline';
        }
        
        // Tagline
        if (data.tagline) {
            document.getElementById('tagline').value = data.tagline;
            this.state.set('tagline', data.tagline);
            document.getElementById('tagline-badge').style.display = 'inline';
        }
        
        // Description
        if (data.description) {
            document.getElementById('description').value = data.description;
            this.state.set('description', data.description);
            document.getElementById('description-badge').style.display = 'inline';
        }
        
        // Theme colors
        if (data.theme_colors) {
            if (data.theme_colors.primary) {
                document.getElementById('color-primary').value = data.theme_colors.primary;
                this.state.set('color_primary', data.theme_colors.primary);
            }
            if (data.theme_colors.secondary) {
                document.getElementById('color-secondary').value = data.theme_colors.secondary;
                this.state.set('color_secondary', data.theme_colors.secondary);
            }
            if (data.theme_colors.accent) {
                document.getElementById('color-accent').value = data.theme_colors.accent;
                this.state.set('color_accent', data.theme_colors.accent);
            }
            if (data.theme_colors.text) {
                document.getElementById('color-text').value = data.theme_colors.text;
                this.state.set('color_text', data.theme_colors.text);
            }
            document.getElementById('colors-badge').style.display = 'inline';
        }
        
        // Personality data (for Step 1)
        if (data.accent_markers) {
            this.state.set('accent_markers', data.accent_markers);
        }
        if (data.catchphrases) {
            this.state.set('catchphrases', data.catchphrases);
        }
        if (data.system_prompt_hints) {
            this.state.set('system_prompt', data.system_prompt_hints);
        }
        
        // Voice data (for Step 2)
        if (data.edge_voice) {
            this.state.set('edge_voice', data.edge_voice);
        }
        if (data.voice_rate !== undefined) {
            const rate = String(data.voice_rate).replace('%', '').replace('+', '');
            this.state.set('voice_rate', parseInt(rate) || 0);
        }
        if (data.voice_pitch !== undefined) {
            const pitch = String(data.voice_pitch).replace('Hz', '').replace('+', '');
            this.state.set('voice_pitch', parseInt(pitch) || 0);
        }
        if (data.pronunciation) {
            this.state.set('pronunciation', data.pronunciation);
        }
        
        // Appearance data (for Step 3)
        if (data.visual_description) {
            this.state.set('visual_description', data.visual_description);
        }
        if (data.art_style) {
            this.state.set('art_style', data.art_style);
        }
        
        // Store voice search terms for auto-find
        if (data.voice_search_terms) {
            this.state.set('voice_search_terms', data.voice_search_terms);
        }
    }
    
    clearAutoFill() {
        document.getElementById('display-name-badge').style.display = 'none';
        document.getElementById('tagline-badge').style.display = 'none';
        document.getElementById('description-badge').style.display = 'none';
        document.getElementById('colors-badge').style.display = 'none';
    }
    
    // ================================
    // Step 1: Personality
    // ================================
    
    addTag(type) {
        const input = document.getElementById(`${type}-input`);
        const value = input.value.trim();
        
        if (!value) return;
        
        const key = type === 'accent' ? 'accent_markers' : 'catchphrases';
        const current = this.state.get(key, []);
        
        if (!current.includes(value)) {
            current.push(value);
            this.state.set(key, current);
            this.renderTags(type, current);
        }
        
        input.value = '';
    }
    
    removeTag(type, value) {
        const key = type === 'accent' ? 'accent_markers' : 'catchphrases';
        const current = this.state.get(key, []);
        const filtered = current.filter(item => item !== value);
        this.state.set(key, filtered);
        this.renderTags(type, filtered);
    }
    
    renderTags(type, tags) {
        const container = document.getElementById(`${type}-tags`);
        container.innerHTML = tags.map(tag => `
            <span class="tag">
                ${tag}
                <button class="tag-remove" onclick="wizard.removeTag('${type}', '${tag.replace(/'/g, "\\'")}')">×</button>
            </span>
        `).join('');
    }
    
    // ================================
    // Step 2: Voice
    // ================================
    
    async initStep2() {
        await this.loadVoiceEngines();
        await this.loadEdgeVoices();
        this.restorePronunciationRules();
    }
    
    async loadVoiceEngines() {
        const list = document.getElementById('voice-engines-list');
        
        try {
            const data = await api('GET', '/api/voice/engines');
            
            list.innerHTML = data.engines.map(engine => `
                <div class="engine-card ${engine.available ? 'available' : 'unavailable'}">
                    <h4>${engine.name}</h4>
                    <p>${engine.description}</p>
                    <span class="badge ${engine.available ? 'badge-success' : 'badge-gray'}">
                        ${engine.available ? '✓ Available' : '✗ Unavailable'}
                    </span>
                </div>
            `).join('');
        } catch (error) {
            list.innerHTML = '<p class="error">Failed to load voice engines</p>';
            console.error('Error loading engines:', error);
        }
    }
    
    async loadEdgeVoices() {
        const select = document.getElementById('edge-voice-select');
        
        try {
            const data = await api('GET', '/api/voice/edge-voices');
            this.edgeVoices = data.voices || [];
            
            this.filterEdgeVoices();
            
            // Restore saved voice
            const savedVoice = this.state.get('edge_voice');
            if (savedVoice) {
                select.value = savedVoice;
            }
        } catch (error) {
            select.innerHTML = '<option>Failed to load voices</option>';
            console.error('Error loading Edge voices:', error);
        }
    }
    
    filterEdgeVoices() {
        const select = document.getElementById('edge-voice-select');
        const filter = document.getElementById('voice-gender-filter').value;
        
        const filtered = filter 
            ? this.edgeVoices.filter(v => v.gender === filter)
            : this.edgeVoices;
        
        select.innerHTML = '<option value="">-- Select a voice --</option>' + 
            filtered.map(voice => 
                `<option value="${voice.name}">${voice.display_name} (${voice.locale})</option>`
            ).join('');
        
        // Restore saved voice after filter
        const savedVoice = this.state.get('edge_voice');
        if (savedVoice && filtered.find(v => v.name === savedVoice)) {
            select.value = savedVoice;
        }
    }
    
    async handleAudioUpload(file) {
        if (!file.type.startsWith('audio/')) {
            showToast('Please upload an audio file', 'error');
            return;
        }
        
        if (file.size > 50 * 1024 * 1024) {
            showToast('File too large (max 50MB)', 'error');
            return;
        }
        
        const charName = this.state.get('char_name');
        if (!charName) {
            showToast('Please enter a character name first', 'error');
            return;
        }
        
        const formData = new FormData();
        formData.append('file', file);
        formData.append('character_name', charName);
        
        try {
            showToast('Uploading audio...', 'info');
            
            const response = await fetch('/api/upload/audio', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.state.set('audio_path', data.path);
                this.state.set('audio_filename', file.name);
                this.showAudioPreview(file);
                showToast('Audio uploaded successfully', 'success');
            } else {
                throw new Error(data.error || 'Upload failed');
            }
        } catch (error) {
            showToast(`Upload failed: ${error.message}`, 'error');
            console.error('Audio upload error:', error);
        }
    }
    
    showAudioPreview(file) {
        const preview = document.getElementById('audio-preview');
        const player = document.getElementById('audio-player');
        const uploadZone = document.getElementById('audio-upload-zone');
        
        player.src = URL.createObjectURL(file);
        preview.style.display = 'block';
        uploadZone.style.display = 'none';
    }
    
    removeAudio() {
        this.state.set('audio_path', null);
        this.state.set('audio_filename', null);
        document.getElementById('audio-preview').style.display = 'none';
        document.getElementById('audio-upload-zone').style.display = 'block';
        document.getElementById('audio-player').src = '';
    }
    
    async toggleRecording() {
        const btn = document.getElementById('btn-record');
        
        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
            this.mediaRecorder.stop();
            btn.textContent = '🎙️ Record';
            btn.classList.remove('recording');
        } else {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                this.mediaRecorder = new MediaRecorder(stream);
                this.audioChunks = [];
                
                this.mediaRecorder.ondataavailable = (e) => {
                    this.audioChunks.push(e.data);
                };
                
                this.mediaRecorder.onstop = async () => {
                    const blob = new Blob(this.audioChunks, { type: 'audio/webm' });
                    const file = new File([blob], 'recording.webm', { type: 'audio/webm' });
                    await this.handleAudioUpload(file);
                    stream.getTracks().forEach(track => track.stop());
                };
                
                this.mediaRecorder.start();
                btn.textContent = '⏹️ Stop Recording';
                btn.classList.add('recording');
                showToast('Recording started', 'info');
            } catch (error) {
                showToast('Microphone access denied', 'error');
                console.error('Recording error:', error);
            }
        }
    }
    
    async autoFindVoice() {
        const searchTerms = this.state.get('voice_search_terms');
        const charName = this.state.get('char_name');
        
        if (!searchTerms && !charName) {
            showToast('Enter a character name first', 'warning');
            return;
        }
        
        const query = searchTerms || `${charName} voice`;
        
        try {
            showToast('Searching for voice clips...', 'info');
            const data = await api('POST', '/api/voice/search', { query });
            
            if (data.available && data.results && data.results.length > 0) {
                this.showVoiceSearchResults(data.results);
            } else {
                showToast('No voice clips found', 'warning');
            }
        } catch (error) {
            showToast('Voice search failed', 'error');
            console.error('Voice search error:', error);
        }
    }
    
    showVoiceSearchResults(results) {
        const html = `
            <div class="search-results-modal">
                <h3>Found Voice Clips</h3>
                <div class="results-list">
                    ${results.map((result, i) => `
                        <div class="result-item">
                            <div>
                                <strong>${result.title}</strong>
                                <p>${result.duration || 'Unknown duration'}</p>
                            </div>
                            <button class="btn btn-sm btn-primary" onclick="wizard.downloadVoiceClip('${result.url}')">
                                Use This
                            </button>
                        </div>
                    `).join('')}
                </div>
                <button class="btn btn-secondary" onclick="this.parentElement.remove()">Close</button>
            </div>
        `;
        
        const container = document.createElement('div');
        container.innerHTML = html;
        document.body.appendChild(container.firstElementChild);
    }
    
    async downloadVoiceClip(url) {
        const charName = this.state.get('char_name');
        
        try {
            showToast('Downloading voice clip...', 'info');
            const data = await api('POST', '/api/voice/download', { url, character_name: charName });
            
            if (data.success) {
                this.state.set('audio_path', data.path);
                showToast('Voice clip downloaded', 'success');
                document.querySelector('.search-results-modal')?.remove();
            } else {
                throw new Error(data.error || 'Download failed');
            }
        } catch (error) {
            showToast(`Download failed: ${error.message}`, 'error');
            console.error('Voice download error:', error);
        }
    }
    
    async previewVoice() {
        const voice = document.getElementById('edge-voice-select').value;
        const rate = parseInt(document.getElementById('voice-rate').value);
        const pitch = parseInt(document.getElementById('voice-pitch').value);
        
        if (!voice) {
            showToast('Please select a voice first', 'warning');
            return;
        }
        
        const text = "Hello! This is how I'll sound.";
        
        try {
            showToast('Generating preview...', 'info');
            const data = await api('POST', '/api/voice/preview', { voice, text, rate, pitch });
            
            if (data.success && data.audio_base64) {
                const audio = new Audio(`data:audio/mp3;base64,${data.audio_base64}`);
                audio.play();
                showToast('Playing preview', 'success');
            } else {
                throw new Error('Preview generation failed');
            }
        } catch (error) {
            showToast('Preview failed', 'error');
            console.error('Preview error:', error);
        }
    }
    
    addPronunciation() {
        const container = document.getElementById('pronunciation-rules');
        const row = document.createElement('div');
        row.className = 'pronunciation-row';
        row.innerHTML = `
            <input type="text" placeholder="Word" class="pron-word">
            <span class="arrow">→</span>
            <input type="text" placeholder="How to say it" class="pron-say">
            <button class="btn btn-danger btn-sm" onclick="wizard.removePronunciation(this)">✕</button>
        `;
        container.appendChild(row);
    }
    
    removePronunciation(btn) {
        btn.parentElement.remove();
        this.savePronunciationRules();
    }
    
    savePronunciationRules() {
        const rows = document.querySelectorAll('.pronunciation-row');
        const rules = {};
        
        rows.forEach(row => {
            const word = row.querySelector('.pron-word').value.trim();
            const pronunciation = row.querySelector('.pron-say').value.trim();
            if (word && pronunciation) {
                rules[word] = pronunciation;
            }
        });
        
        this.state.set('pronunciation', rules);
    }
    
    restorePronunciationRules() {
        const rules = this.state.get('pronunciation', {});
        const container = document.getElementById('pronunciation-rules');
        
        // Clear existing rows except the first
        container.innerHTML = '';
        
        if (Object.keys(rules).length === 0) {
            this.addPronunciation();
        } else {
            Object.entries(rules).forEach(([word, pronunciation]) => {
                const row = document.createElement('div');
                row.className = 'pronunciation-row';
                row.innerHTML = `
                    <input type="text" placeholder="Word" class="pron-word" value="${word}">
                    <span class="arrow">→</span>
                    <input type="text" placeholder="How to say it" class="pron-say" value="${pronunciation}">
                    <button class="btn btn-danger btn-sm" onclick="wizard.removePronunciation(this)">✕</button>
                `;
                container.appendChild(row);
            });
        }
        
        // Add change listeners
        container.querySelectorAll('input').forEach(input => {
            input.addEventListener('change', () => this.savePronunciationRules());
        });
    }
    
    // ================================
    // Step 3: Appearance
    // ================================
    
    toggleSpriteMode(mode) {
        document.getElementById('generate-section').style.display = mode === 'generate' ? 'block' : 'none';
        document.getElementById('upload-section').style.display = mode === 'upload' ? 'block' : 'none';
        
        if (mode === 'upload') {
            this.initUploadGrid();
        }
    }
    
    initUploadGrid() {
        const emotions = ['neutral', 'happy', 'sad', 'angry', 'surprised', 'thinking'];
        const states = ['idle', 'talking', 'listening'];
        
        const emotionGrid = document.getElementById('emotion-sprite-grid');
        const stateGrid = document.getElementById('state-sprite-grid');
        
        emotionGrid.innerHTML = emotions.map(emotion => this.createUploadSlot('emotion', emotion)).join('');
        stateGrid.innerHTML = states.map(state => this.createUploadSlot('state', state)).join('');
    }
    
    createUploadSlot(category, name) {
        const id = `upload-${category}-${name}`;
        return `
            <div class="upload-slot">
                <label for="${id}">${name}</label>
                <input type="file" id="${id}" accept="image/*" 
                    onchange="wizard.handleSpriteUpload(event, '${category}', '${name}')">
                <div class="sprite-preview" id="preview-${id}"></div>
            </div>
        `;
    }
    
    async handleSpriteUpload(event, category, emotion) {
        const file = event.target.files[0];
        if (!file) return;
        
        const charName = this.state.get('char_name');
        if (!charName) {
            showToast('Please enter a character name first', 'error');
            return;
        }
        
        const formData = new FormData();
        formData.append('file', file);
        formData.append('character_name', charName);
        formData.append('category', category);
        formData.append('emotion', emotion);
        
        try {
            showToast('Uploading sprite...', 'info');
            
            const response = await fetch('/api/upload/sprite', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.success) {
                const preview = document.getElementById(`preview-upload-${category}-${emotion}`);
                preview.innerHTML = `<img src="${URL.createObjectURL(file)}" alt="${emotion}">`;
                showToast('Sprite uploaded', 'success');
            } else {
                throw new Error(data.error || 'Upload failed');
            }
        } catch (error) {
            showToast(`Upload failed: ${error.message}`, 'error');
            console.error('Sprite upload error:', error);
        }
    }
    
    async generateSprites() {
        const charName = this.state.get('char_name');
        const visualDesc = document.getElementById('visual-description').value.trim();
        const artStyle = this.state.get('art_style', '3d_figurine');
        
        if (!charName) {
            showToast('Please enter a character name first', 'error');
            return;
        }
        
        if (!visualDesc) {
            showToast('Please enter a visual description', 'warning');
            document.getElementById('visual-description').focus();
            return;
        }
        
        const btn = document.getElementById('btn-generate-sprites');
        const progress = document.getElementById('generation-progress');
        const progressFill = document.getElementById('sprite-progress-fill');
        const progressText = document.getElementById('sprite-progress-text');
        
        btn.disabled = true;
        progress.style.display = 'block';
        
        try {
            showToast('Starting sprite generation...', 'info');
            
            const data = await api('POST', '/api/sprites/generate', {
                character_name: charName,
                visual_description: visualDesc,
                art_style: artStyle
            });
            
            this.spriteTaskId = data.task_id;
            
            // Poll for status
            const checkStatus = async () => {
                try {
                    const status = await api('GET', `/api/sprites/status/${this.spriteTaskId}`);
                    
                    const percent = Math.round((status.completed / status.total) * 100);
                    progressFill.style.width = `${percent}%`;
                    progressText.textContent = `Generating ${status.current_pose || ''}... (${status.completed}/${status.total})`;
                    
                    if (status.status === 'completed') {
                        progressFill.style.width = '100%';
                        progressText.textContent = 'Generation complete!';
                        showToast('All sprites generated successfully', 'success');
                        btn.disabled = false;
                    } else if (status.status === 'failed') {
                        throw new Error('Generation failed');
                    } else {
                        setTimeout(checkStatus, 2000);
                    }
                } catch (error) {
                    console.error('Status check error:', error);
                    showToast('Failed to check generation status', 'error');
                    btn.disabled = false;
                    progress.style.display = 'none';
                }
            };
            
            setTimeout(checkStatus, 2000);
            
        } catch (error) {
            showToast(`Generation failed: ${error.message}`, 'error');
            console.error('Sprite generation error:', error);
            btn.disabled = false;
            progress.style.display = 'none';
        }
    }
    
    // ================================
    // Step 4: Hardware & Models
    // ================================
    
    async initStep4() {
        await this.loadHardwareInfo();
        await this.loadModels();
    }
    
    async loadHardwareInfo() {
        const grid = document.getElementById('hardware-grid');
        
        try {
            const data = await api('GET', '/api/hardware');
            
            grid.innerHTML = `
                <div class="hardware-item">
                    <strong>CPU</strong>
                    <span>${data.cpu || 'Unknown'}</span>
                </div>
                <div class="hardware-item">
                    <strong>RAM</strong>
                    <span>${data.ram_gb || 'Unknown'} GB</span>
                </div>
                <div class="hardware-item">
                    <strong>GPU</strong>
                    <span>${data.gpu_name || 'None detected'}</span>
                </div>
                <div class="hardware-item">
                    <strong>VRAM</strong>
                    <span>${data.gpu_vram_gb || 0} GB</span>
                </div>
                <div class="hardware-item">
                    <strong>Tier</strong>
                    <span class="badge badge-info">${data.tier || 'Unknown'}</span>
                </div>
            `;
        } catch (error) {
            grid.innerHTML = '<p class="error">Failed to detect hardware</p>';
            console.error('Hardware detection error:', error);
        }
    }
    
    async loadModels() {
        const list = document.getElementById('models-list');
        const banner = document.getElementById('no-ollama-banner');
        
        try {
            const data = await api('GET', '/api/models');
            this.availableModels = data.models || [];
            
            if (this.availableModels.length === 0) {
                banner.style.display = 'block';
                list.innerHTML = '<p class="help-text">Install Ollama to use local AI models</p>';
                return;
            }
            
            banner.style.display = 'none';
            
            list.innerHTML = this.availableModels.map((model, index) => {
                const compatibilityClass = 
                    model.compatibility === 'compatible' ? 'badge-success' :
                    model.compatibility === 'slow' ? 'badge-warning' :
                    'badge-gray';
                
                const compatibilityText = 
                    model.compatibility === 'compatible' ? '✓ Compatible' :
                    model.compatibility === 'slow' ? '⚠ Slow' :
                    '✗ Incompatible';
                
                const isRecommended = model.recommended;
                const isDisabled = model.compatibility === 'incompatible';
                
                return `
                    <label class="model-card ${isDisabled ? 'disabled' : ''} ${isRecommended ? 'recommended' : ''}">
                        <input type="radio" name="selected_model" value="${model.name}" 
                            ${isRecommended ? 'checked' : ''} 
                            ${isDisabled ? 'disabled' : ''}
                            onchange="wizard.selectModel('${model.name}')">
                        <div class="model-info">
                            <strong>${model.name}</strong>
                            ${isRecommended ? '<span class="badge badge-primary">Recommended</span>' : ''}
                            <p>VRAM: ${model.vram_gb || '?'} GB${model.installed ? ' | Installed' : ''}</p>
                            <span class="badge ${compatibilityClass}">${compatibilityText}</span>
                        </div>
                    </label>
                `;
            }).join('');
            
            // Populate dropdown selects for advanced mode
            this.populateModelDropdowns();
            
            // Auto-select recommended model (without marking as dirty)
            const recommended = this.availableModels.find(m => m.recommended);
            if (recommended) {
                this.state.set('selected_model', recommended.name);
            }
            
        } catch (error) {
            list.innerHTML = '<p class="error">Failed to load models</p>';
            console.error('Model loading error:', error);
        }
    }
    
    populateModelDropdowns() {
        const qualitySelect = document.getElementById('quality-model-select');
        const fastSelect = document.getElementById('fast-model-select');
        
        const options = this.availableModels.map(m => 
            `<option value="${m.name}">${m.name} (${m.size})</option>`
        ).join('');
        
        qualitySelect.innerHTML = options;
        fastSelect.innerHTML = options;
        
        // Set defaults
        const recommended = this.availableModels.find(m => m.recommended);
        if (recommended) {
            qualitySelect.value = recommended.name;
            fastSelect.value = recommended.name;
        }
    }
    
    selectModel(modelName) {
        this.state.set('selected_model', modelName);
        this.modelConfigDirty = true; // User manually selected a model
    }
    
    // ================================
    // Step 5: Review & Create
    // ================================
    
    initStep5() {
        this.renderReviewCards();
    }
    
    formatVoiceParam(value, suffix) {
        const str = String(value);
        if (str.endsWith(suffix)) return str;
        return `${str}${suffix}`;
    }

    renderReviewCards() {
        const container = document.getElementById('review-cards');
        
        const sections = [
            {
                step: 0,
                title: '👤 Identity',
                items: [
                    { label: 'Character Name', value: this.state.get('char_name') },
                    { label: 'Display Name', value: this.state.get('display_name') },
                    { label: 'Tagline', value: this.state.get('tagline') }
                ]
            },
            {
                step: 1,
                title: '🎭 Personality',
                items: [
                    { label: 'System Prompt', value: this.state.get('system_prompt') ? 'Configured' : 'None' },
                    { label: 'Accent Markers', value: (this.state.get('accent_markers') || []).length + ' items' },
                    { label: 'Catchphrases', value: (this.state.get('catchphrases') || []).length + ' items' }
                ]
            },
            {
                step: 2,
                title: '🎤 Voice',
                items: [
                    { label: 'Edge Voice', value: this.state.get('edge_voice') || 'Not selected' },
                    { label: 'Reference Audio', value: this.state.get('audio_path') ? 'Uploaded' : 'None' },
                    { label: 'Voice Rate', value: this.formatVoiceParam(this.state.get('voice_rate', 0), '%') },
                    { label: 'Voice Pitch', value: this.formatVoiceParam(this.state.get('voice_pitch', 0), 'Hz') }
                ]
            },
            {
                step: 3,
                title: '🎨 Appearance',
                items: [
                    { label: 'Source', value: this.state.get('sprite_source') === 'generate' ? 'AI Generated' : 'Manual Upload' },
                    { label: 'Art Style', value: this.state.get('art_style', '3d_figurine') },
                    { label: 'Visual Description', value: this.state.get('visual_description') ? 'Configured' : 'None' }
                ]
            },
            {
                step: 4,
                title: '⚙️ Hardware',
                items: [
                    { label: 'Selected Model', value: this.state.get('selected_model') || 'None' }
                ]
            }
        ];
        
        container.innerHTML = sections.map(section => `
            <div class="review-card">
                <div class="review-header">
                    <h3>${section.title}</h3>
                    <button class="btn btn-sm btn-secondary" onclick="wizard.goToStep(${section.step})">Edit</button>
                </div>
                <dl class="review-details">
                    ${section.items.map(item => `
                        <dt>${item.label}</dt>
                        <dd>${item.value || 'Not set'}</dd>
                    `).join('')}
                </dl>
            </div>
        `).join('');
    }
    
    async createCharacter() {
        const btn = document.getElementById('btn-create-character');
        const progress = document.getElementById('creation-progress');
        const progressFill = document.getElementById('create-progress-fill');
        const progressText = document.getElementById('create-progress-text');
        
        btn.disabled = true;
        progress.style.display = 'block';
        progressFill.style.width = '10%';
        progressText.textContent = 'Preparing character...';
        
        try {
            // Step 1: Update model config if user manually selected a model
            if (this.modelConfigDirty) {
                progressText.textContent = 'Configuring AI models...';
                progressFill.style.width = '20%';
                
                const selectedModel = this.state.get('selected_model');
                const advancedMode = this.state.get('advanced_models', false);
                
                let modelConfig;
                if (advancedMode) {
                    const qualityModel = document.getElementById('quality-model-select').value;
                    const fastModel = document.getElementById('fast-model-select').value;
                    modelConfig = {
                        quality_model: qualityModel,
                        fast_model: fastModel,
                        character: selectedModel
                    };
                } else {
                    modelConfig = {
                        quality_model: selectedModel,
                        fast_model: selectedModel,
                        character: selectedModel
                    };
                }
                
                await api('POST', '/api/config/models', modelConfig);
            }
            
            // Step 2: Create character
            progressText.textContent = 'Creating character profile...';
            progressFill.style.width = '50%';
            
            const characterData = {
                name: this.state.get('char_name'),
                display_name: this.state.get('display_name'),
                tagline: this.state.get('tagline'),
                description: this.state.get('description'),
                theme_colors: {
                    primary: this.state.get('color_primary', '#7B2FBE'),
                    secondary: this.state.get('color_secondary', '#1E90FF'),
                    accent: this.state.get('color_accent', '#FFD700'),
                    text: this.state.get('color_text', '#FFFFFF')
                },
                accent_markers: this.state.get('accent_markers', []),
                catchphrases: this.state.get('catchphrases', []),
                system_prompt: this.state.get('system_prompt', ''),
                edge_voice: this.state.get('edge_voice', ''),
                voice_rate: this.state.get('voice_rate', 0),
                voice_pitch: this.state.get('voice_pitch', 0),
                pronunciation: this.state.get('pronunciation', {}),
                preferred_engine: 'edge',
                visual_description: this.state.get('visual_description', ''),
                art_style: this.state.get('art_style', '3d_figurine')
            };
            
            progressFill.style.width = '80%';
            const result = await api('POST', '/api/create-character', characterData);
            
            progressFill.style.width = '100%';
            
            // Store the created character path for content generation
            this.state.set('char_dir', result.path);
            this.state.set('creation_result', result);
            
            // Show sprite generation status if auto-started
            if (result.sprite_task_id) {
                progressText.textContent = 'Character created! AI sprites generating in background...';
                this.state.set('sprite_task_id', result.sprite_task_id);
                showToast('✨ AI sprites are generating automatically in the background!', 'success');
            } else {
                progressText.textContent = 'Character created! Moving to content generation...';
            }
            
            // Navigate to Step 7 (content generation)
            setTimeout(() => {
                this.goToStep(6);
            }, 800);
            
        } catch (error) {
            showToast(`Character creation failed: ${error.message}`, 'error');
            console.error('Character creation error:', error);
            
            btn.disabled = false;
            progress.style.display = 'none';
            
            // Show retry option
            const retry = confirm('Character creation failed. Would you like to try again?');
            if (retry) {
                this.createCharacter();
            }
        }
    }

    // ================================
    // Step 7: Content Generation
    // ================================

    async initStep6() {
        // Load backend info
        try {
            const backendInfo = await api('GET', '/api/content/backend');
            const nameEl = document.getElementById('content-backend-name');
            const noteEl = document.getElementById('content-backend-note');
            
            if (backendInfo.type === 'openai') {
                nameEl.textContent = `OpenAI (${backendInfo.model})`;
                noteEl.textContent = 'Using cloud API — fast generation, high quality.';
            } else if (backendInfo.type === 'anthropic') {
                nameEl.textContent = `Anthropic (${backendInfo.model})`;
                noteEl.textContent = 'Using cloud API — fast generation, high quality.';
            } else {
                nameEl.textContent = `Ollama Local (${backendInfo.model})`;
                noteEl.textContent = 'Using local AI model. Generation may take 5-10 minutes depending on hardware.';
            }
        } catch (e) {
            document.getElementById('content-backend-name').textContent = 'Ollama (local)';
        }
    }

    async startContentGeneration() {
        const btn = document.getElementById('btn-start-generation');
        const skipBtn = document.getElementById('btn-skip-generation');
        const categories = document.getElementById('content-categories');
        const progressDiv = document.getElementById('content-gen-progress');
        
        btn.disabled = true;
        skipBtn.style.display = 'none';
        categories.style.display = 'none';
        progressDiv.style.display = 'block';
        
        // Gather selected categories
        const selectedCategories = [];
        if (document.getElementById('gen-idle').checked) selectedCategories.push('idle');
        if (document.getElementById('gen-games').checked) selectedCategories.push('games');
        if (document.getElementById('gen-extras').checked) selectedCategories.push('extras');
        
        if (selectedCategories.length === 0) {
            showToast('Please select at least one category', 'warning');
            btn.disabled = false;
            skipBtn.style.display = 'inline-block';
            categories.style.display = 'block';
            progressDiv.style.display = 'none';
            return;
        }
        
        // Build personality string from description + tone
        const tone = document.getElementById('content-tone').value.trim();
        const description = this.state.get('description', '');
        const personality = tone ? `${description}. Tone: ${tone}` : description;
        
        const body = {
            character_name: this.state.get('char_name'),
            description: description,
            personality: personality,
            char_dir: this.state.get('char_dir'),
            categories: selectedCategories
        };
        
        // Track per-category pool counts
        const poolCounts = { idle: 14, games: 16, extras: 9 };
        const poolDone = { idle: 0, games: 0, extras: 0 };
        
        try {
            const response = await fetch('/api/content/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop(); // Keep incomplete chunk
                
                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    try {
                        const event = JSON.parse(line.slice(6));
                        this._handleGenEvent(event, poolCounts, poolDone);
                    } catch (e) {
                        console.warn('SSE parse error:', e);
                    }
                }
            }
            
            // Process any remaining buffer
            if (buffer.startsWith('data: ')) {
                try {
                    const event = JSON.parse(buffer.slice(6));
                    this._handleGenEvent(event, poolCounts, poolDone);
                } catch (e) {}
            }
            
        } catch (error) {
            showToast(`Content generation error: ${error.message}`, 'error');
            btn.disabled = false;
            btn.textContent = '🔄 Retry Generation';
            skipBtn.style.display = 'inline-block';
        }
    }

    _handleGenEvent(event, poolCounts, poolDone) {
        const overallEl = document.getElementById('gen-overall-status');
        
        if (event.type === 'start') {
            overallEl.textContent = `Starting content generation (${event.backend} backend)...`;
        }
        else if (event.type === 'progress') {
            const cat = event.data.current_category;
            const pool = event.data.current_pool;
            if (cat) {
                document.getElementById(`gen-${cat}-status`).textContent = `Generating: ${pool}...`;
            }
            overallEl.textContent = `${event.data.completed_pools}/${event.data.total_pools} pools generated (${event.data.percent}%)`;
        }
        else if (event.type === 'pool_done') {
            const cat = event.category;
            poolDone[cat] = (poolDone[cat] || 0) + 1;
            const pct = Math.round((poolDone[cat] / poolCounts[cat]) * 100);
            document.getElementById(`gen-${cat}-fill`).style.width = `${pct}%`;
            document.getElementById(`gen-${cat}-status`).textContent = `${poolDone[cat]}/${poolCounts[cat]} pools done`;
            
            overallEl.textContent = `${event.data.completed_pools}/${event.data.total_pools} pools generated (${event.data.percent}%)`;
        }
        else if (event.type === 'complete') {
            this._showGenComplete(event.summary, event.data.errors);
        }
    }

    _showGenComplete(summary, errors) {
        document.getElementById('content-gen-progress').style.display = 'none';
        document.getElementById('content-gen-actions').style.display = 'none';
        
        const completeDiv = document.getElementById('content-gen-complete');
        const summaryDiv = document.getElementById('content-gen-summary');
        
        let html = `<p><strong>${summary.total_generated}</strong> content pools generated using <strong>${summary.backend_used}</strong>.</p>`;
        
        if (summary.items && summary.items.length > 0) {
            const totalItems = summary.items.reduce((acc, i) => acc + i.count, 0);
            html += `<p>Total items: <strong>${totalItems}</strong></p>`;
            html += '<ul class="gen-summary-list">';
            for (const item of summary.items) {
                html += `<li>${item.category}/${item.pool}: ${item.count} items</li>`;
            }
            html += '</ul>';
        }
        
        if (errors && errors.length > 0) {
            html += `<p class="gen-errors">⚠️ ${errors.length} pool(s) failed to generate (character will use LLM fallback for those):</p>`;
            html += '<ul class="gen-error-list">';
            for (const err of errors) {
                html += `<li>${err}</li>`;
            }
            html += '</ul>';
        }
        
        summaryDiv.innerHTML = html;
        completeDiv.style.display = 'block';
        
        showToast('Content generation complete!', 'success');
    }

    skipContentGeneration() {
        showToast('Skipping content generation. Character will generate responses on-the-fly using AI.', 'info');
        this.showSuccessScreen(this.state.get('creation_result'));
    }

    finishCreation() {
        this.showSuccessScreen(this.state.get('creation_result'));
    }
    
    showSuccessScreen(result) {
        // Hide wizard steps and nav
        document.querySelectorAll('.wizard-step').forEach(step => step.style.display = 'none');
        document.getElementById('wizard-nav').style.display = 'none';
        
        // Show success screen
        const successScreen = document.getElementById('success-screen');
        const successDetails = document.getElementById('success-details');
        
        successDetails.innerHTML = `
            <div class="success-card">
                <p>✅ Character profile created</p>
                <p>📁 Saved to: <code>${result.path || 'characters/'}</code></p>
                <p>🎤 Voice: ${typeof result.voice === 'object' ? (result.voice.engine || result.voice.status || 'Configured') : (result.voice || 'Edge TTS')}</p>
            </div>
        `;
        
        successScreen.style.display = 'block';
        successScreen.querySelector('h2').focus();
        
        // Clear state
        this.state.clear();
    }
    
    startServer() {
        // This would typically launch the server or redirect to it
        showToast('Feature not yet implemented', 'info');
    }
    
    createAnother() {
        location.reload();
    }
}

// ================================
// Initialize Wizard
// ================================

const wizard = new WizardUI();
document.addEventListener('DOMContentLoaded', () => wizard.init());
