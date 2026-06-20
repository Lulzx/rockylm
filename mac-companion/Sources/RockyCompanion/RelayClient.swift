import Foundation

/// Talks to the Rocky relay (relay/server.py): POSTs a WAV, gets back Rocky's
/// voice WAV plus the transcript / reply text in response headers.
struct RelayResult {
    let transcript: String
    let reply: String
    let audio: Data
}

final class RelayClient {
    let baseURL: URL

    init() {
        let env = ProcessInfo.processInfo.environment["ROCKY_RELAY"] ?? "http://127.0.0.1:8765"
        self.baseURL = URL(string: env)!
    }

    func health(_ done: @escaping (Bool) -> Void) {
        var req = URLRequest(url: baseURL.appendingPathComponent("health"))
        req.timeoutInterval = 3
        URLSession.shared.dataTask(with: req) { data, _, _ in
            DispatchQueue.main.async { done(data != nil) }
        }.resume()
    }

    /// Send a recorded WAV to /audio and deliver Rocky's spoken reply.
    func sendAudio(_ wavURL: URL, _ done: @escaping (RelayResult?) -> Void) {
        guard let body = try? Data(contentsOf: wavURL) else { done(nil); return }
        var req = URLRequest(url: baseURL.appendingPathComponent("audio"))
        req.httpMethod = "POST"
        req.setValue("audio/wav", forHTTPHeaderField: "Content-Type")
        req.timeoutInterval = 60
        URLSession.shared.uploadTask(with: req, from: body) { data, resp, _ in
            let result = Self.parse(data, resp)
            DispatchQueue.main.async { done(result) }
        }.resume()
    }

    private static func parse(_ data: Data?, _ resp: URLResponse?) -> RelayResult? {
        guard let http = resp as? HTTPURLResponse, let data = data else { return nil }
        func header(_ k: String) -> String {
            let v = (http.value(forHTTPHeaderField: k)) ?? ""
            return v.removingPercentEncoding ?? v
        }
        return RelayResult(transcript: header("X-Transcript"),
                           reply: header("X-Reply"),
                           audio: data)
    }
}
