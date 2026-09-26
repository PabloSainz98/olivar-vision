#if os(iOS) && canImport(SwiftUI) && canImport(ARKit)
import ARKit
import Foundation
import SceneKit
import SwiftUI
import UIKit

@available(iOS 15.4, *)
@MainActor
public final class LidarCaptureViewModel: ObservableObject {
    @Published public private(set) var capabilities: LidarCapabilityReport
    @Published public private(set) var statusMessage: String
    @Published public private(set) var isCapturing = false
    @Published public private(set) var lastSessionURL: URL?
    @Published public private(set) var activeSession: ARSession?

    private let exportRootURL: URL
    private let repeatGroupID: String
    private let context: LidarCaptureContext
    private var controller: ARKitCaptureController?

    public init(
        exportRootURL: URL,
        repeatGroupID: String,
        context: LidarCaptureContext
    ) {
        self.exportRootURL = exportRootURL
        self.repeatGroupID = repeatGroupID
        self.context = context
        let report = SystemLidarCapabilityDetector.detect()
        self.capabilities = report
        self.statusMessage = report.status == .supported
            ? "LiDAR disponible. Captura preparada."
            : (report.reason ?? "LiDAR no disponible en este dispositivo.")
    }

    public func refreshCapabilities() {
        capabilities = SystemLidarCapabilityDetector.detect()
        if capabilities.status == .unsupported {
            statusMessage = capabilities.reason ?? "LiDAR no disponible en este dispositivo."
        } else if !isCapturing {
            statusMessage = "LiDAR disponible. Captura preparada."
        }
    }

    public func startCapture() {
        refreshCapabilities()
        guard capabilities.status == .supported else { return }
        let sessionID = UUID().uuidString.lowercased()
        let sessionURL = exportRootURL.appendingPathComponent(sessionID, isDirectory: true)
        do {
            let writer = try OfflineSessionWriter(
                rootURL: sessionURL,
                sessionID: sessionID,
                repeatGroupID: repeatGroupID,
                context: context
            )
            let controller = ARKitCaptureController(writer: writer)
            controller.onError = { [weak self] error in
                DispatchQueue.main.async {
                    self?.statusMessage = "Captura rechazada: \(error.localizedDescription)"
                }
            }
            try controller.start()
            self.controller = controller
            self.activeSession = controller.session
            self.lastSessionURL = sessionURL
            self.isCapturing = true
            self.statusMessage = "Capturando sin red. Conserva el recorrido estable."
        } catch {
            statusMessage = "No se pudo iniciar: \(error.localizedDescription)"
        }
    }

    public func stopCapture() {
        guard let controller else { return }
        do {
            try controller.stopAndFinalize()
            statusMessage = "Sesion finalizada y conservada sin sobrescritura."
        } catch {
            statusMessage = "No se pudo finalizar: \(error.localizedDescription)"
        }
        self.controller = nil
        activeSession = nil
        isCapturing = false
    }

    public func addScaleReference(
        expectedDistanceM: Double,
        pointAWorldM: [Double],
        pointBWorldM: [Double]
    ) -> Bool {
        guard let controller else {
            statusMessage = "Inicia una captura antes de registrar la referencia."
            return false
        }
        do {
            try controller.addScaleReference(
                LidarScaleReference(
                    referenceID: UUID().uuidString.lowercased(),
                    expectedDistanceM: expectedDistanceM,
                    pointAWorldM: pointAWorldM,
                    pointBWorldM: pointBWorldM,
                    toleranceM: 0.02
                )
            )
            statusMessage = "Referencia metrica registrada con tolerancia de 0,02 m."
            return true
        } catch {
            statusMessage = "No se pudo registrar la referencia: \(error.localizedDescription)"
            return false
        }
    }

    public func restoreCaptureDelegate() {
        controller?.restoreCaptureDelegate()
    }
}

@available(iOS 15.4, *)
public struct LidarCaptureView: View {
    @StateObject private var model: LidarCaptureViewModel
    @State private var selectedScalePoints: [[Double]] = []
    @State private var expectedScaleDistance = ""
    @State private var previewResetToken = UUID()

    public init(
        exportRootURL: URL,
        repeatGroupID: String,
        context: LidarCaptureContext
    ) {
        _model = StateObject(
            wrappedValue: LidarCaptureViewModel(
                exportRootURL: exportRootURL,
                repeatGroupID: repeatGroupID,
                context: context
            )
        )
    }

