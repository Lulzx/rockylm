import AppKit

/// Rocky Companion — a floating pixel Rocky that lives on your Dock line,
/// listens to your microphone, asks RockyLM (via relay/server.py), and speaks
/// back in Rocky's voice. Mac-only UI surface.
final class AppDelegate: NSObject, NSApplicationDelegate {
    var window: NSWindow!

    func applicationDidFinishLaunching(_ note: Notification) {
        let size: CGFloat = 130
        let screen = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1200, height: 800)
        let rect = NSRect(x: screen.minX + 60, y: screen.minY + 8, width: size, height: size + 40)

        window = NSWindow(contentRect: rect, styleMask: .borderless,
                          backing: .buffered, defer: false)
        window.isOpaque = false
        window.backgroundColor = .clear
        window.hasShadow = false
        window.level = .floating
        window.collectionBehavior = [.canJoinAllSpaces, .stationary, .fullScreenAuxiliary]
        window.ignoresMouseEvents = false

        let view = CompanionView(frame: NSRect(origin: .zero, size: rect.size))
        window.contentView = view
        window.makeKeyAndOrderFront(nil)
        window.makeFirstResponder(view)

        NSApp.setActivationPolicy(.accessory)   // no Dock icon, lives as overlay
        NSApp.activate(ignoringOtherApps: true)
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
