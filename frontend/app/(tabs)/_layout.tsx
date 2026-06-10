import { Ionicons } from "@expo/vector-icons";
import { BlurView } from "expo-blur";
import { Redirect, Tabs } from "expo-router";
import { Platform, StyleSheet, View } from "react-native";

import { useAuth } from "@/src/store/auth";
import { colors } from "@/src/theme";

export default function TabsLayout() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Redirect href="/(auth)/welcome" />;

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textMedium,
        tabBarStyle: {
          position: "absolute",
          borderTopWidth: 0,
          elevation: 0,
          height: 88,
          paddingTop: 8,
          backgroundColor: Platform.OS === "android" ? "rgba(24,24,27,0.95)" : "transparent",
        },
        tabBarBackground: () =>
          Platform.OS === "ios" ? (
            <BlurView
              tint="dark"
              intensity={80}
              style={[StyleSheet.absoluteFill, { backgroundColor: "rgba(9,9,11,0.6)" }]}
            />
          ) : (
            <View style={[StyleSheet.absoluteFill, { backgroundColor: "rgba(24,24,27,0.95)" }]} />
          ),
        tabBarLabelStyle: { fontSize: 11, fontWeight: "600" },
      }}
    >
      <Tabs.Screen
        name="dashboard"
        options={{
          title: "Home",
          tabBarIcon: ({ color, size }) => <Ionicons name="home" color={color} size={size ?? 22} />,
          tabBarButtonTestID: "tab-dashboard",
        }}
      />
      <Tabs.Screen
        name="studio"
        options={{
          title: "Studio",
          tabBarIcon: ({ color, size }) => <Ionicons name="film" color={color} size={size ?? 22} />,
          tabBarButtonTestID: "tab-studio",
        }}
      />
      <Tabs.Screen
        name="hub"
        options={{
          title: "Hub",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="albums" color={color} size={size ?? 22} />
          ),
          tabBarButtonTestID: "tab-hub",
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: "Profile",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="person-circle" color={color} size={size ?? 22} />
          ),
          tabBarButtonTestID: "tab-profile",
        }}
      />
    </Tabs>
  );
}
