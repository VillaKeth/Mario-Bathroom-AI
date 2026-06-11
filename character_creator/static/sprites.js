/**
 * Sprite Manager — manages AI sprite generation for all characters.
 * Polls /api/characters for status, POSTs to /api/sprites/generate/{name},
 * and polls /api/sprites/status/{task_id} for per-character progress.
 */

let allChars = [];
let currentFilter = 'all';
let activeTasks = {};     // char_id → { task_id, intervalId }
let previewOpen = {};     // char_id → bool
let bgOpen = {};          // char_id → bool
let bgData = {};          // char_id → { backgrounds, default }
let bgGenerating = {};    // char_id → bool

const DEFAULT_EXPECTED = 39;
const POLL_MS  = 4000;

function expectedFor(ch) {
    return ch?.expected_sprites || DEFAULT_EXPECTED;
}

// ── Settings Panel ────────────────────────────────────────────────────────────

let settingsOpen = false;

async function toggleSettings() {
    settingsOpen = !settingsOpen;
    document.getElementById('settings-panel').style.display = settingsOpen ? 'block' : 'none';
    if (settingsOpen) await loadSettings();
}

async function loadSettings() {
    try {
        const [backends, cfg] = await Promise.all([
            fetch('/api/sprites/backends').then(r => r.json()),
            fetch('/api/sprites/config').then(r => r.json()),
        ]);

        // Set current backend select
        document.getElementById('backend-select').value = cfg.backend || 'auto';
        document.getElementById('policy-select').value  = cfg.router_policy || 'cheapest';

        // Show token status
        const hfInput = document.getElementById('hf-token-input');
        hfInput.placeholder = cfg.hf_token_set ? `Current: ${cfg.hf_token}` : 'hf_xxxxxxxxxxxx — get free at huggingface.co';

        // Premium provider key placeholders + budgets
        for (const p of ['grok', 'openai', 'gemini']) {
            const keyInput = document.getElementById(`${p}-key-input`);
            if (keyInput) keyInput.placeholder = cfg[`${p}_key_set`] ? `Current: ${cfg[`${p}_key`]}` : keyInput.placeholder;
            const budInput = document.getElementById(`${p}-budget-input`);
            if (budInput) budInput.value = cfg[`${p}_budget`] ?? '';
        }

        // Render backend cards
        const cards = [
            {
                id: 'grok',
                icon: '🚀',
                name: 'Grok / xAI',
                desc: 'Premium. Excellent character framing & anatomy (~$0.07/img). Budget-capped.',
                status: backends.grok,
            },
            {
                id: 'openai',
                icon: '🧠',
                name: 'OpenAI gpt-image-1',
                desc: 'Premium. Best prompt adherence (~$0.06/img). Budget-capped.',
                status: backends.openai,
            },
            {
                id: 'gemini',
                icon: '✨',
                name: 'Google Gemini',
                desc: 'Premium. Fast, strong stylization (~$0.04/img). Budget-capped.',
                status: backends.gemini,
            },
            {
                id: 'huggingface',
                icon: '🤗',
                name: 'HuggingFace API',
                desc: 'Best free option. Fast (30-60s/sprite), high quality FLUX model. Requires free HF account.',
                status: backends.huggingface,
                recommended: true,
            },
            {
                id: 'a1111',
                icon: '🖥️',
                name: 'AUTOMATIC1111',
                desc: 'Run Stable Diffusion locally. Needs 8GB+ VRAM GPU and SD WebUI installed.',
                status: backends.a1111,
            },
            {
                id: 'comfyui',
                icon: '🖥️',
                name: 'ComfyUI',
                desc: 'Local generation via ComfyUI. Needs 8GB+ VRAM GPU and ComfyUI installed.',
                status: backends.comfyui,
            },
            {
                id: 'pollinations',
                icon: '🌐',
                name: 'Pollinations.ai',
                desc: 'Free cloud, no account needed. Very slow (90s/sprite + rate limits). Use as fallback.',
                status: backends.pollinations,
            },
        ];

        document.getElementById('backend-cards').innerHTML = cards.map(card => {
            const avail = card.status?.available;
            const statusColor = avail ? 'var(--color-green)' : 'var(--color-orange)';
            const statusIcon  = avail ? '✅' : '⚠️';
            const border = card.recommended ? 'var(--color-purple)' : 'var(--border-color)';
            return `
                <div style="background:var(--bg-card);border:1px solid ${border};border-radius:var(--radius-md);padding:1rem">
                    <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.4rem">
                        <span style="font-size:1.3rem">${card.icon}</span>
                        <strong style="font-size:0.9rem">${card.name}</strong>
                        ${card.recommended ? '<span style="font-size:0.7rem;background:var(--color-purple);color:white;padding:0.1rem 0.4rem;border-radius:8px">Recommended</span>' : ''}
                    </div>
                    <p style="font-size:0.78rem;color:var(--text-muted);margin-bottom:0.5rem">${card.desc}</p>
                    <div style="font-size:0.78rem;color:${statusColor}">${statusIcon} ${card.status?.reason || (avail ? 'Available' : 'Not available')}</div>
                </div>`;
        }).join('');

    } catch (e) {
        document.getElementById('settings-status').textContent = `Error loading settings: ${e.message}`;
    }
}

