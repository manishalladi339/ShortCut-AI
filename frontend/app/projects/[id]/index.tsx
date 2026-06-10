import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Asset, assetsApi } from "@/src/api/assets";
import { Project, projectsApi } from "@/src/api/projects";
import { Button } from "@/src/components/ui/Button";
import { colors, radius, spacing, typography } from "@/src/theme";

export default function ProjectDetail() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [p, a] = await Promise.all([
        projectsApi.get(id),
        assetsApi.list({ project_id: id }).catch(() => ({ items: [], next_cursor: null, has_more: false })),
      ]);
      setProject(p);
      setAssets(a.items);
    } catch (e: any) {
      Alert.alert("Could not load project", e?.message ?? "Try again");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  async function archive() {
    if (!project) return;
    try {
      await projectsApi.archive(project.id);
      router.back();
    } catch (e: any) {
      Alert.alert("Failed", e?.message ?? "");
    }
  }
  async function duplicate() {
    if (!project) return;
    try {
      const p = await projectsApi.duplicate(project.id);
      router.replace(`/projects/${p.id}` as any);
    } catch (e: any) {
      Alert.alert("Failed", e?.message ?? "");
    }
  }
  async function remove() {
    if (!project) return;
    Alert.alert("Delete project?", "This cannot be undone.", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete",
        style: "destructive",
        onPress: async () => {
          try {
            await projectsApi.remove(project.id);
            router.back();
          } catch (e: any) {
            Alert.alert("Failed", e?.message ?? "");
          }
        },
      },
    ]);
  }

  if (loading || !project) {
    return (
      <SafeAreaView style={styles.root} edges={["top"]}>
        <ActivityIndicator color={colors.primary} style={{ marginTop: 100 }} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.root} edges={["top", "bottom"]}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} testID="project-back" style={styles.iconBtn}>
          <Ionicons name="chevron-back" color={colors.textHigh} size={24} />
        </Pressable>
        <Text style={[typography.h3, { color: colors.textHigh, flex: 1, marginHorizontal: spacing.md }]} numberOfLines={1}>
          {project.title}
        </Text>
        <Pressable onPress={duplicate} testID="project-duplicate" style={styles.iconBtn}>
          <Ionicons name="copy-outline" color={colors.textHigh} size={22} />
        </Pressable>
      </View>

      <ScrollView contentContainerStyle={{ padding: spacing.screenPadding, paddingBottom: spacing.xxxl }}>
        <View style={styles.heroCard}>
          <View style={styles.heroIcon}>
            <Ionicons name="film" color={colors.primary} size={32} />
          </View>
          <Text style={[typography.caption, { color: colors.aiAccent, marginTop: spacing.md }]}>
            {project.creation_mode === "create_for_me" ? "AI AUTOMATIC" : "AI GUIDED"}
          </Text>
          <Text style={[typography.h3, { color: colors.textHigh, marginTop: spacing.xs }]}>
            {project.title}
          </Text>
          {project.description ? (
            <Text style={[typography.body, { color: colors.textMedium, marginTop: spacing.sm }]}>
              {project.description}
            </Text>
          ) : null}
          <View style={styles.metaRow}>
            <Meta label={label(project.content_type)} />
            {project.desired_style ? <Meta label={label(project.desired_style)} /> : null}
            {project.target_platforms.map((p) => (
              <Meta key={p} label={label(p)} />
            ))}
          </View>
        </View>

        <View style={{ marginTop: spacing.xl, gap: spacing.md }}>
          <Button
            label="Upload an asset"
            variant="ai"
            iconLeft={<Ionicons name="cloud-upload" size={18} color="#001318" />}
            onPress={() => router.push({ pathname: "/library", params: { project_id: project.id } })}
            testID="project-upload-asset-button"
          />
          {project.creation_mode === "create_for_me" ? (
            <Button
              label="Run AI Pipeline (Phase 2.2)"
              variant="secondary"
              onPress={() => Alert.alert("Coming soon", "The Create For Me pipeline ships in Phase 2.2.")}
              testID="project-run-pipeline-button"
            />
          ) : (
            <Button
              label="Open AI Editor (Phase 2.3)"
              variant="secondary"
              onPress={() => Alert.alert("Coming soon", "Create With Me ships in Phase 2.3.")}
              testID="project-open-editor-button"
            />
          )}
        </View>

        <View style={{ marginTop: spacing.xl, gap: spacing.md }}>
          <Text style={[typography.overline, { color: colors.textMedium }]}>
            Assets ({assets.length})
          </Text>
          {assets.length === 0 ? (
            <View style={styles.emptyAssets} testID="project-assets-empty">
              <Ionicons name="cloud-upload-outline" color={colors.textLow} size={32} />
              <Text style={[typography.body, { color: colors.textMedium, marginTop: spacing.sm }]}>
                No assets linked yet.
              </Text>
            </View>
          ) : (
            assets.map((a) => (
              <View key={a.id} style={styles.assetRow} testID={`project-asset-${a.id}`}>
                <View style={styles.assetIcon}>
                  <Ionicons
                    name={a.kind === "video" ? "videocam" : a.kind === "audio" ? "musical-notes" : "image"}
                    color={colors.aiAccent}
                    size={18}
                  />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={[typography.bodyMed, { color: colors.textHigh }]} numberOfLines={1}>
                    {a.filename}
                  </Text>
                  <Text style={[typography.caption, { color: colors.textMedium, marginTop: 2 }]}>
                    {a.upload_status === "uploaded" ? "Uploaded" : "Pending"} · {(a.size_bytes / 1024).toFixed(1)} KB
                  </Text>
                </View>
              </View>
            ))
          )}
        </View>

        <View style={styles.dangerSection}>
          <Pressable style={styles.dangerRow} onPress={archive} testID="project-archive-button">
            <Ionicons name="archive-outline" color={colors.textMedium} size={20} />
            <Text style={[typography.bodyMed, { color: colors.textHigh, flex: 1, marginLeft: spacing.md }]}>
              Archive project
            </Text>
          </Pressable>
          <Pressable style={styles.dangerRow} onPress={remove} testID="project-delete-button">
            <Ionicons name="trash-outline" color={colors.danger} size={20} />
            <Text style={[typography.bodyMed, { color: colors.danger, flex: 1, marginLeft: spacing.md }]}>
              Delete project
            </Text>
          </Pressable>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function Meta({ label }: { label: string }) {
  return (
    <View style={metaChipStyle}>
      <Text style={[typography.caption, { color: colors.textHigh, fontWeight: "600" }]}>{label}</Text>
    </View>
  );
}

const metaChipStyle = {
  paddingHorizontal: 10,
  paddingVertical: 6,
  borderRadius: 8,
  backgroundColor: colors.surface2,
} as const;

const label = (s: string) => s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  iconBtn: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  heroCard: {
    backgroundColor: colors.surface1,
    borderRadius: radius.lg,
    padding: spacing.xxl,
    borderWidth: 1,
    borderColor: colors.border,
  },
  heroIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primaryMuted,
    alignItems: "center",
    justifyContent: "center",
  },
  metaRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: spacing.lg },
  emptyAssets: {
    alignItems: "center",
    padding: spacing.xl,
    backgroundColor: colors.surface1,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  assetRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.md,
    backgroundColor: colors.surface1,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  assetIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.aiAccentMuted,
    alignItems: "center",
    justifyContent: "center",
  },
  dangerSection: { marginTop: spacing.xxxl, gap: spacing.sm },
  dangerRow: {
    flexDirection: "row",
    alignItems: "center",
    padding: spacing.md,
    backgroundColor: colors.surface1,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
});
