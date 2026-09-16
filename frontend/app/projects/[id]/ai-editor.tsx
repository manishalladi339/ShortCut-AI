import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import {
  ConstrainedEditOperation,
  ConstrainedEditProposal,
  constrainedEditsApi,
} from "@/src/api/constrainedEdits";
import { Project, projectsApi } from "@/src/api/projects";
import { ProjectState, projectStateApi } from "@/src/api/projectState";
import { Button } from "@/src/components/ui/Button";
import { colors, radius, spacing, typography } from "@/src/theme";

const EXAMPLES = [
  "Remove Speaker B",
  "Make the captions smaller in the first 10 seconds",
  "Remove B-roll from the intro",
  "Lower the music",
  "Remove captions from the ending",
];

export default function AIEditorScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();

  const [project, setProject] = useState<Project | null>(null);
  const [state, setState] = useState<ProjectState | null>(null);
  const [proposal, setProposal] = useState<ConstrainedEditProposal | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const [instruction, setInstruction] = useState("");
  const [scopeStart, setScopeStart] = useState("");
  const [scopeEnd, setScopeEnd] = useState("");
  const [loading, setLoading] = useState(true);
  const [planning, setPlanning] = useState(false);
  const [applying, setApplying] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [p, s, proposals] = await Promise.all([
        projectsApi.get(id),
        projectStateApi.get(id),
        constrainedEditsApi.list(id).catch(() => []),
      ]);
      setProject(p);
      setState(s);
      const latest = proposals.find((item) => item.status === "proposed") ?? null;
      if (latest && latest.project_state_version === s.version) {
        setProposal(latest);
        setSelectedIds(new Set(latest.operations.map((operation) => operation.id)));
      } else {
        setProposal(null);
        setSelectedIds(new Set());
      }
    } catch (e: any) {
      Alert.alert("Could not open AI Editor", e?.message ?? "Try again");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const selectedOperations = useMemo(
    () =>
      proposal?.operations.filter((operation) => selectedIds.has(operation.id)) ?? [],
    [proposal, selectedIds],
  );

  async function previewChanges() {
    if (!project || !state || instruction.trim().length < 2) return;
    const start = scopeStart.trim() ? Number(scopeStart) : undefined;
    const end = scopeEnd.trim() ? Number(scopeEnd) : undefined;
    if (start !== undefined && !Number.isFinite(start)) {
      Alert.alert("Invalid scope", "Start time must be a number of seconds.");
      return;
    }
    if (end !== undefined && !Number.isFinite(end)) {
      Alert.alert("Invalid scope", "End time must be a number of seconds.");
      return;
    }

    setPlanning(true);
    try {
      const next = await constrainedEditsApi.create(project.id, {
        instruction: instruction.trim(),
        scope_start_sec: start,
        scope_end_sec: end,
      });
      setProposal(next);
      setSelectedIds(new Set(next.operations.map((operation) => operation.id)));
    } catch (e: any) {
      Alert.alert(
        "ShortCut kept your timeline unchanged",
        e?.message ??
          "This instruction is not supported safely yet. Try speaker removal, a caption change, B-roll removal, or a music adjustment.",
      );
    } finally {
      setPlanning(false);
    }
  }

  function toggleOperation(operation: ConstrainedEditOperation) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(operation.id)) next.delete(operation.id);
      else next.add(operation.id);
      return next;
    });
  }

  async function applyChanges() {
    if (!project || !proposal || !state || selectedOperations.length === 0) return;
    setApplying(true);
    try {
      const nextState = await constrainedEditsApi.apply(project.id, proposal.id, {
        expected_version: proposal.project_state_version,
        operation_ids: selectedOperations.map((operation) => operation.id),
      });
      setState(nextState);
      setProposal({
        ...proposal,
        status: "applied",
        applied_project_state_version: nextState.version,
        applied_operation_ids: selectedOperations.map((operation) => operation.id),
        skipped_operation_ids: proposal.operations
          .filter((operation) => !selectedIds.has(operation.id))
          .map((operation) => operation.id),
      });
      Alert.alert(
        "Edit applied",
        `Only the approved localized changes were applied. Timeline is now v${nextState.version}.`,
      );
    } catch (e: any) {
      Alert.alert(
        "Edit was not applied",
        e?.message ??
          "The timeline may have changed since this proposal was created. Build a new preview.",
      );
    } finally {
      setApplying(false);
    }
  }

  if (loading || !project || !state) {
    return (
      <SafeAreaView style={styles.root} edges={["top"]}>
        <ActivityIndicator color={colors.aiAccent} style={{ marginTop: 120 }} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.root} edges={["top", "bottom"]}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={styles.iconBtn}>
          <Ionicons name="chevron-back" color={colors.textHigh} size={24} />
        </Pressable>
        <View style={{ flex: 1 }}>
          <Text style={[typography.h3, { color: colors.textHigh }]}>Create With Me</Text>
          <Text style={[typography.caption, { color: colors.aiAccent }]}>
            Constrained AI editing
          </Text>
        </View>
        <View style={styles.versionPill}>
          <Text style={[typography.caption, { color: colors.textMedium }]}>
            v{state.version}
          </Text>
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.hero}>
          <View style={styles.heroIcon}>
            <Ionicons name="chatbubble-ellipses-outline" color={colors.aiAccent} size={24} />
          </View>
          <Text style={[typography.h2, { color: colors.textHigh, marginTop: spacing.md }]}>
            Tell ShortCut what to change.
          </Text>
          <Text style={[typography.body, { color: colors.textMedium, marginTop: spacing.sm }]}>
            ShortCut previews localized operations first. Nothing changes until you approve them,
            and anything outside the requested scope is preserved.
          </Text>
        </View>

        <Text style={[typography.overline, styles.sectionTitle]}>Instruction</Text>
        <View style={styles.card}>
          <TextInput
            value={instruction}
            onChangeText={setInstruction}
            multiline
            placeholder="e.g. Remove B-roll from the intro"
            placeholderTextColor={colors.textLow}
            style={styles.textArea}
          />

          <Text style={[typography.caption, { color: colors.textMedium, marginTop: spacing.md }]}>
            Try one
          </Text>
          <View style={styles.exampleWrap}>
            {EXAMPLES.map((example) => (
              <Pressable
                key={example}
                onPress={() => setInstruction(example)}
                style={styles.exampleChip}
              >
                <Text style={[typography.caption, { color: colors.textHigh }]}>{example}</Text>
              </Pressable>
            ))}
          </View>

          <Text style={[typography.label, { color: colors.textMedium, marginTop: spacing.lg }]}>
            Optional exact scope (seconds)
          </Text>
          <View style={styles.scopeRow}>
            <TextInput
              value={scopeStart}
              onChangeText={setScopeStart}
              keyboardType="decimal-pad"
              placeholder="Start"
              placeholderTextColor={colors.textLow}
              style={styles.scopeInput}
            />
            <Text style={[typography.body, { color: colors.textLow }]}>to</Text>
            <TextInput
              value={scopeEnd}
              onChangeText={setScopeEnd}
              keyboardType="decimal-pad"
              placeholder="End"
              placeholderTextColor={colors.textLow}
              style={styles.scopeInput}
            />
          </View>

          <Button
            label="Preview exact changes"
            variant="ai"
            loading={planning}
            disabled={instruction.trim().length < 2 || applying}
            onPress={previewChanges}
            style={{ marginTop: spacing.lg }}
            iconLeft={<Ionicons name="sparkles" size={18} color="#001318" />}
          />
        </View>

        <View style={styles.safetyCard}>
          <Ionicons name="shield-checkmark-outline" color={colors.success} size={21} />
          <View style={{ flex: 1 }}>
            <Text style={[typography.bodyMed, { color: colors.textHigh }]}>
              Story edits use ripple safety
            </Text>
            <Text style={[typography.caption, { color: colors.textMedium, marginTop: spacing.xs }]}>
              Speaker removal ripples synchronized tracks atomically. If a locked or user-authored
              item would be destructively truncated, ShortCut refuses the edit instead.
            </Text>
          </View>
        </View>

        {proposal ? (
          <>
            <Text style={[typography.overline, styles.sectionTitle]}>Change preview</Text>
            <View style={styles.card}>
              <View style={styles.row}>
                <View style={styles.intentPill}>
                  <Text style={[typography.caption, { color: colors.aiAccent }]}>
                    {proposal.status.toUpperCase()}
                  </Text>
                </View>
                <Text style={[typography.caption, { color: colors.textMedium, marginLeft: "auto" }]}>
                  source v{proposal.project_state_version}
                </Text>
              </View>
              <Text style={[typography.h3, { color: colors.textHigh, marginTop: spacing.md }]}>
                {proposal.summary}
              </Text>
              <Text style={[typography.body, { color: colors.textMedium, marginTop: spacing.sm }]}>
                Scope {proposal.scope_start_sec.toFixed(2)}s–{proposal.scope_end_sec.toFixed(2)}s
              </Text>

              <View style={styles.intentWrap}>
                {proposal.interpreted_intents.map((intent) => (
                  <View key={intent} style={styles.intentPill}>
                    <Text style={[typography.caption, { color: colors.aiAccent }]}>
                      {intent.replace(/_/g, " ")}
                    </Text>
                  </View>
                ))}
              </View>
            </View>

            <Text style={[typography.overline, styles.sectionTitle]}>Preservation contract</Text>
            <View style={styles.card}>
              {proposal.preserve_rules.map((rule) => (
                <View key={rule} style={styles.preserveRow}>
                  <Ionicons name="lock-closed-outline" color={colors.success} size={16} />
                  <Text style={[typography.body, { color: colors.textHigh, flex: 1 }]}>{rule}</Text>
                </View>
              ))}
            </View>

            <Text style={[typography.overline, styles.sectionTitle]}>Approved operations</Text>
            {proposal.operations.map((operation) => {
              const selected = selectedIds.has(operation.id);
              return (
                <Pressable
                  key={operation.id}
                  onPress={() => proposal.status === "proposed" && toggleOperation(operation)}
                  disabled={proposal.status !== "proposed"}
                  style={[styles.operationCard, selected && styles.operationSelected]}
                >
                  <View style={styles.operationIcon}>
                    <Ionicons
                      name={componentIcon(operation.component)}
                      color={selected ? colors.aiAccent : colors.textMedium}
                      size={19}
                    />
                  </View>
                  <View style={{ flex: 1 }}>
                    <View style={styles.row}>
                      <Text style={[typography.bodyMed, { color: colors.textHigh, flex: 1 }]}>
                        {operationTitle(operation)}
                      </Text>
                      <Text
                        style={[
                          typography.caption,
                          { color: selected ? colors.success : colors.textLow },
                        ]}
                      >
                        {selected ? "INCLUDED" : "SKIPPED"}
                      </Text>
                    </View>
                    <Text
                      style={[
                        typography.caption,
                        { color: colors.textMedium, marginTop: spacing.xs },
                      ]}
                    >
                      {operation.reason}
                    </Text>
                  </View>
                </Pressable>
              );
            })}

            {proposal.status === "proposed" ? (
              <Button
                label={`Apply ${selectedOperations.length} approved change${
                  selectedOperations.length === 1 ? "" : "s"
                }`}
                variant="primary"
                loading={applying}
                disabled={planning || selectedOperations.length === 0}
                onPress={applyChanges}
                style={{ marginTop: spacing.md }}
                iconLeft={<Ionicons name="checkmark-circle" color="#FFFFFF" size={18} />}
              />
            ) : (
              <View style={styles.appliedCard}>
                <Ionicons name="checkmark-circle" color={colors.success} size={22} />
                <Text style={[typography.bodyMed, { color: colors.textHigh, flex: 1 }]}>
                  Applied to timeline v{proposal.applied_project_state_version ?? state.version}
                </Text>
              </View>
            )}
          </>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

function componentIcon(
  component: ConstrainedEditOperation["component"],
): keyof typeof Ionicons.glyphMap {
  if (component === "story") return "cut-outline";
  if (component === "captions") return "text-outline";
  if (component === "broll") return "layers-outline";
  return "musical-notes-outline";
}

function operationTitle(operation: ConstrainedEditOperation) {
  const action = operation.operation.replace(/_/g, " ");
  return `${operation.component.toUpperCase()} · ${action}`;
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
    gap: spacing.sm,
  },
  iconBtn: {
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
  },
  versionPill: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: radius.pill,
    backgroundColor: colors.surface2,
  },
  scroll: {
    padding: spacing.screenPadding,
    paddingBottom: 64,
    gap: spacing.md,
  },
  hero: { paddingVertical: spacing.lg },
  heroIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.aiAccentMuted,
    alignItems: "center",
    justifyContent: "center",
  },
  sectionTitle: {
    color: colors.textMedium,
    marginTop: spacing.lg,
    marginBottom: spacing.xs,
  },
  card: {
    backgroundColor: colors.surface1,
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  textArea: {
    minHeight: 108,
    borderRadius: radius.md,
    backgroundColor: colors.surface2,
    color: colors.textHigh,
    padding: spacing.md,
    textAlignVertical: "top",
    fontSize: 16,
  },
  exampleWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  exampleChip: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 7,
    borderRadius: radius.md,
    backgroundColor: colors.surface2,
    borderWidth: 1,
    borderColor: colors.border,
  },
  scopeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  scopeInput: {
    flex: 1,
    minHeight: 46,
    borderRadius: radius.md,
    backgroundColor: colors.surface2,
    color: colors.textHigh,
    paddingHorizontal: spacing.md,
    fontSize: 16,
  },
  safetyCard: {
    flexDirection: "row",
    gap: spacing.md,
    padding: spacing.lg,
    backgroundColor: "rgba(0,255,102,0.06)",
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: "rgba(0,255,102,0.35)",
  },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  intentWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  intentPill: {
    paddingHorizontal: 9,
    paddingVertical: 5,
    borderRadius: radius.pill,
    backgroundColor: colors.aiAccentMuted,
  },
  preserveRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.sm,
    paddingVertical: spacing.sm,
  },
  operationCard: {
    flexDirection: "row",
    gap: spacing.md,
    padding: spacing.md,
    backgroundColor: colors.surface1,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  operationSelected: {
    borderColor: "rgba(0,229,255,0.45)",
  },
  operationIcon: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surface2,
  },
  appliedCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.lg,
    borderRadius: radius.lg,
    backgroundColor: "rgba(0,255,102,0.06)",
    borderWidth: 1,
    borderColor: "rgba(0,255,102,0.35)",
    marginTop: spacing.md,
  },
});
