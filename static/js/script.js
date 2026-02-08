const STYLES = [
    { id: 261, name: 'Golden 3D' },
    { id: 3475, name: 'Green Announcement' },
    { id: 4500, name: 'Cyber Neon' },
    { id: 1234, name: 'Retro Wave' },
    { id: 888, name: 'Pink Barbie' },
    { id: 567, name: 'Street Graffiti' },
    { id: 99, name: 'Liquid Silver' },
    { id: 202, name: 'Comic Boom' }
];

let selectedStyleId = null;

document.addEventListener('DOMContentLoaded', () => {
    const styleGrid = document.getElementById('style-grid');
    const userTextInput = document.getElementById('user-text');
    const createBtn = document.getElementById('create-btn');
    const previewSection = document.getElementById('preview-section');
    const resultImg = document.getElementById('result-img');
    const loader = document.getElementById('loader');
    const downloadBtn = document.getElementById('download-btn');
    const copyBtn = document.getElementById('copy-btn');

    // Initialize style grid
    STYLES.forEach(style => {
        const card = document.createElement('div');
        card.className = 'style-card';
        card.dataset.id = style.id;
        card.innerHTML = `
            <span class="style-name">${style.name}</span>
            <span class="style-preview-text">ABC</span>
        `;
        
        card.addEventListener('click', () => {
            document.querySelectorAll('.style-card').forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');
            selectedStyleId = style.id;
        });
        
        styleGrid.appendChild(card);
    });

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