async function saveSettings() {
    const hfToken  = document.getElementById('hf-token-input').value.trim();
    const backend  = document.getElementById('backend-select').value;
    const policy   = document.getElementById('policy-select').value;
    const statusEl = document.getElementById('settings-status');

    statusEl.textContent = 'Saving…';
    statusEl.style.color = 'var(--text-muted)';

    try {
        const body = { backend, router_policy: policy };
        if (hfToken) body.hf_token = hfToken;
        for (const p of ['grok', 'openai', 'gemini']) {
            const key = document.getElementById(`${p}-key-input`)?.value.trim();
            if (key) body[`${p}_key`] = key;
            const bud = document.getElementById(`${p}-budget-input`)?.value;
            if (bud !== '' && bud != null) body[`${p}_budget`] = parseFloat(bud);
        }

        const r = await fetch('/api/sprites/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const data = await r.json();
        if (data.success) {
            statusEl.textContent = `✅ Saved! Backend: ${backend}, policy: ${policy}${hfToken ? ' — HF token updated' : ''}`;
            statusEl.style.color = 'var(--color-green)';
            document.getElementById('hf-token-input').value = '';
            for (const p of ['grok', 'openai', 'gemini']) {
                const ki = document.getElementById(`${p}-key-input`);
                if (ki) ki.value = '';
            }
            await loadSettings(); // Refresh backend status
        } else {
            statusEl.textContent = `Error: ${data.error}`;
            statusEl.style.color = 'var(--color-red)';
        }
    } catch (e) {
        statusEl.textContent = `Error: ${e.message}`;
        statusEl.style.color = 'var(--color-red)';
    }
}


// ── Boot ─────────────────────────────────────────────────────────────────────

async function loadCharacters() {
    document.getElementById('loading-state').style.display = 'flex';
    document.getElementById('chars-grid').style.display   = 'none';

    try {
        const res  = await fetch('/api/characters');
        const data = await res.json();
        allChars   = data.characters || [];

        // Resume polling for any in-progress tasks
        for (const ch of allChars) {
            if (ch.generating) {
                startPolling(ch.id, ch.generating.task_id);
            }
        }

        renderAll();
    } catch (e) {
        document.getElementById('loading-state').innerHTML =
            `<span style="color:var(--color-red)">Failed to load characters: ${e.message}</span>`;
    }
}

// ── Rendering ─────────────────────────────────────────────────────────────────

function renderAll() {
    const query   = document.getElementById('search-input').value.toLowerCase();
    const grid    = document.getElementById('chars-grid');
    const loading = document.getElementById('loading-state');

    loading.style.display = 'none';
    grid.style.display    = 'grid';

    let visible = allChars;

    // Search filter
    if (query) {
        visible = visible.filter(c =>
            c.name.toLowerCase().includes(query) ||
            c.id.toLowerCase().includes(query) ||
            (c.tagline || '').toLowerCase().includes(query)
        );
    }

    // Status filter
    if (currentFilter !== 'all') {
        visible = visible.filter(c => {
            const task = activeTasks[c.id];
            if (currentFilter === 'generating') return !!task;
            const expected = expectedFor(c);
            if (currentFilter === 'complete')   return c.sprite_count >= expected;
            if (currentFilter === 'partial')    return c.sprite_count > 0 && c.sprite_count < expected;
            if (currentFilter === 'missing')    return c.sprite_count === 0;
            return true;
        });
    }

    // Stats
    const total    = allChars.length;
    const complete = allChars.filter(c => c.sprite_count >= expectedFor(c)).length;
    const genCount = Object.keys(activeTasks).length;
    document.getElementById('stats-label').textContent =
        `${total} characters — ${complete} complete, ${genCount} generating`;
    document.getElementById('btn-gen-all').disabled = false;

    if (visible.length === 0) {
        grid.innerHTML = `<div class="empty-state"><h3>No characters match</h3><p>Try a different filter or search term.</p></div>`;
        return;
    }

    grid.innerHTML = visible.map(c => buildCard(c)).join('');

    // Restore open preview strips
    for (const id of Object.keys(previewOpen)) {
        const strip = document.getElementById(`strip-${id}`);
        if (strip) strip.classList.add('open');
    }
}

function buildCard(ch) {
    const task     = activeTasks[ch.id];
    const isGen    = !!task;
    const expected = expectedFor(ch);
    const pct      = isGen ? Math.round((task.completed / (task.total || expected)) * 100) : 0;
    const count    = isGen ? task.completed : ch.sprite_count;
    const total    = isGen ? (task.total || expected) : expected;

    const badgeClass =
        isGen                     ? 'badge-gen'      :
        count >= expected         ? 'badge-complete'  :
        count > 0                 ? 'badge-partial'   :
                                    'badge-empty';
    const badgeIcon =
        isGen                     ? '🔄'  :
        count >= expected         ? '✅'  :
        count > 0                 ? '⚠️' :
                                    '❌';
    const badgeText =
        isGen ? `${count}/${total} generating…` :
                `${count}/${expected} sprites`;

    const cardClass =
        isGen             ? 'generating' :
        count >= expected ? 'complete'   : '';

    // Avatar: try the first valid sprite
    const firstSprite = (ch.sprites || []).find(s => s.valid);
    const avatarHTML = firstSprite
        ? `<img src="/api/sprites/preview/${ch.id}/${firstSprite.key}" alt="${ch.name}" loading="lazy">`
        : `<span>${ch.name.charAt(0).toUpperCase()}</span>`;

    const progressHTML = isGen ? `
        <div class="gen-progress">
            <div class="progress-track">
                <div class="progress-fill" id="fill-${ch.id}" style="width:${pct}%"></div>
            </div>
            <div class="progress-label">
                <span>${count} / ${total} poses</span>
                <span>${pct}%</span>
            </div>
        </div>
        <div class="current-pose" id="pose-${ch.id}">
            Generating: ${task.current || '…'}
        </div>` : '';

    const genBtnLabel  = isGen     ? '🔄 Generating…'    :
                         count > 0 ? '⚡ Regenerate All' :
                                     '⚡ Generate Sprites';
    const genBtnDisabled = isGen ? 'disabled' : '';

    const validSprites  = (ch.sprites || []).filter(s => s.valid);
    const viewBtnLabel  = previewOpen[ch.id] ? '▲ Hide' : `🖼 Preview (${validSprites.length})`;

    const thumbsHTML = (ch.sprites || []).map(s => {
        if (!s.valid) return `
            <div class="sprite-thumb broken" title="${s.key} (broken — ${s.size} bytes)">
                <span style="font-size:1.2rem">❌</span>
                <div class="thumb-label">${s.key.split('/').pop()}</div>
            </div>`;
        return `
            <div class="sprite-thumb" onclick="openLightbox('/api/sprites/preview/${ch.id}/${s.key}','${ch.name} — ${s.key}')" title="${s.key}">
                <img src="/api/sprites/preview/${ch.id}/${s.key}" alt="${s.key}" loading="lazy">
                <div class="thumb-label">${s.key.split('/').pop()}</div>
            </div>`;
    }).join('');

    return `
        <div class="char-card ${cardClass}" id="card-${ch.id}">
            <div class="card-header">
                <div class="char-avatar">${avatarHTML}</div>
                <div class="char-info">
                    <div class="char-name">${ch.display_name || ch.name}</div>
                    <div class="char-tagline">${ch.tagline || ch.id}</div>
                </div>
                <div class="sprite-badge ${badgeClass}">${badgeIcon} ${badgeText}</div>
            </div>
            ${progressHTML}
            <div class="card-actions">
                <button class="btn-gen btn-gen-start" ${genBtnDisabled}
                    onclick="startGeneration('${ch.id}')">
                    ${genBtnLabel}
                </button>
                <button class="btn-gen btn-gen-view"
                    onclick="togglePreview('${ch.id}')" id="view-btn-${ch.id}">
                    ${viewBtnLabel}
                </button>
                <button class="btn-gen btn-gen-view"
                    onclick="toggleBackgrounds('${ch.id}')" id="bg-btn-${ch.id}">
                    ${bgOpen[ch.id] ? '▲ BG' : '🏞 Backgrounds'}
                </button>
            </div>
            <div class="sprite-strip ${previewOpen[ch.id] ? 'open' : ''}" id="strip-${ch.id}">
                ${thumbsHTML || '<span style="color:var(--text-muted);font-size:0.85rem;padding:0.5rem">No sprites yet. Generate to get started.</span>'}
            </div>
            <div class="bg-strip ${bgOpen[ch.id] ? 'open' : ''}" id="bgstrip-${ch.id}">
                ${bgOpen[ch.id] ? buildBgStrip(ch.id) : ''}
            </div>
        </div>`;
}

// ── Actions ───────────────────────────────────────────────────────────────────

async function startGeneration(charId) {
    if (activeTasks[charId]) return;

    const ch = allChars.find(c => c.id === charId);
    if (!ch) return;

    try {
        const res  = await fetch(`/api/sprites/generate/${charId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
        });
        const data = await res.json();

        if (!data.success) {
            alert(`Could not start generation: ${data.error}`);
            return;
        }

        startPolling(charId, data.task_id);
        renderAll();

    } catch (e) {
        alert(`Error: ${e.message}`);
    }
}

async function generateAllMissing() {
    const missing = allChars.filter(c =>
        c.sprite_count < expectedFor(c) && !activeTasks[c.id]
    );

    if (missing.length === 0) {
        alert('All characters already have complete sprites!');
        return;
    }

    const ok = confirm(
        `Start sprite generation for ${missing.length} characters with missing sprites?\n\n` +
        `Note: Pollinations.ai requires ~90s between each pose, so this will run in the background for a long time.\n\n` +
        missing.map(c => `• ${c.display_name || c.name} (${c.sprite_count}/${expectedFor(c)})`).join('\n')
    );
    if (!ok) return;

    // Start them all (they'll queue themselves)
    for (const ch of missing) {
        await startGeneration(ch.id);
        await sleep(500);  // small stagger so tasks don't collide
    }
}

function togglePreview(charId) {
    if (previewOpen[charId]) {
        delete previewOpen[charId];
    } else {
        previewOpen[charId] = true;
    }
    // Update just this card's strip and button
    const strip = document.getElementById(`strip-${charId}`);
    const btn   = document.getElementById(`view-btn-${charId}`);
    if (strip) strip.classList.toggle('open', !!previewOpen[charId]);

    const ch = allChars.find(c => c.id === charId);
    if (btn && ch) {
        const validSprites = (ch.sprites || []).filter(s => s.valid);
        btn.textContent = previewOpen[charId] ? '▲ Hide' : `🖼 Preview (${validSprites.length})`;
    }
}

// ── Backgrounds ───────────────────────────────────────────────────────────────

async function toggleBackgrounds(charId) {
    if (bgOpen[charId]) {
        delete bgOpen[charId];
        renderBgStrip(charId);
        return;
    }
    bgOpen[charId] = true;
    await loadBackgrounds(charId);
}

async function loadBackgrounds(charId) {
    try {
        const res  = await fetch(`/api/backgrounds/${charId}`);
        const data = await res.json();
        if (data.success) bgData[charId] = data;
    } catch (e) {
        console.warn(`Backgrounds load failed for ${charId}:`, e);
    }
    renderBgStrip(charId);
}

function buildBgStrip(charId) {
    const data = bgData[charId] || { backgrounds: [], default: '' };
    const generating = bgGenerating[charId];

    const thumbs = (data.backgrounds || []).map(bg => {
        const base = bg.filename.replace(/\.[^.]+$/, '');
        const isDefault = data.default && data.default === base;
        const src = `/api/backgrounds/preview/${charId}/${encodeURIComponent(bg.filename)}?t=${bg.size}`;
        return `
            <div class="bg-thumb ${isDefault ? 'default' : ''}" title="${bg.filename}">
                <img src="${src}" alt="${bg.filename}" loading="lazy"
                     onclick="openLightbox('${src}','${charId} — ${bg.filename}')">
                <div class="bg-thumb-bar">
                    ${isDefault
                        ? '<span class="bg-default-star">★ default</span>'
                        : `<button onclick="setDefaultBackground('${charId}','${bg.filename}')" title="Use as default">☆ set default</button>`}
                    <button onclick="deleteBackground('${charId}','${bg.filename}')" title="Delete">✕</button>
                </div>
            </div>`;
    }).join('');

    return `
        <div class="bg-gen-row">
            <input type="text" id="bg-prompt-${charId}"
                   placeholder="Describe a background scene, e.g. cozy coffee shop interior, warm lighting"
                   onkeydown="if(event.key==='Enter')generateBackground('${charId}')">
            <button class="btn-gen btn-gen-start" style="flex:0 0 auto" ${generating ? 'disabled' : ''}
                    onclick="generateBackground('${charId}')">
                ${generating ? '🔄 Generating…' : '✨ Generate'}
            </button>
            <label class="btn-gen btn-gen-view" style="flex:0 0 auto;display:flex;align-items:center;cursor:pointer">
                📤 Upload
                <input type="file" accept=".png,.jpg,.jpeg" style="display:none"
                       onchange="uploadBackground('${charId}', this)">
            </label>
        </div>
        <div class="bg-thumbs">
            ${thumbs || '<span style="color:var(--text-muted);font-size:0.82rem">No backgrounds yet. Generate one or upload an image. The ★ default shows automatically in the party client.</span>'}
        </div>`;
}

function renderBgStrip(charId) {
    const strip = document.getElementById(`bgstrip-${charId}`);
    const btn   = document.getElementById(`bg-btn-${charId}`);
    if (!strip) return;
    strip.classList.toggle('open', !!bgOpen[charId]);
    strip.innerHTML = bgOpen[charId] ? buildBgStrip(charId) : '';
    if (btn) btn.textContent = bgOpen[charId] ? '▲ BG' : '🏞 Backgrounds';
}

async function generateBackground(charId) {
    if (bgGenerating[charId]) return;
    const input  = document.getElementById(`bg-prompt-${charId}`);
    const prompt = (input?.value || '').trim();
    if (!prompt) { alert('Describe the background scene first!'); return; }

    bgGenerating[charId] = true;
    renderBgStrip(charId);
    // Preserve typed prompt across the re-render
    const newInput = document.getElementById(`bg-prompt-${charId}`);
    if (newInput) newInput.value = prompt;

    try {
        const res  = await fetch(`/api/backgrounds/generate/${charId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt }),
        });
        const data = await res.json();
        if (!data.success) alert(`Background generation failed: ${data.error}`);
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
    delete bgGenerating[charId];
    await loadBackgrounds(charId);
}

