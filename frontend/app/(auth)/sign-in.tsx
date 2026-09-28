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

export default function SignIn() {
  const router = useRouter();
  const { signin } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit() {
    setErr(null);
    setBusy(true);
    try {
      await signin(email.trim().toLowerCase(), password);
      router.replace("/(tabs)/dashboard");
    } catch (e: any) {
      setErr(e?.message ?? "Sign in failed");
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
        <ScrollView
          contentContainerStyle={styles.scroll}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <Pressable onPress={() => router.back()} style={styles.back} testID="signin-back">
            <Text style={[typography.body, { color: colors.textMedium }]}>← Back</Text>
          </Pressable>
          <Text style={[typography.h2, { color: colors.textHigh }]} testID="signin-title">
            Welcome back
          </Text>
          <Text style={[typography.body, { color: colors.textMedium, marginBottom: spacing.xxl }]}>
            Sign in to continue creating.
          </Text>
          <View style={{ gap: spacing.lg }}>
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
              autoComplete="password"
              testID="auth-password-input"
              placeholder="••••••••"
            />
            <Pressable
              onPress={() => router.push("/(auth)/forgot-password")}
              testID="signin-forgot-link"
              style={{ alignSelf: "flex-end" }}
            >
              <Text style={[typography.caption, { color: colors.aiAccent }]}>Forgot password?</Text>
            </Pressable>
            {err ? (
              <Text style={[typography.caption, { color: colors.danger }]} testID="signin-error">
                {err}
              </Text>
            ) : null}
            <Button label="Sign in" onPress={submit} loading={busy} testID="auth-signin-submit-button" />
            <Pressable
              onPress={() => router.replace("/(auth)/sign-up")}
              testID="signin-go-signup"
              style={{ alignSelf: "center", marginTop: spacing.md }}
            >
              <Text style={[typography.body, { color: colors.textMedium }]}>
                New here? <Text style={{ color: colors.primary }}>Create account</Text>
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
