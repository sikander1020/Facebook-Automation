let isProcessing = false;
let currentJobId = null;

// Inject a floating status box
const statusBox = document.createElement('div');
statusBox.style.cssText = 'position:fixed; top:20px; right:20px; background:rgba(0,0,0,0.8); color:#00ff00; padding:15px; z-index:999999; border-radius:8px; font-family:monospace; pointer-events:none; min-width:250px;';
statusBox.innerHTML = '<b>Google Vids Automator</b><br>Status: Idle (Polling...)';
document.body.appendChild(statusBox);

function updateStatus(msg, isError=false) {
    statusBox.style.color = isError ? '#ff4444' : '#00ff00';
    statusBox.innerHTML = `<b>Google Vids Automator</b><br>Status: ${msg}`;
    console.log(`[Automator] ${msg}`);
}

async function pollJobs() {
    if (isProcessing) return;

    try {
        const response = await fetch("http://127.0.0.1:5005/api/extension/job");
        const data = await response.json();
        
        if (data && data.prompt && data.job_id) {
            updateStatus(`Job Received!`);
            isProcessing = true;
            currentJobId = data.job_id;
            
            await processJob(data.prompt);
        }
    } catch (e) {
        // Silent fail
    }
}

async function processJob(prompt) {
    try {
        updateStatus('Step 1: Finding prompt box...');
        
        // Find input box (Google uses contenteditable heavily)
        let inputEl = null;
        
        // Strategy A: Find by placeholder or aria-label containing 'prompt', 'describe', 'help me'
        const allElements = document.querySelectorAll('*');
        for (let el of allElements) {
            const aria = (el.getAttribute('aria-label') || '').toLowerCase();
            const placeholder = (el.getAttribute('placeholder') || '').toLowerCase();
            if (el.isContentEditable || el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
                if (aria.includes('prompt') || aria.includes('describe') || aria.includes('help me') || placeholder.includes('describe')) {
                    inputEl = el;
                    break;
                }
            }
        }
        
        // Strategy B: Fallback to any contenteditable that isn't the main document canvas
        if (!inputEl) {
            const editables = document.querySelectorAll('[contenteditable="true"]');
            for (let el of editables) {
                // Usually the prompt box is smaller or inside a specific panel
                if (el.clientHeight < 400) {
                    inputEl = el;
                    break;
                }
            }
        }

        if (!inputEl) {
            throw new Error("Could not find the prompt input box. Please open the 'Help me create a video' panel first!");
        }
        
        // Highlight it
        inputEl.style.border = "4px solid red";
        updateStatus(`Found input box. Typing prompt...`);
        
        // Focus and type
        inputEl.focus();
        inputEl.click();
        
        if (inputEl.tagName === 'TEXTAREA' || inputEl.tagName === 'INPUT') {
            inputEl.value = prompt;
            inputEl.dispatchEvent(new Event('input', { bubbles: true }));
        } else {
            // For contenteditable, sometimes setting innerText works, or we might need execCommand
            inputEl.innerText = prompt;
            inputEl.dispatchEvent(new Event('input', { bubbles: true }));
        }
        
        await new Promise(r => setTimeout(r, 1500));
        
        updateStatus('Step 2: Finding Generate button...');
        // Find the "Generate" or "Create" button
        const buttons = Array.from(document.querySelectorAll('button, div[role="button"], span[role="button"]'));
        const generateBtn = buttons.find(b => {
            const text = (b.innerText || b.getAttribute('aria-label') || "").toLowerCase();
            // Need to make sure it's the right button, not something else
            return text.includes('generate') || text.includes('create');
        });
        
        if (generateBtn) {
            generateBtn.style.border = "4px solid red";
            updateStatus(`Clicking generate button...`);
            generateBtn.click();
        } else {
            throw new Error("Could not find Generate/Create button. Press it manually!");
        }
        
        updateStatus('Waiting 10s for video to process...');
        await new Promise(r => setTimeout(r, 10000));
        
        await finishJob(currentJobId, true, "Video triggered! (Download logic pending)");
        updateStatus('Job complete. Awaiting next...', false);
        
    } catch (e) {
        updateStatus(`Error: ${e.message}`, true);
        await finishJob(currentJobId, false, e.message);
        setTimeout(() => updateStatus('Idle (Polling...)'), 5000);
    }
}

async function finishJob(jobId, success, message) {
    try {
        await fetch("http://127.0.0.1:5005/api/extension/complete", {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ job_id: jobId, success, message })
        });
    } catch(e) {
        console.error("Failed to report job completion", e);
    }
    
    isProcessing = false;
    currentJobId = null;
}

// Start polling
setInterval(pollJobs, 3000);
