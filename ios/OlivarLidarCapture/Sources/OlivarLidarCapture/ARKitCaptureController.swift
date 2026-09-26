#if os(iOS) && canImport(ARKit) && canImport(CoreVideo)
import ARKit
import CoreVideo
import Foundation
import simd

@available(iOS 15.4, *)
public final class ARKitCaptureController: NSObject, ARSessionDelegate {
    public let session = ARSession()
    public var onError: ((Error) -> Void)?

    private let writer: OfflineSessionWriter
    private let sampleInterval: TimeInterval
    private let captureQueue = DispatchQueue(label: "olivar.lidar.capture")
    private var lastCapturedTimestamp: TimeInterval?

    public init(writer: OfflineSessionWriter, sampleInterval: TimeInterval = 0.2) {
        self.writer = writer
        self.sampleInterval = sampleInterval
        super.init()
        restoreCaptureDelegate()
    }

    public func restoreCaptureDelegate() {
        session.delegate = self
        session.delegateQueue = captureQueue
    }

    public func start() throws {
        let capabilities = SystemLidarCapabilityDetector.detect()
        guard capabilities.status == .supported else {
            throw LidarCaptureWriterError.invalidFrame(
                capabilities.reason ?? "LiDAR scene depth is unsupported"
            )
        }
        let configuration = ARWorldTrackingConfiguration()
        configuration.frameSemantics.insert(.sceneDepth)
        if capabilities.smoothedSceneDepth {
            configuration.frameSemantics.insert(.smoothedSceneDepth)
        }
        if capabilities.sceneMesh {
            configuration.sceneReconstruction = .mesh
        }
        session.run(configuration, options: [.resetTracking, .removeExistingAnchors])
    }

    public func stopAndFinalize() throws {
        session.pause()
        var result: Result<Void, Error>!
        captureQueue.sync {
            result = Result { try writer.finalize() }
        }
        try result.get()
    }

    public func addScaleReference(_ reference: LidarScaleReference) throws {
        var result: Result<Void, Error>!
        captureQueue.sync {
            result = Result { try writer.addScaleReference(reference) }
        }
        try result.get()
    }

    public func session(_ session: ARSession, didUpdate frame: ARFrame) {
        if let previous = lastCapturedTimestamp,
           frame.timestamp - previous < sampleInterval {
            return
        }
        guard case .normal = frame.camera.trackingState else {
            recordDiscardedFrame(
                timestampSeconds: frame.timestamp,
                reason: trackingReason(frame.camera.trackingState)
            )
            return
        }
        guard let sceneDepth = frame.sceneDepth else {
            recordDiscardedFrame(timestampSeconds: frame.timestamp, reason: "missing_scene_depth")
            return
        }
        guard let confidenceMap = sceneDepth.confidenceMap else {
            recordDiscardedFrame(timestampSeconds: frame.timestamp, reason: "missing_confidence_map")
            return
        }

        do {
            let payload = try makePayload(
                frame: frame,
                depthMap: sceneDepth.depthMap,
                confidenceMap: confidenceMap
            )
            try writer.append(payload)
            lastCapturedTimestamp = frame.timestamp
        } catch {
            recordDiscardedFrame(
                timestampSeconds: frame.timestamp,
                reason: "frame_processing_failed"
            )
            onError?(error)
        }
    }

    private func recordDiscardedFrame(timestampSeconds: TimeInterval, reason: String) {
        do {
            try writer.recordDiscardedFrame(
                timestampSeconds: timestampSeconds,
                reason: reason
            )
        } catch {
            onError?(error)
        }
    }

