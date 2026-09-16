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
  View,
  useWindowDimensions,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { WebView } from "react-native-webview";

import { Asset, assetsApi } from "@/src/api/assets";
import { ExportArtifact, exportsApi } from "@/src/api/exports";
import {
  ProjectCaptionCue,
  ProjectClip,
  ProjectSequence,
  ProjectState,
  ProjectTrack,
  projectStateApi,
} from "@/src/api/projectState";
import { Project, projectsApi } from "@/src/api/projects";
import { Button } from "@/src/components/ui/Button";
import { colors, radius, spacing, typography } from "@/src/theme";

const LABEL_WIDTH = 92;
const RULER_HEIGHT = 34;
const LANE_HEIGHT = 62;
const MIN_BLOCK_WIDTH = 26;

type Selection =
  | { kind: "clip"; track: ProjectTrack; clip: ProjectClip }
  | { kind: "caption"; cue: ProjectCaptionCue };

export default function TimelineReviewScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { width: windowWidth } = useWindowDimensions();

  const [project, setProject] = useState<Project | null>(null);
  const [state, setState] = useState<ProjectState | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [exports, setExports] = useState<ExportArtifact[]>([]);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [pixelsPerSecond, setPixelsPerSecond] = useState(28);
  const [loading, setLoading] = useState(true);
  const [rendering, setRendering] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [p, s, a, e] = await Promise.all([
        projectsApi.get(id),
        projectStateApi.get(id),
        assetsApi
          .list({ project_id: id })
          .catch(() => ({ items: [], next_cursor: null, has_more: false })),
        exportsApi.list(id).catch(() => []),
      ]);
      setProject(p);
      setState(s);
      setAssets(a.items);
      setExports(e);
      setSelection(null);
    } catch (error: any) {
      Alert.alert("Could not load timeline", error?.message ?? "Try again");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const sequence = useMemo(
    () =>
      state?.sequences.find(
        (item) => item.id === state.active_sequence_id,
      ) ?? null,
    [state],
  );

  const assetById = useMemo(
    () => new Map(assets.map((asset) => [asset.id, asset])),
    [assets],
  );

  const latestCompletedExport = useMemo(() => {
    if (!state) return null;
    const current = exports.find(
      (item) =>
        item.status === "completed" &&
        item.download_url &&
        item.project_state_version === state.version,
    );
    return (
      current ??
      exports.find(
        (item) => item.status === "completed" && item.download_url,
      ) ??
      null
    );
  }, [exports, state]);

  const durationSec = useMemo(
    () => (sequence ? sequenceDurationSec(sequence) : 0),
    [sequence],
  );

  const canvasWidth = Math.max(
    Math.max(320, windowWidth - LABEL_WIDTH - spacing.screenPadding * 2),
    durationSec * pixelsPerSecond,
  );

  async function renderCurrentTimeline() {
    if (!project || !sequence) return;
    setRendering(true);
    try {
      let artifact = await exportsApi.create(project.id, {
        sequence_id: sequence.id,
        preset: "vertical_1080p",
      });
      setExports((current) => upsertExport(current, artifact));

      for (let attempt = 0; attempt < 90; attempt += 1) {
        if (artifact.status === "completed") {
          setRendering(false);
          return;
        }
        if (artifact.status === "failed") {
          throw new Error("The render worker could not complete this preview.");
        }
        await sleep(2000);
        artifact = await exportsApi.get(project.id, artifact.id);
        setExports((current) => upsertExport(current, artifact));
      }

      Alert.alert(
        "Render is still processing",
        "The export is continuing in the render queue. Reopen the timeline to check it.",
      );
    } catch (error: any) {
      Alert.alert("Preview render failed", error?.message ?? "Try again");
    } finally {
      setRendering(false);
    }
  }

  function openAIEdit(instruction: string, startSec: number, endSec: number) {
    if (!project) return;
    router.push({
      pathname: "/projects/[id]/ai-editor",
      params: {
        id: project.id,
        instruction,
        scope_start: startSec.toFixed(3),
        scope_end: endSec.toFixed(3),
      },
    } as any);
  }

  if (loading || !project || !state || !sequence) {
    return (
      <SafeAreaView style={styles.root} edges={["top"]}>
        <ActivityIndicator color={colors.aiAccent} style={{ marginTop: 120 }} />
      </SafeAreaView>
    );
  }

  const exportIsCurrent =
    latestCompletedExport?.project_state_version === state.version;

  return (
    <SafeAreaView style={styles.root} edges={["top", "bottom"]}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={styles.iconButton}>
          <Ionicons name="chevron-back" color={colors.textHigh} size={24} />
        </Pressable>
        <View style={{ flex: 1 }}>
          <Text style={[typography.h3, { color: colors.textHigh }]}>
            Timeline
          </Text>
          <Text style={[typography.caption, { color: colors.textMedium }]}>
            {sequence.name} · v{state.version} · {formatTime(durationSec)}
          </Text>
        </View>
        <View style={styles.versionPill}>
          <Ionicons name="git-branch-outline" color={colors.aiAccent} size={14} />
          <Text style={[typography.caption, { color: colors.textHigh }]}>
            v{state.version}
          </Text>
        </View>
      </View>

      <ScrollView
        contentContainerStyle={styles.page}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.previewCard}>
          <View style={styles.sectionHeader}>
            <View style={{ flex: 1 }}>
              <Text style={[typography.overline, { color: colors.textMedium }]}>
                Rendered preview
              </Text>
              <Text
                style={[
                  typography.bodyMed,
                  { color: colors.textHigh, marginTop: spacing.xs },
                ]}
              >
                {latestCompletedExport
                  ? exportIsCurrent
                    ? "Current timeline render"
                    : `Preview from timeline v${latestCompletedExport.project_state_version}`
                  : "No preview rendered yet"}
              </Text>
            </View>
            {latestCompletedExport?.qa_status ? (
              <View
                style={[
                  styles.statusPill,
                  {
                    borderColor: qaColor(latestCompletedExport.qa_status),
                  },
                ]}
              >
                <Text
                  style={[
                    typography.caption,
                    { color: qaColor(latestCompletedExport.qa_status) },
                  ]}
                >
                  QA {latestCompletedExport.qa_status.toUpperCase()}
                </Text>
              </View>
            ) : null}
          </View>

          {latestCompletedExport?.download_url ? (
            <View style={styles.playerFrame}>
              <WebView
                source={{
                  html: videoPlayerHtml(latestCompletedExport.download_url),
                }}
                originWhitelist={["*"]}
                allowsInlineMediaPlayback
                mediaPlaybackRequiresUserAction
                scrollEnabled={false}
                style={styles.webview}
              />
            </View>
          ) : (
            <View style={styles.previewEmpty}>
              <Ionicons
                name="play-circle-outline"
                color={colors.textLow}
                size={42}
              />
              <Text
                style={[
                  typography.body,
                  { color: colors.textMedium, marginTop: spacing.sm },
                ]}
              >
                Render the canonical timeline to review the actual output here.
              </Text>
            </View>
          )}

          {!exportIsCurrent && latestCompletedExport ? (
            <View style={styles.warningRow}>
              <Ionicons
                name="warning-outline"
                color={colors.warning}
                size={18}
              />
              <Text
                style={[typography.caption, { color: colors.textMedium, flex: 1 }]}
              >
                The timeline changed after this preview. Render v{state.version} before
                judging the current edit.
              </Text>
            </View>
          ) : null}

          <Button
            label={exportIsCurrent ? "Re-render current timeline" : "Render current timeline"}
            variant="secondary"
            loading={rendering}
            disabled={rendering}
            onPress={renderCurrentTimeline}
            style={{ marginTop: spacing.md }}
            iconLeft={
              <Ionicons name="refresh-outline" color={colors.textHigh} size={18} />
            }
          />
        </View>

        <View style={styles.timelineCard}>
          <View style={styles.sectionHeader}>
            <View style={{ flex: 1 }}>
              <Text style={[typography.overline, { color: colors.textMedium }]}>
                Canonical ProjectState
              </Text>
              <Text
                style={[
                  typography.body,
                  { color: colors.textMedium, marginTop: spacing.xs },
                ]}
              >
                Tap any block to inspect its source and refine that exact range with AI.
              </Text>
            </View>
            <View style={styles.zoomControls}>
              <Pressable
                style={styles.zoomButton}
                onPress={() =>
                  setPixelsPerSecond((current) => Math.max(8, current / 1.5))
                }
              >
                <Ionicons name="remove" color={colors.textHigh} size={18} />
              </Pressable>
              <Pressable
                style={styles.zoomButton}
                onPress={() =>
                  setPixelsPerSecond((current) => Math.min(90, current * 1.5))
                }
              >
                <Ionicons name="add" color={colors.textHigh} size={18} />
              </Pressable>
            </View>
          </View>

          <View style={styles.timelineShell}>
            <View style={styles.trackLabels}>
              <View style={[styles.rulerLabel, { height: RULER_HEIGHT }]}>
                <Text style={[typography.caption, { color: colors.textLow }]}>
                  TIME
                </Text>
              </View>
              {sequence.tracks.map((track) => (
                <View
                  key={track.id}
                  style={[styles.trackLabel, { height: LANE_HEIGHT }]}
                >
                  <Ionicons
                    name={trackIcon(track.kind)}
                    color={trackColor(track.kind)}
                    size={16}
                  />
                  <Text
                    style={[typography.caption, { color: colors.textHigh }]}
                    numberOfLines={1}
                  >
                    {track.name}
                  </Text>
                  <View style={styles.trackFlags}>
                    {track.locked ? (
                      <Ionicons
                        name="lock-closed"
                        color={colors.textLow}
                        size={11}
                      />
                    ) : null}
                    {track.muted ? (
                      <Ionicons
                        name="volume-mute"
                        color={colors.textLow}
                        size={12}
                      />
                    ) : null}
                  </View>
                </View>
              ))}
              <View style={[styles.trackLabel, { height: LANE_HEIGHT }]}>
                <Ionicons name="text-outline" color={colors.textMedium} size={16} />
                <Text style={[typography.caption, { color: colors.textHigh }]}>
                  Captions
                </Text>
              </View>
            </View>

            <ScrollView
              horizontal
              showsHorizontalScrollIndicator
              contentContainerStyle={{ width: canvasWidth }}
            >
              <View style={{ width: canvasWidth }}>
                <TimeRuler
                  durationSec={durationSec}
                  pixelsPerSecond={pixelsPerSecond}
                  width={canvasWidth}
                />
                {sequence.tracks.map((track) => (
                  <TrackLane
                    key={track.id}
                    track={track}
                    sequence={sequence}
                    pixelsPerSecond={pixelsPerSecond}
                    width={canvasWidth}
                    assetById={assetById}
                    selected={selection}
                    onSelect={(clip) =>
                      setSelection({ kind: "clip", track, clip })
                    }
                  />
                ))}
                <CaptionLane
                  sequence={sequence}
                  pixelsPerSecond={pixelsPerSecond}
                  width={canvasWidth}
                  selected={selection}
                  onSelect={(cue) => setSelection({ kind: "caption", cue })}
                />
              </View>
            </ScrollView>
          </View>
        </View>

        {selection ? (
          <SelectionInspector
            selection={selection}
            sequence={sequence}
            assetById={assetById}
            onAIEdit={openAIEdit}
            onClear={() => setSelection(null)}
          />
        ) : (
          <View style={styles.inspectorEmpty}>
            <Ionicons name="scan-outline" color={colors.textLow} size={24} />
            <Text
              style={[
                typography.body,
                { color: colors.textMedium, marginLeft: spacing.md, flex: 1 },
              ]}
            >
              Select a timeline block to inspect exactly what ShortCut placed there.
            </Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function TrackLane({
  track,
  sequence,
  pixelsPerSecond,
  width,
  assetById,
  selected,
  onSelect,
}: {
  track: ProjectTrack;
  sequence: ProjectSequence;
  pixelsPerSecond: number;
  width: number;
  assetById: Map<string, Asset>;
  selected: Selection | null;
  onSelect: (clip: ProjectClip) => void;
}) {
  const tps = ticksPerSecond(sequence);
  return (
    <View style={[styles.lane, { width, height: LANE_HEIGHT }]}>
      {track.clips.map((clip) => {
        const startSec = clip.timeline_start / tps;
        const duration = clip.duration / tps;
        const left = startSec * pixelsPerSecond;
        const blockWidth = Math.max(MIN_BLOCK_WIDTH, duration * pixelsPerSecond);
        const isSelected =
          selected?.kind === "clip" && selected.clip.id === clip.id;
        const asset = assetById.get(clip.asset_id);

        return (
          <Pressable
            key={clip.id}
            onPress={() => onSelect(clip)}
            style={[
              styles.clipBlock,
              {
                left,
                width: blockWidth,
                borderColor: trackColor(track.kind),
                backgroundColor: trackFill(track.kind),
              },
              isSelected && styles.selectedBlock,
            ]}
          >
            <Text
              style={[typography.caption, { color: colors.textHigh }]}
              numberOfLines={1}
            >
              {clipTitle(track, clip, asset)}
            </Text>
            <Text
              style={[styles.tinyText, { color: colors.textMedium }]}
              numberOfLines={1}
            >
              {formatTime(duration)}
              {clip.playback_rate && Math.abs(clip.playback_rate - 1) > 0.01
                ? ` · ${clip.playback_rate.toFixed(2)}x`
                : ""}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

function CaptionLane({
  sequence,
  pixelsPerSecond,
  width,
  selected,
  onSelect,
}: {
  sequence: ProjectSequence;
  pixelsPerSecond: number;
  width: number;
  selected: Selection | null;
  onSelect: (cue: ProjectCaptionCue) => void;
}) {
  const tps = ticksPerSecond(sequence);
  return (
    <View style={[styles.lane, { width, height: LANE_HEIGHT }]}>
      {sequence.captions.map((cue) => {
        const left = (cue.start / tps) * pixelsPerSecond;
        const blockWidth = Math.max(
          MIN_BLOCK_WIDTH,
          (cue.duration / tps) * pixelsPerSecond,
        );
        const isSelected =
          selected?.kind === "caption" && selected.cue.id === cue.id;
        return (
          <Pressable
            key={cue.id}
            onPress={() => onSelect(cue)}
            style={[
              styles.clipBlock,
              {
                left,
                width: blockWidth,
                borderColor: colors.textMedium,
                backgroundColor: colors.surface3,
              },
              isSelected && styles.selectedBlock,
            ]}
          >
            <Text
              style={[typography.caption, { color: colors.textHigh }]}
              numberOfLines={2}
            >
              {cue.text}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

function TimeRuler({
  durationSec,
  pixelsPerSecond,
  width,
}: {
  durationSec: number;
  pixelsPerSecond: number;
  width: number;
}) {
  const step = rulerStep(pixelsPerSecond);
  const markers = Array.from(
    { length: Math.ceil(durationSec / step) + 1 },
    (_, index) => index * step,
  ).filter((value) => value <= durationSec + 0.001);

  return (
    <View style={[styles.ruler, { width, height: RULER_HEIGHT }]}>
      {markers.map((value) => (
        <View
          key={value}
          style={[styles.rulerMark, { left: value * pixelsPerSecond }]}
        >
          <View style={styles.rulerTick} />
          <Text style={styles.rulerText}>{formatTime(value)}</Text>
        </View>
      ))}
    </View>
  );
}

function SelectionInspector({
  selection,
  sequence,
  assetById,
  onAIEdit,
  onClear,
}: {
  selection: Selection;
  sequence: ProjectSequence;
  assetById: Map<string, Asset>;
  onAIEdit: (instruction: string, startSec: number, endSec: number) => void;
  onClear: () => void;
}) {
  const tps = ticksPerSecond(sequence);
  const isClip = selection.kind === "clip";
  const startSec = isClip
    ? selection.clip.timeline_start / tps
    : selection.cue.start / tps;
  const durationSec = isClip
    ? selection.clip.duration / tps
    : selection.cue.duration / tps;
  const endSec = startSec + durationSec;

  const asset =
    isClip ? assetById.get(selection.clip.asset_id) ?? null : null;
  const metadata = isClip ? selection.clip.metadata ?? {} : selection.cue.style ?? {};

  return (
    <View style={styles.inspector}>
      <View style={styles.sectionHeader}>
        <View style={{ flex: 1 }}>
          <Text style={[typography.overline, { color: colors.textMedium }]}>
            Selected {isClip ? selection.track.kind : "caption"}
          </Text>
          <Text
            style={[
              typography.h3,
              { color: colors.textHigh, marginTop: spacing.xs },
            ]}
            numberOfLines={2}
          >
            {isClip
              ? asset?.filename ?? selection.clip.asset_id
              : selection.cue.text}
          </Text>
        </View>
        <Pressable onPress={onClear} style={styles.closeButton}>
          <Ionicons name="close" color={colors.textMedium} size={20} />
        </Pressable>
      </View>

      <View style={styles.detailGrid}>
        <Detail label="Timeline" value={`${formatTime(startSec)}–${formatTime(endSec)}`} />
        <Detail label="Duration" value={formatTime(durationSec)} />
        {isClip ? (
          <>
            <Detail
              label="Source"
              value={`${formatTime(selection.clip.source_start / tps)}–${formatTime(
                (selection.clip.source_start + selection.clip.source_duration) / tps,
              )}`}
            />
            <Detail
              label="Speed"
              value={`${(selection.clip.playback_rate || 1).toFixed(2)}x`}
            />
          </>
        ) : null}
      </View>

      <View style={styles.metadataWrap}>
        {metadata.primary_speaker ? (
          <MetaChip label={humanSpeaker(String(metadata.primary_speaker))} />
        ) : null}
        {metadata.narrative_role ? (
          <MetaChip label={titleCase(String(metadata.narrative_role))} />
        ) : null}
        {metadata.broll ? <MetaChip label="AI B-roll" /> : null}
        {metadata.semantic_replacement ? (
          <MetaChip label="Semantic replacement" />
        ) : null}
        {metadata.pacing_retimed ? <MetaChip label="Retimed" /> : null}
        {isClip && (selection.clip.transform as any)?.keyframes?.length ? (
          <MetaChip
            label={`Motion · ${(selection.clip.transform as any).keyframes.length} keyframes`}
          />
        ) : null}
        {isClip && selection.clip.transition_in ? (
          <MetaChip
            label={`In · ${titleCase(String((selection.clip.transition_in as any).kind))}`}
          />
        ) : null}
        {isClip && selection.clip.transition_out ? (
          <MetaChip
            label={`Out · ${titleCase(String((selection.clip.transition_out as any).kind))}`}
          />
        ) : null}
        {!isClip && metadata.preset ? (
          <MetaChip label={`Caption preset · ${titleCase(String(metadata.preset))}`} />
        ) : null}
        {!isClip && metadata.animation && metadata.animation !== "none" ? (
          <MetaChip label={`Animation · ${titleCase(String(metadata.animation))}`} />
        ) : null}
        {metadata.reframe ? (
          <MetaChip
            label={`Smart reframe · ${Math.round(
              Number(metadata.reframe.confidence ?? 0) * 100,
            )}%`}
          />
        ) : null}
        {metadata.qa_repaired ? <MetaChip label="QA repaired" /> : null}
        {metadata.ai_plan_id ? <MetaChip label="AI planned" /> : null}
      </View>

      <View style={styles.quickActions}>
        {isClip && selection.track.kind === "video" ? (
          <>
            <QuickAction
              icon="speedometer-outline"
              label="Tighten pacing"
              onPress={() =>
                onAIEdit("Make this section faster", startSec, endSec)
              }
            />
            <QuickAction
              icon="expand-outline"
              label="Slow push-in"
              onPress={() =>
                onAIEdit("Add a subtle push-in to this shot", startSec, endSec)
              }
            />
            <QuickAction
              icon="arrow-forward-outline"
              label="Slide in"
              onPress={() =>
                onAIEdit("Slide this shot in from the left", startSec, endSec)
              }
            />
            <QuickAction
              icon="remove-outline"
              label="Fade out"
              onPress={() =>
                onAIEdit("Fade this shot out", startSec, endSec)
              }
            />
            {metadata.primary_speaker ? (
              <QuickAction
                icon="person-remove-outline"
                label={`Remove ${humanSpeaker(String(metadata.primary_speaker))}`}
                onPress={() =>
                  onAIEdit(
                    `Remove ${humanSpeaker(String(metadata.primary_speaker))}`,
                    startSec,
                    endSec,
                  )
                }
              />
            ) : null}
          </>
        ) : null}

        {isClip && selection.track.kind === "overlay" ? (
          <>
            <QuickAction
              icon="images-outline"
              label="Replace B-roll"
              onPress={() =>
                onAIEdit("Replace B-roll in this section", startSec, endSec)
              }
            />
            <QuickAction
              icon="remove-outline"
              label="Fade B-roll out"
              onPress={() =>
                onAIEdit("Fade the B-roll out", startSec, endSec)
              }
            />
            <QuickAction
              icon="trash-outline"
              label="Remove B-roll"
              onPress={() =>
                onAIEdit("Remove B-roll from this section", startSec, endSec)
              }
            />
          </>
        ) : null}

        {isClip && selection.track.kind === "audio" ? (
          <>
            <QuickAction
              icon="volume-low-outline"
              label="Lower music"
              onPress={() => onAIEdit("Lower the music", startSec, endSec)}
            />
            <QuickAction
              icon="volume-mute-outline"
              label="Remove music"
              onPress={() => onAIEdit("Remove music", startSec, endSec)}
            />
          </>
        ) : null}

        {!isClip ? (
          <>
            <QuickAction
              icon="text-outline"
              label="Smaller captions"
              onPress={() =>
                onAIEdit("Make the captions smaller", startSec, endSec)
              }
            />
            <QuickAction
              icon="trash-outline"
              label="Remove caption"
              onPress={() =>
                onAIEdit("Remove captions from this section", startSec, endSec)
              }
            />
          </>
        ) : null}
      </View>
    </View>
  );
}

function QuickAction({
  icon,
  label,
  onPress,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable style={styles.quickAction} onPress={onPress}>
      <Ionicons name={icon} color={colors.aiAccent} size={18} />
      <Text style={[typography.caption, { color: colors.textHigh }]}>
        {label}
      </Text>
    </Pressable>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.detailCell}>
      <Text style={[typography.caption, { color: colors.textLow }]}>{label}</Text>
      <Text
        style={[
          typography.bodyMed,
          { color: colors.textHigh, marginTop: spacing.xs },
        ]}
      >
        {value}
      </Text>
    </View>
  );
}

function MetaChip({ label }: { label: string }) {
  return (
    <View style={styles.metaChip}>
      <Text style={[typography.caption, { color: colors.textHigh }]}>{label}</Text>
    </View>
  );
}

function ticksPerSecond(sequence: ProjectSequence) {
  return (
    sequence.timebase.numerator /
    Math.max(1, sequence.timebase.denominator)
  );
}

function sequenceDurationSec(sequence: ProjectSequence) {
  const tps = ticksPerSecond(sequence);
  const ends = [
    ...sequence.tracks.flatMap((track) =>
      track.clips.map((clip) => clip.timeline_start + clip.duration),
    ),
    ...sequence.captions.map((cue) => cue.start + cue.duration),
    0,
  ];
  return Math.max(...ends) / tps;
}

function clipTitle(
  track: ProjectTrack,
  clip: ProjectClip,
  asset?: Asset,
) {
  if (track.kind === "overlay" && clip.metadata?.broll) {
    return asset?.filename ? `B-roll · ${asset.filename}` : "AI B-roll";
  }
  if (track.kind === "audio" && clip.metadata?.music_bed) {
    return asset?.filename ? `Music · ${asset.filename}` : "Music bed";
  }
  return asset?.filename ?? clip.asset_id;
}

function rulerStep(pixelsPerSecond: number) {
  const desiredSeconds = 82 / pixelsPerSecond;
  return (
    [1, 2, 5, 10, 15, 30, 60, 120, 300].find(
      (value) => value >= desiredSeconds,
    ) ?? 300
  );
}

function formatTime(seconds: number) {
  const safe = Math.max(0, seconds);
  const minutes = Math.floor(safe / 60);
  const remainder = safe - minutes * 60;
  if (safe < 60) return `${remainder.toFixed(1)}s`;
  return `${minutes}:${remainder.toFixed(1).padStart(4, "0")}`;
}

function trackIcon(kind: ProjectTrack["kind"]): keyof typeof Ionicons.glyphMap {
  if (kind === "video") return "videocam-outline";
  if (kind === "overlay") return "layers-outline";
  if (kind === "audio") return "musical-notes-outline";
  return "text-outline";
}

function trackColor(kind: ProjectTrack["kind"]) {
  if (kind === "video") return colors.primary;
  if (kind === "overlay") return colors.aiAccent;
  if (kind === "audio") return colors.warning;
  return colors.textMedium;
}

function trackFill(kind: ProjectTrack["kind"]) {
  if (kind === "video") return colors.primaryMuted;
  if (kind === "overlay") return colors.aiAccentMuted;
  if (kind === "audio") return "rgba(255, 214, 10, 0.12)";
  return colors.surface3;
}

function qaColor(status: "passed" | "warnings" | "failed") {
  if (status === "passed") return colors.success;
  if (status === "failed") return colors.danger;
  return colors.warning;
}

function humanSpeaker(value: string) {
  const match = value.match(/^speaker_(\d+)$/i);
  if (!match) return titleCase(value);
  const index = Number(match[1]);
  if (index >= 0 && index < 26) {
    return `Speaker ${String.fromCharCode(65 + index)}`;
  }
  return `Speaker ${index + 1}`;
}

function titleCase(value: string) {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function videoPlayerHtml(url: string) {
  const safe = url
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return `<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<style>
html,body{margin:0;padding:0;width:100%;height:100%;background:#000;overflow:hidden}
video{width:100%;height:100%;object-fit:contain;background:#000}
</style>
</head>
<body>
<video src="${safe}" controls playsinline preload="metadata"></video>
</body>
</html>`;
}

function upsertExport(
  current: ExportArtifact[],
  next: ExportArtifact,
): ExportArtifact[] {
  return [next, ...current.filter((item) => item.id !== next.id)];
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  iconButton: {
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
  },
  versionPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingHorizontal: 9,
    paddingVertical: 6,
    borderRadius: radius.pill,
    backgroundColor: colors.aiAccentMuted,
  },
  page: {
    padding: spacing.screenPadding,
    paddingBottom: 72,
    gap: spacing.xl,
  },
  previewCard: {
    padding: spacing.lg,
    borderRadius: radius.lg,
    backgroundColor: colors.surface1,
    borderWidth: 1,
    borderColor: colors.border,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.md,
  },
  statusPill: {
    borderWidth: 1,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 5,
  },
  playerFrame: {
    height: 260,
    marginTop: spacing.md,
    borderRadius: radius.md,
    overflow: "hidden",
    backgroundColor: "#000000",
    borderWidth: 1,
    borderColor: colors.border,
  },
  webview: {
    flex: 1,
    backgroundColor: "#000000",
  },
  previewEmpty: {
    height: 170,
    marginTop: spacing.md,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.xl,
    borderRadius: radius.md,
    backgroundColor: colors.surface2,
  },
  warningRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.sm,
    marginTop: spacing.md,
    padding: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: "rgba(255, 214, 10, 0.08)",
  },
  timelineCard: {
    paddingVertical: spacing.lg,
    borderRadius: radius.lg,
    backgroundColor: colors.surface1,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: "hidden",
  },
  timelineShell: {
    flexDirection: "row",
    marginTop: spacing.lg,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  trackLabels: {
    width: LABEL_WIDTH,
    backgroundColor: colors.surface2,
    borderRightWidth: StyleSheet.hairlineWidth,
    borderRightColor: colors.border,
    zIndex: 2,
  },
  rulerLabel: {
    justifyContent: "center",
    paddingHorizontal: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  trackLabel: {
    justifyContent: "center",
    gap: 3,
    paddingHorizontal: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  trackFlags: {
    flexDirection: "row",
    gap: 4,
  },
  ruler: {
    position: "relative",
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
    backgroundColor: colors.surface2,
  },
  rulerMark: {
    position: "absolute",
    top: 0,
    height: RULER_HEIGHT,
    minWidth: 50,
  },
  rulerTick: {
    width: 1,
    height: 8,
    backgroundColor: colors.textLow,
  },
  rulerText: {
    ...typography.caption,
    color: colors.textLow,
    marginTop: 2,
    marginLeft: 3,
  },
  lane: {
    position: "relative",
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
    backgroundColor: colors.bg,
  },
  clipBlock: {
    position: "absolute",
    top: 7,
    height: LANE_HEIGHT - 14,
    borderRadius: radius.sm,
    borderWidth: 1,
    paddingHorizontal: 7,
    paddingVertical: 5,
    overflow: "hidden",
  },
  selectedBlock: {
    borderWidth: 2,
    borderColor: colors.success,
  },
  tinyText: {
    fontSize: 10,
    lineHeight: 13,
    fontWeight: "500",
  },
  zoomControls: {
    flexDirection: "row",
    gap: spacing.xs,
    marginRight: spacing.lg,
  },
  zoomButton: {
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surface2,
    borderWidth: 1,
    borderColor: colors.border,
  },
  inspector: {
    padding: spacing.lg,
    borderRadius: radius.lg,
    backgroundColor: colors.surface1,
    borderWidth: 1,
    borderColor: colors.aiAccent,
  },
  inspectorEmpty: {
    flexDirection: "row",
    alignItems: "center",
    padding: spacing.lg,
    borderRadius: radius.lg,
    backgroundColor: colors.surface1,
    borderWidth: 1,
    borderColor: colors.border,
  },
  closeButton: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 18,
    backgroundColor: colors.surface2,
  },
  detailGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginTop: spacing.lg,
  },
  detailCell: {
    minWidth: 120,
    flexGrow: 1,
    padding: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: colors.surface2,
  },
  metadataWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  metaChip: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: radius.pill,
    backgroundColor: colors.aiAccentMuted,
  },
  quickActions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginTop: spacing.lg,
  },
  quickAction: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: colors.surface2,
    borderWidth: 1,
    borderColor: colors.border,
  },
});
