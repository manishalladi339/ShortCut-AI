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

import { Button } from "@/src/components/ui/Button";
import { Input } from "@/src/components/ui/Input";
import { useAuth } from "@/src/store/auth";
import { colors, spacing, typography } from "@/src/theme";

export default function SignUp() {
  const router = useRouter();
  const { signup } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit() {
    setErr(null);
    if (password.length < 8) {
      setErr("Password must be at least 8 characters");
      return;
    }
    setBusy(true);
    try {
      await signup(email.trim().toLowerCase(), password, name.trim());
      router.replace("/(tabs)/dashboard");
    } catch (e: any) {
      setErr(e?.message ?? "Sign up failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView style={styles.root} edges={["top", "bottom"]}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        style={{ flex: 1 }}
        keyboardVerticalOffset={Platform.OS === "ios" ? 0 : 24}
      >
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <Pressable onPress={() => router.back()} style={styles.back} testID="signup-back">
            <Text style={[typography.body, { color: colors.textMedium }]}>← Back</Text>
          </Pressable>
          <Text style={[typography.h2, { color: colors.textHigh }]} testID="signup-title">
            Create your studio
          </Text>
          <Text style={[typography.body, { color: colors.textMedium, marginBottom: spacing.xxl }]}>
            Free tier · 3 projects per month.
          </Text>
          <View style={{ gap: spacing.lg }}>
            <Input
              label="Name"
              value={name}
              onChangeText={setName}
              autoCapitalize="words"
              autoComplete="name"
              testID="auth-name-input"
              placeholder="Your name"
            />
            <Input
              label="Email"
              value={email}
              onChangeText={setEmail}
              autoCapitalize="none"
              keyboardType="email-address"
              autoComplete="email"
              testID="auth-email-input"
              placeholder="you@example.com"
            />
            <Input
              label="Password"
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              autoComplete="new-password"
              testID="auth-password-input"
              placeholder="At least 8 characters"
            />
            {err ? (
              <Text style={[typography.caption, { color: colors.danger }]} testID="signup-error">
                {err}
              </Text>
            ) : null}
            <Button label="Create account" onPress={submit} loading={busy} testID="auth-signup-submit-button" />
            <Pressable
              onPress={() => router.replace("/(auth)/sign-in")}
              testID="signup-go-signin"
              style={{ alignSelf: "center", marginTop: spacing.md }}
            >
              <Text style={[typography.body, { color: colors.textMedium }]}>
                Already have an account? <Text style={{ color: colors.primary }}>Sign in</Text>
              </Text>
            </Pressable>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  scroll: { paddingHorizontal: spacing.screenPadding, paddingTop: spacing.lg, paddingBottom: spacing.xxxl },
  back: { paddingVertical: spacing.sm, marginBottom: spacing.lg },
});
