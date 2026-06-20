import AppKit

/// The floating pixel-Rocky view: animates sprite frames, walks the Dock line,
/// toggles recording on click/Space/Tab/Enter, and shows speech bubbles.
final class CompanionView: NSView {
    private let recorder = AudioRecorder()
    private let player = AudioPlayer()
    private let relay = RelayClient()

    private var frames: [NSImage] = []          // animation frames (may be empty -> fallback)
    private var frameIndex = 0
    private var animTimer: Timer?
    private var walkTimer: Timer?

    private var isRecording = false
    private var isBusy = false
    private var bobPhase: CGFloat = 0

    private let transcriptBubble = BubbleLabel()
    private let replyBubble = BubbleLabel()

    override var acceptsFirstResponder: Bool { true }
    override var isFlipped: Bool { true }

    override init(frame: NSRect) {
        super.init(frame: frame)
        wantsLayer = true
        loadFrames()
        addSubview(transcriptBubble)
        addSubview(replyBubble)
        startAnimating()
        startWalking()
        relay.health { ok in
            self.showBubbles(transcript: "", reply: ok ? "rocky here. ready work." : "no relay. start server.")
        }
    }

    required init?(coder: NSCoder) { fatalError() }

    // ── sprites ──────────────────────────────────────────────────────────────
    private func loadFrames() {
        let dir = ProcessInfo.processInfo.environment["ROCKY_SPRITES"]
            ?? (NSHomeDirectory() + "/.rockycompanion/sprites")
        for name in ["jazz1", "jazz2", "jazz3", "jazz2"] {
            if let img = NSImage(contentsOfFile: "\(dir)/\(name).png") {
                frames.append(img)
            }
        }
        // also try stand.png as a single idle frame
        if frames.isEmpty, let img = NSImage(contentsOfFile: "\(dir)/stand.png") {
            frames.append(img)
        }
    }

    private func startAnimating() {
        animTimer = Timer.scheduledTimer(withTimeInterval: 0.22, repeats: true) { [weak self] _ in
            guard let self = self else { return }
            self.bobPhase += 0.22
            if !self.frames.isEmpty { self.frameIndex = (self.frameIndex + 1) % self.frames.count }
            self.needsDisplay = true
        }
    }

    private func startWalking() {
        // drift horizontally along the Dock line, turn around at screen edges
        var dx: CGFloat = 1.4
        walkTimer = Timer.scheduledTimer(withTimeInterval: 0.03, repeats: true) { [weak self] _ in
            guard let self = self, let win = self.window,
                  let screen = win.screen, !self.isRecording, !self.isBusy else { return }
            var f = win.frame
            f.origin.x += dx
            let vis = screen.visibleFrame
            if f.maxX > vis.maxX { dx = -abs(dx) }
            if f.minX < vis.minX { dx = abs(dx) }
            win.setFrameOrigin(f.origin)
        }
    }

    // ── drawing ──────────────────────────────────────────────────────────────
    override func draw(_ dirty: NSRect) {
        let bob = sin(bobPhase * 3) * 5
        let box = NSRect(x: 8, y: 30 + bob, width: bounds.width - 16, height: bounds.width - 16)
        if !frames.isEmpty {
            frames[min(frameIndex, frames.count - 1)].draw(in: box)
        } else {
            drawFallbackRocky(in: box)
        }
        if isRecording {  // red "listening" dot
            NSColor.systemRed.setFill()
            NSBezierPath(ovalIn: NSRect(x: bounds.midX - 5, y: 20, width: 10, height: 10)).fill()
        }
    }

    /// Code-drawn Rocky if no sprite PNGs are present.
    private func drawFallbackRocky(in r: NSRect) {
        let body = NSBezierPath(roundedRect: r.insetBy(dx: r.width*0.1, dy: r.height*0.05),
                                xRadius: r.width*0.28, yRadius: r.height*0.28)
        NSColor(calibratedRed: 0.78, green: 0.42, blue: 0.16, alpha: 1).setFill()
        body.fill()
        NSColor(white: 0, alpha: 0.18).setStroke(); body.stroke()
        NSColor(white: 0.05, alpha: 1).setFill()
        for ex in [r.midX - r.width*0.16, r.midX + r.width*0.16] {
            NSBezierPath(ovalIn: NSRect(x: ex - 4, y: r.midY - 2, width: 8, height: 8)).fill()
        }
    }

