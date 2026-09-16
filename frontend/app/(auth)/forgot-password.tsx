import { useRouter } from "expo-router";
import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { authApi } from "@/src/api/auth";
import { Button } from "@/src/components/ui/Button";
import { Input } from "@/src/components/ui/Input";
import { colors, spacing, typography } from "@/src/theme";

export default function ForgotPassword() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);

  async function submit() {
    setBusy(true);
    setError("");
    try {
      await authApi.forgotPassword(email.trim().toLowerCase());
      setSent(true);
    } catch (e: any) {
      setError(e?.message || "Could not request a reset link. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView style={styles.root} edges={["top", "bottom"]}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Pressable onPress={() => router.back()} style={styles.back} testID="forgot-back">
          <Text style={[typography.body, { color: colors.textMedium }]}>← Back</Text>
        </Pressable>
        <Text style={[typography.h2, { color: colors.textHigh }]} testID="forgot-title">
          Reset password
        </Text>
        <Text style={[typography.body, { color: colors.textMedium, marginBottom: spacing.xxl }]}>
          We&apos;ll send you a link if this email is registered.
        </Text>
        {error ? <Text accessibilityRole="alert" style={{color: colors.danger}}>{error}</Text> : null}
        {sent ? (
          <View>
            <Text style={[typography.body, { color: colors.success }]} testID="forgot-success">
              Check your inbox. If we have your email, the reset link is on its way.
            </Text>
            <Button
              label="Back to sign in"
              variant="secondary"
              onPress={() => router.replace("/(auth)/sign-in")}
              style={{ marginTop: spacing.xl }}
              testID="forgot-back-to-signin"
            />
          </View>
        ) : (
          <View style={{ gap: spacing.lg }}>
            <Input
              label="Email"
              value={email}
              onChangeText={setEmail}
              keyboardType="email-address"
              autoCapitalize="none"
              autoComplete="email"
              testID="forgot-email-input"
              placeholder="you@example.com"
            />
            <Button label="Send reset link" onPress={submit} loading={busy} testID="forgot-submit-button" />
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  scroll: { paddingHorizontal: spacing.screenPadding, paddingTop: spacing.lg, paddingBottom: spacing.xxxl },
  back: { paddingVertical: spacing.sm, marginBottom: spacing.lg },
});
