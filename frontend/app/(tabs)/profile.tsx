import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";

import { Button } from "@/src/components/ui/Button";
import { useAuth } from "@/src/store/auth";
import { colors, radius, spacing, typography } from "@/src/theme";

export default function Profile() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user, signout } = useAuth();

  async function doSignout() {
    await signout();
    router.replace("/(auth)/welcome");
  }

  if (!user) return null;

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <ScrollView contentContainerStyle={{ paddingBottom: 88 + insets.bottom + spacing.xl }}>
        <View style={styles.header}>
          <Text style={[typography.h2, { color: colors.textHigh }]} testID="profile-title">
            Profile
          </Text>
        </View>

        <View style={styles.card}>
          <View style={styles.avatar}>
            <Text style={{ color: colors.textHigh, fontSize: 28, fontWeight: "700" }}>
              {user.name.charAt(0).toUpperCase()}
            </Text>
          </View>
          <Text style={[typography.h3, { color: colors.textHigh, textAlign: "center", marginTop: spacing.md }]} testID="profile-name">
            {user.name}
          </Text>
          <Text style={[typography.body, { color: colors.textMedium, textAlign: "center", marginTop: 2 }]} testID="profile-email">
            {user.email}
          </Text>
          <View style={styles.pill}>
            <Ionicons name="ribbon" color={colors.aiAccent} size={14} />
            <Text style={[typography.caption, { color: colors.aiAccent, fontWeight: "700" }]}>
              {user.subscription_tier.toUpperCase()} TIER
            </Text>
          </View>
        </View>

        <View style={styles.section}>
          <Text style={[typography.overline, { color: colors.textMedium }]}>Account</Text>
          <Row icon="person" label="Edit profile" testID="profile-edit-row" />
          <Row icon="card" label="Subscription" testID="profile-subscription-row" />
          <Row icon="color-palette" label="Brand Kit" testID="profile-brand-row" />
          <Row icon="notifications" label="Notifications" testID="profile-notif-row" />
          <Row icon="help-circle" label="Help & Support" testID="profile-help-row" />
        </View>

        <View style={{ paddingHorizontal: spacing.screenPadding, marginTop: spacing.xl }}>
          <Button label="Sign out" variant="secondary" onPress={doSignout} testID="profile-signout-button" />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function Row({ icon, label, testID }: { icon: any; label: string; testID: string }) {
  return (
    <Pressable style={styles.row} testID={testID}>
      <View style={styles.rowIcon}>
        <Ionicons name={icon} color={colors.aiAccent} size={20} />
      </View>
      <Text style={[typography.bodyMed, { color: colors.textHigh, flex: 1 }]}>{label}</Text>
      <Ionicons name="chevron-forward" color={colors.textMedium} size={20} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  header: { paddingHorizontal: spacing.screenPadding, paddingTop: spacing.md, paddingBottom: spacing.lg },
  card: {
    marginHorizontal: spacing.screenPadding,
    backgroundColor: colors.surface1,
    borderRadius: radius.lg,
    padding: spacing.xxl,
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.border,
  },
  avatar: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: colors.surface2,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 2,
    borderColor: colors.primary,
  },
  pill: {
    flexDirection: "row",
    gap: 6,
    alignItems: "center",
    marginTop: spacing.md,
    backgroundColor: colors.aiAccentMuted,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
  },
  section: { marginTop: spacing.xl, paddingHorizontal: spacing.screenPadding, gap: spacing.sm },
  row: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface1,
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    gap: spacing.md,
  },
  rowIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.aiAccentMuted,
    alignItems: "center",
    justifyContent: "center",
  },
});
