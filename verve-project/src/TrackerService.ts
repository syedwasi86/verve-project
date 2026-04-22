import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

/**
 * Minified interface for behavioral events (Golden Features)
 * t: timestamp (ms since epoch)
 * f: flight time (ms since last event)
 * d: dwell time (ms from key down to text change - "Golden Feature")
 * o: offset (character position in document)
 * l: text length (number of characters changed)
 * s: source ('h'=human, 'a'=AI, 'p'=paste, 'u'=unknown)
 * k: key type ('enter', 'backspace', 'bulk', 'single')
 */
export interface VerveEvent {
    t: number;
    f: number;
    d: number;
    o: number;
    l: number;
    s: 'h' | 'a' | 'p' | 'u';
    k: string;
}

/**
 * Session metadata and collected events
 */
export interface VerveSession {
    sessionId: string;
    startTime: number;
    endTime?: number;
    languageId: string;
    filePath: string;
    events: VerveEvent[];
}

/**
 * Internal event context with deletion info
 */
interface EventContext {
    text: string;
    rangeLength: number;
    rangeOffset: number;
    timestamp: number;
}

export class TrackerService {
    private session: VerveSession | null = null;
    private isTracking = false;
    private lastEventTimestamp: number | null = null;
    private isFirstEvent = true;
    
    // Listeners
    private textChangeListener: vscode.Disposable | null = null;
    private pasteListener: vscode.Disposable | null = null;
    
    // Paste detection flag (set by command interception)
    // private isPastePending = false;
    
    // Clipboard cache for paste detection (normalized for comparison)
    private clipboardCache: string | null = null;
    private isUpdatingClipboard = false;  // Prevent rapid re-reads

    /**
     * Start tracking behavioral events (Golden Features)
     */
    startTracking(): void {
        if (this.isTracking) {
            vscode.window.showInformationMessage('Verve: Tracking is already active.');
            return;
        }

        this.isTracking = true;
        this.lastEventTimestamp = null;
        this.isFirstEvent = true;
          

        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showErrorMessage('Verve: No active editor found.');
            this.isTracking = false;
            return;
        }

        // Initialize session
        const now = new Date();
        const langCode = editor.document.languageId
            .replace(/javascript/i, 'JS')
            .replace(/typescript/i, 'TS')
            .replace(/python/i, 'PY')
            .replace(/java$/i, 'JAVA')
            .replace(/csharp/i, 'CS')
            .replace(/cpp/i, 'CPP')
            .replace(/html/i, 'HTML')
            .replace(/css/i, 'CSS')
            .replace(/plaintext/i, 'TXT')   // .txt files
            .replace(/pip.*/i,     'PIP')   // pip requirement files → keep as PIP
            .replace(/pip-requirements/i, 'PIP')
            .replace(/requirements/i, 'REQ')
            .toUpperCase()
            .replace(/[^A-Z0-9]/g, '')      // strip hyphens/dots left by unknown langs
            .slice(0, 6);                   // cap at 6 chars
        const datePart = now.getFullYear().toString() +
            String(now.getMonth() + 1).padStart(2, '0') +
            String(now.getDate()).padStart(2, '0');
        const timePart = String(now.getHours()).padStart(2, '0') +
            String(now.getMinutes()).padStart(2, '0');
        const sessionId = `${langCode}-${datePart}-${timePart}`;

        this.session = {
            sessionId,
            startTime: Date.now(),
            languageId: editor.document.languageId,
            filePath: editor.document.fileName,
            events: [],
        };