    // ── interaction ──────────────────────────────────────────────────────────
    override func mouseDown(with event: NSEvent) { toggle() }
    override func keyDown(with event: NSEvent) {
        // space (49), tab (48), return (36)
        if [49, 48, 36].contains(Int(event.keyCode)) { toggle() } else { super.keyDown(with: event) }
    }

    private func toggle() {
        if isBusy { return }
        if isRecording { stopAndSend() } else { startRecording() }
    }

    private func startRecording() {
        recorder.requestPermission { ok in
            guard ok else {
                self.showBubbles(transcript: "", reply: "rocky need microphone. allow in settings.")
                return
            }
            self.isRecording = true
            self.recorder.start()
            self.showBubbles(transcript: "", reply: "rocky listen...")
            self.needsDisplay = true
        }
    }

    private func stopAndSend() {
        isRecording = false
        isBusy = true
        needsDisplay = true
        guard let wav = recorder.stop() else { isBusy = false; return }
        showBubbles(transcript: "", reply: "rocky think...")
        relay.sendAudio(wav) { result in
            self.isBusy = false
            guard let r = result else {
                self.showBubbles(transcript: "", reply: "no answer. relay running. question?")
                return
            }
            self.showBubbles(transcript: r.transcript, reply: r.reply)
            if !r.audio.isEmpty { self.player.play(r.audio) }
        }
    }

    // ── bubbles ──────────────────────────────────────────────────────────────
    private func showBubbles(transcript: String, reply: String) {
        layoutBubbles(transcript: transcript, reply: reply)
        NSObject.cancelPreviousPerformRequests(withTarget: self)
        if !isRecording && !isBusy {
            perform(#selector(clearBubbles), with: nil, afterDelay: 6)
        }
    }

    @objc private func clearBubbles() {
        transcriptBubble.isHidden = true
        replyBubble.isHidden = true
    }

    private func layoutBubbles(transcript: String, reply: String) {
        transcriptBubble.set(text: transcript, kind: .user)
        replyBubble.set(text: reply, kind: .rocky)
        let w = bounds.width
        replyBubble.sizeToFitWidth(w + 80)
        transcriptBubble.sizeToFitWidth(w + 80)
        replyBubble.frame.origin = NSPoint(x: -40, y: 2)
        transcriptBubble.frame.origin = NSPoint(x: -40, y: replyBubble.frame.maxY + 4)
        transcriptBubble.isHidden = transcript.isEmpty
        replyBubble.isHidden = reply.isEmpty
    }
}

/// A rounded speech bubble label.
final class BubbleLabel: NSView {
    enum Kind { case user, rocky }
    private let label = NSTextField(labelWithString: "")
    private var kind: Kind = .rocky

    override init(frame: NSRect) {
        super.init(frame: frame)
        wantsLayer = true
        layer?.cornerRadius = 9
        label.font = .systemFont(ofSize: 11)
        label.lineBreakMode = .byWordWrapping
        label.maximumNumberOfLines = 4
        label.isEditable = false
        label.drawsBackground = false
        addSubview(label)
    }
    required init?(coder: NSCoder) { fatalError() }

    func set(text: String, kind: Kind) {
        self.kind = kind
        label.stringValue = text
        label.textColor = .white
        layer?.backgroundColor = (kind == .user
            ? NSColor.systemBlue : NSColor(calibratedRed: 0.05, green: 0.13, blue: 0.22, alpha: 0.95)).cgColor
    }

    func sizeToFitWidth(_ maxW: CGFloat) {
        let inset: CGFloat = 8
        label.preferredMaxLayoutWidth = maxW - 2 * inset
        let s = label.sizeThatFits(NSSize(width: maxW - 2 * inset, height: 200))
        label.frame = NSRect(x: inset, y: inset, width: s.width, height: s.height)
        frame.size = NSSize(width: s.width + 2 * inset, height: s.height + 2 * inset)
    }
}
