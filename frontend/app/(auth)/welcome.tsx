import { LinearGradient } from "expo-linear-gradient";
import { Link, useRouter } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Button } from "@/src/components/ui/Button";
import { colors, spacing, typography } from "@/src/theme";

export default function Welcome() {
  const router = useRouter();
  return (
    <SafeAreaView style={styles.root} edges={["top", "bottom"]}>
      <LinearGradient
        colors={["rgba(255,68,51,0.18)", "rgba(0,229,255,0.06)", "transparent"]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.gradient}
      />
      <View style={styles.body}>
        <Text style={[typography.overline, { color: colors.aiAccent }]} testID="welcome-overline">
          AI Studio · Mobile
        </Text>
        <Text style={[typography.h1, styles.title]} testID="welcome-title">
          ShortCut{"\n"}
          <Text style={{ color: colors.primary }}>your story.</Text>
        </Text>
        <Text style={[typography.body, styles.subtitle]} testID="welcome-subtitle">
          Turn raw video, audio & photos into Reels, Shorts and posts. Zero editing skill required.
        </Text>
      </View>
      <View style={styles.footer}>
        <Button
          label="Create account"
          variant="primary"
          onPress={() => router.push("/(auth)/sign-up")}
          testID="welcome-signup-button"
        />
        <Button
          label="I already have an account"
          variant="secondary"
          onPress={() => router.push("/(auth)/sign-in")}
          testID="welcome-signin-button"
          style={{ marginTop: spacing.md }}
        />
        <Link href="/(tabs)/dashboard" asChild>
          <Pressable testID="welcome-skip-link" style={styles.skip}>
            <Text style={[typography.caption, { color: colors.textLow }]}>Browse without account</Text>
          </Pressable>
        </Link>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  gradient: { position: "absolute", top: 0, left: 0, right: 0, height: "60%" },
  body: { flex: 1, paddingHorizontal: spacing.screenPadding, justifyContent: "flex-end", paddingBottom: spacing.xxl },
  title: { color: colors.textHigh, marginTop: spacing.md, marginBottom: spacing.lg },
  subtitle: { color: colors.textMedium, maxWidth: 480 },
  footer: { paddingHorizontal: spacing.screenPadding, paddingBottom: spacing.md },
  skip: { alignItems: "center", paddingVertical: spacing.lg, opacity: 0.6 },
});
