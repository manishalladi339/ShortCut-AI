import React, { forwardRef, useState } from "react";
import { StyleSheet, Text, TextInput, TextInputProps, View } from "react-native";

import { colors, radius, spacing, typography } from "@/src/theme";

interface Props extends TextInputProps {
  label?: string;
  error?: string | null;
  testID?: string;
}

export const Input = forwardRef<TextInput, Props>(function Input(
  { label, error, style, onFocus, onBlur, testID, ...rest },
  ref,
) {
  const [focused, setFocused] = useState(false);
  return (
    <View style={{ gap: spacing.xs }}>
      {label ? <Text style={[typography.label, { color: colors.textMedium }]}>{label}</Text> : null}
      <TextInput
        ref={ref}
        testID={testID}
        placeholderTextColor={colors.textLow}
        style={[
          styles.input,
          focused && styles.focused,
          error ? styles.errored : null,
          style as any,
        ]}
        onFocus={(e) => {
          setFocused(true);
          onFocus?.(e);
        }}
        onBlur={(e) => {
          setFocused(false);
          onBlur?.(e);
        }}
        {...rest}
      />
      {error ? <Text style={[typography.caption, { color: colors.danger }]}>{error}</Text> : null}
    </View>
  );
});

const styles = StyleSheet.create({
  input: {
    minHeight: 56,
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: 16,
    color: colors.textHigh,
    fontSize: 16,
    fontFamily: "System",
  },
  focused: { borderColor: colors.borderFocus },
  errored: { borderColor: colors.danger },
});
