import Foundation

#if os(iOS) && canImport(ARKit) && canImport(AVFoundation) && canImport(UIKit)
import ARKit
import AVFoundation
import Darwin
import UIKit
#endif

public enum SystemLidarCapabilityDetector {
    public static func detect() -> LidarCapabilityReport {
        #if os(iOS) && canImport(ARKit) && canImport(AVFoundation)
        let sceneDepth = ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth)
        let smoothedDepth = ARWorldTrackingConfiguration.supportsFrameSemantics(.smoothedSceneDepth)
        let mesh = ARWorldTrackingConfiguration.supportsSceneReconstruction(.mesh)
        let lidarCamera = AVCaptureDevice.default(
            .builtInLiDARDepthCamera,
            for: .video,
            position: .back
        ) != nil
        let supported = sceneDepth && lidarCamera
        return LidarCapabilityReport(
            status: supported ? .supported : .unsupported,
            sceneDepth: sceneDepth,
            smoothedSceneDepth: smoothedDepth,
            sceneMesh: mesh,
            lidarDepthCamera: lidarCamera,
            reason: supported ? nil : "This device does not expose ARKit scene depth and a LiDAR depth camera."
        )
        #else
        return LidarCapabilityReport(
            status: .unsupported,
            sceneDepth: false,
            smoothedSceneDepth: false,
            sceneMesh: false,
            lidarDepthCamera: false,
            reason: "ARKit LiDAR capture is unavailable on this platform."
        )
        #endif
    }
}

public enum SystemLidarDeviceDescriptor {
    public static func current() -> LidarDeviceDescriptor {
        #if os(iOS) && canImport(UIKit)
        var systemInfo = utsname()
        uname(&systemInfo)
        let identifier = withUnsafePointer(to: &systemInfo.machine) {
            $0.withMemoryRebound(to: CChar.self, capacity: 1) {
                String(cString: $0)
            }
        }
        return LidarDeviceDescriptor(
            modelIdentifier: identifier,
            osName: UIDevice.current.systemName,
            osVersion: UIDevice.current.systemVersion
        )
        #else
        return LidarDeviceDescriptor(
            modelIdentifier: "non-ios-host",
            osName: ProcessInfo.processInfo.operatingSystemVersionString,
            osVersion: ProcessInfo.processInfo.operatingSystemVersionString
        )
        #endif
    }
}