    public var body: some View {
        Form {
            Section("Compatibilidad real") {
                capabilityRow("Profundidad de escena", model.capabilities.sceneDepth)
                capabilityRow("Profundidad suavizada", model.capabilities.smoothedSceneDepth)
                capabilityRow("Malla de escena", model.capabilities.sceneMesh)
                capabilityRow("Camara LiDAR", model.capabilities.lidarDepthCamera)
            }
            Section("Estado") {
                Text(model.statusMessage)
                if let sessionURL = model.lastSessionURL {
                    Text(sessionURL.lastPathComponent)
                        .font(.caption.monospaced())
                        .textSelection(.enabled)
                }
            }
            if let activeSession = model.activeSession {
                Section("Vista de captura") {
                    ARSessionPreview(
                        session: activeSession,
                        resetToken: previewResetToken,
                        selectionLimitReached: selectedScalePoints.count >= 2,
                        onSessionAttached: model.restoreCaptureDelegate
                    ) { point in
                        if selectedScalePoints.count < 2 {
                            selectedScalePoints.append(point)
                        }
                    }
                    .frame(height: 280)
                    .clipped()
                }
                Section("Referencia metrica") {
                    Text("Puntos seleccionados: \(selectedScalePoints.count)/2")
                    TextField("Distancia medida (m)", text: $expectedScaleDistance)
                        .keyboardType(.decimalPad)
                    Button {
                        addScaleReference()
                    } label: {
                        Label("Registrar referencia", systemImage: "ruler")
                    }
                    .disabled(selectedScalePoints.count != 2 || scaleDistance == nil)
                    Button {
                        selectedScalePoints = []
                        previewResetToken = UUID()
                    } label: {
                        Label("Reiniciar puntos", systemImage: "arrow.counterclockwise")
                    }
                    .disabled(selectedScalePoints.isEmpty)
                }
            }
            Section {
                if model.isCapturing {
                    Button(role: .destructive, action: model.stopCapture) {
                        Label("Finalizar captura", systemImage: "stop.fill")
                    }
                } else {
                    Button(action: model.startCapture) {
                        Label("Iniciar captura", systemImage: "record.circle")
                    }
                    .disabled(model.capabilities.status == .unsupported)
                }
            }
            Section {
                NavigationLink(destination: BiomassCarbonView()) {
                    Label("Biomasa y carbono", systemImage: "function")
                }
            }
        }
        .navigationTitle("Captura LiDAR")
    }

    private func capabilityRow(_ label: String, _ available: Bool) -> some View {
        HStack {
            Text(label)
            Spacer()
            Image(systemName: available ? "checkmark.circle.fill" : "xmark.circle.fill")
                .foregroundStyle(available ? Color.green : Color.red)
                .accessibilityLabel(available ? "Disponible" : "No disponible")
        }
    }

    private var scaleDistance: Double? {
        guard let value = Double(expectedScaleDistance.replacingOccurrences(of: ",", with: ".")),
              value > 0 else {
            return nil
        }
        return value
    }

    private func addScaleReference() {
        guard selectedScalePoints.count == 2, let distance = scaleDistance else { return }
        if model.addScaleReference(
            expectedDistanceM: distance,
            pointAWorldM: selectedScalePoints[0],
            pointBWorldM: selectedScalePoints[1]
        ) {
            selectedScalePoints = []
            expectedScaleDistance = ""
            previewResetToken = UUID()
        }
    }
}

@available(iOS 15.4, *)
private struct ARSessionPreview: UIViewRepresentable {
    let session: ARSession
    let resetToken: UUID
    let selectionLimitReached: Bool
    let onSessionAttached: () -> Void
    let onPointSelected: ([Double]) -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(
            resetToken: resetToken,
            selectionLimitReached: selectionLimitReached,
            onPointSelected: onPointSelected
        )
    }

    func makeUIView(context: Context) -> ARSCNView {
        let view = ARSCNView(frame: .zero)
        view.session = session
        onSessionAttached()
        view.automaticallyUpdatesLighting = true
        let tap = UITapGestureRecognizer(
            target: context.coordinator,
            action: #selector(Coordinator.didTap(_:))
        )
        view.addGestureRecognizer(tap)
        return view
    }

    func updateUIView(_ view: ARSCNView, context: Context) {
        view.session = session
        onSessionAttached()
        context.coordinator.onPointSelected = onPointSelected
        context.coordinator.selectionLimitReached = selectionLimitReached
        if context.coordinator.resetToken != resetToken {
            context.coordinator.resetToken = resetToken
            view.scene.rootNode.childNodes
                .filter { $0.name == "scale-reference-point" }
                .forEach { $0.removeFromParentNode() }
        }
    }

    final class Coordinator: NSObject {
        var resetToken: UUID
        var selectionLimitReached: Bool
        var onPointSelected: ([Double]) -> Void

        init(
            resetToken: UUID,
            selectionLimitReached: Bool,
            onPointSelected: @escaping ([Double]) -> Void
        ) {
            self.resetToken = resetToken
            self.selectionLimitReached = selectionLimitReached
            self.onPointSelected = onPointSelected
        }

        @objc func didTap(_ recognizer: UITapGestureRecognizer) {
            guard !selectionLimitReached else { return }
            guard let view = recognizer.view as? ARSCNView else { return }
            let location = recognizer.location(in: view)
            guard let hit = view.hitTest(location, types: [.featurePoint]).first else { return }
            let transform = hit.worldTransform
            let point = SCNVector3(
                transform.columns.3.x,
                transform.columns.3.y,
                transform.columns.3.z
            )
            let marker = SCNSphere(radius: 0.015)
            marker.firstMaterial?.diffuse.contents = UIColor.systemYellow
            let node = SCNNode(geometry: marker)
            node.name = "scale-reference-point"
            node.position = point
            view.scene.rootNode.addChildNode(node)
            onPointSelected([Double(point.x), Double(point.y), Double(point.z)])
        }
    }
}
#endif
