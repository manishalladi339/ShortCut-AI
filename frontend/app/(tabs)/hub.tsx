import { Ionicons } from "@expo/vector-icons";
import { StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { colors, spacing, typography } from "@/src/theme";

export default function Hub() {
  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <View style={styles.header}>
        <Text style={[typography.h2, { color: colors.textHigh }]} testID="hub-title">
          Content Hub
        </Text>
      </View>
      <View style={styles.center}>
        <Ionicons name="albums-outline" color={colors.textLow} size={64} />
        <Text style={[typography.h3, { color: colors.textHigh, marginTop: spacing.lg }]}>
          Coming in Phase 2.5
        </Text>
        <Text style={[typography.body, { color: colors.textMedium, textAlign: "center", marginTop: spacing.sm, maxWidth: 320 }]}>
          Your library of AI-generated clips, titles, hashtags, and thumbnails — searchable and filterable across all projects.
        </Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  header: { paddingHorizontal: spacing.screenPadding, paddingTop: spacing.md, paddingBottom: spacing.md },
  center: { flex: 1, alignItems: "center", justifyContent: "center", paddingHorizontal: spacing.screenPadding },
});
