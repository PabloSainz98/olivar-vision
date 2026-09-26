import CryptoKit
import Foundation

public final class OfflineSessionWriter {
    public let rootURL: URL
    public let sessionID: String
    public let repeatGroupID: String

    private let fileManager: FileManager
    private let encoder: JSONEncoder
    private let context: LidarCaptureContext
    private let device: LidarDeviceDescriptor
    private let capabilities: LidarCapabilityReport
    private let createdAt: String
    private var frameRecords: [[String: Any]] = []
    private var discardedFrames: [[String: Any]] = []
    private var scaleReferences: [LidarScaleReference] = []
    private var finalized = false

    public convenience init(
        rootURL: URL,
        sessionID: String,
        repeatGroupID: String,
        context: LidarCaptureContext,
        fileManager: FileManager = .default,
        now: Date = Date()
    ) throws {
        try self.init(
            rootURL: rootURL,
            sessionID: sessionID,
            repeatGroupID: repeatGroupID,
            context: context,
            device: SystemLidarDeviceDescriptor.current(),
            capabilities: SystemLidarCapabilityDetector.detect(),
            fileManager: fileManager,
            now: now
        )
    }

    init(
        rootURL: URL,
        sessionID: String,
        repeatGroupID: String,
        context: LidarCaptureContext,
        device: LidarDeviceDescriptor,
        capabilities: LidarCapabilityReport,
        fileManager: FileManager = .default,
        now: Date = Date()
    ) throws {
        self.rootURL = rootURL
        self.sessionID = sessionID
        self.repeatGroupID = repeatGroupID
        self.context = context
        self.device = device
        self.capabilities = capabilities
        self.fileManager = fileManager
        self.createdAt = ISO8601DateFormatter().string(from: now)
        self.encoder = JSONEncoder()
        self.encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]

