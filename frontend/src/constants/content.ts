import { ContentType, CreationMode, Platform, Style } from "@/src/api/projects";

export const CONTENT_TYPES: { value: ContentType; label: string; emoji: string }[] = [
  { value: "podcast", label: "Podcast", emoji: "🎙" },
  { value: "educational", label: "Educational", emoji: "📚" },
  { value: "business", label: "Business", emoji: "💼" },
  { value: "travel", label: "Travel", emoji: "✈️" },
  { value: "fitness", label: "Fitness", emoji: "💪" },
  { value: "comedy", label: "Comedy", emoji: "😂" },
  { value: "dance", label: "Dance", emoji: "💃" },
  { value: "vlog", label: "Vlog", emoji: "📹" },
  { value: "gaming", label: "Gaming", emoji: "🎮" },
  { value: "food", label: "Food", emoji: "🍔" },
  { value: "fashion", label: "Fashion", emoji: "👗" },
  { value: "real_estate", label: "Real Estate", emoji: "🏠" },
  { value: "events", label: "Events", emoji: "🎉" },
  { value: "product_ad", label: "Product Ad", emoji: "📦" },
  { value: "personal_brand", label: "Personal Brand", emoji: "⭐️" },
];

export const STYLES: { value: Style; label: string }[] = [
  { value: "cinematic", label: "Cinematic" },
  { value: "professional", label: "Professional" },
  { value: "emotional", label: "Emotional" },
  { value: "funny", label: "Funny" },
  { value: "energetic", label: "Energetic" },
  { value: "inspirational", label: "Inspirational" },
  { value: "luxury", label: "Luxury" },
];

export const PLATFORMS: { value: Platform; label: string }[] = [
  { value: "ig_reels", label: "Instagram Reels" },
  { value: "yt_shorts", label: "YouTube Shorts" },
  { value: "fb_reels", label: "Facebook Reels" },
  { value: "linkedin", label: "LinkedIn" },
  { value: "x", label: "X (Twitter)" },
];

export const CREATION_MODES: { value: CreationMode; label: string; description: string }[] = [
  {
    value: "create_for_me",
    label: "Create For Me",
    description: "Drop a video. AI generates clips, captions, titles, thumbnails.",
  },
  {
    value: "create_with_me",
    label: "Create With Me",
    description: "Guide the edit with sliders & commands. AI does the heavy lifting.",
  },
];
