/**
 * Sprite Manager — manages AI sprite generation for all characters.
 * Polls /api/characters for status, POSTs to /api/sprites/generate/{name},
 * and polls /api/sprites/status/{task_id} for per-character progress.
 */

let allChars = [];
let currentFilter = 'all';
let activeTasks = {};     // char_id → { task_id, intervalId }
let previewOpen = {};     // char_id → bool

const EXPECTED = 34;
const POLL_MS  = 4000;

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
            if (currentFilter === 'complete')   return c.sprite_count >= EXPECTED;
            if (currentFilter === 'partial')    return c.sprite_count > 0 && c.sprite_count < EXPECTED;
            if (currentFilter === 'missing')    return c.sprite_count === 0;
            return true;
        });
    }

    // Stats
    const total    = allChars.length;
    const complete = allChars.filter(c => c.sprite_count >= EXPECTED).length;
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
    const pct      = isGen ? Math.round((task.completed / (task.total || EXPECTED)) * 100) : 0;
    const count    = isGen ? task.completed : ch.sprite_count;
    const total    = isGen ? (task.total || EXPECTED) : EXPECTED;

    const badgeClass =
        isGen                     ? 'badge-gen'      :
        count >= EXPECTED         ? 'badge-complete'  :
        count > 0                 ? 'badge-partial'   :
                                    'badge-empty';
    const badgeIcon =
        isGen                     ? '🔄'  :
        count >= EXPECTED         ? '✅'  :
        count > 0                 ? '⚠️' :
                                    '❌';
    const badgeText =
        isGen ? `${count}/${total} generating…` :
                `${count}/${EXPECTED} sprites`;

    const cardClass =
        isGen             ? 'generating' :
        count >= EXPECTED ? 'complete'   : '';

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
            </div>
            <div class="sprite-strip ${previewOpen[ch.id] ? 'open' : ''}" id="strip-${ch.id}">
                ${thumbsHTML || '<span style="color:var(--text-muted);font-size:0.85rem;padding:0.5rem">No sprites yet. Generate to get started.</span>'}
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
        c.sprite_count < EXPECTED && !activeTasks[c.id]
    );

    if (missing.length === 0) {
        alert('All characters already have complete sprites!');
        return;
    }

    const ok = confirm(
        `Start sprite generation for ${missing.length} characters with missing sprites?\n\n` +
        `Note: Pollinations.ai requires ~90s between each pose, so this will run in the background for a long time.\n\n` +
        missing.map(c => `• ${c.display_name || c.name} (${c.sprite_count}/${EXPECTED})`).join('\n')
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

// ── Polling ───────────────────────────────────────────────────────────────────

function startPolling(charId, taskId) {
    if (activeTasks[charId]) clearInterval(activeTasks[charId].intervalId);

    const intervalId = setInterval(() => pollTask(charId, taskId), POLL_MS);
    activeTasks[charId] = { task_id: taskId, intervalId, completed: 0, total: EXPECTED, current: '' };
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
            task.total     = data.total     || EXPECTED;
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

    const pct = Math.round(((taskData.completed || 0) / (taskData.total || EXPECTED)) * 100);
    fill.style.width = `${pct}%`;

    const progLabels = fill.closest('.gen-progress')?.querySelectorAll('.progress-label span');
    if (progLabels) {
        progLabels[0].textContent = `${taskData.completed} / ${taskData.total || EXPECTED} poses`;
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
