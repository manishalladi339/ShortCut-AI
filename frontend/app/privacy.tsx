import { useRouter } from "expo-router";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { colors, spacing, typography } from "@/src/theme";

const sections = [
  ["What we collect", "Account details, project metadata, uploaded video/audio/images, generated edits/exports, service logs, and security/audit events needed to operate ShortCut AI."],
  ["How media is processed", "Uploaded content is stored in private object storage. Configured AI providers may receive audio, representative frames, transcript text, or embeddings needed to provide transcription, visual analysis, retrieval, and editing features."],
  ["Service providers", "ShortCut AI may use cloud hosting/storage, MongoDB, OpenAI-compatible AI services, Resend for account-security email, and Sentry for error monitoring. Providers process data only for the service functions we configure."],
  ["Retention and deletion", "You can permanently delete your account from Profile. ShortCut then deletes your account records and owned stored media/exports after active background jobs finish. Infrastructure backups and provider logs may persist for limited operational or legal retention periods."],
  ["Your choices", "You can delete individual assets and projects, request account deletion, and choose not to upload content you do not have the right to process."],
  ["Contact", "Before public launch, replace the launch contact in the repository policy with the final privacy/support email for ShortCut AI."],
];

export default function PrivacyPolicy() {
  const router = useRouter();
  return (
    <SafeAreaView style={styles.root} edges={["top", "bottom"]}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={styles.back}>
          <Text style={[typography.body, { color: colors.textMedium }]}>← Back</Text>
        </Pressable>
        <Text style={[typography.h2, { color: colors.textHigh }]}>Privacy Policy</Text>
        <Text style={[typography.caption, { color: colors.textMedium }]}>Effective 28 September 2026</Text>
      </View>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={[typography.body, { color: colors.textMedium }]}>
          This in-app summary describes the public-beta privacy model. The repository policy is the release source of truth and must be finalized with operator/contact details before public launch.
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
