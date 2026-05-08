// ApprovalsView.swift — the killer feature. List of pending permission
// gates, each with one-tap approve / deny.
//
// Per spec: this is what earns War Room its keep over Telegram. Native
// one-tap approval. Get this right before anything else.

import SwiftUI

struct ApprovalsView: View {
    @State private var approvals: [PendingApproval] = []
    @State private var loading = true
    @State private var error: String?
    @State private var actionInFlight: Set<Int> = []

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            header

            if loading && approvals.isEmpty {
                ProgressView("Loading…").padding()
            } else if let e = error {
                Text("Error: \(e)").foregroundStyle(.red).padding()
            } else if approvals.isEmpty {
                emptyState
            } else {
                List(approvals) { approval in
                    ApprovalRow(
                        approval: approval,
                        inFlight: actionInFlight.contains(approval.id),
                        onApprove: { Task { await act(approval, approve: true) } },
                        onDeny: { Task { await act(approval, approve: false) } }
                    )
                }
                .listStyle(.inset)
            }
        }
        .task { await load() }
        .navigationTitle("Approvals")
        .toolbar {
            ToolbarItem {
                Button(action: { Task { await load() } }) {
                    Image(systemName: "arrow.clockwise")
                }
                .help("Refresh")
            }
        }
    }

    private var header: some View {
        HStack {
            Image(systemName: "exclamationmark.shield.fill")
                .font(.title2)
                .foregroundStyle(approvals.isEmpty ? Color.green : Color.orange)
            VStack(alignment: .leading) {
                Text("Pending Approvals")
                    .font(.title2.bold())
                Text(approvals.isEmpty
                     ? "Nothing waiting on you."
                     : "\(approvals.count) request\(approvals.count == 1 ? "" : "s") waiting.")
                    .foregroundStyle(.secondary)
                    .font(.subheadline)
            }
            Spacer()
        }
        .padding()
    }

    private var emptyState: some View {
        VStack(spacing: 16) {
            Image(systemName: "checkmark.shield.fill")
                .font(.system(size: 48))
                .foregroundStyle(.green)
            Text("All clear.")
                .font(.title3)
            Text("Charles isn't blocked on anything. He'll appear here when he needs your call.")
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 400)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding()
    }

    private func load() async {
        loading = true
        error = nil
        do {
            approvals = try await CharlesAPI.shared.approvals()
        } catch {
            self.error = error.localizedDescription
        }
        loading = false
    }

    private func act(_ approval: PendingApproval, approve: Bool) async {
        actionInFlight.insert(approval.id)
        defer { actionInFlight.remove(approval.id) }
        do {
            if approve {
                _ = try await CharlesAPI.shared.approve(factId: approval.id)
            } else {
                _ = try await CharlesAPI.shared.deny(factId: approval.id, reason: "denied via War Room")
            }
            await load()
        } catch {
            self.error = error.localizedDescription
        }
    }
}

struct ApprovalRow: View {
    let approval: PendingApproval
    let inFlight: Bool
    let onApprove: () -> Void
    let onDeny: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("#\(approval.id)")
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
                Spacer()
                Text(relativeTime(approval.createdAt))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Text(approval.fact)
                .font(.body)
                .textSelection(.enabled)
            HStack(spacing: 12) {
                Button(action: onDeny) {
                    Label("Deny", systemImage: "xmark.circle.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(.red)
                .disabled(inFlight)

                Button(action: onApprove) {
                    Label("Approve", systemImage: "checkmark.circle.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(.green)
                .disabled(inFlight)
            }
            .controlSize(.large)
        }
        .padding(.vertical, 8)
    }

    private func relativeTime(_ iso: String) -> String {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        guard let d = f.date(from: iso) else { return iso }
        let r = RelativeDateTimeFormatter()
        return r.localizedString(for: d, relativeTo: Date())
    }
}
