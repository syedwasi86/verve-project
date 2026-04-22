const vscode = acquireVsCodeApi();
let trackingActive = false;

const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const statusDiv = document.getElementById('status');
const sessionInfoDiv = document.getElementById('sessionInfo');

startBtn.addEventListener('click', () => {
    vscode.postMessage({
        command: 'startTracking'
    });
    trackingActive = true;
    updateStatus();
});

stopBtn.addEventListener('click', () => {
    vscode.postMessage({
        command: 'stopTracking'
    });
});

// Listen for messages from the extension
window.addEventListener('message', (event) => {
    const message = event.data;

    switch (message.command) {
        case 'statusUpdate':
            trackingActive = message.isTracking;
            updateStatus();
            break;
    }
});

function updateStatus() {
    statusDiv.textContent = trackingActive 
        ? 'Status: Tracking Active ⏱️' 
        : 'Status: Inactive';
    statusDiv.className = trackingActive ? 'status active' : 'status';
    
    startBtn.disabled = trackingActive;
    stopBtn.disabled = !trackingActive;
    
    if (trackingActive) {
        sessionInfoDiv.textContent = 'Session in progress...';
    } else {
        sessionInfoDiv.textContent = '';
    }
}