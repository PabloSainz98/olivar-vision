// swift-tools-version: 5.9

import PackageDescription

let package = Package(
    name: "OlivarLidarCapture",
    platforms: [
        .iOS("15.4"),
        .macOS(.v13),
    ],
    products: [
        .library(name: "OlivarLidarCapture", targets: ["OlivarLidarCapture"]),
    ],
    targets: [
        .target(name: "OlivarLidarCapture"),
        .testTarget(
            name: "OlivarLidarCaptureTests",
            dependencies: ["OlivarLidarCapture"]
        ),
    ]
)
