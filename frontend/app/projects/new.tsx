import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { CreationMode, Platform as TargetPlatform, projectsApi, Style as StyleT } from "@/src/api/projects";
import { Button } from "@/src/components/ui/Button";
import { ChipMultiRow } from "@/src/components/ui/Chip";
import { Input } from "@/src/components/ui/Input";
import { CONTENT_TYPES, CREATION_MODES, PLATFORMS, STYLES } from "@/src/constants/content";
import { colors, radius, spacing, typography } from "@/src/theme";

export default function NewProject() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [contentType, setContentType] = useState(CONTENT_TYPES[0].value);
  const [mode, setMode] = useState<CreationMode>("create_for_me");
  const [style, setStyle] = useState<StyleT | null>(null);
  const [platforms, setPlatforms] = useState<TargetPlatform[]>([]);
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  function togglePlatform(p: TargetPlatform) {
    setPlatforms((arr) => (arr.includes(p) ? arr.filter((x) => x !== p) : [...arr, p]));
  }

  async function create() {
    setErr(null);
    if (!title.trim()) {
      setErr("Project needs a title");
      return;
    }
    setBusy(true);
    try {
      const p = await projectsApi.create({
        title: title.trim(),
        content_type: contentType,
        creation_mode: mode,
        desired_style: style ?? undefined,
        target_platforms: platforms,
        prompt: prompt.trim() || undefined,
      });
      router.replace(`/projects/${p.id}` as any);
    } catch (e: any) {
      setErr(e?.message ?? "Could not create project");
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView style={styles.root} edges={["top", "bottom"]}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        style={{ flex: 1 }}
      >
        <View style={styles.header}>
          <Pressable onPress={() => router.back()} testID="new-project-back" style={styles.iconBtn}>
            <Ionicons name="close" color={colors.textHigh} size={24} />
          </Pressable>
          <Text style={[typography.h3, { color: colors.textHigh }]} testID="new-project-title">
            New Project
          </Text>
          <View style={{ width: 44 }} />
        </View>

        <ScrollView
          contentContainerStyle={styles.scroll}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <View style={{ paddingHorizontal: spacing.screenPadding }}>
            <Input
              label="Project title"
              value={title}
              onChangeText={setTitle}
              testID="new-project-title-input"
              placeholder="e.g. Episode 12 — AI in 2026"
            />
          </View>

          <Section title="Content Type">
            <ChipMultiRow
              items={CONTENT_TYPES.map((c) => ({ value: c.value, label: `${c.emoji} ${c.label}` }))}
              values={[contentType] as any}
              onToggle={(v) => setContentType(v as any)}
              testIDPrefix="new-project-content-chip"
            />
          </Section>

          <Section title="Creation Mode">
            <View style={{ paddingHorizontal: spacing.screenPadding, gap: spacing.md }}>
              {CREATION_MODES.map((m) => {
                const active = m.value === mode;
                return (
                  <Pressable
                    key={m.value}
                    onPress={() => setMode(m.value)}
                    style={[styles.modeCard, active && styles.modeCardActive]}
                    testID={`new-project-mode-${m.value}`}
                  >
                    <View style={[styles.modeIcon, {backgroundColor: active ? colors.primaryMuted : colors.surface2}]}>
                      <Ionicons
                        name={m.value === "create_for_me" ? "sparkles" : "options"}
                        color={active ? colors.primary : colors.textMedium}
                        size={20}
                      />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={[typography.bodyMed, { color: colors.textHigh }]}>{m.label}</Text>
                      <Text style={[typography.caption, { color: colors.textMedium, marginTop: 2 }]}>
                        {m.description}
                      </Text>
                    </View>
                    {active ? <Ionicons name="checkmark-circle" color={colors.primary} size={20} /> : null}
                  </Pressable>
                );
              })}
            </View>
          </Section>

          <Section title="Style (optional)">
            <ChipMultiRow
              items={STYLES.map((s) => ({ value: s.value, label: s.label }))}
              values={style ? [style] : []}
              onToggle={(v) => setStyle((cur) => (cur === v ? null : (v as StyleT)))}
              testIDPrefix="new-project-style-chip"
            />
          </Section>

          <Section title="Target Platforms">
            <ChipMultiRow
              items={PLATFORMS}
              values={platforms}
              onToggle={(v) => togglePlatform(v as TargetPlatform)}
              testIDPrefix="new-project-platform-chip"
            />
          </Section>

          <Section title="Prompt (optional)">
            <View style={{ paddingHorizontal: spacing.screenPadding }}>
              <Input
                value={prompt}
                onChangeText={setPrompt}
                placeholder="e.g. Turn this into 20 YouTube Shorts focused on hooks"
                multiline
                style={{ minHeight: 100, paddingTop: 14 }}
                testID="new-project-prompt-input"
              />
            </View>
          </Section>

          {err ? (
            <Text style={[typography.caption, styles.errText]} testID="new-project-error">
              {err}
            </Text>
          ) : null}
        </ScrollView>

        <View style={styles.footer}>
          <Button
            label="Create project"
            onPress={create}
            loading={busy}
            testID="new-project-submit-button"
          />
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={{ marginTop: spacing.xl, gap: spacing.md }}>
      <Text
        style={[typography.overline, { color: colors.textMedium, paddingHorizontal: spacing.screenPadding }]}
      >
        {title}
      </Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.md,
    paddingTop: spacing.sm,
    paddingBottom: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  iconBtn: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  scroll: { paddingTop: spacing.lg, paddingBottom: spacing.xxxl },
  errText: { color: colors.danger, paddingHorizontal: spacing.screenPadding, marginTop: spacing.md },
  footer: {
    paddingHorizontal: spacing.screenPadding,
    paddingTop: spacing.md,
    paddingBottom: spacing.lg,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
    backgroundColor: colors.bg,
  },
  modeCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.lg,
    backgroundColor: colors.surface1,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  modeCardActive: { borderColor: colors.primary, backgroundColor: "rgba(255,68,51,0.06)" },
  modeIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.surface2,
    alignItems: "center" as const,
    justifyContent: "center" as const,
  },
});
