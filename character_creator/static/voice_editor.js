// voice_editor.js
// Waveform region editor for the character-creator wizard (Step 3: Voice).
// Depends on: wavesurfer.js v6 UMD  (window.WaveSurfer)
//             wavesurfer.regions plugin (window.WaveSurfer.regions)
//
// Usage:
//   const editor = new VoiceEditor(containerEl, audioUrl);
//   editor.getRegions()  // -> [{start, end}, ...]
//
// Exposed globally as window.VoiceEditor to match the wizard's classic-script style.

(function (global) {
    'use strict';

    // ----------------------------------------------------------------
    // Internal helpers
    // ----------------------------------------------------------------

    function _secondsToStr(s) {
        var m = Math.floor(s / 60);
        var sec = (s - m * 60).toFixed(2);
        return m + ':' + (sec < 10 ? '0' : '') + sec;
    }

    function _randomColor() {
        var hue = Math.floor(Math.random() * 360);
        return 'hsla(' + hue + ', 70%, 55%, 0.35)';
    }

    // ----------------------------------------------------------------
    // VoiceEditor class
    // ----------------------------------------------------------------

    /**
     * @param {HTMLElement} container  — element to render the waveform + controls into
     * @param {string}      audioUrl   — URL of the audio file to display
     * @param {object}      [opts]     — optional overrides
     * @param {number}      [opts.height=80]          waveform height in px
     * @param {boolean}     [opts.normalize=true]     normalize waveform peaks
     * @param {boolean}     [opts.scrollParent=false] allow horizontal scroll
     */
    function VoiceEditor(container, audioUrl, opts) {
        if (!(container instanceof HTMLElement)) {
            throw new Error('VoiceEditor: first argument must be an HTMLElement');
        }
        if (!audioUrl || typeof audioUrl !== 'string') {
            throw new Error('VoiceEditor: second argument must be an audio URL string');
        }
        if (typeof WaveSurfer === 'undefined') {
            throw new Error('VoiceEditor: WaveSurfer global not found — load wavesurfer.min.js first');
        }

        this._container = container;
        this._audioUrl = audioUrl;
        this._opts = Object.assign({ height: 80, normalize: true, scrollParent: false }, opts || {});
        this._ws = null;
        this._regionMap = {};   // regionId -> region object
        this._nextColor = _randomColor;

        this._build();
    }

    // ---- DOM construction ------------------------------------------

    VoiceEditor.prototype._build = function () {
        var self = this;
        var c = this._container;
        c.innerHTML = '';
        c.className = (c.className || '') + ' voice-editor';

        // ---- Waveform area ----
        var waveDiv = document.createElement('div');
        waveDiv.className = 've-wave';
        waveDiv.style.cssText = 'width:100%;cursor:crosshair;';
        c.appendChild(waveDiv);

        // ---- Loading indicator ----
        var loadingEl = document.createElement('p');
        loadingEl.className = 've-loading help-text';
        loadingEl.textContent = 'Loading waveform...';
        c.appendChild(loadingEl);

        // ---- Transport controls ----
        var transport = document.createElement('div');
        transport.className = 've-transport';
        transport.style.cssText = 'display:flex;gap:0.5rem;align-items:center;flex-wrap:wrap;margin:0.5rem 0;';
        transport.innerHTML =
            '<button class="btn btn-secondary btn-sm ve-btn-play">▶ Play</button>' +
            '<button class="btn btn-secondary btn-sm ve-btn-pause">⏸ Pause</button>' +
            '<button class="btn btn-secondary btn-sm ve-btn-stop">⏹ Stop</button>' +
            '<button class="btn btn-primary btn-sm ve-btn-add">+ Add Region</button>' +
            '<span class="ve-time-display help-text" style="min-width:7rem">0:00.00 / 0:00.00</span>';
        c.appendChild(transport);

        // ---- Region list ----
        var regionListLabel = document.createElement('p');
        regionListLabel.className = 've-region-list-label help-text';
        regionListLabel.style.cssText = 'margin:0.4rem 0 0.2rem;font-size:0.8rem;';
        regionListLabel.textContent = 'Regions (drag handles on waveform to resize):';
        c.appendChild(regionListLabel);

        var regionList = document.createElement('div');
        regionList.className = 've-region-list';
        regionList.style.cssText = 'display:flex;flex-direction:column;gap:0.35rem;';
        c.appendChild(regionList);

        this._loadingEl = loadingEl;
        this._regionListEl = regionList;
        this._timeDisplayEl = transport.querySelector('.ve-time-display');

        // ---- Init WaveSurfer ----
        this._ws = WaveSurfer.create({
            container: waveDiv,
            waveColor: 'var(--color-purple, #7B2FBE)',
            progressColor: 'var(--color-purple-dark, #5a1f8e)',
            cursorColor: '#fff',
            backend: 'WebAudio',
            height: this._opts.height,
            normalize: this._opts.normalize,
            scrollParent: this._opts.scrollParent,
            plugins: [
                WaveSurfer.regions.create({
                    regionsMinLength: 0.1,
                    dragSelection: {
                        // Drag anywhere on the waveform to create a new region
                        slop: 5
                    }
                })
            ]
        });

        this._ws.load(audioUrl);

        // ---- Wire events ----
        this._ws.on('ready', function () {
            loadingEl.style.display = 'none';
            var dur = self._ws.getDuration();
            self._timeDisplayEl.textContent = '0:00.00 / ' + _secondsToStr(dur);
        });

        this._ws.on('error', function (err) {
            loadingEl.textContent = 'Error loading audio: ' + err;
            loadingEl.style.color = 'var(--color-red, #e55)';
        });

        this._ws.on('audioprocess', function () {
            var cur = self._ws.getCurrentTime();
            var dur = self._ws.getDuration();
            self._timeDisplayEl.textContent = _secondsToStr(cur) + ' / ' + _secondsToStr(dur);
        });

        this._ws.on('seek', function () {
            var cur = self._ws.getCurrentTime();
            var dur = self._ws.getDuration();
            self._timeDisplayEl.textContent = _secondsToStr(cur) + ' / ' + _secondsToStr(dur);
        });

        // Region created by drag-to-draw
        this._ws.on('region-created', function (region) {
            if (!self._regionMap[region.id]) {
                region.color = self._nextColor();
                self._regionMap[region.id] = region;
            }
            self._renderRegionList();
        });

        this._ws.on('region-updated', function () {
            self._renderRegionList();
        });

        this._ws.on('region-removed', function () {
            self._renderRegionList();
        });

        // ---- Button events ----
        transport.querySelector('.ve-btn-play').addEventListener('click', function () {
            self._ws.play();
        });
        transport.querySelector('.ve-btn-pause').addEventListener('click', function () {
            self._ws.pause();
        });
        transport.querySelector('.ve-btn-stop').addEventListener('click', function () {
            self._ws.stop();
        });
        transport.querySelector('.ve-btn-add').addEventListener('click', function () {
            self._addRegionProgrammatically();
        });
    };

    // ---- Region management -----------------------------------------

    /**
     * Add a region programmatically when the user clicks "+ Add Region".
     * Places it around the current playhead (or at 20-30% of total if not playing).
     */
    VoiceEditor.prototype._addRegionProgrammatically = function () {
        var dur = this._ws.getDuration() || 10;
        var cur = this._ws.getCurrentTime() || 0;

        var start, end;
        if (cur > 0 && cur < dur - 0.5) {
            start = Math.max(0, cur - 0.5);
            end   = Math.min(dur, cur + 2);
        } else {
            start = dur * 0.2;
            end   = dur * 0.3;
        }

        var region = this._ws.addRegion({
            start: start,
            end:   end,
            color: this._nextColor(),
            drag:  true,
            resize: true
        });
        this._regionMap[region.id] = region;
        this._renderRegionList();
    };

    VoiceEditor.prototype._removeRegion = function (regionId) {
        var region = this._regionMap[regionId];
        if (region) {
            region.remove();
            delete this._regionMap[regionId];
        }
        this._renderRegionList();
    };

    VoiceEditor.prototype._playRegion = function (regionId) {
        var region = this._regionMap[regionId];
        if (region) {
            region.play();
        }
    };

    // ---- Region list rendering ------------------------------------

    VoiceEditor.prototype._renderRegionList = function () {
        var self = this;
        var el = this._regionListEl;
        var regions = Object.values(this._regionMap);

        if (regions.length === 0) {
            el.innerHTML = '<p class="help-text" style="font-size:0.8rem;color:var(--text-muted)">No regions yet — drag on the waveform or click "+ Add Region".</p>';
            return;
        }

        // Sort by start time for display
        regions = regions.slice().sort(function (a, b) { return a.start - b.start; });

        el.innerHTML = regions.map(function (r) {
            var dur = r.end - r.start;
            var colorSwatch = '<span style="display:inline-block;width:12px;height:12px;border-radius:2px;background:' + r.color + ';border:1px solid rgba(255,255,255,0.3);vertical-align:middle;margin-right:4px"></span>';
            return (
                '<div class="ve-region-row" style="display:flex;align-items:center;gap:0.4rem;flex-wrap:wrap;' +
                    'background:var(--bg-input,#1a1a2e);border:1px solid var(--border-color,#333);' +
                    'border-radius:6px;padding:0.3rem 0.5rem;font-size:0.8rem;">' +
                    colorSwatch +
                    '<span style="min-width:11rem;color:var(--text-primary)">' +
                        _secondsToStr(r.start) + ' &ndash; ' + _secondsToStr(r.end) +
                        ' <span style="color:var(--text-muted)">(' + dur.toFixed(2) + 's)</span>' +
                    '</span>' +
                    '<button class="btn btn-sm btn-secondary" ' +
                        'onclick="VoiceEditor._instances && VoiceEditor._instances[\'' + self._instanceId + '\']._playRegion(\'' + r.id + '\')">' +
                        '▶ Play' +
                    '</button>' +
                    '<button class="btn btn-sm btn-danger" ' +
                        'onclick="VoiceEditor._instances && VoiceEditor._instances[\'' + self._instanceId + '\']._removeRegion(\'' + r.id + '\')">' +
                        '✕ Delete' +
                    '</button>' +
                '</div>'
            );
        }).join('');
    };

    // ---- Public API ------------------------------------------------

    /**
     * Returns the current regions as a plain array.
     * @returns {{ start: number, end: number }[]}
     */
    VoiceEditor.prototype.getRegions = function () {
        return Object.values(this._regionMap)
            .sort(function (a, b) { return a.start - b.start; })
            .map(function (r) { return { start: r.start, end: r.end }; });
    };

    /**
     * Clear all regions.
     */
    VoiceEditor.prototype.clearRegions = function () {
        this._ws.clearRegions();
        this._regionMap = {};
        this._renderRegionList();
    };

    /**
     * Destroy the WaveSurfer instance and clean up the container.
     */
    VoiceEditor.prototype.destroy = function () {
        if (this._ws) {
            this._ws.destroy();
            this._ws = null;
        }
        this._container.innerHTML = '';
        if (this._instanceId && VoiceEditor._instances) {
            delete VoiceEditor._instances[this._instanceId];
        }
    };

    // ---- Instance registry (needed for inline onclick handlers) ----
    // Inline onclick attributes in _renderRegionList look up
    // VoiceEditor._instances[id] to call methods.  This avoids eval.

    VoiceEditor._instances = {};
    var _instanceCounter = 0;

    var _OriginalVoiceEditor = VoiceEditor;

    // Wrap constructor to auto-register instances
    function VoiceEditorFactory(container, audioUrl, opts) {
        var instance = new _OriginalVoiceEditor(container, audioUrl, opts);
        var id = 've_' + (++_instanceCounter);
        instance._instanceId = id;
        VoiceEditorFactory._instances[id] = instance;
        return instance;
    }

    VoiceEditorFactory._instances = VoiceEditor._instances;
    VoiceEditorFactory.prototype = VoiceEditor.prototype;

    // Expose globally
    global.VoiceEditor = VoiceEditorFactory;

}(window));
