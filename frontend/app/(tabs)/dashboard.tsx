import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useRouter } from "expo-router";
import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Image,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";

import { Project, projectsApi } from "@/src/api/projects";
import { useAuth } from "@/src/store/auth";
import { colors, radius, spacing, typography } from "@/src/theme";

const QUICK_ACTIONS = [
  { id: "new", label: "New Project", icon: "add-circle" as const, href: "/projects/new" },
  { id: "upload", label: "Upload Video", icon: "cloud-upload" as const, href: "/library" },
  { id: "reel", label: "Generate Reel", icon: "videocam" as const, href: "/projects/new" },
  { id: "thumb", label: "Generate Thumbnail", icon: "image" as const, href: "/projects/new" },
];

export default function Dashboard() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user } = useAuth();
  const [recent, setRecent] = useState<Project[]>([]);
  const [cont, setCont] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [r, c] = await Promise.all([
        projectsApi.recent().catch(() => []),
        projectsApi.continueEditing().catch(() => []),
      ]);
      setRecent(r);
      setCont(c);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <ScrollView
        contentContainerStyle={{ paddingBottom: 88 + insets.bottom + spacing.xl }}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => {
              setRefreshing(true);
              load();
            }}
            tintColor={colors.primary}
          />
        }
      >
        <View style={styles.header}>
          <View>
            <Text style={[typography.caption, { color: colors.textMedium }]} testID="dashboard-greeting">
              Welcome back
            </Text>
            <Text style={[typography.h2, { color: colors.textHigh }]} testID="dashboard-username">
              {user?.name ?? "Creator"}
            </Text>
          </View>
          <Pressable
            onPress={() => router.push("/(tabs)/profile")}
            testID="dashboard-avatar"
            style={styles.avatar}
          >
            {user?.avatar_url ? (
              <Image source={{ uri: user.avatar_url }} style={{ width: 48, height: 48, borderRadius: 24 }} />
            ) : (
              <Text style={{ color: colors.textHigh, fontWeight: "700" }}>
                {(user?.name ?? "C").charAt(0).toUpperCase()}
              </Text>
            )}
          </Pressable>
        </View>

        {/* Quick Actions */}
        <View style={styles.section}>
          <Text style={[typography.overline, { color: colors.textMedium }]}>Quick Actions</Text>
          <View style={styles.actionsGrid}>
            {QUICK_ACTIONS.map((a) => (
              <Pressable
                key={a.id}
                style={styles.actionCard}
                onPress={() => router.push(a.href as any)}
                testID={`dashboard-quickaction-${a.id}`}
              >
                <View style={styles.actionIcon}>
                  <Ionicons name={a.icon} color={colors.primary} size={22} />
                </View>
                <Text style={[typography.bodyMed, { color: colors.textHigh, marginTop: spacing.sm }]}>
                  {a.label}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>

        {/* Continue editing */}
        {cont.length > 0 ? (
          <View style={styles.section}>
            <Text style={[typography.overline, { color: colors.textMedium }]}>Continue Editing</Text>
            {cont.map((p) => (
              <ProjectRow key={p.id} p={p} onPress={() => router.push(`/projects/${p.id}` as any)} />
            ))}
          </View>
        ) : null}

        {/* Recent projects */}
        <View style={styles.section}>
          <View style={styles.rowBetween}>
            <Text style={[typography.overline, { color: colors.textMedium }]}>Recent Projects</Text>
            <Pressable onPress={() => router.push("/(tabs)/studio")} testID="dashboard-view-all">
              <Text style={[typography.caption, { color: colors.aiAccent }]}>View all</Text>
            </Pressable>
          </View>
          {loading ? (
            <ActivityIndicator color={colors.primary} style={{ marginTop: spacing.xl }} />
          ) : recent.length === 0 ? (
            <View style={styles.emptyCard} testID="dashboard-empty-state">
              <Ionicons name="rocket" color={colors.aiAccent} size={32} />
              <Text style={[typography.h3, { color: colors.textHigh, marginTop: spacing.md }]}>
                Start your first project
              </Text>
              <Text style={[typography.body, { color: colors.textMedium, textAlign: "center", marginTop: spacing.sm }]}>
                Upload a video or podcast and let AI cut it into viral-ready clips.
              </Text>
              <Pressable
                style={styles.emptyBtn}
                onPress={() => router.push("/projects/new")}
                testID="dashboard-empty-new-project"
              >
                <Text style={{ color: "#FFF", fontWeight: "700" }}>New Project</Text>
              </Pressable>
            </View>
          ) : (
            recent.map((p) => (
              <ProjectRow key={p.id} p={p} onPress={() => router.push(`/projects/${p.id}` as any)} />
            ))
          )}
        </View>

        {/* AI Suggestions (placeholder for Phase 2.3) */}
        <View style={styles.section}>
          <Text style={[typography.overline, { color: colors.textMedium }]}>AI Suggestions</Text>
          <View style={styles.suggestionCard}>
            <Ionicons name="sparkles" color={colors.aiAccent} size={20} />
            <View style={{ flex: 1, marginLeft: spacing.md }}>
              <Text style={[typography.bodyMed, { color: colors.textHigh }]}>Tip</Text>
              <Text style={[typography.caption, { color: colors.textMedium, marginTop: 2 }]}>
                Open a project to analyze clips, review AI edits, and export your video.
              </Text>
            </View>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function ProjectRow({ p, onPress }: { p: Project; onPress: () => void }) {
  return (
    <Pressable
      style={styles.projectRow}
      onPress={onPress}
      testID={`dashboard-recent-project-${p.id}`}
    >
      <View style={styles.thumbStub}>
        <Ionicons name="film" color={colors.textMedium} size={24} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={[typography.bodyMed, { color: colors.textHigh }]} numberOfLines={1}>
          {p.title}
        </Text>
        <Text style={[typography.caption, { color: colors.textMedium, marginTop: 2 }]}>
          {labelOf(p.content_type)} · {labelOfMode(p.creation_mode)}
        </Text>
      </View>
      <Ionicons name="chevron-forward" color={colors.textMedium} size={20} />
    </Pressable>
  );
}

const labelOf = (s: string) => s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
const labelOfMode = (m: string) => (m === "create_for_me" ? "AI Auto" : "AI Guided");

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.screenPadding,
    paddingTop: spacing.md,
    paddingBottom: spacing.lg,
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.surface2,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.border,
  },
  section: { paddingHorizontal: spacing.screenPadding, marginTop: spacing.xl, gap: spacing.md },
  rowBetween: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  actionsGrid: { flexDirection: "row", flexWrap: "wrap", gap: 12 },
  actionCard: {
    width: "48%",
    backgroundColor: colors.surface1,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    padding: spacing.lg,
    minHeight: 110,
  },
  actionIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.primaryMuted,
    alignItems: "center",
    justifyContent: "center",
  },
  emptyCard: {
    backgroundColor: colors.surface1,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    padding: spacing.xxl,
    alignItems: "center",
    gap: spacing.sm,
  },
  emptyBtn: {
    marginTop: spacing.lg,
    backgroundColor: colors.primary,
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: radius.md,
  },
  projectRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface1,
    borderRadius: radius.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    gap: spacing.md,
  },
  thumbStub: {
    width: 56,
    height: 56,
    borderRadius: radius.md,
    backgroundColor: colors.surface2,
    alignItems: "center",
    justifyContent: "center",
  },
  suggestionCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.aiAccentMuted,
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: "rgba(0,229,255,0.3)",
  },
});
