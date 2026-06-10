import React from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View, ViewStyle } from "react-native";

import { colors, radius, typography } from "@/src/theme";

type Variant = "primary" | "secondary" | "ai" | "ghost" | "danger";

export function Button({
  label,
  onPress,
  variant = "primary",
  loading,
  disabled,
  testID,
  style,
  iconLeft,
}: {
  label: string;
  onPress?: () => void;
  variant?: Variant;
  loading?: boolean;
  disabled?: boolean;
  testID?: string;
  style?: ViewStyle;
  iconLeft?: React.ReactNode;
}) {
  const isDisabled = disabled || loading;
  return (
    <Pressable
      testID={testID}
      onPress={onPress}
      disabled={isDisabled}
      style={({ pressed }) => [
        styles.base,
        styleByVariant[variant],
        isDisabled && styles.disabled,
        pressed && !isDisabled && styles.pressed,
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={textByVariant[variant]} />
      ) : (
        <View style={styles.row}>
          {iconLeft}
          <Text style={[typography.bodyMed, { color: textByVariant[variant] }]}>{label}</Text>
        </View>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    minHeight: 56,
    borderRadius: radius.md,
    paddingHorizontal: 24,
    paddingVertical: 16,
    alignItems: "center",
    justifyContent: "center",
  },
  row: { flexDirection: "row", alignItems: "center", gap: 10 },
  disabled: { opacity: 0.5 },
  pressed: { opacity: 0.85, transform: [{ scale: 0.98 }] },
});

const styleByVariant: Record<Variant, ViewStyle> = {
  primary: { backgroundColor: colors.primary },
  secondary: { backgroundColor: colors.surface1, borderWidth: 1, borderColor: colors.surface3 },
  ai: { backgroundColor: colors.aiAccent },
  ghost: { backgroundColor: "transparent" },
  danger: { backgroundColor: colors.danger },
};

const textByVariant: Record<Variant, string> = {
  primary: "#FFFFFF",
  secondary: colors.textHigh,
  ai: "#001318",
  ghost: colors.textHigh,
  danger: "#FFFFFF",
};
