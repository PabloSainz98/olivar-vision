import Foundation
import XCTest
@testable import OlivarLidarCapture

final class CaptureContractTests: XCTestCase {
    func testNonIOSHostReportsUnsupportedInsteadOfSimulatingLiDAR() {
        #if !os(iOS)
        let report = SystemLidarCapabilityDetector.detect()
        XCTAssertEqual(report.status, .unsupported)
        XCTAssertFalse(report.sceneDepth)
        XCTAssertFalse(report.lidarDepthCamera)
        XCTAssertNotNil(report.reason)
        #endif
    }

    func testWriterCreatesVersionedSeparatedLayoutAndRefusesReuse() throws {
        let base = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        defer { try? FileManager.default.removeItem(at: base) }
        let root = base.appendingPathComponent("capture", isDirectory: true)
        let context = LidarCaptureContext(
            treeID: "tree-1",
            operatorID: "operator-local",
            siteID: "plot-a"
        )
        let capabilities = LidarCapabilityReport(
            status: .unsupported,
            sceneDepth: false,
            smoothedSceneDepth: false,
            sceneMesh: false,
            lidarDepthCamera: false,
            reason: "test host"
        )
        _ = try OfflineSessionWriter(
            rootURL: root,
            sessionID: "session-1",
            repeatGroupID: "tree-1-repeat",
            context: context,
            device: SystemLidarDeviceDescriptor.current(),
            capabilities: capabilities
        )

        XCTAssertTrue(FileManager.default.fileExists(atPath: root.appendingPathComponent("session.json").path))
        XCTAssertTrue(FileManager.default.fileExists(atPath: root.appendingPathComponent("captured").path))
        XCTAssertTrue(FileManager.default.fileExists(atPath: root.appendingPathComponent("derived").path))
        XCTAssertTrue(FileManager.default.fileExists(atPath: root.appendingPathComponent("validation").path))
        XCTAssertThrowsError(
            try OfflineSessionWriter(
                rootURL: root,
                sessionID: "session-2",
                repeatGroupID: "tree-1-repeat",
                context: context,
                device: SystemLidarDeviceDescriptor.current(),
                capabilities: capabilities
            )
        ) { error in
            XCTAssertEqual(error as? LidarCaptureWriterError, .sessionAlreadyExists)
        }
    }

    func testWriterStoresRawFrameAndFinalizesWithoutOverwritingArtifacts() throws {
        let base = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        defer { try? FileManager.default.removeItem(at: base) }
        let root = base.appendingPathComponent("capture", isDirectory: true)
        let writer = try OfflineSessionWriter(
            rootURL: root,
            sessionID: "session-1",
            repeatGroupID: "tree-1-repeat",
            context: LidarCaptureContext(
                treeID: "tree-1",
                operatorID: "operator-local",
                siteID: "plot-a"
            ),
            device: LidarDeviceDescriptor(
                modelIdentifier: "fixture",
                osName: "test",
                osVersion: "1"
            ),
            capabilities: LidarCapabilityReport(
                status: .supported,
                sceneDepth: true,
                smoothedSceneDepth: true,
                sceneMesh: true,
                lidarDepthCamera: true,
                reason: nil
            )
        )
        let one = Float(1).bitPattern.littleEndian
        let depth = withUnsafeBytes(of: one) { Data($0) }
        let payload = LidarFramePayload(
            timestampSeconds: 0.1,
            colorWidth: 1,
            colorHeight: 1,
            colorPixelFormat: "420f",
            colorPlanes: [
                LidarColorPlane(index: 0, width: 1, height: 1, bytesPerRow: 1, data: Data([127]))
            ],
            depthWidth: 1,
            depthHeight: 1,
            depthFloat32LittleEndian: depth,
            confidenceUInt8: Data([2]),
            intrinsics: LidarIntrinsics(width: 1, height: 1, fx: 1, fy: 1, cx: 0, cy: 0),
            opticalCameraToWorldRowMajor: [
                1, 0, 0, 0,
                0, 1, 0, 0,
                0, 0, 1, 0,
                0, 0, 0, 1,
            ],
            trackingState: "normal"
        )

        try writer.append(payload)
        try writer.addScaleReference(
            LidarScaleReference(
                referenceID: "ruler-1",
                expectedDistanceM: 1,
                pointAWorldM: [0, 0, 0],
                pointBWorldM: [1, 0, 0],
                toleranceM: 0.02
            )
        )
        try writer.finalize()

        let manifestData = try Data(contentsOf: root.appendingPathComponent("session.json"))
        let manifest = try XCTUnwrap(
            JSONSerialization.jsonObject(with: manifestData) as? [String: Any]
        )
        XCTAssertEqual(manifest["format_id"] as? String, LidarCaptureContract.formatID)
        XCTAssertEqual(manifest["schema_version"] as? Int, 1)
        XCTAssertEqual(manifest["status"] as? String, "complete")
        XCTAssertEqual((manifest["frames"] as? [[String: Any]])?.count, 1)
        XCTAssertEqual((manifest["scale_references"] as? [[String: Any]])?.count, 1)
        XCTAssertThrowsError(try writer.append(payload)) { error in
            XCTAssertEqual(error as? LidarCaptureWriterError, .sessionFinalized)
        }
    }
}
