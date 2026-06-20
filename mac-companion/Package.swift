// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "RockyCompanion",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "RockyCompanion",
            path: "Sources/RockyCompanion"
        )
    ]
)
