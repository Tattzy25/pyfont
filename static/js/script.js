let selectedStyleId = null;

const PREVIEW_TEXT = 'ABC';
const PREVIEW_CACHE_PREFIX = 'textstudio_preview_v1_';
const PREVIEW_CONCURRENCY = 3;

function getCachedPreview(styleId) {
    try {
        return localStorage.getItem(PREVIEW_CACHE_PREFIX + styleId);
    } catch {
        return null;
    }
}

function setCachedPreview(styleId, dataUrl) {
    try {
        localStorage.setItem(PREVIEW_CACHE_PREFIX + styleId, dataUrl);
    } catch {
        // ignore
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const styleGrid = document.getElementById('style-grid');
    const userTextInput = document.getElementById('user-text');
    const createBtn = document.getElementById('create-btn');
    const previewSection = document.getElementById('preview-section');
    const resultImg = document.getElementById('result-img');
    const loader = document.getElementById('loader');
    const downloadBtn = document.getElementById('download-btn');
    const copyBtn = document.getElementById('copy-btn');

    async function fetchStyles() {
        const resp = await fetch('/styles');
        const data = await resp.json();
        if (!data.success || !Array.isArray(data.styles)) {
            throw new Error(data.error || 'Failed to load styles');
        }
        return data.styles;
    }

    async function fetchPreview(styleId) {
        const cached = getCachedPreview(styleId);
        if (cached) return cached;

        const resp = await fetch(`/preview?styleId=${encodeURIComponent(styleId)}&text=${encodeURIComponent(PREVIEW_TEXT)}`);
        const data = await resp.json();
        if (data.success && data.dataUrl) {
            setCachedPreview(styleId, data.dataUrl);
            return data.dataUrl;
        }
        throw new Error(data.error || 'Preview generation failed');
    }

    function createStyleCard(style) {
        const card = document.createElement('div');
        card.className = 'style-card';
        card.dataset.id = style.id;
        card.innerHTML = `
            <div class="style-preview">
                <div class="style-preview-skeleton" aria-hidden="true"></div>
                <img class="style-preview-img hidden" alt="${style.name} preview" />
            </div>
            <span class="style-name">${style.name}</span>
        `;

        card.addEventListener('click', () => {
            document.querySelectorAll('.style-card').forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');
            selectedStyleId = style.id;
        });

        return card;
    }

    async function loadPreviewsWithLimit(cards) {
        let idx = 0;

        async function worker() {
            while (idx < cards.length) {
                const current = cards[idx++];
                const styleId = current.dataset.id;
                const img = current.querySelector('.style-preview-img');
                const skeleton = current.querySelector('.style-preview-skeleton');

                try {
                    const dataUrl = await fetchPreview(styleId);
                    img.src = dataUrl;
                    img.classList.remove('hidden');
                    skeleton.classList.add('hidden');
                } catch (e) {
                    console.warn(`Preview failed for styleId=${styleId}`, e);
                    skeleton.classList.add('style-preview-error');
                }
            }
        }

        const workers = Array.from({ length: PREVIEW_CONCURRENCY }, () => worker());
        await Promise.all(workers);
    }

    // Initialize style grid from backend curated styles
    (async () => {
        try {
            const styles = await fetchStyles();
            const cards = styles.map(style => {
                const card = createStyleCard(style);
                styleGrid.appendChild(card);
                return card;
            });
            await loadPreviewsWithLimit(cards);
        } catch (e) {
            console.error('Failed to initialize style grid:', e);
            styleGrid.innerHTML = '<div style="opacity:0.7">Failed to load styles.</div>';
        }
    })();

    // Create magic
    createBtn.addEventListener('click', async () => {
        const text = userTextInput.value.trim();
        
        if (!text) {
            alert('Please type something first!');
            return;
        }
        
        if (!selectedStyleId) {
            alert('Pick a style vibe!');
            return;
        }

        // Show preview section and loader
        previewSection.classList.remove('hidden');
        resultImg.classList.add('hidden');
        loader.classList.remove('hidden');
        createBtn.disabled = true;
        createBtn.innerText = 'Creating...';

        try {
            const response = await fetch('/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text, styleId: selectedStyleId })
            });

            const data = await response.json();

            if (data.success && data.dataUrl) {
                resultImg.src = data.dataUrl;
                resultImg.classList.remove('hidden');
                
                // Scroll to preview
                previewSection.scrollIntoView({ behavior: 'smooth' });
            } else {
                alert('Error: ' + (data.error || 'Failed to generate image'));
            }
        } catch (error) {
            console.error('Generation failed:', error);
            alert('Something went wrong. Check console.');
        } finally {
            loader.classList.add('hidden');
            createBtn.disabled = false;
            createBtn.innerText = 'Create Magic';
        }
    });

    // Download functionality
    downloadBtn.addEventListener('click', () => {
        const link = document.createElement('a');
        link.href = resultImg.src;
        link.download = `NameYourInk_${Date.now()}.png`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    });

    // Copy to clipboard
    copyBtn.addEventListener('click', async () => {
        try {
            const response = await fetch(resultImg.src);
            const blob = await response.blob();
            await navigator.clipboard.write([
                new ClipboardItem({ 'image/png': blob })
            ]);
            alert('Image copied to clipboard!');
        } catch (err) {
            console.error('Copy failed:', err);
            alert('Copy failed. Try downloading instead.');
        }
    });
});
