import React from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { colors, typography } from "@/src/theme";

export interface ChipItem {
  value: string;
  label: string;
}

export function ChipRow<T extends string>({
  items,
  value,
  onChange,
  testIDPrefix,
}: {
  items: ChipItem[];
  value: T;
  onChange: (next: T) => void;
  testIDPrefix?: string;
}) {
  return (
    <View style={styles.container}>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.scroll}
      >
        {items.map((it) => {
          const active = it.value === value;
          return (
            <Pressable
              key={it.value}
              onPress={() => onChange(it.value as T)}
              style={[styles.chip, active && styles.chipActive]}
              testID={testIDPrefix ? `${testIDPrefix}-${it.value}` : undefined}
            >
              <Text style={[typography.chip, { color: active ? colors.primary : colors.textHigh }]}>
                {it.label}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}

export function ChipMultiRow<T extends string>({
  items,
  values,
  onToggle,
  testIDPrefix,
}: {
  items: ChipItem[];
  values: T[];
  onToggle: (v: T) => void;
  testIDPrefix?: string;
}) {
  return (
    <View style={styles.container}>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.scroll}
      >
        {items.map((it) => {
          const active = values.includes(it.value as T);
          return (
            <Pressable
              key={it.value}
              onPress={() => onToggle(it.value as T)}
              style={[styles.chip, active && styles.chipActive]}
              testID={testIDPrefix ? `${testIDPrefix}-${it.value}` : undefined}
            >
              <Text style={[typography.chip, { color: active ? colors.primary : colors.textHigh }]}>
                {it.label}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { height: 56, flexShrink: 0 },
  scroll: { paddingHorizontal: 20, alignItems: "center", gap: 12 },
  chip: {
    height: 36,
    minWidth: 44,
    flexShrink: 0,
    borderRadius: 18,
    paddingHorizontal: 16,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: colors.surface2,
    borderWidth: 1,
    borderColor: "transparent",
  },
  chipActive: { backgroundColor: "rgba(255, 68, 51, 0.15)", borderColor: colors.primary },
});
