import Foundation

public enum LidarCaptureContract {
    public static let formatID = "olivar-lidar-capture"
    public static let schemaVersion = 1
    public static let cameraCoordinates = "depth_camera_optical_x_right_y_down_z_forward"
    public static let worldCoordinates = "arkit_world_right_handed_y_up"
}

public enum LidarCapabilityStatus: String, Codable, Sendable {
    case supported
    case unsupported
}

public struct LidarCapabilityReport: Codable, Equatable, Sendable {
    public let status: LidarCapabilityStatus
    public let sceneDepth: Bool
    public let smoothedSceneDepth: Bool
    public let sceneMesh: Bool
    public let lidarDepthCamera: Bool
    public let reason: String?

    public init(
        status: LidarCapabilityStatus,
        sceneDepth: Bool,
        smoothedSceneDepth: Bool,
        sceneMesh: Bool,
        lidarDepthCamera: Bool,
        reason: String?
    ) {
        self.status = status
        self.sceneDepth = sceneDepth
        self.smoothedSceneDepth = smoothedSceneDepth
        self.sceneMesh = sceneMesh
        self.lidarDepthCamera = lidarDepthCamera
        self.reason = reason
    }

    enum CodingKeys: String, CodingKey {
        case status
        case sceneDepth = "scene_depth"
        case smoothedSceneDepth = "smoothed_scene_depth"
        case sceneMesh = "scene_mesh"
        case lidarDepthCamera = "lidar_depth_camera"
        case reason
    }
}

public struct LidarDeviceDescriptor: Codable, Equatable, Sendable {
    public let modelIdentifier: String
    public let osName: String
    public let osVersion: String

    public init(modelIdentifier: String, osName: String, osVersion: String) {
        self.modelIdentifier = modelIdentifier
        self.osName = osName
        self.osVersion = osVersion
    }

    enum CodingKeys: String, CodingKey {
        case modelIdentifier = "model_identifier"
        case osName = "os_name"
        case osVersion = "os_version"
    }
}

public struct LidarCaptureContext: Codable, Equatable, Sendable {
    public let treeID: String
    public let operatorID: String
    public let siteID: String
    public let protocolID: String
    public let variety: String?
    public let weather: String?
    public let wind: String?
    public let pruningState: String?

    public init(
        treeID: String,
        operatorID: String,
        siteID: String,
        protocolID: String = "lidar-carbon-l1-v1",
        variety: String? = nil,
        weather: String? = nil,
        wind: String? = nil,
        pruningState: String? = nil
    ) {
        self.treeID = treeID
        self.operatorID = operatorID
        self.siteID = siteID
        self.protocolID = protocolID
        self.variety = variety
        self.weather = weather
        self.wind = wind
        self.pruningState = pruningState
    }

    enum CodingKeys: String, CodingKey {
        case treeID = "tree_id"
        case operatorID = "operator_id"
        case siteID = "site_id"
        case protocolID = "protocol_id"
        case variety
        case weather
        case wind
        case pruningState = "pruning_state"
    }
}

public struct LidarIntrinsics: Codable, Equatable, Sendable {
    public let width: Int
    public let height: Int
    public let fx: Float
    public let fy: Float
    public let cx: Float
    public let cy: Float

    public init(width: Int, height: Int, fx: Float, fy: Float, cx: Float, cy: Float) {
        self.width = width
        self.height = height
        self.fx = fx
        self.fy = fy
        self.cx = cx
        self.cy = cy
    }
}

public struct LidarColorPlane: Sendable {
    public let index: Int
    public let width: Int
    public let height: Int
    public let bytesPerRow: Int
    public let data: Data

    public init(index: Int, width: Int, height: Int, bytesPerRow: Int, data: Data) {
        self.index = index
        self.width = width
        self.height = height
        self.bytesPerRow = bytesPerRow
        self.data = data
    }
}

public struct LidarFramePayload: Sendable {
    public let timestampSeconds: TimeInterval
    public let colorWidth: Int
    public let colorHeight: Int
    public let colorPixelFormat: String
    public let colorPlanes: [LidarColorPlane]
    public let depthWidth: Int
    public let depthHeight: Int
    public let depthFloat32LittleEndian: Data
    public let confidenceUInt8: Data
    public let intrinsics: LidarIntrinsics
    public let opticalCameraToWorldRowMajor: [Float]
    public let trackingState: String

    public init(
        timestampSeconds: TimeInterval,
        colorWidth: Int,
        colorHeight: Int,
        colorPixelFormat: String,
        colorPlanes: [LidarColorPlane],
        depthWidth: Int,
        depthHeight: Int,
        depthFloat32LittleEndian: Data,
        confidenceUInt8: Data,
        intrinsics: LidarIntrinsics,
        opticalCameraToWorldRowMajor: [Float],
        trackingState: String
    ) {
        self.timestampSeconds = timestampSeconds
        self.colorWidth = colorWidth
        self.colorHeight = colorHeight
        self.colorPixelFormat = colorPixelFormat
        self.colorPlanes = colorPlanes
        self.depthWidth = depthWidth
        self.depthHeight = depthHeight
        self.depthFloat32LittleEndian = depthFloat32LittleEndian
        self.confidenceUInt8 = confidenceUInt8
        self.intrinsics = intrinsics
        self.opticalCameraToWorldRowMajor = opticalCameraToWorldRowMajor
        self.trackingState = trackingState
    }
}

public struct LidarScaleReference: Codable, Equatable, Sendable {
    public let referenceID: String
    public let expectedDistanceM: Double
    public let pointAWorldM: [Double]
    public let pointBWorldM: [Double]
    public let toleranceM: Double

    public init(
        referenceID: String,
        expectedDistanceM: Double,
        pointAWorldM: [Double],
        pointBWorldM: [Double],
        toleranceM: Double
    ) {
        self.referenceID = referenceID
        self.expectedDistanceM = expectedDistanceM
        self.pointAWorldM = pointAWorldM
        self.pointBWorldM = pointBWorldM
        self.toleranceM = toleranceM
    }

    enum CodingKeys: String, CodingKey {
        case referenceID = "reference_id"
        case expectedDistanceM = "expected_distance_m"
        case pointAWorldM = "point_a_world_m"
        case pointBWorldM = "point_b_world_m"
        case toleranceM = "tolerance_m"
    }
}

public enum LidarCaptureWriterError: Error, Equatable {
    case sessionAlreadyExists
    case sessionFinalized
    case invalidFrame(String)
    case writeFailed(String)
}