    private func makePayload(
        frame: ARFrame,
        depthMap: CVPixelBuffer,
        confidenceMap: CVPixelBuffer
    ) throws -> LidarFramePayload {
        let depthWidth = CVPixelBufferGetWidth(depthMap)
        let depthHeight = CVPixelBufferGetHeight(depthMap)
        let imageWidth = CVPixelBufferGetWidth(frame.capturedImage)
        let imageHeight = CVPixelBufferGetHeight(frame.capturedImage)
        let scaleX = Float(depthWidth) / Float(imageWidth)
        let scaleY = Float(depthHeight) / Float(imageHeight)
        let cameraIntrinsics = frame.camera.intrinsics
        let intrinsics = LidarIntrinsics(
            width: depthWidth,
            height: depthHeight,
            fx: cameraIntrinsics.columns.0.x * scaleX,
            fy: cameraIntrinsics.columns.1.y * scaleY,
            cx: cameraIntrinsics.columns.2.x * scaleX,
            cy: cameraIntrinsics.columns.2.y * scaleY
        )
        let opticalToARKit = simd_float4x4(
            SIMD4<Float>(1, 0, 0, 0),
            SIMD4<Float>(0, -1, 0, 0),
            SIMD4<Float>(0, 0, -1, 0),
            SIMD4<Float>(0, 0, 0, 1)
        )
        let opticalToWorld = simd_mul(frame.camera.transform, opticalToARKit)
        return LidarFramePayload(
            timestampSeconds: frame.timestamp,
            colorWidth: imageWidth,
            colorHeight: imageHeight,
            colorPixelFormat: fourCC(CVPixelBufferGetPixelFormatType(frame.capturedImage)),
            colorPlanes: try copyColorPlanes(frame.capturedImage),
            depthWidth: depthWidth,
            depthHeight: depthHeight,
            depthFloat32LittleEndian: try copyActiveRows(
                depthMap,
                bytesPerPixel: MemoryLayout<Float32>.size,
                expectedPixelFormat: kCVPixelFormatType_DepthFloat32
            ),
            confidenceUInt8: try copyActiveRows(
                confidenceMap,
                bytesPerPixel: 1,
                expectedPixelFormat: kCVPixelFormatType_OneComponent8
            ),
            intrinsics: intrinsics,
            opticalCameraToWorldRowMajor: rowMajor(opticalToWorld),
            trackingState: "normal"
        )
    }

    private func copyColorPlanes(_ buffer: CVPixelBuffer) throws -> [LidarColorPlane] {
        CVPixelBufferLockBaseAddress(buffer, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(buffer, .readOnly) }
        let count = CVPixelBufferGetPlaneCount(buffer)
        guard count > 0 else {
            throw LidarCaptureWriterError.invalidFrame("captured RGB buffer is not planar")
        }
        return try (0..<count).map { index in
            guard let base = CVPixelBufferGetBaseAddressOfPlane(buffer, index) else {
                throw LidarCaptureWriterError.invalidFrame("RGB plane has no base address")
            }
            let height = CVPixelBufferGetHeightOfPlane(buffer, index)
            let bytesPerRow = CVPixelBufferGetBytesPerRowOfPlane(buffer, index)
            return LidarColorPlane(
                index: index,
                width: CVPixelBufferGetWidthOfPlane(buffer, index),
                height: height,
                bytesPerRow: bytesPerRow,
                data: Data(bytes: base, count: bytesPerRow * height)
            )
        }
    }

    private func copyActiveRows(
        _ buffer: CVPixelBuffer,
        bytesPerPixel: Int,
        expectedPixelFormat: OSType
    ) throws -> Data {
        guard CVPixelBufferGetPixelFormatType(buffer) == expectedPixelFormat else {
            throw LidarCaptureWriterError.invalidFrame("unexpected depth/confidence pixel format")
        }
        CVPixelBufferLockBaseAddress(buffer, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(buffer, .readOnly) }
        guard let base = CVPixelBufferGetBaseAddress(buffer) else {
            throw LidarCaptureWriterError.invalidFrame("pixel buffer has no base address")
        }
        let width = CVPixelBufferGetWidth(buffer)
        let height = CVPixelBufferGetHeight(buffer)
        let bytesPerRow = CVPixelBufferGetBytesPerRow(buffer)
        let activeBytes = width * bytesPerPixel
        var data = Data(capacity: activeBytes * height)
        for row in 0..<height {
            let start = base.advanced(by: row * bytesPerRow).assumingMemoryBound(to: UInt8.self)
            data.append(start, count: activeBytes)
        }
        return data
    }

    private func rowMajor(_ matrix: simd_float4x4) -> [Float] {
        (0..<4).flatMap { row in
            (0..<4).map { column in matrix[column][row] }
        }
    }

    private func fourCC(_ value: OSType) -> String {
        let bytes: [UInt8] = [24, 16, 8, 0].map { UInt8((value >> $0) & 0xff) }
        return String(bytes: bytes, encoding: .ascii) ?? String(value)
    }

    private func trackingReason(_ state: ARCamera.TrackingState) -> String {
        switch state {
        case .normal:
            return "normal"
        case .notAvailable:
            return "tracking_not_available"
        case .limited(let reason):
            return "tracking_limited_\(String(describing: reason))"
        }
    }
}
#endif
