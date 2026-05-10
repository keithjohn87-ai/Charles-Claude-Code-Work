// WarRoomApp.swift — app entry. NavigationSplitView with a sidebar.
//
// On first launch: SettingsView prompts for server URL + shared secret.
// Subsequent launches: reads from Keychain and goes straight to the
// permission queue (the killer feature).

import SwiftUI
import Combine

@main
struct WarRoomApp: App {
    @StateObject private var config = CharlesConfig.shared

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(config)
                .frame(minWidth: 1000, minHeight: 600)
                .preferredColorScheme(.dark)
                .tint(Color.bronzeCopper)
        }
        .windowStyle(.hiddenTitleBar)

        Settings {
            SettingsView()
                .environmentObject(config)
                .preferredColorScheme(.dark)
                .tint(Color.bronzeCopper)
        }
    }
}

enum SidebarItem: String, CaseIterable, Identifiable {
    case tasks = "Tasks"          // formerly "Approvals" — these are things Charles needs FROM John
    case conversation = "Conversation"
    case activity = "Activity"
    case goals = "Goals"
    case system = "System"
    case tools = "Tools"
    case secrets = "Secrets"

    var id: String { rawValue }

    var systemImage: String {
        switch self {
        case .tasks: return "checklist"
        case .conversation: return "message"
        case .activity: return "list.bullet.rectangle"
        case .goals: return "flag"
        case .system: return "cpu"
        case .tools: return "wrench.and.screwdriver"
        case .secrets: return "key.fill"
        }
    }
}

struct ContentView: View {
    @State private var selection: SidebarItem? = .tasks
    @StateObject private var pollState = PollingState()

    var body: some View {
        NavigationSplitView {
            List(SidebarItem.allCases, selection: $selection) { item in
                NavigationLink(value: item) {
                    Label(item.rawValue, systemImage: item.systemImage)
                        .badge(badgeFor(item))
                        .foregroundStyle(.bronzeIvory)
                }
            }
            .listStyle(.sidebar)
            .scrollContentBackground(.hidden)
            .background(Color.bronzeSurface)
            .navigationTitle("WAR ROOM")
            .frame(minWidth: 180)
        } detail: {
            switch selection ?? .tasks {
            case .tasks: ApprovalsView()       // view file kept the same; only the sidebar label changed
            case .conversation: ConversationView()
            case .activity: ActivityView()
            case .goals: GoalsView()
            case .system: SystemView()
            case .tools: ToolsView()
            case .secrets: SecretsView()
            }
        }
        .environmentObject(pollState)
        .task {
            await pollState.start()
        }
    }

    private func badgeFor(_ item: SidebarItem) -> Int {
        switch item {
        case .tasks:
            // Use the unified count if available; fall back to approvals only
            // for older server versions.
            return pollState.now?.unifiedPendingCount ?? pollState.now?.pendingApprovalsCount ?? 0
        default: return 0
        }
    }
}

// Polls /api/state/now every 3s for badges + the Now header. Reactive
// state for the rest comes from each individual view.
@MainActor
final class PollingState: ObservableObject {
    @Published var now: NowSummary?
    @Published var lastPollError: String?

    private var task: Task<Void, Never>?

    func start() async {
        task?.cancel()
        task = Task { [weak self] in
            while !Task.isCancelled {
                await self?.pollOnce()
                try? await Task.sleep(nanoseconds: 3_000_000_000)
            }
        }
    }

    func stop() {
        task?.cancel()
    }

    private func pollOnce() async {
        do {
            let s = try await CharlesAPI.shared.now()
            self.now = s
            self.lastPollError = nil
        } catch {
            self.lastPollError = error.localizedDescription
        }
    }
}
