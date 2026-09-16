import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Linking,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { AIEditPlan, ProposedEditOperation, aiPlansApi } from "@/src/api/aiPlans";
import { Asset, assetsApi } from "@/src/api/assets";
import { ExportArtifact, exportsApi } from "@/src/api/exports";
import { intelligenceApi, jobsApi } from "@/src/api/intelligence";
import { Project, projectsApi } from "@/src/api/projects";
import { ProjectState, projectStateApi } from "@/src/api/projectState";
import { Button } from "@/src/components/ui/Button";
import { colors, radius, spacing, typography } from "@/src/theme";

type Phase =
  | "idle"
  | "analyzing"
  | "planning"
  | "applying"
  | "rendering";

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export default function AIDirectorScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();

  const [project, setProject] = useState<Project | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [state, setState] = useState<ProjectState | null>(null);
  const [plan, setPlan] = useState<AIEditPlan | null>(null);
  const [latestExport, setLatestExport] = useState<ExportArtifact | null>(null);

  const [objective, setObjective] = useState("");
  const [targetDuration, setTargetDuration] = useState("45");
  const [includeCaptions, setIncludeCaptions] = useState(true);
  const [removeDeadAir, setRemoveDeadAir] = useState(true);
  const [rhythmBroll, setRhythmBroll] = useState(true);
  const [replaceExisting, setReplaceExisting] = useState(false);
  const [selectedOperationIds, setSelectedOperationIds] = useState<Set<string>>(new Set());

  const [phase, setPhase] = useState<Phase>("idle");
  const [statusText, setStatusText] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [p, a, s, plans, exports] = await Promise.all([
        projectsApi.get(id),
        assetsApi.list({ project_id: id }),
        projectStateApi.get(id),
        aiPlansApi.list(id).catch(() => []),
        exportsApi.list(id).catch(() => []),
      ]);
      setProject(p);
      setAssets(a.items);
      setState(s);
      setLatestExport(exports[0] ?? null);

      setObjective((current) =>
        current ||
        p.prompt?.trim() ||
        p.description?.trim() ||
        `Create a strong ${p.content_type.replace(/_/g, " ")} edit`,
      );

      const proposed = plans.find((item) => item.status === "proposed");
      const newest = proposed ?? plans[0] ?? null;
      if (newest) {
        setPlan(newest);
        selectAllOperations(newest);
      }
    } catch (e: any) {
      Alert.alert("Could not open AI Director", e?.message ?? "Try again");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const mediaAssets = useMemo(
    () =>
      assets.filter(
        (asset) =>
          asset.kind === "video" &&
          asset.processing_status === "ready",
      ),
    [assets],
  );

  const pendingAssets = useMemo(
    () =>
      assets
        .filter((asset) => asset.kind === "video")
        .filter((asset) => asset.processing_status !== "ready"),
    [assets],
  );

  function selectAllOperations(nextPlan: AIEditPlan) {
    setSelectedOperationIds(
      new Set(
        nextPlan.operations
          .map((operation) => operation.id)
          .filter((value): value is string => Boolean(value)),
      ),
    );
  }

  async function waitForJob(jobId: string, label: string) {
    for (let attempt = 0; attempt < 150; attempt += 1) {
      const job = await jobsApi.get(jobId);
      setStatusText(`${label} · ${job.progress}%`);
      if (job.status === "succeeded") return job;
      if (job.status === "failed") {
        throw new Error(job.error_message || `${label} failed`);
      }
      await sleep(2000);
    }
    throw new Error(`${label} is taking longer than expected. You can reopen this screen to continue.`);
  }

  async function ensureIntelligence() {
    if (mediaAssets.length === 0) {
      throw new Error("Upload at least one processed video asset first.");
    }

    setPhase("analyzing");
    let completed = 0;

    for (const asset of mediaAssets) {
      setStatusText(
        `Checking ${asset.filename} · ${completed}/${mediaAssets.length} ready`,
      );

      let alreadyComplete = false;
      try {
        const intelligence = await intelligenceApi.get(asset.id);
        alreadyComplete = intelligence.status === "completed";
      } catch {
        alreadyComplete = false;
      }

      if (!alreadyComplete) {
        const analysis = await intelligenceApi.analyze(asset.id);
        await waitForJob(analysis.job_id, `Analyzing ${asset.filename}`);
      }

      completed += 1;
      setStatusText(
        `Media intelligence ready · ${completed}/${mediaAssets.length}`,
      );
    }
  }

  async function generatePlan() {
    if (!project || !state) return;
    try {
      await ensureIntelligence();
      setPhase("planning");
      setStatusText("Building a grounded story and edit plan…");

      const duration = Number(targetDuration);
      const nextPlan = await aiPlansApi.create(project.id, {
        objective: objective.trim() || undefined,
        target_duration_sec: Number.isFinite(duration)
          ? Math.max(5, Math.min(300, duration))
          : 45,
        include_captions: includeCaptions,
        remove_dead_air: removeDeadAir,
        rhythm_snap_broll: rhythmBroll,
        broll_fade: true,
        music_ducking: true,
      });

      setPlan(nextPlan);
      selectAllOperations(nextPlan);
      setStatusText("Plan ready for review.");
    } catch (e: any) {
      Alert.alert("AI Director could not build the plan", e?.message ?? "Try again");
      setStatusText("");
    } finally {
      setPhase("idle");
    }
  }

  async function rebuildPlan() {
    if (project && plan?.status === "proposed") {
      await aiPlansApi
        .feedback(project.id, plan.id, {
          outcome: "rejected",
          notes: "User requested a different plan before applying this proposal.",
        })
        .catch(() => undefined);
    }
    await generatePlan();
  }

  function toggleOperation(operation: ProposedEditOperation) {
    if (!operation.id || operation.operation === "add_clip") return;
    setSelectedOperationIds((current) => {
      const next = new Set(current);
      if (next.has(operation.id!)) next.delete(operation.id!);
      else next.add(operation.id!);
      return next;
    });
  }

  async function applyPlan() {
    if (!project || !state || !plan) return;

    const ids = plan.operations
      .filter(
        (operation) =>
          operation.operation === "add_clip" ||
          (operation.id ? selectedOperationIds.has(operation.id) : false),
      )
      .map((operation) => operation.id)
      .filter((value): value is string => Boolean(value));

    try {
      setPhase("applying");
      setStatusText("Applying approved edit decisions…");
      const nextState = await aiPlansApi.apply(project.id, plan.id, {
        expected_version: plan.project_state_version,
        replace_existing_video_clips: replaceExisting,
        operation_ids: ids,
      });

      const totalSelectable = plan.operations.filter((operation) => operation.id).length;
      const outcome = ids.length === totalSelectable ? "accepted" : "modified";
      aiPlansApi
        .feedback(project.id, plan.id, {
          outcome,
          notes:
            outcome === "modified"
              ? "User skipped one or more optional AI operations before apply."
              : "User applied the complete proposed plan.",
        })
        .catch(() => undefined);

      setState(nextState);
      setPlan({
        ...plan,
        status: "applied",
        feedback_outcome: outcome,
        applied_project_state_version: nextState.version,
      });
      setStatusText("Edit applied. Ready to render.");
    } catch (e: any) {
      Alert.alert("Could not apply AI plan", e?.message ?? "Try again");
      setStatusText("");
    } finally {
      setPhase("idle");
    }
  }

  async function renderExport() {
    if (!project || !state) return;
    try {
      setPhase("rendering");
      setStatusText("Queueing final render…");
      const queued = await exportsApi.create(project.id, {
        sequence_id: state.active_sequence_id,
        preset: "vertical_1080p",
      });
      setLatestExport(queued);
      await waitForJob(queued.job_id, "Rendering final video");
      const finished = await exportsApi.get(project.id, queued.id);
      setLatestExport(finished);
      setStatusText("Render complete.");
    } catch (e: any) {
      Alert.alert("Render failed", e?.message ?? "Try again");
      setStatusText("");
    } finally {
      setPhase("idle");
    }
  }

  if (loading || !project || !state) {
    return (
      <SafeAreaView style={styles.root} edges={["top"]}>
        <ActivityIndicator color={colors.aiAccent} style={{ marginTop: 120 }} />
      </SafeAreaView>
    );
  }

  const isBusy = phase !== "idle";
  const canBuild = mediaAssets.length > 0 && pendingAssets.length === 0;
  const timelineHasClips = hasVideoClips(state);
  const canApply =
    plan?.status === "proposed" &&
    (!timelineHasClips || replaceExisting);
  const canRender =
    Boolean(plan?.status === "applied") ||
    hasVideoClips(state);

  return (
    <SafeAreaView style={styles.root} edges={["top", "bottom"]}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={styles.iconBtn}>
          <Ionicons name="chevron-back" color={colors.textHigh} size={24} />
        </Pressable>
        <View style={{ flex: 1 }}>
          <Text style={[typography.h3, { color: colors.textHigh }]}>AI Director</Text>
          <Text style={[typography.caption, { color: colors.aiAccent }]}>
            Grounded, reviewable editing
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
            <Ionicons name="sparkles" color={colors.aiAccent} size={24} />
          </View>
          <Text style={[typography.h2, { color: colors.textHigh, marginTop: spacing.md }]}>
            Tell ShortCut what you want to make.
          </Text>
          <Text style={[typography.body, { color: colors.textMedium, marginTop: spacing.sm }]}>
            ShortCut analyzes your media, builds a story from grounded source moments, and lets you approve the edit before anything changes.
          </Text>
        </View>

        <SectionTitle title="Creative brief" />
        <View style={styles.card}>
          <Text style={[typography.label, { color: colors.textMedium }]}>Objective</Text>
          <TextInput
            value={objective}
            onChangeText={setObjective}
            multiline
            placeholder="Describe the story you want ShortCut to create"
            placeholderTextColor={colors.textLow}
            style={styles.textArea}
          />

          <Text style={[typography.label, { color: colors.textMedium, marginTop: spacing.md }]}>
            Target duration (seconds)
          </Text>
          <TextInput
            value={targetDuration}
            onChangeText={setTargetDuration}
            keyboardType="number-pad"
            placeholder="45"
            placeholderTextColor={colors.textLow}
            style={styles.input}
          />

          <ToggleRow
            label="Grounded captions"
            value={includeCaptions}
            onValueChange={setIncludeCaptions}
          />
          <ToggleRow
            label="Remove internal dead air"
            value={removeDeadAir}
            onValueChange={setRemoveDeadAir}
          />
          <ToggleRow
            label="Rhythm-aware B-roll timing"
            value={rhythmBroll}
            onValueChange={setRhythmBroll}
          />
        </View>

        <SectionTitle title="Media readiness" />
        <View style={styles.card}>
          <MetricRow
            icon="videocam-outline"
            label="Ready video"
            value={String(mediaAssets.length)}
            ok={mediaAssets.length > 0}
          />
          <MetricRow
            icon="hourglass-outline"
            label="Still processing"
            value={String(pendingAssets.length)}
            ok={pendingAssets.length === 0}
          />
          {pendingAssets.length > 0 ? (
            <Text style={[typography.caption, { color: colors.warning, marginTop: spacing.sm }]}>
              Wait for media probing to finish before analysis. Reopen this screen after processing completes.
            </Text>
          ) : null}
        </View>

        {statusText ? (
          <View style={styles.statusCard}>
            {isBusy ? <ActivityIndicator color={colors.aiAccent} /> : null}
            <Text style={[typography.bodyMed, { color: colors.textHigh, flex: 1 }]}>
              {statusText}
            </Text>
          </View>
        ) : null}

        {!plan || plan.status !== "proposed" ? (
          <Button
            label={plan?.status === "applied" ? "Generate a new AI plan" : "Analyze media & build plan"}
            variant="ai"
            loading={phase === "analyzing" || phase === "planning"}
            disabled={!canBuild || isBusy}
            onPress={generatePlan}
            iconLeft={<Ionicons name="sparkles" size={18} color="#001318" />}
          />
        ) : null}

        {plan ? (
          <>
            <SectionTitle title="Story plan" />
            <View style={styles.card}>
              <Text style={[typography.overline, { color: colors.aiAccent }]}>
                {plan.status.toUpperCase()}
              </Text>
              <Text style={[typography.h3, { color: colors.textHigh, marginTop: spacing.sm }]}>
                {plan.narrative_summary || "Grounded edit proposal"}
              </Text>
              <Text style={[typography.body, { color: colors.textMedium, marginTop: spacing.sm }]}>
                {plan.objective}
              </Text>
              <View style={styles.metricGrid}>
                <MiniMetric label="Story moments" value={String(plan.candidates.length)} />
                <MiniMetric label="Edit decisions" value={String(plan.operations.length)} />
                <MiniMetric
                  label="Target"
                  value={`${Math.round(plan.target_duration_sec)}s`}
                />
              </View>
            </View>

            {plan.project_intelligence_summary ? (
              <>
                <SectionTitle title="What ShortCut understood" />
                <View style={styles.card}>
                  <View style={styles.row}>
                    <Ionicons name="git-network-outline" color={colors.aiAccent} size={20} />
                    <Text style={[typography.bodyMed, { color: colors.textHigh, flex: 1 }]}>
                      Whole-project intelligence
                    </Text>
                  </View>
                  <Text style={[typography.body, { color: colors.textMedium, marginTop: spacing.sm }]}>
                    {plan.project_intelligence_summary}
                  </Text>
                  {plan.project_topics.length > 0 ? (
                    <View style={styles.topicWrap}>
                      {plan.project_topics.slice(0, 6).map((topic, index) => (
                        <View key={String(topic.id ?? index)} style={styles.topicPill}>
                          <Text style={[typography.caption, { color: colors.textHigh }]}>
                            {String(topic.label ?? `Topic ${index + 1}`)}
                          </Text>
                        </View>
                      ))}
                    </View>
                  ) : null}
                </View>
              </>
            ) : null}

            {plan.story_beats.length > 0 ? (
              <>
                <SectionTitle title="Story blueprint" />
                <Text style={[typography.caption, { color: colors.textMedium, marginBottom: spacing.sm }]}>
                  ShortCut structures the story first, then grounds each beat in exact source moments.
                </Text>
                {plan.story_beats.map((beat) => (
                  <View key={beat.id} style={styles.storyCard}>
                    <View style={styles.storyTop}>
                      <View style={styles.rolePill}>
                        <Text style={[typography.caption, { color: colors.aiAccent }]}>
                          {beat.role.toUpperCase()}
                        </Text>
                      </View>
                      <Text style={[typography.caption, { color: colors.textMedium }]}>
                        {beat.target_duration_sec.toFixed(1)}s · {beat.evidence_keys.length} source{beat.evidence_keys.length === 1 ? "" : "s"}
                      </Text>
                    </View>
                    <Text style={[typography.h3, { color: colors.textHigh, marginTop: spacing.sm }]}>
                      {beat.title}
                    </Text>
                    <Text style={[typography.body, { color: colors.textMedium, marginTop: spacing.xs }]}>
                      {beat.purpose}
                    </Text>
                  </View>
                ))}
              </>
            ) : null}

            <SectionTitle title="Grounded source moments" />
            {plan.candidates.map((candidate, index) => (
              <View
                key={`${candidate.asset_id}-${candidate.unit_index}-${index}`}
                style={styles.storyCard}
              >
                <View style={styles.storyTop}>
                  <View style={styles.rolePill}>
                    <Text style={[typography.caption, { color: colors.aiAccent }]}>
                      {(candidate.narrative_role || "body").toUpperCase()}
                    </Text>
                  </View>
                  <Text style={[typography.caption, { color: colors.textMedium }]}>
                    {candidate.planned_duration_sec
                      ? `${candidate.planned_duration_sec.toFixed(1)}s`
                      : `${(candidate.end - candidate.start).toFixed(1)}s`}
                  </Text>
                </View>
                <Text style={[typography.bodyMed, { color: colors.textHigh, marginTop: spacing.sm }]}>
                  “{candidate.text}”
                </Text>
                <Text style={[typography.caption, { color: colors.textMedium, marginTop: spacing.sm }]}>
                  Source {formatSeconds(candidate.start)}–{formatSeconds(candidate.end)}
                  {candidate.primary_speaker ? ` · Speaker ${candidate.primary_speaker}` : ""}
                </Text>
                <Text style={[typography.caption, { color: colors.textLow, marginTop: spacing.xs }]}>
                  {candidate.reasons.slice(0, 3).join(" · ")}
                </Text>
              </View>
            ))}

            <SectionTitle title="Review AI decisions" />
            <Text style={[typography.caption, { color: colors.textMedium, marginBottom: spacing.md }]}>
              Primary story clips stay together to preserve timing. Optional B-roll, captions and music can be excluded before applying.
            </Text>

            {plan.operations.map((operation, index) => {
              const required = operation.operation === "add_clip";
              const selected =
                required ||
                (operation.id ? selectedOperationIds.has(operation.id) : false);

              return (
                <Pressable
                  key={operation.id ?? `${operation.operation}-${index}`}
                  onPress={() => toggleOperation(operation)}
                  disabled={required || plan.status !== "proposed"}
                  style={[
                    styles.operationCard,
                    selected && styles.operationSelected,
                    required && styles.operationRequired,
                  ]}
                >
                  <View style={styles.operationIcon}>
                    <Ionicons
                      name={operationIcon(operation.operation)}
                      color={selected ? colors.aiAccent : colors.textMedium}
                      size={19}
                    />
                  </View>
                  <View style={{ flex: 1 }}>
                    <View style={styles.row}>
                      <Text style={[typography.bodyMed, { color: colors.textHigh, flex: 1 }]}>
                        {operationLabel(operation.operation)}
                      </Text>
                      <Text
                        style={[
                          typography.caption,
                          { color: required ? colors.warning : selected ? colors.success : colors.textLow },
                        ]}
                      >
                        {required ? "REQUIRED" : selected ? "INCLUDED" : "SKIPPED"}
                      </Text>
                    </View>
                    <Text style={[typography.caption, { color: colors.textMedium, marginTop: spacing.xs }]}>
                      {operation.reason}
                    </Text>
                  </View>
                </Pressable>
              );
            })}

            {plan.status === "proposed" && timelineHasClips ? (
              <View style={styles.replaceWarning}>
                <View style={{ flex: 1 }}>
                  <Text style={[typography.bodyMed, { color: colors.warning }]}>
                    Existing primary video clips detected
                  </Text>
                  <Text style={[typography.caption, { color: colors.textMedium, marginTop: spacing.xs }]}>
                    ShortCut will not replace them unless you explicitly allow it.
                  </Text>
                </View>
                <Switch
                  value={replaceExisting}
                  onValueChange={setReplaceExisting}
                  trackColor={{ false: colors.surface3, true: colors.warning }}
                />
              </View>
            ) : null}

            {plan.status === "proposed" ? (
              <View style={{ gap: spacing.sm, marginTop: spacing.lg }}>
                <Button
                  label="Apply approved edit"
                  variant="primary"
                  loading={phase === "applying"}
                  disabled={isBusy || !canApply}
                  onPress={applyPlan}
                  iconLeft={<Ionicons name="checkmark-circle" color="#FFF" size={18} />}
                />
                <Button
                  label="Build a different plan"
                  variant="secondary"
                  disabled={isBusy}
                  onPress={rebuildPlan}
                  iconLeft={<Ionicons name="refresh" color={colors.textHigh} size={18} />}
                />
              </View>
            ) : null}
          </>
        ) : null}

        {canRender ? (
          <>
            <SectionTitle title="Render" />
            <View style={styles.card}>
              <Text style={[typography.h3, { color: colors.textHigh }]}>
                Your edit is on the canonical timeline.
              </Text>
              <Text style={[typography.body, { color: colors.textMedium, marginTop: spacing.sm }]}>
                Rendering uses the exact ProjectState version shown above, so later edits cannot silently change a queued export.
              </Text>
              <Button
                label="Render vertical 1080p"
                variant="ai"
                loading={phase === "rendering"}
                disabled={isBusy}
                onPress={renderExport}
                style={{ marginTop: spacing.lg }}
                iconLeft={<Ionicons name="play" color="#001318" size={18} />}
              />
            </View>
          </>
        ) : null}

        {latestExport ? (
          <>
            <SectionTitle title="Latest export" />
            <View style={styles.card}>
              <View style={styles.row}>
                <View style={{ flex: 1 }}>
                  <Text style={[typography.bodyMed, { color: colors.textHigh }]}>
                    {latestExport.preset.replace(/_/g, " ")}
                  </Text>
                  <Text style={[typography.caption, { color: colors.textMedium, marginTop: spacing.xs }]}>
                    {latestExport.status} · state v{latestExport.project_state_version}
                  </Text>
                </View>
                <StatusDot ok={latestExport.status === "completed"} />
              </View>
              {latestExport.download_url ? (
                <Button
                  label="Open finished video"
                  variant="secondary"
                  onPress={() => Linking.openURL(latestExport.download_url!)}
                  style={{ marginTop: spacing.md }}
                  iconLeft={<Ionicons name="open-outline" color={colors.textHigh} size={18} />}
                />
              ) : null}
            </View>
          </>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

function hasVideoClips(state: ProjectState) {
  const sequence = state.sequences.find((item) => item.id === state.active_sequence_id);
  return Boolean(
    sequence?.tracks.some(
      (track) => track.kind === "video" && track.clips.length > 0,
    ),
  );
}

function ToggleRow({
  label,
  value,
  onValueChange,
}: {
  label: string;
  value: boolean;
  onValueChange: (value: boolean) => void;
}) {
  return (
    <View style={styles.toggleRow}>
      <Text style={[typography.body, { color: colors.textHigh, flex: 1 }]}>{label}</Text>
      <Switch
        value={value}
        onValueChange={onValueChange}
        trackColor={{ false: colors.surface3, true: colors.aiAccent }}
      />
    </View>
  );
}

function SectionTitle({ title }: { title: string }) {
  return (
    <Text style={[typography.overline, styles.sectionTitle]}>
      {title}
    </Text>
  );
}

function MetricRow({
  icon,
  label,
  value,
  ok,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  value: string;
  ok: boolean;
}) {
  return (
    <View style={styles.metricRow}>
      <Ionicons name={icon} color={ok ? colors.success : colors.warning} size={18} />
      <Text style={[typography.body, { color: colors.textHigh, flex: 1 }]}>{label}</Text>
      <Text style={[typography.bodyMed, { color: ok ? colors.success : colors.warning }]}>
        {value}
      </Text>
    </View>
  );
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.miniMetric}>
      <Text style={[typography.h3, { color: colors.textHigh }]}>{value}</Text>
      <Text style={[typography.caption, { color: colors.textMedium }]}>{label}</Text>
    </View>
  );
}

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <View
      style={[
        styles.statusDot,
        { backgroundColor: ok ? colors.success : colors.warning },
      ]}
    />
  );
}

