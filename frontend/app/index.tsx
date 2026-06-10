import { Redirect } from "expo-router";
import { ActivityIndicator, StyleSheet, View } from "react-native";

import { useAuth } from "@/src/store/auth";
import { colors } from "@/src/theme";

export default function Index() {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <View style={styles.splash}>
        <ActivityIndicator color={colors.primary} size="large" testID="splash-loading" />
      </View>
    );
  }
  return user ? <Redirect href="/(tabs)/dashboard" /> : <Redirect href="/(auth)/welcome" />;
}

const styles = StyleSheet.create({
  splash: { flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center" },
});
