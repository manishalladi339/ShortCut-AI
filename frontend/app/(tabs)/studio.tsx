import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useRouter } from "expo-router";
import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";

import { Project, projectsApi } from "@/src/api/projects";
import { ChipRow } from "@/src/components/ui/Chip";
import { colors, radius, spacing, typography } from "@/src/theme";

type Filter = "active" | "archived";

export default function Studio() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [filter, setFilter] = useState<Filter>("active");
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await projectsApi.list(filter === "archived");
      setProjects(r.items);
    } catch (e: any) {
      Alert.alert("Could not load projects", e?.message ?? "Try again");
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <View style={styles.header}>
        <Text style={[typography.h2, { color: colors.textHigh }]} testID="studio-title">
          Studio
        </Text>
        <Pressable
          style={styles.fab}
          onPress={() => router.push("/projects/new")}
          testID="studio-new-project-fab"
        >
          <Ionicons name="add" size={22} color="#FFF" />
        </Pressable>
      </View>

      <ChipRow<Filter>
        items={[
          { value: "active", label: "Active" },
          { value: "archived", label: "Archived" },
        ]}
        value={filter}
        onChange={setFilter}
        testIDPrefix="studio-filter-chip"
      />

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.primary} />
        </View>
      ) : projects.length === 0 ? (
        <View style={styles.center}>
          <Ionicons name="film-outline" color={colors.textLow} size={64} />
          <Text style={[typography.h3, { color: colors.textHigh, marginTop: spacing.lg }]}>
            No projects yet
          </Text>
          <Text style={[typography.body, { color: colors.textMedium, textAlign: "center", marginTop: spacing.sm, maxWidth: 280 }]}>
            Create a project to start turning your content into Reels, Shorts, and thumbnails.
          </Text>
          <Pressable
            style={styles.bigBtn}
            onPress={() => router.push("/projects/new")}
            testID="studio-empty-create-button"
          >
            <Text style={{ color: "#FFF", fontWeight: "700" }}>Create your first project</Text>
          </Pressable>
        </View>
      ) : (
        <FlatList
          data={projects}
          keyExtractor={(p) => p.id}
          contentContainerStyle={{ paddingHorizontal: spacing.screenPadding, paddingTop: spacing.md, paddingBottom: 88 + insets.bottom + spacing.xl, gap: 12 }}
          renderItem={({ item }) => (
            <Pressable
              style={styles.card}
              onPress={() => router.push(`/projects/${item.id}` as any)}
              testID={`studio-project-card-${item.id}`}
            >
              <View style={styles.thumb}>
                <Ionicons name="film" color={colors.textMedium} size={28} />
              </View>
              <View style={{ flex: 1 }}>
                <View style={styles.row}>
                  <Text style={[typography.bodyMed, { color: colors.textHigh, flex: 1 }]} numberOfLines={1}>
                    {item.title}
                  </Text>
                  <StatusPill status={item.status} />
                </View>
                <Text style={[typography.caption, { color: colors.textMedium, marginTop: 2 }]}>
                  {label(item.content_type)} · {modeLabel(item.creation_mode)}
                </Text>
                <Text style={[typography.caption, { color: colors.textLow, marginTop: 4 }]}>
                  Updated {timeAgo(item.updated_at)}
                </Text>
              </View>
            </Pressable>
          )}
        />
      )}
    </SafeAreaView>
  );
}

function StatusPill({ status }: { status: Project["status"] }) {
  const map: Record<Project["status"], { label: string; bg: string; fg: string }> = {
    draft: { label: "Draft", bg: colors.surface2, fg: colors.textMedium },
    processing: { label: "Processing", bg: "rgba(0,229,255,0.15)", fg: colors.aiAccent },
    completed: { label: "Ready", bg: "rgba(0,255,102,0.15)", fg: colors.success },
    archived: { label: "Archived", bg: colors.surface2, fg: colors.textLow },
    failed: { label: "Failed", bg: "rgba(255,68,51,0.15)", fg: colors.primary },
  };
  const m = map[status];
  return (
    <View style={[styles.pill, { backgroundColor: m.bg }]}>
      <Text style={[typography.caption, { color: m.fg, fontWeight: "700" }]}>{m.label}</Text>
    </View>
  );
}

const label = (s: string) => s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
const modeLabel = (m: string) => (m === "create_for_me" ? "AI Auto" : "AI Guided");
function timeAgo(iso: string): string {
  const d = new Date(iso).getTime();
  const diff = Date.now() - d;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  header: {
    paddingHorizontal: spacing.screenPadding,
    paddingTop: spacing.md,
    paddingBottom: spacing.md,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  fab: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  center: { flex: 1, alignItems: "center", justifyContent: "center", paddingHorizontal: spacing.screenPadding },
  card: {
    flexDirection: "row",
    backgroundColor: colors.surface1,
    borderRadius: radius.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    gap: spacing.md,
    alignItems: "center",
  },
  thumb: {
    width: 64,
    height: 64,
    borderRadius: radius.md,
    backgroundColor: colors.surface2,
    alignItems: "center",
    justifyContent: "center",
  },
  row: { flexDirection: "row", alignItems: "center", gap: 8 },
  pill: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6 },
  bigBtn: {
    marginTop: spacing.xl,
    backgroundColor: colors.primary,
    paddingVertical: 16,
    paddingHorizontal: 32,
    borderRadius: radius.md,
  },
});
