#if os(iOS) && canImport(SwiftUI)
import SwiftUI

@available(iOS 15.4, *)
public struct BiomassCarbonView: View {
    @State private var diameter = ""
    @State private var diameterUncertainty = ""
    @State private var density = ""
    @State private var cultivar = ""
    @State private var carbonFraction = ""
    @State private var carbonSource = ""
    @State private var proxyFraction = false
    @State private var confirmsVaseTraining = false
    @State private var confirmsTraditionalRainfed = false
    @State private var estimate: BiomassCarbonEstimate?

    public init() {}

    public var body: some View {
        Form {
            Section("Geometria de entrada") {
                TextField("Diametro basal a 0,30 m (cm)", text: $diameter)
                    .keyboardType(.decimalPad)
                TextField("Incertidumbre del diametro (cm)", text: $diameterUncertainty)
                    .keyboardType(.decimalPad)
            }
            Section("Dominio del modelo") {
                TextField("Variedad", text: $cultivar)
                TextField("Densidad (arboles/ha)", text: $density)
                    .keyboardType(.decimalPad)
                Toggle("Confirmo formacion en vaso", isOn: $confirmsVaseTraining)
                Toggle("Confirmo secano tradicional", isOn: $confirmsTraditionalRainfed)
            }
            Section("Factor de carbono") {
                TextField("Fraccion, por ejemplo 0,47", text: $carbonFraction)
                    .keyboardType(.decimalPad)
                TextField("Fuente", text: $carbonSource)
                Toggle("Usado como proxy", isOn: $proxyFraction)
            }
            Section {
                Button {
                    estimate = BiomassCarbonEstimator.estimate(currentInput)
                } label: {
                    Label("Calcular estimacion", systemImage: "function")
                }
            }
            if let estimate {
                estimateSections(estimate)
            }
        }
        .navigationTitle("Biomasa y carbono")
    }

    private var currentInput: BiomassCarbonInput {
        BiomassCarbonInput(
            basalDiameterCM: number(diameter),
            measurementHeightM: 0.3,
            diameterUncertaintyCM: number(diameterUncertainty),
            diameterSource: .manualTape,
            cultivar: cultivar,
            trainingSystem: confirmsVaseTraining ? "vase" : "",
            waterRegime: confirmsTraditionalRainfed ? "traditional_rainfed" : "",
            orchardDensityTreesPerHa: number(density),
            carbonFraction: number(carbonFraction),
            carbonFractionSource: carbonSource,
            carbonFractionIsProxy: proxyFraction
        )
    }

    @ViewBuilder
    private func estimateSections(_ value: BiomassCarbonEstimate) -> some View {
        if value.isAvailable {
            Section("Estado") {
                Text("Estimacion experimental")
                Text("Pendiente de calibracion local y validacion independiente.")
                    .font(.caption)
            }
            Section("Biomasa seca aerea modelada") {
                resultRow(value.abovegroundDryBiomassKG, unit: "kg")
                sensitivityRow(value.biomassSensitivityKG, unit: "kg")
                Text(BiomassCarbonEstimator.equation)
                    .font(.caption.monospaced())
                Text(BiomassCarbonEstimator.modelVersion)
                    .font(.caption.monospaced())
            }
            Section("Carbono almacenado") {
                resultRow(value.storedCarbonKG, unit: "kg C")
                sensitivityRow(value.storedCarbonSensitivityKG, unit: "kg C")
                Text(carbonSource).font(.caption)
            }
            Section("CO2 equivalente almacenado") {
                resultRow(value.storedCO2EquivalentKG, unit: "kg CO2e")
                sensitivityRow(value.storedCO2EquivalentSensitivityKG, unit: "kg CO2e")
                Text("Stock calculado con 44/12; no es absorcion anual.")
                    .font(.caption)
            }
        } else {
            Section("Estimacion no disponible") {
                ForEach(value.reasons, id: \.self) { reason in
                    Label(reason, systemImage: "exclamationmark.triangle")
                }
            }
        }
        if !value.warnings.isEmpty {
            Section("Limites") {
                ForEach(value.warnings, id: \.self) { warning in
                    Text(warning)
                }
            }
        }
    }

    private func resultRow(_ value: Double?, unit: String) -> some View {
        HStack {
            Text(value.map { $0.formatted(.number.precision(.fractionLength(2))) } ?? "No disponible")
            Spacer()
            Text(unit)
                .foregroundStyle(.secondary)
        }
    }

    @ViewBuilder
    private func sensitivityRow(_ value: ClosedRange<Double>?, unit: String) -> some View {
        if let value {
            Text(
                "Sensibilidad DB: \(formatted(value.lowerBound))-\(formatted(value.upperBound)) \(unit)"
            )
            .font(.caption)
        }
    }

    private func formatted(_ value: Double) -> String {
        value.formatted(.number.precision(.fractionLength(2)))
    }

    private func number(_ value: String) -> Double? {
        Double(value.replacingOccurrences(of: ",", with: "."))
    }
}
#endif