        guard !fileManager.fileExists(atPath: rootURL.path) else {
            throw LidarCaptureWriterError.sessionAlreadyExists
        }
        do {
            try fileManager.createDirectory(at: rootURL, withIntermediateDirectories: true)
            try fileManager.createDirectory(
                at: rootURL.appendingPathComponent("captured", isDirectory: true),
                withIntermediateDirectories: false
            )
            try fileManager.createDirectory(
                at: rootURL.appendingPathComponent("derived", isDirectory: true),
                withIntermediateDirectories: false
            )
            try fileManager.createDirectory(
                at: rootURL.appendingPathComponent("validation", isDirectory: true),
                withIntermediateDirectories: false
            )
            try writeManifest(status: "in_progress")
        } catch let error as LidarCaptureWriterError {
            throw error
        } catch {
            throw LidarCaptureWriterError.writeFailed(error.localizedDescription)
        }
    }

    public func append(_ payload: LidarFramePayload) throws {
        guard !finalized else { throw LidarCaptureWriterError.sessionFinalized }
        try validate(payload)
        let frameID = String(format: "frame-%06d", frameRecords.count + 1)
        let frameDirectory = rootURL
            .appendingPathComponent("captured", isDirectory: true)
            .appendingPathComponent(frameID, isDirectory: true)
        do {
            try fileManager.createDirectory(at: frameDirectory, withIntermediateDirectories: false)

            var colorPlaneRecords: [[String: Any]] = []
            for plane in payload.colorPlanes {
                let fileName = "color-plane-\(plane.index).u8"
                let relative = "captured/\(frameID)/\(fileName)"
                let artifact = try writeArtifact(plane.data, relativePath: relative)
                colorPlaneRecords.append([
                    "path": relative,
                    "format": "raw_bytes",
                    "width": plane.width,
                    "height": plane.height,
                    "bytes_per_row": plane.bytesPerRow,
                    "size_bytes": artifact.size,
                    "sha256": artifact.sha256,
                ])
            }

            let depthRelative = "captured/\(frameID)/depth.f32le"
            let depthArtifact = try writeArtifact(
                payload.depthFloat32LittleEndian,
                relativePath: depthRelative
            )
            let confidenceRelative = "captured/\(frameID)/confidence.u8"
            let confidenceArtifact = try writeArtifact(
                payload.confidenceUInt8,
                relativePath: confidenceRelative
            )
            let metadata: [String: Any] = [
                "format_id": "olivar-lidar-frame",
                "schema_version": 1,
                "frame_id": frameID,
                "timestamp_s": payload.timestampSeconds,
                "tracking_state": payload.trackingState,
                "color": [
                    "width": payload.colorWidth,
                    "height": payload.colorHeight,
                    "pixel_format": payload.colorPixelFormat,
                    "orientation": "arkit_captured_image_sensor_native",
                    "planes": colorPlaneRecords,
                ],
                "depth": [
                    "path": depthRelative,
                    "format": "float32_le",
                    "units": "meter",
                    "width": payload.depthWidth,
                    "height": payload.depthHeight,
                    "size_bytes": depthArtifact.size,
                    "sha256": depthArtifact.sha256,
                ],
                "confidence": [
                    "path": confidenceRelative,
                    "format": "uint8",
                    "levels": ["0": "low", "1": "medium", "2": "high"],
                    "width": payload.depthWidth,
                    "height": payload.depthHeight,
                    "size_bytes": confidenceArtifact.size,
                    "sha256": confidenceArtifact.sha256,
                ],
                "intrinsics": [
                    "model": "pinhole",
                    "reference": "depth_resolution",
                    "width": payload.intrinsics.width,
                    "height": payload.intrinsics.height,
                    "fx": payload.intrinsics.fx,
                    "fy": payload.intrinsics.fy,
                    "cx": payload.intrinsics.cx,
                    "cy": payload.intrinsics.cy,
                ],
                "pose": [
                    "layout": "row_major",
                    "from": LidarCaptureContract.cameraCoordinates,
                    "to": LidarCaptureContract.worldCoordinates,
                    "matrix": payload.opticalCameraToWorldRowMajor,
                ],
            ]
            let metadataData = try JSONSerialization.data(
                withJSONObject: metadata,
                options: [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
            ) + Data([0x0A])
            let metadataRelative = "captured/\(frameID)/frame.json"
            let metadataArtifact = try writeArtifact(metadataData, relativePath: metadataRelative)
            frameRecords.append([
                "frame_id": frameID,
                "timestamp_s": payload.timestampSeconds,
                "metadata_path": metadataRelative,
                "metadata_size_bytes": metadataArtifact.size,
                "metadata_sha256": metadataArtifact.sha256,
            ])
            try writeManifest(status: "in_progress")
        } catch let error as LidarCaptureWriterError {
            throw error
        } catch {
            throw LidarCaptureWriterError.writeFailed(error.localizedDescription)
        }
    }

    public func recordDiscardedFrame(timestampSeconds: TimeInterval, reason: String) throws {
        guard !finalized else { throw LidarCaptureWriterError.sessionFinalized }
        discardedFrames.append(["timestamp_s": timestampSeconds, "reason": reason])
        try writeManifest(status: "in_progress")
    }

    public func addScaleReference(_ reference: LidarScaleReference) throws {
        guard !finalized else { throw LidarCaptureWriterError.sessionFinalized }
        guard reference.pointAWorldM.count == 3, reference.pointBWorldM.count == 3 else {
            throw LidarCaptureWriterError.invalidFrame("scale reference points require three values")
        }
        scaleReferences.append(reference)
        try writeManifest(status: "in_progress")
    }

    public func finalize() throws {
        guard !finalized else { throw LidarCaptureWriterError.sessionFinalized }
        try writeManifest(status: "complete")
        finalized = true
    }

    private func validate(_ payload: LidarFramePayload) throws {
        guard payload.depthWidth > 0, payload.depthHeight > 0 else {
            throw LidarCaptureWriterError.invalidFrame("depth resolution must be positive")
        }
        let sampleCount = payload.depthWidth * payload.depthHeight
        guard payload.depthFloat32LittleEndian.count == sampleCount * MemoryLayout<Float32>.size else {
            throw LidarCaptureWriterError.invalidFrame("depth byte count does not match resolution")
        }
        guard payload.confidenceUInt8.count == sampleCount else {
            throw LidarCaptureWriterError.invalidFrame("confidence byte count does not match resolution")
        }
        guard payload.intrinsics.width == payload.depthWidth,
              payload.intrinsics.height == payload.depthHeight else {
            throw LidarCaptureWriterError.invalidFrame("intrinsics must match depth resolution")
        }
        guard payload.opticalCameraToWorldRowMajor.count == 16 else {
            throw LidarCaptureWriterError.invalidFrame("pose must contain 16 row-major values")
        }
        guard !payload.colorPlanes.isEmpty else {
            throw LidarCaptureWriterError.invalidFrame("at least one RGB plane is required")
        }
        if let previous = frameRecords.last?["timestamp_s"] as? TimeInterval,
           payload.timestampSeconds <= previous {
            throw LidarCaptureWriterError.invalidFrame("timestamps must increase strictly")
        }
    }

    private func writeManifest(status: String) throws {
        let capture = try dictionary(from: context)
        let deviceDictionary = try dictionary(from: device)
        let capabilityDictionary = try dictionary(from: capabilities)
        let references = try scaleReferences.map { try dictionary(from: $0) }
        let manifest: [String: Any] = [
            "format_id": LidarCaptureContract.formatID,
            "schema_version": LidarCaptureContract.schemaVersion,
            "session_id": sessionID,
            "repeat_group_id": repeatGroupID,
            "source_type": "real_device",
            "status": status,
            "created_at": createdAt,
            "capture": capture,
            "device": deviceDictionary,
            "app": appDescriptor(),
            "capabilities": capabilityDictionary,
            "units": ["depth": "meter", "translation": "meter"],
            "coordinate_system": [
                "camera": LidarCaptureContract.cameraCoordinates,
                "world": LidarCaptureContract.worldCoordinates,
            ],
            "frames": frameRecords,
            "discarded_frames": discardedFrames,
            "scale_references": references,
        ]
        let data = try JSONSerialization.data(
            withJSONObject: manifest,
            options: [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        ) + Data([0x0A])
        try data.write(to: rootURL.appendingPathComponent("session.json"), options: .atomic)
    }

    private func appDescriptor() -> [String: String] {
        [
            "bundle_id": Bundle.main.bundleIdentifier ?? "unknown",
            "version": Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "unknown",
            "build": Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown",
        ]
    }

    private func dictionary<T: Encodable>(from value: T) throws -> [String: Any] {
        let data = try encoder.encode(value)
        guard let result = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw LidarCaptureWriterError.writeFailed("encoded metadata is not an object")
        }
        return result
    }

    private func writeArtifact(_ data: Data, relativePath: String) throws -> (size: Int, sha256: String) {
        let target = rootURL.appendingPathComponent(relativePath)
        guard !fileManager.fileExists(atPath: target.path) else {
            throw LidarCaptureWriterError.writeFailed("refusing to overwrite \(relativePath)")
        }
        try data.write(to: target, options: .withoutOverwriting)
        return (data.count, SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined())
    }
}
