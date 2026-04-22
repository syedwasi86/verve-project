import * as vscode from 'vscode';
import { TrackerService, VerveSession } from './TrackerService';
import { Buffer } from 'buffer';

let trackerService: TrackerService;

class VerveTrackingViewProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'verveTrackingView';
    private webviewView?: vscode.WebviewView;

    constructor(private readonly context: vscode.ExtensionContext) {}

    resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        token: vscode.CancellationToken
    ) {
        this.webviewView = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this.context.extensionUri]
        };

        webviewView.webview.html = this.getHtmlContent(webviewView.webview);

        webviewView.webview.onDidReceiveMessage(
            (message) => this.handleWebviewMessage(message),
            undefined,
            this.context.subscriptions
        );
    }

    private async handleWebviewMessage(message: any) {
        switch (message.command) {
            case 'startTracking':
                trackerService.startTracking();
                this.updateWebviewStatus();
                break;
            case 'stopTracking':
                await this.handleStopTracking();
                this.updateWebviewStatus();
                break;
        }
    }

    private async handleStopTracking() {
        const session = trackerService.stopTracking();
        if (!session) {
            return;
        }

        if (session.events.length === 0) {
            vscode.window.showInformationMessage('Verve: No behavioral data was collected.');
            return;
        }

        // Show options for saving and/or posting
        const option = await vscode.window.showQuickPick(
            [
                { label: 'Save Locally', description: 'Save to a JSON file' },
                { label: 'Post to Backend', description: 'Send to http://localhost:8000' },
                { label: 'Both', description: 'Save and post' },
                { label: 'Cancel', description: 'Do nothing' },
            ],
            { placeHolder: 'What would you like to do with the session data?' }
        );

        if (!option || option.label === 'Cancel') {
            return;
        }

        if (option.label === 'Save Locally' || option.label === 'Both') {
            await trackerService.saveSessionLocally(session);
        }

        if (option.label === 'Post to Backend' || option.label === 'Both') {
            await trackerService.postSessionToBackend(session);
        }
    }

    private updateWebviewStatus() {
        const isTracking = trackerService.isCurrentlyTracking();
        this.webviewView?.webview.postMessage({
            command: 'statusUpdate',
            isTracking,
        });
    }


    private getHtmlContent(webview: vscode.Webview): string {
        const scriptUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this.context.extensionUri, 'resources', 'webview.js')
        );
        const styleUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this.context.extensionUri, 'resources', 'webview.css')
        );

        return `<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="${styleUri}">
    <title>Verve Typing Dynamics Tracker</title>
</head>
<body>
    <div class="container">
        <h2>Typing Dynamics Tracker</h2>
        <div class="status" id="status">Status: Inactive</div>
        <div class="info" id="info">
            <p id="sessionInfo"></p>
        </div>
        <div class="button-group">
            <button id="startBtn" class="btn btn-primary">Start Tracking</button>
            <button id="stopBtn" class="btn btn-secondary">Stop Tracking</button>
        </div>
    </div>
    <script src="${scriptUri}"></script>
</body>
</html>`;
    }
}

export function activate(context: vscode.ExtensionContext) {
    // Initialize the tracker service
    trackerService = new TrackerService();

    const provider = new VerveTrackingViewProvider(context);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(VerveTrackingViewProvider.viewType, provider)
    );

    // Register command: Start Tracking
    const startTrackingCommand = vscode.commands.registerCommand('verve.startTracking', () => {
        trackerService.startTracking();
    });

    // Register command: Stop Tracking (with dual-output)
    const stopTrackingCommand = vscode.commands.registerCommand(
        'verve.stopTracking',
        async () => {
            const session = trackerService.stopTracking();
            if (!session) {
                return;
            }

            if (session.events.length === 0) {
                vscode.window.showInformationMessage('Verve: No behavioral data was collected.');
                return;
            }

            // Show options for dual-output
            const option = await vscode.window.showQuickPick(
                [
                    { label: 'Save Locally', description: 'Save to a JSON file' },
                    { label: 'Post to Backend', description: 'Send to http://localhost:8000' },
                    { label: 'Both', description: 'Save and post' },
                    { label: 'Cancel', description: 'Do nothing' },
                ],
                { placeHolder: 'What would you like to do with the session data?' }
            );

            if (!option || option.label === 'Cancel') {
                return;
            }

            if (option.label === 'Save Locally' || option.label === 'Both') {
                await trackerService.saveSessionLocally(session);
            }

            if (option.label === 'Post to Backend' || option.label === 'Both') {
                await trackerService.postSessionToBackend(session);
            }
        }
    );

    // Register command: End Tracking (convenience command)
    const endTrackingCommand = vscode.commands.registerCommand(
        'verve.endTracking',
        async () => {
            const session = trackerService.stopTracking();
            if (!session) {
                return;
            }

            if (session.events.length === 0) {
                vscode.window.showInformationMessage('Verve: No behavioral data was collected.');
                return;
            }

            // Execute both functions for dual-output
            await Promise.all([
                trackerService.saveSessionLocally(session),
                trackerService.postSessionToBackend(session),
            ]);
        }
    );

    context.subscriptions.push(startTrackingCommand, stopTrackingCommand, endTrackingCommand);
}

export function deactivate() {
    // Cleanup on extension deactivation
    trackerService?.stopTracking();
}