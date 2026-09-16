import asyncio
import wave
from services.transcription import OpenAITranscriptionProvider


def test_long_audio_is_split_and_timestamps_are_absolute(tmp_path, monkeypatch):
    source = tmp_path / "speech.wav"
    with wave.open(str(source), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\x00\x00" * 16000 * 3)
    provider = OpenAITranscriptionProvider()
    monkeypatch.setattr(provider, "CHUNK_SECONDS", 1)
    sizes = []

    async def fake_chunk(path):
        sizes.append(path.stat().st_size)
        return {
            "text": "A word",
            "words": [{"start": 0.1, "end": 0.8, "word": "word"}],
            "segments": [{"start": 0.0, "end": 1.0, "text": "A word", "speaker": "A"}],
            "speakers": ["A"],
            "diarized": True,
            "language": "en",
        }

    monkeypatch.setattr(provider, "_transcribe_chunk", fake_chunk)
    result = asyncio.run(provider.transcribe(source))
    assert len(sizes) == 3 and max(sizes) < 40000
    assert [w["start"] for w in result["words"]] == [0.1, 1.1, 2.1]
    assert result["segments"][-1]["end"] == 3.0
    assert result["speakers"] == ["part1:A", "part2:A", "part3:A"]
