import { Ionicons } from "@expo/vector-icons";
import * as DocumentPicker from "expo-document-picker";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";

import { Asset, AssetKind, assetsApi, uploadBinary } from "@/src/api/assets";
import { ChipRow } from "@/src/components/ui/Chip";
import { colors, radius, spacing, typography } from "@/src/theme";

type KindFilter = "all" | AssetKind;

function detectKind(mime: string): AssetKind {
  if (mime.startsWith("video/")) return "video";
  if (mime.startsWith("audio/")) return "audio";
  return "image";
}

export default function AssetsLibrary() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const params = useLocalSearchParams<{ project_id?: string }>();
  const [items, setItems] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [kind, setKind] = useState<KindFilter>("all");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await assetsApi.list({
        kind: kind === "all" ? undefined : kind,
        project_id: params.project_id,
      });
      setItems(r.items);
    } catch (e: any) {
      Alert.alert("Could not load assets", e?.message ?? "");
    } finally {
      setLoading(false);
    }
  }, [kind, params.project_id]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  async function pickAndUpload() {
    try {
      const res = await DocumentPicker.getDocumentAsync({
        type: ["video/*", "audio/*", "image/*"],
        copyToCacheDirectory: true,
        multiple: false,
      });
      if (res.canceled || !res.assets?.[0]) return;
      const file = res.assets[0];
      const mime = file.mimeType ?? "application/octet-stream";
      const detectedKind = detectKind(mime);
      const size = file.size ?? 0;
      setUploading(true);

      // 1) Presign
      const presign = await assetsApi.presign({
        filename: file.name,
        mime_type: mime,
        kind: detectedKind,
        size_bytes: size,
        project_id: params.project_id,
      });

      // 2) Fetch blob from local URI, PUT to upload_url
      const blobRes = await fetch(file.uri);
      const blob = await blobRes.blob();
      const ok = await uploadBinary(presign.upload_url, presign.upload_headers, blob);
      if (!ok) throw new Error("Upload failed");

      // 3) Confirm
      await assetsApi.confirm(presign.asset_id, {});
      await load();
    } catch (e: any) {
      Alert.alert("Upload failed", e?.message ?? "Try again");
    } finally {
      setUploading(false);
    }
  }

  async function remove(id: string) {
    Alert.alert("Delete asset?", "The file will be removed.", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete",
        style: "destructive",
        onPress: async () => {
          try {
            await assetsApi.remove(id);
            await load();
          } catch (e: any) {
            Alert.alert("Failed", e?.message ?? "");
          }
        },
      },
    ]);
  }

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} testID="assets-back" style={styles.iconBtn}>
          <Ionicons name="chevron-back" color={colors.textHigh} size={24} />
        </Pressable>
        <Text style={[typography.h3, { color: colors.textHigh, flex: 1, marginLeft: spacing.sm }]}>
          {params.project_id ? "Project Assets" : "Asset Library"}
        </Text>
        <Pressable
          onPress={pickAndUpload}
          disabled={uploading}
          style={[styles.uploadBtn, uploading && { opacity: 0.6 }]}
          testID="assets-upload-button"
        >
          {uploading ? (
            <ActivityIndicator color="#FFF" />
          ) : (
            <>
              <Ionicons name="cloud-upload" color="#FFF" size={16} />
              <Text style={[typography.label, { color: "#FFF" }]}>Upload</Text>
            </>
          )}
        </Pressable>
      </View>

      <ChipRow<KindFilter>
        items={[
          { value: "all", label: "All" },
          { value: "video", label: "Video" },
          { value: "audio", label: "Audio" },
          { value: "image", label: "Images" },
        ]}
        value={kind}
        onChange={setKind}
        testIDPrefix="assets-filter-chip"
      />

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.primary} />
        </View>
      ) : items.length === 0 ? (
        <View style={styles.center}>
          <Ionicons name="cloud-upload-outline" color={colors.textLow} size={64} />
          <Text style={[typography.h3, { color: colors.textHigh, marginTop: spacing.lg }]}>
            No assets yet
          </Text>
          <Text style={[typography.body, { color: colors.textMedium, marginTop: spacing.sm, textAlign: "center", maxWidth: 280 }]}>
            Upload videos, audio, or images to feed the AI pipeline.
          </Text>
          <Pressable
            onPress={pickAndUpload}
            disabled={uploading}
            style={styles.bigBtn}
            testID="assets-empty-upload-button"
          >
            <Text style={{ color: "#FFF", fontWeight: "700" }}>
              {uploading ? "Uploading..." : "Upload your first asset"}
            </Text>
          </Pressable>
        </View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(a) => a.id}
          contentContainerStyle={{
            paddingHorizontal: spacing.screenPadding,
            paddingTop: spacing.md,
            paddingBottom: 88 + insets.bottom + spacing.xl,
            gap: 12,
          }}
          renderItem={({ item }) => (
            <View style={styles.card} testID={`assets-item-${item.id}`}>
              <View style={styles.iconBox}>
                <Ionicons
                  name={
                    item.kind === "video"
                      ? "videocam"
                      : item.kind === "audio"
                        ? "musical-notes"
                        : "image"
                  }
                  color={colors.aiAccent}
                  size={22}
                />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={[typography.bodyMed, { color: colors.textHigh }]} numberOfLines={1}>
                  {item.filename}
                </Text>
                <Text style={[typography.caption, { color: colors.textMedium, marginTop: 2 }]}>
                  {item.kind.toUpperCase()} · {(item.size_bytes / 1024).toFixed(1)} KB ·{" "}
                  <Text style={{ color: item.upload_status === "uploaded" ? colors.success : colors.warning }}>
                    {item.upload_status}
                  </Text>
                </Text>
              </View>
              <Pressable
                onPress={() => remove(item.id)}
                testID={`assets-delete-${item.id}`}
                hitSlop={8}
                style={styles.deleteBtn}
              >
                <Ionicons name="trash-outline" color={colors.danger} size={20} />
              </Pressable>
            </View>
          )}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.sm,
    paddingTop: spacing.md,
    paddingBottom: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  iconBtn: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  uploadBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: colors.primary,
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: radius.md,
    marginRight: spacing.sm,
  },
  center: { flex: 1, alignItems: "center", justifyContent: "center", paddingHorizontal: spacing.screenPadding },
  bigBtn: {
    marginTop: spacing.xl,
    backgroundColor: colors.primary,
    paddingVertical: 16,
    paddingHorizontal: 32,
    borderRadius: radius.md,
  },
  card: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface1,
    borderRadius: radius.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    gap: spacing.md,
  },
  iconBox: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.aiAccentMuted,
    alignItems: "center",
    justifyContent: "center",
  },
  deleteBtn: { width: 36, height: 36, alignItems: "center", justifyContent: "center" },
});
