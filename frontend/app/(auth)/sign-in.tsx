import * as Linking from "expo-linking";
import { useRouter } from "expo-router";
import * as WebBrowser from "expo-web-browser";
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

const AUTH_HOST = "https://auth.emergentagent.com";

export default function SignIn() {
  const router = useRouter();
  const { signin, google } = useAuth();
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

  async function loginWithGoogle() {
    setErr(null);
    try {
      const redirectUrl =
        Platform.OS === "web"
          ? (typeof window !== "undefined" ? window.location.origin + "/" : "/")
          : Linking.createURL("auth");
      const authUrl = `${AUTH_HOST}/?redirect=${encodeURIComponent(redirectUrl)}`;
      if (Platform.OS === "web") {
        // Full redirect on web
        if (typeof window !== "undefined") window.location.href = authUrl;
        return;
      }
      const result = await WebBrowser.openAuthSessionAsync(authUrl, redirectUrl);
      if (result.type !== "success" || !result.url) return;
      const url = result.url;
      const hashIdx = url.indexOf("#");
      const fragment = hashIdx >= 0 ? url.slice(hashIdx + 1) : "";
      const queryIdx = url.indexOf("?");
      const queryPart = queryIdx >= 0 ? url.slice(queryIdx + 1).split("#")[0] : "";
      const params = new URLSearchParams(fragment || queryPart);
      const sessionId = params.get("session_id");
      if (!sessionId) {
        setErr("Google sign-in cancelled");
        return;
      }
      // Fetch session data from Emergent
      const r = await fetch("https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data", {
        headers: { "X-Session-ID": sessionId },
      });
      if (!r.ok) throw new Error("Failed to verify Google session");
      const data = await r.json();
      await google(data.session_token);
      router.replace("/(tabs)/dashboard");
    } catch (e: any) {
      setErr(e?.message ?? "Google sign-in failed");
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
            {process.env.EXPO_PUBLIC_GOOGLE_AUTH_ENABLED === "true" ? <><View style={styles.divider}>
              <View style={styles.line} />
              <Text style={[typography.caption, { color: colors.textLow, marginHorizontal: 12 }]}>
                or continue with
              </Text>
              <View style={styles.line} />
            </View>
            <Button
              label="Continue with Google"
              variant="secondary"
              onPress={loginWithGoogle}
              testID="auth-google-login-button"
            /></> : null}
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
  divider: { flexDirection: "row", alignItems: "center", marginVertical: spacing.md },
  line: { flex: 1, height: 1, backgroundColor: colors.surface2 },
});