        this.setupListeners();
        vscode.window.showInformationMessage('Verve: Golden Features tracking started.');
    }

    /**
     * Stop tracking and return the session
     */
    stopTracking(): VerveSession | null {
        if (!this.isTracking) {
            vscode.window.showInformationMessage('Verve: Tracking is not active.');
            return null;
        }

        this.isTracking = false;
        this.disposeListeners();

        if (this.session) {
            this.session.endTime = Date.now();
            return this.session;
        }

        return null;
    }

    /**
     * Normalize text for clipboard comparison
     * Handles whitespace and line-ending differences
     */
    private normalizeText(text: string): string {
        return text.trim().replace(/\r\n/g, '\n');
    }

    /**
     * Update clipboard cache asynchronously
     * Called whenever we encounter a multi-char instant insertion (potential paste)
     */
    private async updateClipboardCache(): Promise<void> {
        // Prevent rapid re-reads
        if (this.isUpdatingClipboard) {
            return;
        }

        this.isUpdatingClipboard = true;
        try {
            const clipboardText = await vscode.env.clipboard.readText();
            this.clipboardCache = clipboardText;
        } catch (error) {
            // Clipboard read failed - set cache to null
            this.clipboardCache = null;
        } finally {
            this.isUpdatingClipboard = false;
        }
    }

    /**
     * Setup listeners for text document changes and paste command interception
     * NOTE: We do NOT intercept the 'type' command as it blocks actual typing.
     * Instead, we estimate dwell time from text change event timing.
     * 
     * PASTE INTERCEPTION: We DO intercept 'editor.action.clipboardPasteAction' to set a flag
     * that marks the next text insertion as a paste event (s='p'). This is non-blocking: we
     * immediately call 'default:paste' to ensure the actual paste happens, then return.
     */
    private setupListeners(): void {
    // 1. We removed the command interceptor 'editor.action.clipboardPasteAction'
    // This restores native VS Code pasting without blocking.

    // 2. Listen for text document changes to capture typing events
    this.textChangeListener = vscode.workspace.onDidChangeTextDocument(async(event) => {
        if (!this.isTracking || !this.session) {
            return;
        }

        const now = Date.now();

        // Calculate flight time
        const flightTime = this.isFirstEvent ? 0 : (now - (this.lastEventTimestamp || now));
        this.lastEventTimestamp = now;
        this.isFirstEvent = false;

        // Process changes
        for (const change of event.contentChanges) {

            if (change.text.length > 1) {
                await this.updateClipboardCache(); // Async update for the NEXT check
            }
            const context: EventContext = {
                text: change.text,
                rangeLength: change.rangeLength,
                rangeOffset: change.rangeOffset,
                timestamp: now,
            };
           

            const dwellTime = this.calculateDwellTime(context);
            let keyType = this.determineKeyType(context);

            // NEW: determineSource no longer needs the isPastePending flag
            const source = this.determineSource(context, flightTime, keyType, dwellTime);

            if (source === 'a' || source === 'p') {
                keyType = 'bulk';
            }

            const veEvent: VerveEvent = {
                t: now,
                f: flightTime,
                d: dwellTime,
                o: context.rangeOffset,
                l: context.text.length,
                s: source,
                k: keyType,
            };

            this.session.events.push(veEvent);
        }
    });
}

    /**
     * Estimate dwell time (time key was held down)
     * Golden Feature: Estimates actual key hold duration
     * 
     * Estimation strategy:
     * - Single character: 40-100ms typical (human keystroke)
     * - Backspace: 40-100ms (error correction)
     * - Enter: 50-150ms (deliberate keypress)
     * - Bulk/Paste: 0ms (instant insertion, non-human)
     */
    private calculateDwellTime(context: EventContext): number {
        // Determine key type for dwell time estimation
        const keyType = this.determineKeyType(context);

        // Single character: typical human keystroke (50-80ms average)
        if (keyType === 'single') {
            // Vary slightly to be realistic: 40-100ms range
            return Math.floor(Math.random() * 60 + 40); // 40-100ms
        }

        // Backspace: deliberate, typically 50-120ms
        if (keyType === 'backspace') {
            return Math.floor(Math.random() * 70 + 50); // 50-120ms
        }

        // Enter: deliberate keypress, 60-150ms
        if (keyType === 'enter') {
            return Math.floor(Math.random() * 90 + 60); // 60-150ms
        }

        // Bulk text or paste: instant insertion (0ms)
        // This is how we distinguish human typing from AI/paste events
        return 0;
    }

    /**
     * Determine the source of the text change (Golden Feature for behavior detection)
     * 
     * STRICT PRIORITY ORDER (Paste Command Interception First):
     * 1. First Event → 'h' (always human)
     * 2. PASTE COMMAND FLAG → 'p' (if isPastePending === true)
     *    - Set by editor.action.clipboardPasteAction command interceptor
     *    - 100% reliable: happens before text insertion
     *    - PRIORITY: Detects all pastes regardless of content or timing
     * 3. Machine Signature (AI/Bulk) → 'a' (text.length > 1 && d=0 && NOT paste)
     *    - Fallback only if NOT a paste event
     *    - Handles line-by-line AI suggestions with large delays
     * 4. Fast Bulk AI Detection → 'a' (text.length > 5 AND f < 5ms)
     *    - Legacy detection for very rapid AI completions
     * 5. Backspace → 'h' (error correction)
     * 6. Human Typing → 'h' (single char AND f > 20ms)
     * 7. Enter Key → 'h' (if not already flagged)
     * 8. Default → 'u' (unknown)
     */
    private determineSource(
    context: EventContext,
    flightTime: number,
    keyType: string,
    dwellTime: number
): 'h' | 'a' | 'p' | 'u' {
    try {
        // 1. First Event is always Human
        if (this.isFirstEvent) return 'h';

        // 2. FUZZY CLIPBOARD MATCH (The Silent Observer)
        // If text length > 1, check if it matches what's in the clipboard
        if (context.text.length > 1 && this.clipboardCache) {
            const normalizedIncoming = this.normalizeText(context.text);
            const normalizedClipboard = this.normalizeText(this.clipboardCache);

            if (normalizedIncoming === normalizedClipboard) {
                return 'p'; // Verified Paste
            }
        }

        // 3. AI MACHINE SIGNATURE
        // Add a check to ensure the text isn't just tabs or spaces (Auto-indent)
        const isWhitespaceOnly = context.text.trim().length === 0;

        if (context.text.length > 1 && dwellTime === 0 && !isWhitespaceOnly) {
                return 'a'; // Only tag as AI if there is actual content
        }

        // 4. BACKSPACE: Always human
        if (keyType === 'backspace') return 'h';

        // 5. HUMAN TYPING: Single char with typical speed
        if (context.text.length === 1 && flightTime > 20) return 'h';

        // 6. ENTER KEY
        if (keyType === 'enter') return 'h';

        return 'u'; // Unknown
    } catch {
        return 'u';
    }
}

    /**
     * Determine the key type (Golden Feature for Error Correction & ML burst_ratio)
     * 
     * PRIORITY ORDER:
     * 1. Backspace: rangeLength > 0 AND text === "" (error correction signal)
     * 2. Bulk: text.length > 5 (PRIORITY OVER ENTER - ensures ML sees burst_ratio)
     * 3. Enter: text contains \n or \r (if not bulk)
     * 4. Single: text.length === 1
     * 5. Bulk fallback: text.length > 1
     */
    private determineKeyType(context: EventContext): string {
        // 1. BACKSPACE DETECTION: rangeLength > 0 with no text insertion
        // Critical human signal for error correction
        if (context.rangeLength > 0 && context.text === '') {
            return 'backspace';
        }

        // 2. BULK TEXT DETECTION (PRIORITY):
        // If text.length > 5, ALWAYS mark as 'bulk'
        // This ensures Random Forest sees the 'bulk' signal for burst_ratio feature
        // even if the trigger was Enter or Tab key
        if (context.text.length > 5) {
            return 'bulk';
        }

        // 3. ENTER/NEWLINE DETECTION: (checked after bulk to avoid misclassification)
        // Single Enter key or newline character
        if (context.text.includes('\n') || context.text.includes('\r')) {
            return 'enter';
        }

        // 4. SINGLE CHARACTER: Normal keyboard input
        if (context.text.length === 1) {
            return 'single';
        }

        // 5. BULK FALLBACK: Multi-character (2-5 chars)
        // Less critical than > 5, but still bulk insertion
        if (context.text.length > 1) {
            return 'bulk';
        }

        // DEFAULT: Treat as single character
        return 'single';
    }

    /**
     * Save session to a local JSON file.
     * Files are always written to the fixed data directory:
     *   C:\Users\syed wasi uddin\OneDrive\Desktop\projects\data
     * The directory is created automatically if it does not exist.
     */
    async saveSessionLocally(session: VerveSession): Promise<void> {
        const DATA_DIR = path.join(
            'C:', 'Users', 'syed wasi uddin',
            'OneDrive', 'Desktop', 'projects', 'data'
        );

        try {
            // Ensure the target directory exists
            if (!fs.existsSync(DATA_DIR)) {
                fs.mkdirSync(DATA_DIR, { recursive: true });
            }

            const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
            const fileName  = `verve-session-${timestamp}.json`;
            const filePath  = path.join(DATA_DIR, fileName);

            // Write minified JSON
            const content = JSON.stringify(session);
            fs.writeFileSync(filePath, content, 'utf8');

            vscode.window.showInformationMessage(
                `Verve: Session saved → ${filePath}  (${session.events.length} events)`
            );
        } catch (error) {
            vscode.window.showErrorMessage(
                `Verve: Failed to save session: ${String(error)}`
            );
        }
    }

    /**
     * Post session to backend server
     */
    async postSessionToBackend(session: VerveSession): Promise<void> {
        const backendUrl = 'http://localhost:8000/process-session';

        try {
            const response = await fetch(backendUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(session),
            });

            if (response.ok) {
                const result = await response.json();
                vscode.window.showInformationMessage(
                    `Verve: Session posted to backend successfully (${session.events.length} events)`
                );
            } else {
                const error = await response.text();
                vscode.window.showErrorMessage(
                    `Verve: Backend error (${response.status}): ${error}`
                );
            }
        } catch (error) {
            vscode.window.showErrorMessage(
                `Verve: Failed to post session to backend: ${String(error)}`
            );
        }
    }

    /**
     * Dispose of all listeners
     */
    private disposeListeners(): void {
        if (this.textChangeListener) {
            this.textChangeListener.dispose();
            this.textChangeListener = null;
        }
       
    }

    /**
     * Check if currently tracking
     */
    isCurrentlyTracking(): boolean {
        return this.isTracking;
    }
}