async function setDefaultBackground(charId, filename) {
    try {
        const res  = await fetch(`/api/backgrounds/default/${charId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename }),
        });
        const data = await res.json();
        if (!data.success) alert(`Could not set default: ${data.error}`);
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
    await loadBackgrounds(charId);
}

async function deleteBackground(charId, filename) {
    if (!confirm(`Delete background "${filename}"?`)) return;
    try {
        const res  = await fetch(`/api/backgrounds/delete/${charId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename }),
        });
        const data = await res.json();
        if (!data.success) alert(`Could not delete: ${data.error}`);
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
    await loadBackgrounds(charId);
}

async function uploadBackground(charId, fileInput) {
    const file = fileInput.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    form.append('character_name', charId);
    try {
        const res  = await fetch('/api/upload/background', { method: 'POST', body: form });
        const data = await res.json();
        if (!data.success) alert(`Upload failed: ${data.error}`);
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
    fileInput.value = '';
    await loadBackgrounds(charId);
}

// ── Polling ───────────────────────────────────────────────────────────────────

function startPolling(charId, taskId) {
    if (activeTasks[charId]) clearInterval(activeTasks[charId].intervalId);

    const intervalId = setInterval(() => pollTask(charId, taskId), POLL_MS);
    const ch = allChars.find(c => c.id === charId);
    activeTasks[charId] = { task_id: taskId, intervalId, completed: 0, total: expectedFor(ch), current: '' };
    pollTask(charId, taskId); // immediate first poll
}

async function pollTask(charId, taskId) {
    try {
        const res  = await fetch(`/api/sprites/status/${taskId}`);
        const data = await res.json();

        if (!data || data.status === 'not_found') {
            stopPolling(charId);
            return;
        }

        const task = activeTasks[charId];
        if (task) {
            task.completed = data.completed || 0;
            task.total     = data.total || data.total_poses || task.total || DEFAULT_EXPECTED;
            task.current   = data.current   || '';
        }

        // Update UI in-place without full re-render (faster)
        updateCardInPlace(charId, data);

        if (data.status === 'completed') {
            stopPolling(charId);
            // Reload this character's data
            await refreshCharacter(charId);
        }

    } catch (e) {
        console.warn(`Poll failed for ${charId}:`, e);
    }
}

function updateCardInPlace(charId, taskData) {
    const fill  = document.getElementById(`fill-${charId}`);
    const label = document.getElementById(`pose-${charId}`);
    if (!fill) return;  // card not rendered right now (filtered out)

    const pct = Math.round(((taskData.completed || 0) / (taskData.total || DEFAULT_EXPECTED)) * 100);
    fill.style.width = `${pct}%`;

    const progLabels = fill.closest('.gen-progress')?.querySelectorAll('.progress-label span');
    if (progLabels) {
        progLabels[0].textContent = `${taskData.completed} / ${taskData.total || DEFAULT_EXPECTED} poses`;
        progLabels[1].textContent = `${pct}%`;
    }

    if (label) label.textContent = `Generating: ${taskData.current || '…'}`;
}

async function refreshCharacter(charId) {
    delete activeTasks[charId];
    await loadCharacters();
}

function stopPolling(charId) {
    const task = activeTasks[charId];
    if (task) {
        clearInterval(task.intervalId);
        delete activeTasks[charId];
    }
}

// ── Filters ───────────────────────────────────────────────────────────────────

function setFilter(filter, btn) {
    currentFilter = filter;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderAll();
}

function applyFilter() { renderAll(); }

// ── Lightbox ──────────────────────────────────────────────────────────────────

function openLightbox(src, label) {
    document.getElementById('lb-img').src    = src;
    document.getElementById('lb-label').textContent = label;
    document.getElementById('lightbox').classList.add('open');
}

function closeLightbox() {
    document.getElementById('lightbox').classList.remove('open');
    document.getElementById('lb-img').src = '';
}

document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeLightbox();
});

// ── Helpers ───────────────────────────────────────────────────────────────────

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ── Init ──────────────────────────────────────────────────────────────────────
loadCharacters();
