import { useRouter } from "expo-router";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { colors, spacing, typography } from "@/src/theme";

const sections = [
  ["Your content", "You keep ownership of content you upload. You grant ShortCut AI a limited license to store, process, transform, and deliver that content only as needed to provide the service."],
  ["Your responsibilities", "Only upload content you have the right to use. Do not use ShortCut AI for unlawful content, abuse, infringement, malware, or attempts to bypass service limits or security controls."],
  ["AI-assisted output", "AI suggestions and edits can be imperfect. You are responsible for reviewing outputs before publishing them and for ensuring your final use complies with applicable rights and laws."],
  ["Public beta", "The service may change, experience downtime, impose usage limits, or remove experimental features during the beta. Free-beta quotas are intended to protect reliability and cost."],
  ["Account termination", "You may delete your account from Profile. ShortCut AI may suspend access for abuse, security threats, unlawful use, or material violations of these terms."],
  ["Commercial and legal details", "Before public launch, the repository Terms must be finalized with the operator's legal identity, support contact, governing-law choice, and any paid-plan terms."],
];

export default function TermsOfService() {
  const router = useRouter();
  return (
    <SafeAreaView style={styles.root} edges={["top", "bottom"]}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={styles.back}>
          <Text style={[typography.body, { color: colors.textMedium }]}>← Back</Text>
        </Pressable>
        <Text style={[typography.h2, { color: colors.textHigh }]}>Terms of Service</Text>
        <Text style={[typography.caption, { color: colors.textMedium }]}>Version 2026-09-28</Text>
      </View>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={[typography.body, { color: colors.textMedium }]}>
          These public-beta terms explain the product rules in plain language. The repository Terms are the release source of truth and require final operator/legal details before launch.
        </Text>
        {sections.map(([title, body]) => (
          <View key={title} style={styles.section}>
            <Text style={[typography.h3, { color: colors.textHigh }]}>{title}</Text>
            <Text style={[typography.body, { color: colors.textMedium }]}>{body}</Text>
          </View>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  header: { paddingHorizontal: spacing.screenPadding, paddingVertical: spacing.lg, gap: spacing.xs },
  back: { paddingVertical: spacing.sm, alignSelf: "flex-start" },
  content: { paddingHorizontal: spacing.screenPadding, paddingBottom: spacing.xxxl, gap: spacing.xl },
  section: { gap: spacing.sm },
});
