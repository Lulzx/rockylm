import AVFoundation

/// Records the microphone to a temporary 16-bit PCM WAV.
final class AudioRecorder {
    private var recorder: AVAudioRecorder?
    private(set) var url: URL?

    func requestPermission(_ done: @escaping (Bool) -> Void) {
        switch AVCaptureDevice.authorizationStatus(for: .audio) {
        case .authorized: done(true)
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .audio) { ok in
                DispatchQueue.main.async { done(ok) }
            }
        default: done(false)
        }
    }

    func start() {
        let tmp = FileManager.default.temporaryDirectory
            .appendingPathComponent("rocky_in_\(UUID().uuidString).wav")
        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatLinearPCM),
            AVSampleRateKey: 16000,
            AVNumberOfChannelsKey: 1,
            AVLinearPCMBitDepthKey: 16,
            AVLinearPCMIsFloatKey: false,
            AVLinearPCMIsBigEndianKey: false,
        ]
        do {
            recorder = try AVAudioRecorder(url: tmp, settings: settings)
            recorder?.record()
            url = tmp
        } catch {
            NSLog("rocky: record start failed: \(error)")
        }
    }

    /// Stops and returns the recorded WAV URL.
    func stop() -> URL? {
        recorder?.stop()
        recorder = nil
        return url
    }
}

/// Plays Rocky's returned WAV.
final class AudioPlayer {
    private var player: AVAudioPlayer?

    func play(_ data: Data) {
        do {
            player = try AVAudioPlayer(data: data)
            player?.play()
        } catch {
            NSLog("rocky: playback failed: \(error)")
        }
    }
}
