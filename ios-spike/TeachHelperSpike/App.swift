import SwiftUI

/// Phase 0 — минимальный iOS-таргет для проверки пайплайна.
/// Никакой бизнес-логики, только доказательство: репо → CI macOS → unsigned IPA.
@main
struct TeachHelperSpikeApp: App {
    var body: some Scene {
        WindowGroup {
            VStack(spacing: 16) {
                Text("TeachHelper — iOS spike")
                    .font(.title2.bold())
                Text("Pipeline: repo → CI macOS → unsigned IPA — OK")
                    .font(.footnote)
                    .multilineTextAlignment(.center)
                Text("Phase 0 — no signing, no backend changes")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Divider()
                Text("Bundle: com.teachhelper4.spike")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            .padding()
        }
    }
}