function operationLabel(operation: string) {
  const labels: Record<string, string> = {
    add_clip: "Story clip",
    add_broll_overlay: "B-roll overlay",
    add_caption: "Grounded caption",
    add_music_bed: "Music bed",
  };
  return labels[operation] ?? operation.replace(/_/g, " ");
}

function operationIcon(operation: string): keyof typeof Ionicons.glyphMap {
  const icons: Record<string, keyof typeof Ionicons.glyphMap> = {
    add_clip: "cut-outline",
    add_broll_overlay: "layers-outline",
    add_caption: "text-outline",
    add_music_bed: "musical-notes-outline",
  };
  return icons[operation] ?? "sparkles-outline";
}

function formatSeconds(value: number) {
  const total = Math.max(0, Math.floor(value));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
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
  hero: {
    paddingVertical: spacing.lg,
  },
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
    marginTop: spacing.sm,
    minHeight: 112,
    borderRadius: radius.md,
    backgroundColor: colors.surface2,
    color: colors.textHigh,
    padding: spacing.md,
    textAlignVertical: "top",
    fontSize: 16,
  },
  input: {
    marginTop: spacing.sm,
    minHeight: 48,
    borderRadius: radius.md,
    backgroundColor: colors.surface2,
    color: colors.textHigh,
    paddingHorizontal: spacing.md,
    fontSize: 16,
  },
  toggleRow: {
    minHeight: 54,
    flexDirection: "row",
    alignItems: "center",
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
    marginTop: spacing.md,
    paddingTop: spacing.sm,
  },
  metricRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    minHeight: 38,
  },
  statusCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.lg,
    backgroundColor: colors.aiAccentMuted,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.aiAccent,
  },
  metricGrid: {
    flexDirection: "row",
    gap: spacing.sm,
    marginTop: spacing.lg,
  },
  miniMetric: {
    flex: 1,
    backgroundColor: colors.surface2,
    padding: spacing.md,
    borderRadius: radius.md,
  },
  storyCard: {
    backgroundColor: colors.surface1,
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  storyTop: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  rolePill: {
    paddingHorizontal: 9,
    paddingVertical: 5,
    borderRadius: radius.pill,
    backgroundColor: colors.aiAccentMuted,
  },
  topicWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  topicPill: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: radius.pill,
    backgroundColor: colors.surface2,
    borderWidth: 1,
    borderColor: colors.border,
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
  operationRequired: {
    backgroundColor: "rgba(255,214,10,0.04)",
  },
  operationIcon: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surface2,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  statusDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  replaceWarning: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.warning,
    backgroundColor: "rgba(255,214,10,0.06)",
    marginTop: spacing.md,
  },
});
