"""Shared enums + base types."""
from enum import Enum


class ContentType(str, Enum):
    podcast = "podcast"
    educational = "educational"
    business = "business"
    travel = "travel"
    fitness = "fitness"
    comedy = "comedy"
    dance = "dance"
    vlog = "vlog"
    gaming = "gaming"
    food = "food"
    fashion = "fashion"
    real_estate = "real_estate"
    events = "events"
    product_ad = "product_ad"
    personal_brand = "personal_brand"


class Style(str, Enum):
    cinematic = "cinematic"
    professional = "professional"
    emotional = "emotional"
    funny = "funny"
    energetic = "energetic"
    inspirational = "inspirational"
    luxury = "luxury"


class Platform(str, Enum):
    ig_reels = "ig_reels"
    yt_shorts = "yt_shorts"
    fb_reels = "fb_reels"
    linkedin = "linkedin"
    x = "x"


class CreationMode(str, Enum):
    create_for_me = "create_for_me"
    create_with_me = "create_with_me"


class ProjectStatus(str, Enum):
    draft = "draft"
    processing = "processing"
    completed = "completed"
    archived = "archived"
    failed = "failed"


class AssetKind(str, Enum):
    video = "video"
    audio = "audio"
    image = "image"


class UploadStatus(str, Enum):
    pending = "pending"
    uploaded = "uploaded"
    failed = "failed"


class AuthProvider(str, Enum):
    email = "email"
    google = "google"
    both = "both"


class SubscriptionTier(str, Enum):
    free = "free"
    creator = "creator"
    pro = "pro"
    agency = "agency"
