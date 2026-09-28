import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";

import { colors, spacing, typography } from "@/src/theme";

export function LegalPage({
  title,
  sections,
}: {
  title: string;
  sections: Array<{ heading: string; body: string }>;
}) {
  const router = useRouter();
  const operator = process.env.EXPO_PUBLIC_LEGAL_OPERATOR_NAME || "ShortCut AI";
  const support = process.env.EXPO_PUBLIC_SUPPORT_EMAIL || "support contact shown in the app";

  return (
    <SafeAreaView style={styles.root} edges={["top", "bottom"]}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={styles.back}>
          <Text style={[typography.body, { color: colors.textMedium }]}>← Back</Text>
        </Pressable>
        <Text style={[typography.h3, { color: colors.textHigh, flex: 1 }]}>{title}</Text>
      </View>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={[typography.caption, { color: colors.textMedium }]}>
          Effective September 28, 2026 · Operator: {operator} · Contact: {support}
        </Text>
        {sections.map((section) => (
          <View key={section.heading} style={styles.section}>
            <Text style={[typography.h3, { color: colors.textHigh }]}>{section.heading}</Text>
            <Text style={[typography.body, { color: colors.textMedium, marginTop: spacing.sm, lineHeight: 24 }]}>
              {section.body}
            </Text>
          </View>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingHorizontal: spacing.screenPadding,
    paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  back: { paddingVertical: spacing.sm },
  scroll: { padding: spacing.screenPadding, paddingBottom: spacing.xxxl },
  section: { marginTop: spacing.xl },
});
