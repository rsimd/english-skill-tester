"""Tests for audio encoding utilities."""

import numpy as np

from english_skill_tester.audio.encoder import base64_to_pcm16, pcm16_to_base64


class TestEncoder:
    def test_roundtrip(self):
        """Test that encoding and decoding produces approximately the same audio."""
        original = np.random.uniform(-0.5, 0.5, size=2400).astype(np.float32)
        encoded = pcm16_to_base64(original)
        decoded = base64_to_pcm16(encoded)

        assert len(decoded) == len(original)
        # Allow small quantization error from float32 → int16 → float32
        np.testing.assert_allclose(decoded, original, atol=1e-4)

    def test_silence(self):
        """Test encoding silence."""
        silence = np.zeros(1000, dtype=np.float32)
        encoded = pcm16_to_base64(silence)
        decoded = base64_to_pcm16(encoded)
        np.testing.assert_array_equal(decoded, silence)

    def test_clipping(self):
        """Test that values at boundaries encode correctly."""
        audio = np.array([1.0, -1.0, 0.0], dtype=np.float32)
        encoded = pcm16_to_base64(audio)
        decoded = base64_to_pcm16(encoded)
        assert decoded[0] > 0.99
        assert decoded[1] < -0.99
        assert abs(decoded[2]) < 1e-5

    def test_base64_is_string(self):
        """Test that encoding produces a string."""
        audio = np.zeros(100, dtype=np.float32)
        result = pcm16_to_base64(audio)
        assert isinstance(result, str)
