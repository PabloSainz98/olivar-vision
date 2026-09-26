import Foundation
import OlivarLidarCapture
import SwiftUI

struct ContentView: View {
    @State private var treeID = ""
    @State private var operatorID = ""
    @State private var siteID = ""
    @State private var variety = ""
    @State private var weather = ""
    @State private var wind = ""
    @State private var pruningState = ""
    @State private var repeatGroupID = UUID().uuidString.lowercased()

    private var exportRootURL: URL {
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("lidar", isDirectory: true)
    }

    private var contextIsComplete: Bool {
        !treeID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && !operatorID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && !siteID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    var body: some View {
        NavigationView {
            Form {
                Section("Contexto de sesion") {
                    TextField("ID del arbol", text: $treeID)
                    TextField("ID del operador", text: $operatorID)
                    TextField("ID de la finca", text: $siteID)
                    TextField("Variedad, si se conoce", text: $variety)
                    TextField("Tiempo meteorologico", text: $weather)
                    TextField("Viento", text: $wind)
                    TextField("Estado de poda", text: $pruningState)
                }
                Section("Grupo de repeticiones") {
                    Text(repeatGroupID)
                        .font(.caption.monospaced())
                        .textSelection(.enabled)
                    Button {
                        repeatGroupID = UUID().uuidString.lowercased()
                    } label: {
                        Label("Nuevo grupo", systemImage: "arrow.clockwise")
                    }
                }
                Section {
                    NavigationLink(
                        destination: LidarCaptureView(
                            exportRootURL: exportRootURL,
                            repeatGroupID: repeatGroupID,
                            context: LidarCaptureContext(
                                treeID: treeID,
                                operatorID: operatorID,
                                siteID: siteID,
                                variety: optional(variety),
                                weather: optional(weather),
                                wind: optional(wind),
                                pruningState: optional(pruningState)
                            )
                        )
                    ) {
                        Label("Abrir captura LiDAR", systemImage: "viewfinder")
                    }
                    .disabled(!contextIsComplete)

                    NavigationLink(destination: BiomassCarbonView()) {
                        Label("Biomasa y carbono", systemImage: "function")
                    }
                }
                Section("Exportacion local") {
                    Text("Archivos > En mi iPhone > Olivar Vision LiDAR > lidar")
                        .font(.caption)
                }
            }
            .navigationTitle("Olivar Vision")
        }
        .navigationViewStyle(.stack)
    }

    private func optional(_ value: String) -> String? {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }
}
